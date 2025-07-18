from stupidArtnet import StupidArtnet
from time import sleep


class ArtNetSender:
    def __init__(self, ip, universe, channels, fps=30, even_packet_size=True):
        self.artnet = StupidArtnet(
            ip,
            universe,
            channels,
            fps=fps,
            even_packet_size=even_packet_size,
        )
        self.packet_size = channels
        self.packet = bytearray(channels)
        self.block_order = [[1, 3], [2, 4]]
        self.block_shape = (8, 4)  # →↓
        self.block_channels_count = self.block_shape[0] * self.block_shape[1]
        self.__print_block_order_graph()
        print(self.artnet.packet_size)

    def start(self):
        self.artnet.start()

    def send(self, remap=False):
        if remap:
            self.__packet_remap()
        self.artnet.send(self.packet)

    def set_channel(self, channel, value):
        if 0 <= channel < len(self.packet):
            self.packet[channel] = value
        else:
            raise IndexError("Channel index out of range")

    def blackout(self):
        self.artnet.blackout()

    def stop(self):
        self.artnet.blackout()
        self.artnet.stop()

    def __packet_remap(self):
        channels_row = []
        for order in range(0, len(self.packet), self.block_shape[0]):
            channels_row.append(self.packet[order : order + self.block_shape[0]])
            int_values = [x for x in channels_row[-1]]
            print(f"Block {len(channels_row)}: {int_values}")

        # concat the blocks in the order of block_order
        block_order_flat = [item for sublist in self.block_order for item in sublist]
        print(f"Block order flat: {block_order_flat}")
        packet_copy = bytearray(self.packet)
        self.packet = bytearray()
        for block_row in range(len(self.block_order)):
            for sub_row in range(self.block_shape[1]):
                for block in self.block_order[block_row]:
                    self.packet.extend(
                        packet_copy[
                            (block - 1) * self.block_channels_count
                            + (sub_row * self.block_shape[0]) : (block - 1)
                            * self.block_channels_count
                            + (sub_row * self.block_shape[0])
                            + self.block_shape[0]
                        ]
                    )
        # fill the rest of the packet with zeros if needed
        # if len(self.packet) < self.packet_size:
        #     self.packet.extend(bytearray(self.packet_size - len(self.packet)))
        int_values = [x for x in self.packet]
        print(f"Remapped packet: {int_values}")

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


artnet = ArtNetSender("127.0.0.1", universe=0, channels=128)
artnet.block_channels_count = 32
artnet.start()

for i in range(128):
    artnet.set_channel(i, i)
int_values = [x for x in artnet.packet]
print(int_values)
artnet.send(remap=True)
try:
    while True:
        sleep(0.1)
except KeyboardInterrupt:
    print("Stopping ArtNet sender...")
    artnet.stop()
    print("ArtNet sender stopped.")
