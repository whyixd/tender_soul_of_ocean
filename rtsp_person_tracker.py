import cv2
import threading
import time
from dataclasses import dataclass
from ultralytics import YOLO
from typing import Dict, Any
import os
import socketio
import numpy as np


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
        self.x_limit = (635, 740)
        self.y_limit = (90, 650)

        self.detect_time_threshold = 0.8
        self.lost_time_threshold = 0.8
        self.match_iou_threshold = 0.3
        self._next_detection_id = 0
        self.detections: dict[str, dict[int, DetectionState]] = {}

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
                frame = frame * (60/127+1)
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
                    norm_x = normalize(center_x, self.x_limit[0], self.x_limit[1])
                    norm_y = normalize(center_y + 100, self.y_limit[0], self.y_limit[1])

                    now = time.time()
                    matched_id = self._match_detection(camera_states, bbox, used_state_ids)
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

                    if not state.confirmed and now - state.first_seen >= self.detect_time_threshold and state.position[1] > 0.15:
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
        label = (
            f"con:{state.confidence:.2f}/X:{center_x}/{state.position[0]:.2f}/"
            f"Y:{center_y}/{norm_y_for_label:.2f}"
        )
        color = (0, 255, 0) if state.confirmed else (0, 255, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (center_x, center_y), 5, color, -1)
        (label_w, label_h), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
        )
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

    def _display_loop(self):
        print("Press 'q' to exit all windows.")
        try:
            while not self._stop_event.is_set():
                if not any(t.is_alive() for t in self._threads):
                    print("All worker threads exited. Shutting down display.")
                    self._stop_event.set()
                    break

                with self._lock:
                    frames_snapshot = list(self.frame_buffer.items())
                    counts_snapshot = self.person_counts.copy()

                for name, frame in frames_snapshot:
                    count = counts_snapshot.get(name, 0)
                    info_text = f"{name} | Persons: {count}"
                    cv2.putText(
                        frame,
                        info_text,
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 0, 255),
                        2,
                    )
                    display_frame = cv2.resize(
                        frame, (self.display_width, self.display_height)
                    )
                    cv2.imshow(name, display_frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("Quit signal received. Stopping workers...")
                    self._stop_event.set()
                    break

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
    tracker = RTSPPersonTracker(
        sources={
            # "cam A (top)": "rtsp://2.0.0.79:554/user=admin_password=tlJwpbo6_channel=1_stream=0&onvif=0.sdp?real_st",
            # "cam B (desk)": "rtsp://2.0.0.78:554/user=admin_password=tlJwpbo6_channel=1_stream=0&onvif=0.sdp?real_st",
            "cam C (desk)": "rtsp://2.0.0.77:554/user=admin_password=tlJwpbo6_channel=1_stream=0&amp;onvif=0.sdp?real_st",
        },
        ffmpeg_options=ffmpeg_opts,
        use_cuda=False,
    )
    tracker.start()
    try:
        while True:
            time.sleep(0.1)
            # print(tracker.person_pos)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        tracker.stop()


# if __name__ == "__main__":
#     main()
