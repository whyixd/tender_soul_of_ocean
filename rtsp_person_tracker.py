import cv2
import threading
import time
from dataclasses import dataclass
from ultralytics import YOLO
from typing import Dict, Any
import os
import socketio
import numpy as np
from config import Config
import math


@dataclass
class DetectionState:
    bbox: tuple[int, int, int, int]
    first_seen: float
    last_seen: float
    confirmed: bool
    position: tuple[float, float]
    confidence: float


class RTSPPersonTracker:
    def __init__(
        self,
        sources: Dict[str, str],
        model_path: str = "yolo11s.pt",
        target_class: str = "person",
        display_size: tuple[int, int] = (960, 540),
        confidence_threshold: float = 0.5,
        ffmpeg_options: Dict[str, str] | None = None,
        use_cuda: bool = True,
        perspective_points: Dict[str, list[tuple[int, int]]] | None = None,
    ):
        self.sources = sources
        self.source_names = list(self.sources.keys())
        self._source_index = {name: idx for idx, name in enumerate(self.source_names)}
        self.model_path = model_path
        self.target_class = target_class
        self.display_width, self.display_height = display_size
        self.confidence_threshold = confidence_threshold
        self.use_cuda = use_cuda

        self.frame_buffer: Dict[str, Any] = {}
        self.person_counts: Dict[str, int] = {}

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._display_thread: threading.Thread | None = None

        self.inside_area_counts = [0] * 4
        self.person_pos: list[tuple[int, int]] = []
        self.person_pos_by_camera: dict[str, list[tuple[int, int]]] = {}
        self.x_limit = (700, 1200)
        self.y_limit = (100, 780)

        self.detect_time_threshold = 0.6
        self.lost_time_threshold = 0.8
        self.match_iou_threshold = 0.2
        self._next_detection_id = 0
        self.detections: dict[str, dict[int, DetectionState]] = {}

        # 校準設定：用來標記有效的偵測區域
        self._detection_config = Config(
            data_dict={"detection_polygons": {}},
            config_file_name="config/detection_polygons.json",
        )
        self.detection_polygons = (
            self._detection_config.data_dict.get("detection_polygons", {}) or {}
        )
        if perspective_points:
            self.detection_polygons.update(perspective_points)
            self._persist_detection_polygons()
        self._calibration_mode = False
        self._current_calibration_camera = None
        self._calibration_points: list[tuple[int, int]] = []
        self._calibration_window_created = False
        self._last_calibration_window_name: str | None = None
        self._calibration_frame_size = None  # type: tuple[int, int] | None
        self._calibration_display_size = display_size
        self._mouse_display_pos = None
        self._mouse_original_pos = None

        # 透視補償設定：使用線性函數調整偵測後的 Y 值
        self._perspective_config = Config(
            data_dict={"y_adjust": {"scale": 1.0, "offset": 0.0}},
            config_file_name="config/perspective_adjust.json",
        )
        y_adjust_cfg = self._perspective_config.data_dict.get("y_adjust", {})
        self.y_adjust_scale = float(y_adjust_cfg.get("scale", 1.0))
        self.y_adjust_offset = float(y_adjust_cfg.get("offset", 0.0))

        if ffmpeg_options:
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "|".join(
                f"{key};{value}" for key, value in ffmpeg_options.items()
            )

    def start(self):
        # self._connect_socketio()
        self._stop_event.clear()
        self._threads = [
            threading.Thread(
                target=self._yolo_worker,
                args=(name, url),
                daemon=True,
                name=f"YOLOWorker-{name}",
            )
            for name, url in self.sources.items()
        ]

        for thread in self._threads:
            thread.start()
            time.sleep(1)

        if self._display_thread is None or not self._display_thread.is_alive():
            self._display_thread = threading.Thread(
                target=self._display_loop,
                daemon=True,
                name="DisplayLoop",
            )
            self._display_thread.start()

    def stop(self):
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads = []
        if (
            self._display_thread
            and self._display_thread.is_alive()
            and threading.current_thread() is not self._display_thread
        ):
            self._display_thread.join(timeout=5)
        self._display_thread = None
        cv2.destroyAllWindows()

    def _yolo_worker(self, camera_name: str, rtsp_url: str):
        print(f"[{camera_name}] Thread started, connecting to {rtsp_url}...")
        try:
            model = YOLO(self.model_path)
            # if self.use_cuda:
            #     try:
            #         model.to("cuda")
            #     except Exception as exc:
            #         print(f"[{camera_name}] CUDA unavailable: {exc}")

            try:
                person_class_id = list(model.names.keys())[
                    list(model.names.values()).index(self.target_class)
                ]
            except ValueError:
                raise RuntimeError(f"Target class '{self.target_class}' not in model.")

            results = model(rtsp_url, stream=True, verbose=False)

            for r in results:
                if self._stop_event.is_set():
                    break

                frame = r.orig_img.copy()
                frame = frame * (60 / 127 + 1)
                frame = np.clip(frame, 0, 255)
                frame = frame.astype(np.uint8)

                camera_states = self.detections.setdefault(camera_name, {})
                used_state_ids: set[int] = set()

                for box in r.boxes:
                    class_id = int(box.cls.item())
                    confidence = float(box.conf.item())

                    if (
                        class_id != person_class_id
                        or confidence < self.confidence_threshold
                    ):
                        continue

                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                    bbox = (x1, y1, x2, y2)
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

                    polygon = self.detection_polygons.get(camera_name)
                    if polygon and len(polygon) >= 3:
                        if not self._is_point_inside_polygon(
                            (center_x, center_y), polygon
                        ):
                            continue

                    norm_x = normalize(center_x, self.x_limit[0], self.x_limit[1])
                    # norm_x = 1 - norm_x  ##
                    norm_y = normalize(center_y, self.y_limit[0], self.y_limit[1])
                    norm_y = self._apply_perspective_y_adjustment(norm_y)

                    now = time.time()
                    matched_id = self._match_detection(
                        camera_states, bbox, used_state_ids
                    )
                    if matched_id is None:
                        matched_id = self._next_detection_id
                        self._next_detection_id += 1
                        camera_states[matched_id] = DetectionState(
                            bbox=bbox,
                            first_seen=now,
                            last_seen=now,
                            confirmed=False,
                            position=(norm_x, norm_y),
                            confidence=confidence,
                        )
                    state = camera_states[matched_id]
                    state.bbox = bbox
                    state.last_seen = now
                    state.position = (norm_x, norm_y)
                    state.confidence = confidence
                    used_state_ids.add(matched_id)

                    if (
                        not state.confirmed
                        and now - state.first_seen >= self.detect_time_threshold
                        and state.position[1] > 0.15
                    ):
                        state.confirmed = True

                now = time.time()

                active_states: list[DetectionState] = []
                drawable_states: list[DetectionState] = []
                for state_id, state in list(camera_states.items()):
                    if now - state.last_seen > self.lost_time_threshold:
                        camera_states.pop(state_id)
                        continue
                    drawable_states.append(state)
                    if state.confirmed:
                        active_states.append(state)
                for state in drawable_states:
                    self._draw_detection(frame, state)

                camera_positions = [state.position for state in active_states]
                current_person_count = len(camera_positions)

                with self._lock:
                    self.frame_buffer[camera_name] = frame
                    self.person_counts[camera_name] = current_person_count
                    index = self._source_index.get(camera_name)
                    if index is not None and index < len(self.inside_area_counts):
                        self.inside_area_counts[index] = current_person_count
                    self.person_pos_by_camera[camera_name] = camera_positions
                    self.person_pos = [
                        pos
                        for positions in self.person_pos_by_camera.values()
                        for pos in positions
                    ]
                    counts_payload = list(self.inside_area_counts)
                # self._emit_person_tracker_data(counts_payload)
        except Exception as exc:
            print(f"[{camera_name}] Worker error: {exc}")
        finally:
            with self._lock:
                self.frame_buffer.pop(camera_name, None)
                self.person_counts.pop(camera_name, None)
                self.person_pos_by_camera.pop(camera_name, None)
                index = self._source_index.get(camera_name)
                if index is not None and index < len(self.inside_area_counts):
                    self.inside_area_counts[index] = 0
                self.person_pos = [
                    pos
                    for positions in self.person_pos_by_camera.values()
                    for pos in positions
                ]
                counts_payload = list(self.inside_area_counts)
            self.detections.pop(camera_name, None)
            print(f"[{camera_name}] Thread stopped.")
        # self._emit_person_tracker_data(counts_payload)

    def _match_detection(
        self,
        camera_states: dict[int, DetectionState],
        bbox: tuple[int, int, int, int],
        used_ids: set[int],
    ) -> int | None:
        best_id: int | None = None
        best_iou = 0.0
        for state_id, state in camera_states.items():
            if state_id in used_ids:
                continue
            iou = self._bbox_iou(state.bbox, bbox)
            if iou > best_iou:
                best_iou = iou
                best_id = state_id
        if best_id is not None and best_iou >= self.match_iou_threshold:
            return best_id
        return None

    @staticmethod
    def _bbox_iou(
        box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]
    ) -> float:
        x_left = max(box_a[0], box_b[0])
        y_top = max(box_a[1], box_b[1])
        x_right = min(box_a[2], box_b[2])
        y_bottom = min(box_a[3], box_b[3])

        inter_width = max(0, x_right - x_left)
        inter_height = max(0, y_bottom - y_top)
        inter_area = float(inter_width * inter_height)
        if inter_area <= 0:
            return 0.0

        area_a = float(max(0, box_a[2] - box_a[0]) * max(0, box_a[3] - box_a[1]))
        area_b = float(max(0, box_b[2] - box_b[0]) * max(0, box_b[3] - box_b[1]))
        denom = area_a + area_b - inter_area
        if denom <= 0:
            return 0.0
        return inter_area / denom

    def _draw_detection(self, frame: np.ndarray, state: DetectionState) -> None:
        x1, y1, x2, y2 = state.bbox
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        norm_y_for_label = normalize(center_y, self.y_limit[0], self.y_limit[1])
        norm_y_for_label = self._apply_perspective_y_adjustment(norm_y_for_label)
        label = (
            f"con:{state.confidence:.2f}/X:{center_x}/{state.position[0]:.2f}/"
            f"Y:{center_y}/{norm_y_for_label:.2f}"
        )
        color = (0, 255, 0) if state.confirmed else (0, 255, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (center_x, center_y), 5, color, -1)
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(
            frame,
            (x1, y1 - label_h - 10),
            (x1 + label_w, y1),
            color,
            -1,
        )
        cv2.putText(
            frame,
            label,
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
        )

    def start_calibration(self, camera_name: str):
        """启动校准模式，用户可以点击画面定义四个点"""
        if camera_name not in self.sources:
            print(f"摄像头 '{camera_name}' 不存在")
            return

        self._calibration_mode = True
        self._current_calibration_camera = camera_name
        self._calibration_points = []
        print(
            f"开始校准 {camera_name}，请在窗口中点击四个点(按顺序：左上、右上、右下、左下)"
        )
        print("按 'r' 重置点，按 'c' 完成校准")

    def _mouse_callback(self, event, x, y, flags, param):
        """鼠标回调函数，用于点击定义梯形校正点"""
        if not self._calibration_mode:
            return

        if event in (cv2.EVENT_MOUSEMOVE, cv2.EVENT_LBUTTONDOWN):
            self._update_mouse_positions(x, y)

        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self._calibration_points) < 4:
                if self._mouse_original_pos is None:
                    print("尚未取得原始影像尺寸，無法記錄點")
                    return
                ox, oy = self._mouse_original_pos
                self._calibration_points.append((ox, oy))
                print(f"点 {len(self._calibration_points)}/4: ({ox}, {oy})")
                if len(self._calibration_points) == 4:
                    print("已获取4个点，按 'c' 确认或 'r' 重置")

    def _update_mouse_positions(self, display_x: int, display_y: int) -> None:
        """將顯示座標轉換為原始影像座標並保存供校準使用"""
        self._mouse_display_pos = (display_x, display_y)

        if self._calibration_frame_size is None:
            self._mouse_original_pos = None
            return

        orig_w, orig_h = self._calibration_frame_size
        disp_w, disp_h = self._calibration_display_size
        if disp_w == 0 or disp_h == 0:
            self._mouse_original_pos = None
            return

        scale_x = orig_w / disp_w
        scale_y = orig_h / disp_h
        orig_x = int(round(display_x * scale_x))
        orig_y = int(round(display_y * scale_y))
        self._mouse_original_pos = (orig_x, orig_y)

    def _persist_detection_polygons(self) -> None:
        self._detection_config.data_dict["detection_polygons"] = self.detection_polygons
        self._detection_config.save()

    def _apply_perspective_y_adjustment(self, norm_y: float) -> float:
        adjusted = self.easeOutCubic(norm_y)
        # adjusted = norm_y * self.y_adjust_scale + self.y_adjust_offset
        return min(max(adjusted, 0.0), 1.0)

    def easeOutCubic(self, number):
        return 1 - math.pow(1 - number, 3)

    @staticmethod
    def _is_point_inside_polygon(
        point: tuple[int, int], polygon: list[tuple[int, int]]
    ) -> bool:
        x, y = point
        inside = False
        n = len(polygon)
        if n < 3:
            return False

        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            intersects = ((y1 > y) != (y2 > y)) and (
                x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1
            )
            if intersects:
                inside = not inside
        return inside

    def _display_loop(self):
        print("Press 'q' to exit all windows.")
        try:
            while not self._stop_event.is_set():
                calibration_window_name = None
                if self._calibration_mode and self._current_calibration_camera:
                    calibration_window_name = (
                        f"Calibration - {self._current_calibration_camera}"
                    )
                    if not self._calibration_window_created:
                        cv2.namedWindow(calibration_window_name)
                        cv2.setMouseCallback(
                            calibration_window_name, self._mouse_callback
                        )
                        self._calibration_window_created = True
                        self._last_calibration_window_name = calibration_window_name
                elif (
                    self._calibration_window_created
                    and self._last_calibration_window_name
                ):
                    cv2.destroyWindow(self._last_calibration_window_name)
                    self._calibration_window_created = False
                    self._last_calibration_window_name = None

                if not any(t.is_alive() for t in self._threads):
                    print("All worker threads exited. Shutting down display.")
                    self._stop_event.set()
                    break

                with self._lock:
                    frames_snapshot = list(self.frame_buffer.items())
                    counts_snapshot = self.person_counts.copy()

                for name, frame in frames_snapshot:
                    calibrating_this_camera = (
                        self._calibration_mode
                        and name == self._current_calibration_camera
                    )

                    processed_frame = frame.copy()
                    if calibrating_this_camera:
                        self._calibration_frame_size = (
                            processed_frame.shape[1],
                            processed_frame.shape[0],
                        )
                    if calibrating_this_camera:
                        for i, point in enumerate(self._calibration_points):
                            cv2.circle(processed_frame, point, 8, (0, 255, 0), -1)
                            cv2.putText(
                                processed_frame,
                                str(i + 1),
                                (point[0] + 10, point[1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 0),
                                2,
                            )
                        if len(self._calibration_points) > 1:
                            for i in range(len(self._calibration_points)):
                                start = self._calibration_points[i]
                                end = self._calibration_points[
                                    (i + 1) % len(self._calibration_points)
                                ]
                                cv2.line(processed_frame, start, end, (0, 255, 0), 2)

                    polygon_overlay = self.detection_polygons.get(name)
                    if polygon_overlay and len(polygon_overlay) >= 2:
                        overlay_points = polygon_overlay + [polygon_overlay[0]]
                        for start, end in zip(overlay_points, overlay_points[1:]):
                            cv2.line(processed_frame, start, end, (255, 0, 0), 2)

                    count = counts_snapshot.get(name, 0)
                    info_text = f"{name} | Persons: {count}"
                    cv2.putText(
                        processed_frame,
                        info_text,
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 0, 255),
                        2,
                    )
                    display_frame = cv2.resize(
                        processed_frame, (self.display_width, self.display_height)
                    )

                    if (
                        calibrating_this_camera
                        and self._mouse_display_pos
                        and self._mouse_original_pos
                    ):
                        self._calibration_display_size = (
                            display_frame.shape[1],
                            display_frame.shape[0],
                        )
                        mx, my = self._mouse_display_pos
                        max_w = display_frame.shape[1] - 1
                        max_h = display_frame.shape[0] - 1
                        mx = max(0, min(max_w, mx))
                        my = max(0, min(max_h, my))
                        ox, oy = self._mouse_original_pos
                        cv2.circle(display_frame, (mx, my), 4, (0, 255, 255), -1)
                        coord_text = f"({ox}, {oy})"
                        cv2.putText(
                            display_frame,
                            coord_text,
                            (mx + 10, my - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 255),
                            2,
                        )

                    window_name = (
                        f"Calibration - {name}" if calibrating_this_camera else name
                    )
                    cv2.imshow(window_name, display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("Quit signal received. Stopping workers...")
                    self._stop_event.set()
                    break
                elif self._calibration_mode:
                    if key == ord("r"):
                        self._calibration_points = []
                        print("點已重置")
                        self._mouse_display_pos = None
                        self._mouse_original_pos = None
                    elif key == ord("c"):
                        if len(self._calibration_points) == 4:
                            self.detection_polygons[
                                self._current_calibration_camera
                            ] = list(self._calibration_points)
                            self._persist_detection_polygons()
                            if self._last_calibration_window_name:
                                cv2.destroyWindow(self._last_calibration_window_name)
                            print(f"校準完成: {self._calibration_points}")
                            self._calibration_mode = False
                            self._current_calibration_camera = None
                            self._calibration_points = []
                            self._calibration_window_created = False
                            self._last_calibration_window_name = None
                            self._calibration_frame_size = None
                            self._mouse_display_pos = None
                            self._mouse_original_pos = None
                        else:
                            print(
                                f"需要4个点，目前只有 {len(self._calibration_points)} 个点"
                            )

                time.sleep(0.01)
        finally:
            self.stop()

    # def _connect_socketio(self):
    #     if self._socketio_client.connected:
    #         return
    #     now = time.time()
    #     if now - self._last_socketio_attempt < 5:
    #         return
    #     self._last_socketio_attempt = now
    #     try:
    #         self._socketio_client.connect(self._socketio_url, wait_timeout=1)
    #         print("Socket.IO client connected to 127.0.0.1:5000")
    #     except Exception as exc:
    #         print(f"Socket.IO connection failed: {exc}")

    # def _emit_person_tracker_data(self, counts: list[int]):
    #     if not counts:
    #         return
    #     if not self._socketio_client.connected:
    #         self._connect_socketio()
    #     if self._socketio_client.connected:
    #         try:
    #             self._socketio_client.emit("person_tracker_data", counts)
    #         except Exception as exc:
    #             print(f"Socket.IO emit failed: {exc}")


def normalize(value, min_val, max_val):
    if max_val - min_val == 0:
        return 0.0
    return min(max((value - min_val) / (max_val - min_val), 0.0), 1.0)


def main():
    ffmpeg_opts = {
        "rtsp_transport": "udp",
        "fflags": "nobuffer",
        "flags": "low_delay",
        "max_delay": "500000",
    }

    # 预定义的梯形校正点（可选）
    perspective_points = {
        # "cam B (desk)": [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
    }

    tracker = RTSPPersonTracker(
        sources={
            "cam B (desk)": "rtsp://2.0.0.78:554/user=admin_password=tlJwpbo6_channel=1_stream=0&onvif=0.sdp?real_st",
        },
        ffmpeg_options=ffmpeg_opts,
        use_cuda=False,
        perspective_points=perspective_points,
    )
    tracker.start()

    # 启动校准模式
    time.sleep(2)  # 等待摄像头连接
    tracker.start_calibration("cam B (desk)")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        tracker.stop()


if __name__ == "__main__":
    main()
