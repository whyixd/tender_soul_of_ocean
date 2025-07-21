import cv2
import numpy as np
import threading
from time import sleep
from random import random
from artnet_sender import ArtNetSender


artnet = ArtNetSender(
    "127.0.0.1",
    universe=0,
    channels=128,
    block_order=[[1, 4], [2, 3]],
    block_shape=(8, 4),
)
artnet.start()
width, height = 256, 128  # 圖像寬度和高度
# 步驟 2: 定義網格大小
grid_cols = 16  # 16欄
grid_rows = 8  # 8列

# 步驟 3: 計算每個網格小格子的寬度和高度
# 使用整數除法 // 來確保得到整數像素值
cell_width = width // grid_cols
cell_height = height // grid_rows


def draw():
    """繪製一個簡單的圖形"""
    pixel_data = [0] * 128
    count = 0
    row = 0
    while True:
        img = np.zeros((128, 256, 3), dtype=np.uint8)
        # draw grid outline 8x16
        cv2.circle(img, (int(256 * count), int(10 + row * 15)), 10, (0, 0, 255), -1)
        for i in range(0, 256, 16):
            cv2.line(img, (i, 0), (i, 128), (255, 255, 255), 1)
        for j in range(0, 128, 16):
            cv2.line(img, (0, j), (256, j), (255, 255, 255), 1)
        for i in range(grid_rows):
            for j in range(grid_cols):
                # 計算當前格子的左上角座標
                start_x = j * cell_width
                start_y = i * cell_height

                # 計算中心點座標
                # 中心點 = 左上角座標 + 格子尺寸的一半
                center_x = start_x + (cell_width // 2)
                center_y = start_y + (cell_height // 2)

                pixel_value = img[center_y, center_x]
                grid_info = {
                    "grid_coord": (j, i),
                    "center_pixel_coord": (center_x, center_y),
                    "pixel_value_bgr": pixel_value.tolist(),  # 轉換成 list 方便查看
                }
                # 取得中心點的 BGR 像素值
                pixel_data[i * grid_cols + j] = pixel_value.tolist()[2]
                cv2.putText(
                    img,
                    str(i * grid_cols + j),
                    (center_x - 5, center_y + 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.22,
                    (0, 255, 255),
                    1,
                    cv2.LINE_AA,
                )  # 以亮黃色標示
        artnet.set_packet(pixel_data)
        artnet.send(remap=True)
        cv2.imshow("Test", img)
        count += 0.01
        if count > 1:
            count = 0
            row += 1
            if row >= grid_rows:
                row = 0

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
