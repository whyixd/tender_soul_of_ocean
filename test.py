from ultralytics import YOLO
import cv2
import logging
import time
import torch
from pythonosc import udp_client
import numpy as np

logging.getLogger("ultralytics").setLevel(logging.ERROR)  # Suppress warnings


client = udp_client.SimpleUDPClient("127.0.0.1", 5005)  # Create a UDP client

print(torch.cuda.get_device_name())
# print(torch.__version__)  # PyTorch version
# print(torchvision.__version__)  # TorchVision version
# model = YOLO("yolo11n.pt")
model = YOLO("yolo11n-seg.pt")
# model = YOLO("yolo11n-pose.pt")
model.to("cuda")  # Move model to GPU
print(model.device)

prev_fps_calc_time = time.time()  # For FPS calculation
frame_count_for_fps = 0
display_fps = 0

target_fps = 30
# frame_duration = 1.0 / target_fps  # Target duration for each frame in seconds # Not used
# --- Webcam and Resolution Setup ---
CAP_INDEX = 0  # Default webcam
DESIRED_WIDTH = 1280
DESIRED_HEIGHT = 720
# cap = cv2.VideoCapture(CAP_INDEX)
cap = cv2.VideoCapture("people_top.mp4")
cap.set(cv2.CAP_PROP_FRAME_WIDTH, DESIRED_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, DESIRED_HEIGHT)

# --- Temporal Filtering Parameters ---
active_tracks = {}  # Stores info about currently tracked objects
MIN_CONSECUTIVE_HITS = 8  # Min consecutive frames to show a track
MAX_FRAMES_MISSED = 3  # Max frames a track can be missed before removal
# Add counters for people entering and exiting
total_entered = 0  # Total number of people entered
total_exited = 0  # Total number of people exited
# Add timeout threshold for no detections
enable_reset_timeout = 5  # seconds without detections before resetting inside count
last_detection_time = time.time()
# --- End Temporal Filtering Parameters ---

corners = [
    (100, 100),
    (200, 100),
    (200, 200),
    (100, 200),
]  # Example corners for a polygon
current_setting_corners = 0


def set_corner(event, x, y, flags, param):
    global corners
    global current_setting_corners
    if event == cv2.EVENT_LBUTTONDOWN:
        corners[current_setting_corners] = (x, y)


