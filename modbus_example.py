import time
from pymodbus.client import ModbusSerialClient

# --- 1. 設定區塊 (已根據您的說明書修改) ---

# 序列埠設定
SERIAL_PORT = "/dev/ttyUSB0"  # Linux 上的序列埠名稱, Windows 上可能是 'COM3'
BAUDRATE = 4800  # 根據說明書，出廠預設為 4800
PARITY = "N"  # 根據說明書，奇偶校驗為無 [cite: 225]
STOPBITS = 1  # 根據說明書，停止位為 1 [cite: 225]
BYTESIZE = 8  # 根據說明書，數據位為 8 [cite: 225]

# Modbus 設備位址
SLAVE_ID = 1  # 根據說明書，出廠預設為 1 [cite: 242]

# 輪詢間隔時間（秒）
POLLING_INTERVAL = 5

# --- 2. 主程式 ---

# 建立 Modbus 客戶端
client = ModbusSerialClient(
    port=SERIAL_PORT,
    baudrate=BAUDRATE,
    parity=PARITY,
    stopbits=STOPBITS,
    bytesize=BYTESIZE,
    timeout=3,
)

# 用來存放所有解碼後的數據
weather_data = {}


def read_and_decode_weather_station(slave_id):
    """
    分次讀取並解碼氣象站數據。
    返回一個包含解碼後數據的字典。
    """
    decoded_data = {}

    # === 請求 1: 讀取風速與風向 (地址 500, 連續讀取 4 個) ===
    # 包含: 500-風速, 501-風力, 502-風向(0-7), 503-風向(0-360)
    print("Reading Wind Speed & Direction (Addr: 500, Count: 4)...")
    try:
        result = client.read_holding_registers(address=500, count=4, slave=slave_id)
        if result.isError():
            print(f"  ERROR: Failed to read wind data. Modbus response: {result}")
        else:
            # 根據說明書解碼
            decoded_data["wind_speed"] = result.registers[0] / 10.0  # 單位: m/s
            decoded_data["wind_force"] = result.registers[1]  # 單位: 級
            decoded_data["wind_direction"] = result.registers[3]  # 單位: 度
            print("  SUCCESS: Wind data decoded.")
    except Exception as e:
        print(f"  CRITICAL ERROR during wind data read: {e}")
    time.sleep(0.2)  # 請求之間增加延遲

    # === 請求 2: 讀取溫濕度 (地址 504, 連續讀取 2 個) ===
    # 包含: 504-濕度, 505-溫度
    print("Reading Humidity & Temperature (Addr: 504, Count: 2)...")
    try:
        result = client.read_holding_registers(address=504, count=2, slave=slave_id)
        if result.isError():
            print(
                f"  ERROR: Failed to read temp/humidity data. Modbus response: {result}"
            )
        else:
            # 根據說明書解碼
            decoded_data["humidity"] = result.registers[0] / 10.0  # 單位: %RH

            # 處理溫度 (可能是負數)
            temp_raw = result.registers[1]
            # 說明書提示，負溫以補碼形式上傳
            if temp_raw > 32767:  # 判斷是否為負數 (16-bit signed integer)
                temperature = (temp_raw - 65536) / 10.0
            else:
                temperature = temp_raw / 10.0
            decoded_data["temperature"] = temperature  # 單位: °C
            print("  SUCCESS: Temp/Humidity data decoded.")
    except Exception as e:
        print(f"  CRITICAL ERROR during temp/humidity read: {e}")
    time.sleep(0.2)

    # === 請求 3: 讀取大氣壓力 (地址 509, 讀取 1 個) ===
    print("Reading Atmospheric Pressure (Addr: 509, Count: 1)...")
    try:
        result = client.read_holding_registers(address=509, count=1, slave=slave_id)
        if result.isError():
            print(f"  ERROR: Failed to read pressure data. Modbus response: {result}")
        else:
            # 根據說明書解碼 [cite: 258]
            decoded_data["pressure"] = result.registers[0] / 10.0  # 單位: kPa
            print("  SUCCESS: Pressure data decoded.")
    except Exception as e:
        print(f"  CRITICAL ERROR during pressure read: {e}")

    return decoded_data


try:
    print("Connecting to Modbus slave...")
    if not client.connect():
        print(f"Failed to connect to slave at {SERIAL_PORT}")
        exit(1)

    print("Connection successful. Starting continuous reading...")

    while True:
        print(f"\n--- New poll cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

        # 呼叫函式來讀取並解碼數據
        weather_data = read_and_decode_weather_station(SLAVE_ID)

        # 印出格式化後的結果
        print("\n--- Decoded Weather Data ---")
        if weather_data:
            for key, value in weather_data.items():
                unit = ""
                if key == "temperature":
                    unit = "°C"
                elif key == "humidity":
                    unit = "%RH"
                elif key == "wind_speed":
                    unit = "m/s"
                elif key == "wind_direction":
                    unit = "°"
                elif key == "wind_force":
                    unit = " level"
                elif key == "pressure":
                    unit = "kPa"
                print(f"{key.replace('_', ' ').title():<20}: {value} {unit}")
        else:
            print("No data decoded in this cycle.")

        print(f"--- Poll cycle finished. Waiting for {POLLING_INTERVAL} seconds... ---")
        time.sleep(POLLING_INTERVAL)

except KeyboardInterrupt:
    print("\nProgram stopped by user.")

finally:
    if client.is_socket_open():
        client.close()
        print("Modbus connection closed.")
