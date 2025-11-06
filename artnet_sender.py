from stupidArtnet import StupidArtnet
from time import sleep
import random
import threading

from config import Config
import numpy as np


class ArtNetSender:
    """
    海境燈光 ArtNet 發送器，用於控制燈光單元的 DMX 通道映射與發送\n
    使用 set_packet 送出燈光資料，輸入 packet 時輸入整座海境的資料\n
    sender 會根據 unit_config.json 內的單元座標與排列方式，自動切分重新映射到各單元的 DMX 頻道\n
    用到幾個 universe 就使用幾個 sender\n
    """

    def __init__(
        self,
        ip,
        universe,
        fps=30,
        even_packet_size=True,
        unit_order=[[1, 2], [3, 4]],
        unit_shape=(8, 4),
        artnet_index=0,  # TODO:暫時改為多arnet
    ):
        self.artnet_index = artnet_index
        self.artnet = StupidArtnet(
            ip,
            universe,
            512,
            fps=fps,
            even_packet_size=even_packet_size,
        )
        self.target_ip = ip
        self.config = Config(
            data_dict={"unit_config": {"area_size": unit_shape, "units": []}},
            config_file_name="config/unit_config.json",
        )

        self.packet = bytearray(512)
        self.unit_order = unit_order  # 單元排列方式
        self.area_shape = self.config.data_dict["unit_config"][
            "area_size"
        ]  # 單元大小(寬, 高)
        self.intensity = 1.0  # 亮度(0.0~1.0)

        self.cords = []  # 單元座標
        for unit in self.config.data_dict["unit_config"]["units"]:
            self.cords.append((int(unit["cord"]["x"] / 2), unit["cord"]["z"]))
        self.cords = np.array(self.cords)
        self.blocks_ch_orders = []  # 單元頻道順序

        self.__print_block_order_graph()
        self.__caculate_remap_order()

    def start(self):
        """啟動 ArtNet"""
        self.artnet.start()

    def stop(self):
        """停止 ArtNet"""
        self.artnet.blackout()
        self.artnet.stop()
        self.artnet.close()

    def blackout(self):
        """關閉所有通道"""
        self.artnet.blackout()

    def set_packet(self, packet):
        """設定 ArtNet 封包內容並發送"""
        self.packet = self.__packet_remap(packet)
        self.artnet.set(self.packet)

    def __caculate_remap_order(self):
        """計算單元頻道順序，依照單元排列方式與單元大小"""

        def get_block_ch_order(cord_idx):
            unit_ch_setup = np.array(
                [
                    [1, 2, 3, 4, 17, 18, 19, 20],
                    [5, 6, 7, 8, 21, 22, 23, 24],
                    [9, 10, 11, 12, 25, 26, 27, 28],
                    [13, 14, 15, 16, 29, 30, 31, 32],
                ]
            )
            unit_ch_setup_flatten = unit_ch_setup.flatten()
            unit_ch_setup_flatten -= 1
            unit_ch_setup_flatten += cord_idx * 36 + 4
            return unit_ch_setup_flatten.reshape(4, 8)

        wantedUnit = [1, 2, 3, 4, 6, 7, 8, 31, 34, 35, 36, 37, 38, 39, 40]
        cords = []
        for idx, cord in enumerate(self.cords):
            if (idx + 1) in wantedUnit:
                cords.append(cord)
        # cords = self.cords[:7]
        # if self.artnet_index == 1:
        #     cords = self.cords[8:]
        self.cords = cords
        for cord in cords:
            self.blocks_ch_orders.append(get_block_ch_order(len(self.blocks_ch_orders)))
        return self.blocks_ch_orders

    def __packet_remap(self, packet):
        """重新映射封包內容，依照單元排列方式與單元大小"""

        def get_block_data(x, y, data):
            block_data_order = data[y * 4 : (y + 1) * 4, x * 8 : (x + 1) * 8].flatten()
            return block_data_order

        # packet_copy = np.array(packet).reshape(4 * 3, 8 * 6)
        packet_copy = np.array(packet).reshape(4 * 5, 8 * 8)
        data_packets = np.zeros(512)
        cords = self.cords[:7]
        if self.artnet_index == 1:
            cords = self.cords[8:]

        for idx, cord in enumerate(cords):
            block_data = get_block_data(cord[0], cord[1], packet_copy)
            ch_order = self.blocks_ch_orders[idx]
            for idx, ch in enumerate(ch_order.flatten()):
                data_packets[ch] = clamp(
                    round(block_data[idx] * self.intensity), 0, 255
                )
        data_packets = data_packets.astype(np.uint8).tobytes()
        return data_packets

    def packet_remap(self, packet):
        """重新映射封包內容，依照單元排列方式與單元大小"""
        return self.__packet_remap(packet)

    def __print_block_order_graph(self):
        """印出單元排列方式"""

        print(f"[{self.target_ip}] 單元排列方式 ↓")
        self.__print_block_row()

    def __print_block_row(self):
        """印出單元排列方式的行"""

        for row in self.unit_order:
            first_line = "|‾‾‾‾‾‾‾‾‾‾‾|" * len(row) + "\n"
            # second_line = "|     1     |" * len(self.block_order) + "\n"
            second_line = ""
            for i in range(len(row)):
                second_line += f"|     {row[i]}" + (" " * (6 - len(str(row[i])))) + "|"
            second_line += "\n"
            third_line = "|___________|" * len(row) + "\n"
            print(first_line + second_line + third_line)


def clamp(n, min_val, max_val):
    return max(min_val, min(n, max_val))


# if __name__ == "__main__":
#     artnet = ArtNetSender(
#         ip="2.0.0.100",
#         universe=0,
#         # channels=artnet_channels,
#         unit_shape=(8, 4),
#         unit_order=[
#             [1, 2, 3, 4],
#             [5, 6, 7],
#         ],
#         artnet_index=0,
#     )

# artnet.start()
# artnet2 = ArtNetSender(
#     ip="2.0.0.101",
#     universe=0,
#     # channels=artnet_channels,
#     unit_shape=(8, 4),
#     unit_order=[
#         [8],
#         [9, 10, 11],
#         [12, 13, 14, 15, 16],
#     ],
#     artnet_index=1,
# )

# artnet2.start()
# data = [0] * 512
# for i in range(512):
#     data[i] = i
# artnet.set_packet(data)
# artnet2.set_packet(data)
