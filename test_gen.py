import cv2
import numpy as np
import threading
from time import sleep
from random import random


def draw():
    """繪製一個簡單的圖形"""

    count = 0
    while True:
        img = np.zeros((128, 256, 3), dtype=np.uint8)
        # draw grid outline 8x16
        cv2.circle(
            img, (int(256 * count), 64), round((count + 0.1) * 15), (0, 0, 255), -1
        )
        for i in range(0, 256, 16):
            cv2.line(img, (i, 0), (i, 128), (255, 255, 255), 1)
        for j in range(0, 128, 16):
            cv2.line(img, (0, j), (256, j), (255, 255, 255), 1)
        cv2.imshow("Circle", img)
        count += 0.01
        if count > 1:
            count = 0
        if cv2.waitKey(33) & 0xFF == ord("q"):  # 約 30 FPS
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # 啟動繪圖線程
    draw_thread = threading.Thread(target=draw)
    draw_thread.start()

    # 模擬其他操作
    for i in range(5):
        print(f"Main thread working... {i}")
        sleep(1)

    # 等待繪圖線程結束
    draw_thread.join()
    print("All tasks completed.")
