import cv2

cap = cv2.VideoCapture(0)  # 0 is the default webcam index

width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

print(f"Webcam resolution: {int(width)} x {int(height)}")

cap.release()
