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
CAP_INDEX = 1  # Default webcam
DESIRED_WIDTH = 1280
DESIRED_HEIGHT = 720
cap = cv2.VideoCapture(CAP_INDEX)
# cap = cv2.VideoCapture("people_top.mp4")
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

area_edit_mode = False  # Flag to indicate if area edit mode is active
areas = [
    [(100, 100), (200, 100), (200, 200), (100, 200)],  # Example area polygon
    [(300, 300), (400, 300), (400, 400), (300, 400)],  # Another example area polygon
]
current_setting_corners = 0
current_setting_area = 0

inside_area_counts = [0] * len(areas)  # Initialize counts for each area


def set_corner(event, x, y, flags, param):
    global areas, current_setting_corners, current_setting_area, area_edit_mode
    if not area_edit_mode:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        areas[current_setting_area][current_setting_corners] = (x, y)


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
            (5, 15),  # Position at the top-left corner
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,  # Font scale
            (0, 255, 0),  # Green color
            1,  # Thickness
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"Area Edit Mode: {'ON' if area_edit_mode else 'OFF'}",
            (5, 30),  # Position below FPS
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 0, 0),  # Blue color
            1,
            cv2.LINE_AA,
        )

        current_track_ids_in_frame = set()

        if result.boxes is not None and result.boxes.data.numel() > 0:
            for detection_tensor in result.boxes.data:
                # Expected format with tracking: [x1, y1, x2, y2, track_id, confidence, class_id]
                if (
                    len(detection_tensor) == 7
                ):  # Ensure the tensor has the expected length
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
        if keycode == 101:  # e
            area_edit_mode = not area_edit_mode
        if keycode == 113:  # q
            current_setting_corners = 0
        elif keycode == 119:  # w
            current_setting_corners = 1
        elif keycode == 97:  # a
            current_setting_corners = 3
        elif keycode == 115:  # s
            current_setting_corners = 2
        if keycode in range(49, 57):  # 1-9
            current_setting_area = keycode - 49
        overlay = frame.copy()  # Create a copy of the frame for overlay
        for idx, area in enumerate(areas):
            color = (0, 0, 255) if idx == current_setting_area else (255, 0, 0)
            cv2.fillPoly(
                frame,
                [np.array(area, dtype=np.int32)],
                color=(
                    255 * idx % 2,
                    255 * (1 - idx % 2),
                    0,
                ),  # Green color for polygon
            )
            for corner in area:
                cv2.circle(frame, corner, 5, color, -1)
        # Apply transparency (alpha blending)
        alpha = 0.8  # Transparency factor: 0 = fully transparent, 1 = fully opaque
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
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
        inside_area_counts = [0] * len(areas)  # Reset counts for each area
        for track_id, track_info in active_tracks.items():
            if track_info["hits"] >= MIN_CONSECUTIVE_HITS:
                data = track_info["details"]
                x1, y1, x2, y2 = data["x1"], data["y1"], data["x2"], data["y2"]
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                bottom_y = int(y2)
                # drawing code follows
                draw_color = (0, 255, 0)  # Default Green color for drawing
                inside = -1
                for area in areas:
                    result = cv2.pointPolygonTest(
                        np.array(area, dtype=np.int32),
                        (center_x, bottom_y),
                        False,
                    )
                    if result >= 0:
                        inside = 1
                        inside_area_counts[areas.index(area)] += 1
                        break
                if inside >= 0:
                    draw_color = (0, 0, 255)

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
                    thickness=1,
                )

                client.send_message("/person", (track_id, center_x, center_y))

                # # Draw the bounding box center on the frame
                # cv2.circle(
                #     frame,
                #     (center_x, center_y),
                #     radius=3,
                #     color=draw_color,
                #     thickness=-1,
                # )
                # Draw the bounding box bottom on the frame
                cv2.circle(
                    frame,
                    (center_x, bottom_y),
                    radius=3,
                    color=draw_color,
                    thickness=-1,
                )
                cv2.putText(
                    frame,
                    f"ID:{track_id} Conf:{data['confidence']:.2f} C:({center_x},{center_y})",
                    (int(x1), int(y1) - 10),  # Position text above the box
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.3,
                    (0, 0, 255),
                    1,
                    cv2.LINE_AA,
                )
        for idx, count in enumerate(inside_area_counts):
            total_entered += count

            # Calculate midpoint between top-left and top-right corners for text placement
            area = areas[idx]
            top_left = area[0]  # First point in the area
            top_right = area[1]  # Second point in the area
            text_x = int((top_left[0] + top_right[0]) / 2)
            text_y = int(top_left[1] - 10)  # Slightly above the top edge
            # Draw area label above the area
            cv2.putText(
                frame,
                f"Area {idx + 1}: {count}",
                (text_x, text_y),  # Position at the middle-top of the area
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),  # White text
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
