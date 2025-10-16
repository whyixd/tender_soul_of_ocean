import cv2
import threading
import time
from ultralytics import YOLO
from typing import Dict, Any
import os
import socketio


class RTSPPersonTracker:
    def __init__(
        self,
        sources: Dict[str, str],
        model_path: str = "yolo11s.pt",
        target_class: str = "person",
        display_size: tuple[int, int] = (960, 540),
        confidence_threshold: float = 0.25,
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
        # self._socketio_client = socketio.Client(reconnection=True)
        # self._socketio_url = "http://127.0.0.1:5000"
        # self._last_socketio_attempt = 0.0
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
                current_person_count = 0

                for box in r.boxes:
                    class_id = int(box.cls.item())
                    confidence = float(box.conf.item())

                    if (
                        class_id == person_class_id
                        and confidence >= self.confidence_threshold
                    ):
                        current_person_count += 1
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        label = f"{self.target_class} {confidence:.2f}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                        (label_w, label_h), _ = cv2.getTextSize(
                            label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2
                        )
                        cv2.rectangle(
                            frame,
                            (x1, y1 - label_h - 10),
                            (x1 + label_w, y1),
                            (0, 255, 0),
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

                with self._lock:
                    self.frame_buffer[camera_name] = frame
                    self.person_counts[camera_name] = current_person_count
                    index = self._source_index.get(camera_name)
                    if index is not None and index < len(self.inside_area_counts):
                        self.inside_area_counts[index] = current_person_count
                    counts_payload = list(self.inside_area_counts)
                # self._emit_person_tracker_data(counts_payload)
        except Exception as exc:
            print(f"[{camera_name}] Worker error: {exc}")
        finally:
            with self._lock:
                self.frame_buffer.pop(camera_name, None)
                self.person_counts.pop(camera_name, None)
                index = self._source_index.get(camera_name)
                if index is not None and index < len(self.inside_area_counts):
                    self.inside_area_counts[index] = 0
                counts_payload = list(self.inside_area_counts)
            print(f"[{camera_name}] Thread stopped.")
        # self._emit_person_tracker_data(counts_payload)

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
            time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        tracker.stop()


# if __name__ == "__main__":
#     main()
