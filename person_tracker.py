from ultralytics import YOLO
import cv2
import logging
import time
import torch
import numpy as np
import threading
from queue import Queue

logging.getLogger("ultralytics").setLevel(logging.ERROR)  # Suppress warnings


class PersonTracker(threading.Thread):
    def __init__(
        self,
        video_source="people_top.mp4",
        width=1280,
        height=720,
    ):
        """Initialize the person tracker with video source and parameters."""
        super(PersonTracker, self).__init__()
        self.daemon = True  # Thread will exit when main program exits

        # Video settings
        self.video_source = video_source
        self.desired_width = width
        self.desired_height = height

        # YOLO model
        self.model = YOLO("yolo11n-seg.pt")
        if torch.cuda.is_available():
            self.model.to("cuda")
            print(f"Using GPU: {torch.cuda.get_device_name()}")
            print(f"Model device: {self.model.device}")

        # FPS calculation
        self.prev_fps_calc_time = time.time()
        self.frame_count_for_fps = 0
        self.display_fps = 0

        # Detection settings
        self.active_tracks = {}  # Stores info about currently tracked objects
        self.min_consecutive_hits = 8  # Min consecutive frames to show a track
        self.max_frames_missed = 3  # Max frames a track can be missed before removal

        # People count
        self.total_entered = 0
        self.total_exited = 0
        self.enable_reset_timeout = (
            5  # seconds without detections before resetting inside count
        )
        self.last_detection_time = time.time()

        # Area definitions
        self.area_edit_mode = False
        self.areas = [
            [(100, 100), (200, 100), (200, 200), (100, 200)],  # Example area polygon
            [
                (300, 300),
                (400, 300),
                (400, 400),
                (300, 400),
            ],  # Another example area polygon
            [
                (500, 500),
                (600, 500),
                (600, 600),
                (500, 600),
            ],  # Another example area polygon
        ]
        self.current_setting_corners = 0
        self.current_setting_area = 0
        self.inside_area_counts = [0] * len(self.areas)
        self.area_polygons = [np.array(area, dtype=np.int32) for area in self.areas]

        # Display settings
        self.show_visualization = True

        # Thread control
        self.running = False
        self.result_queue = Queue(maxsize=10)  # Buffer for processed results

        # NOTE: Window initialization is now deferred to the display_loop method
        # or _ui_thread_function when running in background
        # This ensures the window is created in the correct thread

    def set_corner(self, event, x, y, flags, param):
        """Mouse callback for setting area corners."""
        if not self.area_edit_mode:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            self.areas[self.current_setting_area][self.current_setting_corners] = (x, y)
            # Update the polygons after changes
            self.area_polygons = [np.array(area, dtype=np.int32) for area in self.areas]

    def toggle_area_edit_mode(self):
        """Toggle the area edit mode."""
        self.area_edit_mode = not self.area_edit_mode
        if self.area_edit_mode:
            self.area_polygons = [np.array(area, dtype=np.int32) for area in self.areas]

    def set_corner_index(self, index):
        """Set the current corner index (0-3)."""
        if 0 <= index <= 3:
            self.current_setting_corners = index

    def set_area_index(self, index):
        """Set the current area index (0-8)."""
        if 0 <= index <= 8 and index < len(self.areas):
            self.current_setting_area = index

    def process_key(self, keycode):
        """Process keyboard input."""
        if keycode == 101:  # e
            self.toggle_area_edit_mode()
        elif keycode == 97:  # a (was q)
            self.set_corner_index(0)
        elif keycode == 115:  # s (was w)
            self.set_corner_index(1)
        elif keycode == 122:  # z (was a)
            self.set_corner_index(3)
        elif keycode == 120:  # x (was s)
            self.set_corner_index(2)
        elif 49 <= keycode <= 57:  # 1-9
            self.set_area_index(keycode - 49)

    def stop(self):
        """Stop the tracking thread."""
        self.running = False

    def run(self):
        """Main thread function that runs the tracking loop."""
        self.running = True

        # Open video capture
        cap = cv2.VideoCapture(self.video_source)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.desired_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.desired_height)

        while self.running and cap.isOpened():
            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to first frame
                success, frame = cap.read()
                if not success:  # Still not successful, exit loop
                    break

            # Process frame with YOLO model
            for result in self.model.track(
                frame,
                show=False,
                classes=[0],
                conf=0.4,
                stream=True,
                persist=True,
                imgsz=(self.desired_width, self.desired_height),
            ):
                # Skip processing if result has no boxes
                if result.boxes is None or result.boxes.data.numel() == 0:
                    processed_frame = frame.copy()
                    if self.show_visualization:
                        cv2.putText(
                            processed_frame,
                            "No detections",
                            (5, 50),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 0, 255),
                            1,
                            cv2.LINE_AA,
                        )

                    # Put the frame in the result queue for display
                    if not self.result_queue.full():
                        self.result_queue.put(processed_frame)
                    continue

                # Get the original frame from the result
                processed_frame = result.orig_img.copy()

                # Reset area_polygons if areas change
                if len(self.area_polygons) != len(self.areas):
                    self.area_polygons = [
                        np.array(area, dtype=np.int32) for area in self.areas
                    ]

                # Update FPS calculation if visualization is enabled
                if self.show_visualization:
                    self.frame_count_for_fps += 1
                    current_time = time.time()
                    if current_time - self.prev_fps_calc_time >= 0.5:
                        self.display_fps = self.frame_count_for_fps / (
                            current_time - self.prev_fps_calc_time
                        )
                        self.frame_count_for_fps = 0
                        self.prev_fps_calc_time = current_time

                    # Display FPS on the frame
                    cv2.putText(
                        processed_frame,
                        f"FPS: {int(self.display_fps)}",
                        (5, 15),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        1,
                        cv2.LINE_AA,
                    )
                    cv2.putText(
                        processed_frame,
                        f"Area Edit Mode: {'ON' if self.area_edit_mode else 'OFF'}",
                        (5, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 0, 0),
                        1,
                        cv2.LINE_AA,
                    )

                # Process detections
                self._process_detections(result, processed_frame)

                # Put the processed frame in the result queue
                if not self.result_queue.full():
                    self.result_queue.put(processed_frame)

        # Release resources
        cap.release()

    def _process_detections(self, result, frame):
        """Process detections from YOLO model."""
        current_track_ids_in_frame = set()

        # Process detections if any exist
        if result.boxes is not None and result.boxes.data.numel() > 0:
            for detection_tensor in result.boxes.data:
                if len(detection_tensor) == 7:  # Ensure tensor has expected length
                    x1, y1, x2, y2, track_id_val, conf_val, cls_val = detection_tensor

                    track_id = int(track_id_val)
                    current_track_ids_in_frame.add(track_id)

                    detection_details = {
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2),
                        "confidence": float(conf_val),
                        "class_id": int(cls_val),
                    }

                    if track_id not in self.active_tracks:
                        self.active_tracks[track_id] = {
                            "details": detection_details,
                            "hits": 1,
                            "misses": 0,
                        }
                    else:
                        self.active_tracks[track_id]["details"] = detection_details
                        self.active_tracks[track_id]["hits"] += 1
                        self.active_tracks[track_id]["misses"] = 0  # Reset misses

        # Draw areas
        self._draw_areas(frame)

        # Update tracking info and remove old tracks
        self._update_tracking(current_track_ids_in_frame)

        # Draw tracks and count people in areas
        self._draw_tracks_and_count(frame)

        # Handle timeout for detections
        self._handle_detection_timeout()

    def _draw_areas(self, frame):
        """Draw the defined areas on the frame."""
        if self.show_visualization:
            overlay = frame.copy()

            # Draw areas based on edit mode
            for idx, area in enumerate(self.areas):
                if self.area_edit_mode:
                    color = (
                        (0, 0, 255) if idx == self.current_setting_area else (255, 0, 0)
                    )
                    cv2.fillPoly(
                        overlay,
                        [np.array(area, dtype=np.int32)],
                        color=(255 * idx % 2, 255 * (1 - idx % 2), 0),
                    )
                    # Only draw corners in edit mode
                    for corner in area:
                        cv2.circle(overlay, corner, 5, color, -1)

            # Apply transparency only in edit mode
            if self.area_edit_mode:
                alpha = 0.3
                cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
            else:
                # Just draw outlines when not in edit mode
                for idx, area in enumerate(self.areas):
                    color = (255 * idx % 2, 255 * (1 - idx % 2), 0)
                    cv2.polylines(
                        frame, [np.array(area, dtype=np.int32)], True, color, 1
                    )

    def _update_tracking(self, current_track_ids_in_frame):
        """Update tracking information and remove stale tracks."""
        tracks_to_remove = []

        # Update misses for tracks not seen in this frame
        for tid, track_info in self.active_tracks.items():
            if tid not in current_track_ids_in_frame:
                track_info["misses"] += 1
                track_info["hits"] = 0  # Reset consecutive hits

            if track_info["misses"] > self.max_frames_missed:
                tracks_to_remove.append(tid)

        # Remove tracks that have been missed too many times
        for tid in tracks_to_remove:
            if tid in self.active_tracks:
                del self.active_tracks[tid]

    def _draw_tracks_and_count(self, frame):
        """Draw tracks and count people in areas."""
        if not self.show_visualization:
            return

        # Reset area counts
        self.inside_area_counts = [0] * len(self.areas)

        # Process each active track
        for track_id, track_info in self.active_tracks.items():
            if track_info["hits"] >= self.min_consecutive_hits:
                data = track_info["details"]
                x1, y1, x2, y2 = data["x1"], data["y1"], data["x2"], data["y2"]
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                bottom_y = int(y2)

                # Check if person is inside any area
                draw_color = (0, 255, 0)  # Default color
                inside = -1

                for i, area_poly in enumerate(self.area_polygons):
                    result = cv2.pointPolygonTest(
                        area_poly,
                        (center_x, bottom_y),
                        False,
                    )
                    if result >= 0:
                        inside = 1
                        self.inside_area_counts[i] += 1
                        break

                if inside >= 0:
                    draw_color = (0, 0, 255)

                # Draw bounding box
                cv2.rectangle(
                    frame,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    color=(3, 78, 252),
                    thickness=1,
                )

                # Draw bottom center point
                cv2.circle(
                    frame,
                    (center_x, bottom_y),
                    radius=3,
                    color=draw_color,
                    thickness=-1,
                )

                # Draw ID and confidence
                cv2.putText(
                    frame,
                    f"ID:{track_id} Conf:{data['confidence']:.2f} C:({center_x},{center_y})",
                    (int(x1), int(y1) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.3,
                    (0, 0, 255),
                    1,
                    cv2.LINE_AA,
                )

        # Draw area counts
        for idx, count in enumerate(self.inside_area_counts):
            self.total_entered += count

            # Calculate text position
            area = self.areas[idx]
            top_left = area[0]
            top_right = area[1]
            text_x = int((top_left[0] + top_right[0]) / 2)
            text_y = int(top_left[1] - 10)

            # Only draw text when count > 0 or in edit mode
            if count > 0 or self.area_edit_mode:
                cv2.putText(
                    frame,
                    f"Area {idx + 1}: {count}",
                    (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

    def _handle_detection_timeout(self):
        """Handle timeout for no detections."""
        inside_count = self.total_entered - self.total_exited

        current_time = time.time()
        if (
            current_time - self.last_detection_time > self.enable_reset_timeout
        ) and inside_count > 0:
            self.total_exited += inside_count
            inside_count = 0
            self.last_detection_time = current_time
        else:
            if inside_count > 0:
                self.last_detection_time = current_time

    def get_latest_frame(self):
        """Get the latest processed frame."""
        if not self.result_queue.empty():
            return self.result_queue.get()
        return None

    def display_loop(self):
        """Start the display loop in the current thread."""
        try:
            # Main display loop that won't block even if tracking is slow
            while self.running:
                # Get the latest processed frame
                frame = self.get_latest_frame()

                if frame is not None:
                    # Display the frame
                    cv2.imshow("Live Stream", frame)

                # Process keyboard input - this is critical for OpenCV to process window events
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):  # Press 'q' to quit
                    break
                elif key != 255:  # If any other key is pressed
                    self.process_key(key)
        finally:
            # Cleanup
            cv2.destroyAllWindows()

    def start_and_display(self):
        """Start the tracking thread and then run the display loop."""
        self.start()  # Start tracking in a separate thread
        self.display_loop()  # Run display loop in the current thread

    def start_all_in_background(self):
        """Start both tracking and display in background threads.
        NOTE: This uses a trick to make OpenCV GUI work in a separate thread,
        but it's not guaranteed to work on all systems."""
        import threading

        # Start tracking thread
        self.start()  # This is already a thread

        # Create a special UI thread for OpenCV
        self.ui_thread = threading.Thread(target=self._ui_thread_function)
        self.ui_thread.daemon = True
        self.ui_thread.start()

    def _ui_thread_function(self):
        """Function to run in the UI thread that handles OpenCV window events."""
        # Create a named window with normal flags in this thread
        cv2.namedWindow("Live Stream", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("Live Stream", self.set_corner)

        # Run the display loop in this thread
        self.display_loop()

    def stop(self):
        """Stop the tracking thread."""
        self.running = False


# if __name__ == "__main__":
#     # Create tracker instance
#     tracker = PersonTracker(
#         video_source="people_top.mp4",  # or 0 for webcam
#         width=1280,
#         height=720,
#     )

#     # Start tracking and display
#     tracker.start_and_display()

# No need for try/finally here as it's handled in display_loop
