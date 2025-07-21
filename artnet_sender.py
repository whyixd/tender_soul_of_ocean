from stupidArtnet import StupidArtnet
from time import sleep
import random


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
            channels,
            fps=fps,
            even_packet_size=even_packet_size,
        )
        self.packet_size = channels
        self.packet = bytearray(channels)
        self.block_order = block_order
        self.block_shape = block_shape
        self.block_channels_count = self.block_shape[0] * self.block_shape[1]
        self.__print_block_order_graph()
        self.channel_order = [i for i in range(0, len(self.packet))]
        self.__caculate_remap_order()

    def start(self):
        self.artnet.start()

    def send(self, remap=False):
        if remap:
            self.__packet_remap()
        self.artnet.send(self.packet)

    def set_packet(self, packet):
        for i in range(len(packet)):
            self.packet[i] = clamp(packet[i], 0, 255)

    def set_channel(self, channel, value):
        if 0 <= channel < self.packet_size:
            self.packet[channel] = value
        else:
            raise IndexError("Channel index out of range")

    def blackout(self):
        self.artnet.blackout()

    def stop(self):
        self.artnet.blackout()
        self.artnet.stop()

    def __caculate_remap_order(self):
        temp_channel_order = list(split_list(self.channel_order, self.block_shape[0]))
        self.channel_order = []
        for block_row_idx, block_row in enumerate(self.block_order):
            for block_repeat in range(self.block_shape[1]):
                for block in block_row:
                    self.channel_order += temp_channel_order[
                        (block - 1) * self.block_shape[1] + block_repeat
                    ]
        # print(self.channel_order)

    def __packet_remap(self):
        packet_copy = bytearray(self.packet)
        for idx, order in enumerate(self.channel_order):
            self.packet[order] = packet_copy[idx]

    def __print_block_order_graph(self):
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

    # →


def clamp(n, min_val, max_val):
    return max(min_val, min(n, max_val))


def split_list(list, n):
    """將list分為n個元素組成的子列表"""
    for idx in range(0, len(list), n):
        yield list[idx : idx + n]


# artnet = ArtNetSender("127.0.0.1", universe=0, channels=128)

# artnet.start()

# matrix = []
# for i in range(0, 128):
#     matrix.append(i)
# artnet.set_packet(matrix)  # 設定初始數據包
# # print(int_values)
# artnet.send(remap=True)
# try:
#     while True:
#         sleep(0.1)
#         matrix[random.randint(0, 127)] = random.randint(0, 255)
#         artnet.set_packet(matrix)  # 設定初始數據包
#         artnet.send(remap=True)
# except KeyboardInterrupt:
#     print("Stopping ArtNet sender...")
#     artnet.stop()
#     print("ArtNet sender stopped.")
