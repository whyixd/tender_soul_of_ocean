from stupidArtnet import StupidArtnet
from time import sleep
import random
import threading

from config import Config


class ArtNetSender:
    def __init__(
        self,
        ip,
        universe,
        channels,
        fps=30,
        even_packet_size=True,
        block_order=[[1, 2], [3, 4]],
        block_shape=(8, 4),
    ):
        self.artnet = StupidArtnet(
            ip,
            universe,
            512,
            fps=fps,
            even_packet_size=even_packet_size,
        )
        self.config = Config(
            data_dict={"unit_config": {"area_size": block_shape, "units": []}},
            config_file_name="config/unit_config.json",
        )

        self.packet_size = channels
        self.packet = bytearray(512)
        self.block_order = block_order
        self.block_shape = self.config.data_dict["unit_config"]["area_size"]
        self.block_count = len([x for sublist in self.block_order for x in sublist])
        self.block_channels_count = self.block_shape[0] * self.block_shape[1]
        self.__print_block_order_graph()
        self.channel_order = [i for i in range(0, len(self.packet))]

        self.__caculate_remap_order()
        print(f"channel_order: {self.channel_order}")

    def start(self):
        self.artnet.start()

    def stop(self):
        self.artnet.blackout()
        self.artnet.stop()
        self.artnet.close()

    def blackout(self):
        self.artnet.blackout()

    def set_packet(self, packet, intensity=1.0):
        for i in range(len(packet)):
            self.packet[i] = clamp(round(packet[i] * intensity), 0, 255)
        self.packet = self.__packet_remap(self.packet)
        # for i in range(len(self.packet)):
        #     self.packet[i] = round(self.packet[i])
        self.artnet.set(self.packet)

    # def set_channel(self, channel, value):
    #     if 0 <= channel < self.packet_size:
    #         self.packet[channel] = value
    #     else:
    #         raise IndexError("Channel index out of range")

    def __caculate_remap_order(self):

        self.channel_order += [
            i for i in range(self.packet_size, 36 * self.block_count)
        ]  # 填充至DMX解碼器全頻道 (36CH * 解碼器數量)
        temp_channel_order = list(
            split_list(self.channel_order, 4)
        )  # 4 為解碼器每個區塊的通道數

        for i in range(0, self.block_count):
            temp_channel_order.pop(i * 8)
        # 把 temp_channel_order 轉為四個 item 一組的二維列表
        temp_channel_order = list(split_list(temp_channel_order, self.block_shape[1]))
        temp_channel_order_copy = temp_channel_order.copy()
        temp_channel_order = []
        for i in range(0, len(temp_channel_order_copy), 2):
            for j in range(len(temp_channel_order_copy[i])):
                combined = (
                    temp_channel_order_copy[i][j] + temp_channel_order_copy[i + 1][j]
                )  # 合併兩個區塊的通道
                temp_channel_order.append(combined)
        temp_channel_order_copy = temp_channel_order.copy()
        temp_channel_order = []
        for i in range(0, len(temp_channel_order_copy), self.block_shape[1]):
            temp_channel_order.append(
                temp_channel_order_copy[i : i + self.block_shape[1]]
            )
        flattend_block_order = [
            item for sublist in self.block_order for item in sublist
        ]
        print(f"flattend_block_order: {flattend_block_order}")
        temp_channel_order = [temp_channel_order[i - 1] for i in flattend_block_order]
        temp_channel_order_copy = temp_channel_order.copy()
        temp_channel_order = []
        for i in range(0, len(temp_channel_order_copy), 2):
            for j in range(0, len(temp_channel_order_copy[i])):
                combined = (
                    temp_channel_order_copy[i][j] + temp_channel_order_copy[i + 1][j]
                )
                temp_channel_order.extend(combined)
        self.channel_order = temp_channel_order.copy()

    def __packet_remap(self, packet):
        packet_copy = bytearray(packet)
        packet = bytearray(512)
        for idx, order in enumerate(self.channel_order):
            packet[order] = packet_copy[idx]
        # fill the rest of the packet with zeros if needed
        # if len(packet) < 512:
        #     packet.extend(bytearray(512 - len(packet)))

        return packet

    def __print_block_order_graph(self):
        print(self.block_order)
        print(
            f"1 --→ {self.block_shape[0]*len(self.block_order[0])}\n↓\n{self.block_shape[0]*len(self.block_order[0])+1} --→ {self.block_shape[0]*len(self.block_order[0])+1+self.block_shape[0]*len(self.block_order[0])}"
        )
        self.__print_block_row()

    def __print_block_row(self):
        for row in self.block_order:
            first_line = "|‾‾‾‾‾‾‾‾‾‾‾|" * len(row) + "\n"
            # second_line = "|     1     |" * len(self.block_order) + "\n"
            second_line = ""
            for i in range(len(row)):
                second_line += f"|     {row[i]}" + (" " * (6 - len(str(row[i])))) + "|"
            second_line += "\n"
            third_line = "|___________|" * len(row) + "\n"
            print(first_line + second_line + third_line)

    # def __del__(self):
    #     self.stop()

    # →


def clamp(n, min_val, max_val):
    return max(min_val, min(n, max_val))


def split_list(list, n):
    """將list分為n個元素組成的子列表"""
    for idx in range(0, len(list), n):
        yield list[idx : idx + n]
