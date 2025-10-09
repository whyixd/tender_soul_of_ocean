from serial_device_finder import print_all_ports, find_usb_serial_device
from modbus_reader import ModbusReader
import re
from time import sleep


class NaturalTracker:
    """Data structure is  [wind_speed, wind_level, wind_direction, wind_direction_compass]"""

    def __init__(
        self,
        vid="0403",
        pid="6001",
        history_file_path="log/[2025-07-10]modbus_reader.log",
    ):
        """
        初始化 NaturalTracker 類

        Args:
            vid (str): 風速計裝置的 Vendor ID
            pid (str): 風速計裝置的 Product ID
            history_file_path (str): 歷史數據文件路徑
        """
        self.vid = vid
        self.pid = pid
        self.history_file_path = history_file_path
        self.data = None
        self.history_data = []
        self.serial = None
        self.modbus = None
        self.read_wind_data = None

        # 初始化設備
        self.init_device()

    def init_device(self):
        """初始化風速計設備或準備歷史數據"""
        print_all_ports()
        self.serial = find_usb_serial_device(vid=self.vid, pid=self.pid)

        if self.serial is not None:
            print(f"找到 風速計 設備: {self.serial}")
            self.modbus = ModbusReader(com_port=self.serial)

            def read_data():
                self.modbus.read_sensor_data_threaded()
                return self.modbus.data

            self.read_wind_data = read_data
        else:
            print("找不到 風速計 設備，使用歷史數據")
            self._load_history_data()
            self.read_wind_data = self._create_history_data_reader()

    def _load_history_data(self):
        """載入歷史數據文件"""
        self.history_data = []
        with open(self.history_file_path, encoding="utf-8") as file:
            for line in file:
                self.history_data.append(line.strip())
        print(f"讀取歷史數據，共 {len(self.history_data)} 條")

    def _create_history_data_reader(self):
        """創建一個讀取歷史數據的函數"""
        count = 0

        def read_history_data_wrapper():
            nonlocal count
            pattern = r"風速:\s*([\d.]+)\s*m/s.*?風向角度:\s*([\d.]+)"
            if self.history_data is not None and len(self.history_data) > 0:
                try:
                    match = re.search(pattern, self.history_data[count])
                    if match:
                        wind_speed = float(match.group(1))
                        dir = float(match.group(2))
                    else:
                        dir = 0
                        wind_speed = float(0.0)

                    # 循環讀取歷史數據
                    count = (count + 1) % len(self.history_data)

                    return [wind_speed, 0, dir, "unknown"]
                except ValueError:
                    print("歷史數據格式錯誤，請檢查文件內容")
                    return None
                except IndexError:
                    print("歷史數據索引錯誤")
                    return None
            return None

        return read_history_data_wrapper

    def update(self):
        """更新風速數據，並返回最新的數據"""
        self.data = self.read_wind_data()
        return self.data

    def get_data(self):
        """獲取最後一次讀取的數據"""
        return self.data

    def start_continuous_update(self, interval=1, print_data=True):
        """
        開始連續更新風速數據

        Args:
            interval (float): 更新間隔時間(秒)
            print_data (bool): 是否打印數據
        """
        try:
            while True:
                self.data = self.read_wind_data()
                if self.data and print_data:
                    print(f"風速: {self.data[0]} m/s, 風向角度: {self.data[2]}")
                sleep(interval)
        except KeyboardInterrupt:
            print("停止連續更新")


# # 以下代碼演示如何使用 NaturalTracker 類
# if __name__ == "__main__":
#     # 創建 NaturalTracker 實例
#     tracker = NaturalTracker()

#     # 開始連續更新數據
#     tracker.start_continuous_update()
