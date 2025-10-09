import numpy as np
from config import Config
from stupidArtnet import StupidArtnet
import time

config = Config(
    data_dict={"unit_config": {"area_size": (8, 4), "units": []}},
    config_file_name="config/unit_config.json",
)
cords = []
for unit in config.data_dict["unit_config"]["units"]:
    cords.append((int(unit["cord"]["x"] / 2), unit["cord"]["z"]))
cords = np.array(cords)


def get_block_data(x, y, data):
    block_data_order = data[y * 4 : (y + 1) * 4, x * 8 : (x + 1) * 8].flatten()
    # print(block_data_order.reshape(4, 8))
    return block_data_order


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


whole_data = np.arange(8 * 4 * 18).reshape(4 * 3, 8 * 6)
cords = cords[:9]
blocks_ch_orders = []
for cord in cords:
    blocks_ch_orders.append(get_block_ch_order(len(blocks_ch_orders)))

data_packets = np.zeros(512)
for idx, cord in enumerate(cords):
    block_data = get_block_data(cord[0], cord[1], whole_data)
    ch_order = blocks_ch_orders[idx]
    print(block_data.reshape(4, 8))
    print(ch_order)
    print("-----")
    for idx, ch in enumerate(ch_order.flatten()):
        data_packets[ch] = block_data[idx]
data_packets = data_packets.astype(np.uint8).tobytes()

artnet = StupidArtnet(
    "169.254.83.107",
    0,
    512,
    fps=30,
    even_packet_size=True,
)
artnet.start()
artnet.set(data_packets)
try:
    while True:
        time.sleep(1 / 30)
except KeyboardInterrupt:
    artnet.blackout()
    artnet.stop()
    pass