cv2.namedWindow("Live Stream")
cv2.setMouseCallback("Live Stream", set_corner)
# Start tracking
while cap.isOpened():
    success, frame = cap.read()
    if not success:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 重置到第一禎
        success, frame = cap.read()
        if not success:  # 如果還是不成功，退出循環
            break

    for result in model.track(
        frame,
        show=False,
        classes=[0],
        conf=0.4,
        stream=True,
        persist=True,  # persist=True is important for tracker
        imgsz=(DESIRED_WIDTH, DESIRED_HEIGHT),  # Resize to desired resolution
    ):  # Use stream=True for live processing
        loop_start_time = time.time()
        frame = result.orig_img  # Get the original frame

        frame_count_for_fps += 1
        current_time = time.time()
        if (
            current_time - prev_fps_calc_time >= 0.5
        ):  # Update FPS display every 0.5 seconds
            display_fps = frame_count_for_fps / (current_time - prev_fps_calc_time)
            frame_count_for_fps = 0
            prev_fps_calc_time = current_time

        # Display FPS on the frame
        cv2.putText(
            frame,
            f"FPS: {int(display_fps)}",
            (10, 30),  # Position at the top-left corner
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,  # Font scale
            (0, 255, 0),  # Green color
            2,  # Thickness
            cv2.LINE_AA,
        )

        current_track_ids_in_frame = set()

        if result.boxes is not None and result.boxes.data.numel() > 0:
            for detection_tensor in result.boxes.data:
                # Expected format with tracking: [x1, y1, x2, y2, track_id, confidence, class_id]
                if len(detection_tensor) == 7:
                    x1, y1, x2, y2, track_id_val, conf_val, cls_val = detection_tensor

                    track_id = int(track_id_val)
                    # class_id is already filtered by classes=[0] in model.track()
                    # but we can double check if needed: if int(cls_val) != 0: continue

                    current_track_ids_in_frame.add(track_id)

                    detection_details = {
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2),
                        "confidence": float(conf_val),
                        "class_id": int(cls_val),
                    }

                    if track_id not in active_tracks:
                        active_tracks[track_id] = {
                            "details": detection_details,
                            "hits": 1,
                            "misses": 0,
                        }
                    else:
                        active_tracks[track_id][
                            "details"
                        ] = detection_details  # Update with latest data
                        active_tracks[track_id]["hits"] += 1
                        active_tracks[track_id][
                            "misses"
                        ] = 0  # Reset misses as it's seen
                # else:
                # Handle cases with unexpected tensor length if necessary,
                # but tracking should provide 7 elements.
                # print(f"Skipping detection with unexpected length: {len(detection_tensor)}")
        keycode = cv2.waitKey(1)
        if keycode == 113:
            current_setting_corners = 0
        elif keycode == 119:  # 'w' key to set next corner
            current_setting_corners = 1
        elif keycode == 97:
            current_setting_corners = 3
        elif keycode == 115:
            current_setting_corners = 2
        overlay = frame.copy()  # Create a copy of the frame for overlay
        cv2.fillPoly(
            frame,
            [np.array(corners, dtype=np.int32)],
            color=(255, 0, 0, 30),  # Green color for polygon
        )
        # Apply transparency (alpha blending)
        alpha = 0.3  # Transparency factor: 0 = fully transparent, 1 = fully opaque
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        for corner in corners:
            cv2.circle(frame, corner, 5, (0, 0, 255), -1)
        # Update misses for tracks not seen in this frame and remove old tracks
        tracks_to_remove = []
        for tid, track_info in active_tracks.items():
            if tid not in current_track_ids_in_frame:
                track_info["misses"] += 1
                track_info["hits"] = 0  # Reset consecutive hits if missed

            if track_info["misses"] > MAX_FRAMES_MISSED:
                tracks_to_remove.append(tid)

        for tid in tracks_to_remove:
            if tid in active_tracks:  # Check if not already removed by another logic
                del active_tracks[tid]

        # Now, draw only confirmed tracks that meet the hit threshold
        midline = frame.shape[0] // 2  # Middle y-coordinate for entry/exit line
        for track_id, track_info in active_tracks.items():
            if track_info["hits"] >= MIN_CONSECUTIVE_HITS:
                data = track_info["details"]
                x1, y1, x2, y2 = data["x1"], data["y1"], data["x2"], data["y2"]
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                # initialize counting side for new track
                # if "counted" not in track_info:
                #     track_info["side"] = "below" if center_y > midline else "above"
                #     track_info["counted"] = False
                # # count crossing
                # elif not track_info["counted"]:
                #     current_side = "below" if center_y > midline else "above"
                #     if track_info["side"] == "above" and current_side == "below":
                #         total_entered += 1
                #         track_info["counted"] = True
                #     elif track_info["side"] == "below" and current_side == "above":
                #         total_exited += 1
                #         track_info["counted"] = True
                # drawing code follows
                draw_color = (0, 255, 0)  # Default Green color for drawing
                inside = cv2.pointPolygonTest(
                    np.array(corners, dtype=np.int32), (center_x, center_y), False
                )
                if inside >= 0:
                    draw_color = (0, 0, 255)
                # if center_y > frame.shape[0] / 2:
                #     draw_color = (
                #         3,
                #         78,
                #         252,
                #     )  # Red if person's center is in the lower half

                # Draw the bounding box on the frame
                cv2.rectangle(
                    frame,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    color=(
                        3,
                        78,
                        252,
                    ),  # Darker green for bounding box
                    thickness=2,
                )

                client.send_message("/person", (track_id, center_x, center_y))

                # Draw the bounding box center on the frame
                cv2.circle(
                    frame,
                    (center_x, center_y),
                    radius=5,
                    color=draw_color,
                    thickness=-1,
                )
                # Draw a horizontal line at the person's center_y
                # cv2.line(
                #     frame,
                #     (0, center_y),
                #     (frame.shape[1], center_y),
                #     color=draw_color,
                #     thickness=1,
                # )
                cv2.putText(
                    frame,
                    f"ID:{track_id} Conf:{data['confidence']:.2f} C:({center_x},{center_y})",
                    (int(x1), int(y1) - 10),  # Position text above the box
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    draw_color,
                    1,
                    cv2.LINE_AA,
                )

        # Display net people inside the frame
        # reset inside count if no detections for a while
        inside_count = total_entered - total_exited

        current_time = time.time()
        if (
            current_time - last_detection_time > enable_reset_timeout
        ) and inside_count > 0:
            total_exited += inside_count
            # reset inside counter and update last detection time
            inside_count = 0
            last_detection_time = current_time
        else:
            # update last detection time when people are present
            if inside_count > 0:
                last_detection_time = current_time

        cv2.imshow("Live Stream", frame)

        # Break the loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
cap.release()
cv2.destroyAllWindows()
