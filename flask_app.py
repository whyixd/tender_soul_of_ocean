# app.py

from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import threading
from time import sleep

from artnet_sender import ArtNetSender

from param_processer import TSOOParamProcesser

app = Flask(__name__, static_folder="static")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Disable caching for development

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# artnet = ArtNetSender("127.0.0.1", universe=0, channels=128)
artnet = ArtNetSender("2.56.31.102", universe=0, channels=128)
artnet.block_shape = (8, 4)
artnet.block_order = [[1, 3], [2, 4]]  #
artnet.start()


# --- Socket.IO 事件處理 ---


@socketio.on("connect")
def handle_connect():
    """當客戶端成功連接時觸發"""
    print("✅ Client connected!")


@socketio.on("disconnect")
def handle_disconnect():
    """當客戶端斷開連接時觸發"""
    print("❌ Client disconnected!")


@socketio.on("client_message")
def handle_client_message(json_data):
    """監聽一個名為 'client_message' 的自訂事件"""
    print(f"📬 Received message from client: {json_data['data']}")

    # 向客戶端發送一個回應事件
    response_data = {"message": "Hello from Flask!"}
    socketio.emit("server_message", response_data)


def send_test_sequence():
    matrix = []
    for i in range(0, 128):
        matrix.append(0)
    count = 0
    time = 0
    off = 1
    print("🚀 Starting test sequence...")
    artnet.set_packet(matrix)  # 設定初始數據包
    # artnet.send(remap=True)  # 初始發送一次
    socketio.emit("dmx_data", {"value": matrix})  # 初始發
    tsoo_param_processor = TSOOParamProcesser()
    tsoo_param_processor.tsoo_param["area_people_count"] = [5, 0, 5, 0]
    tsoo_param_processor.tsoo_param["wind_speed"] = 1.5
    print(tsoo_param_processor.get_tsoo_param())
    basic = tsoo_param_processor.shifting_basic(16, 8, scale=15, z=0.0)
    print(basic)
    while True:
        basic = tsoo_param_processor.shifting_basic(
            16,
            8,
            scale=15,
            z=time,
            gradient_vector=(
                tsoo_param_processor.tsoo_param["effect_vector"][0] * 5,
                tsoo_param_processor.tsoo_param["effect_vector"][1] * 5,
            ),
        )
        matrix = basic.flatten().tolist()
        # matrix[count] = 200 if off else 0
        count = (count + 1) % 128
        time += 0.002
        socketio.emit("dmx_data", {"value": matrix})
        if count == 0:
            off = 1 - off

        artnet.set_packet(matrix, 0.5)
        # artnet.send(remap=True)
        # sleep(0.5)
        sleep(0.03)


# --- Flask 路由 ---


@app.route("/")
def index():
    try:
        return send_from_directory(app.static_folder, "index.html")
    except FileNotFoundError:
        # During development, webpack-dev-server serves the file
        # so it's normal that we don't find it
        return "Development mode: Please access through webpack-dev-server", 200
    except Exception as e:
        print(f"Error serving index.html: {e}")
        return "Error serving the page", 500


@app.route("/show-case")
def show_case():
    try:
        return send_from_directory(app.static_folder, "show_case.html")
    except Exception as e:
        print(f"Error serving show_case.html: {e}")
        return "Error serving the page", 500


# Add a proper static file handler
@app.route("/static/<path:path>")
def serve_static(path):
    try:
        return send_from_directory(app.static_folder, path)
    except Exception as e:
        print(f"Error serving static file {path}: {e}")
        return "File not found", 404


def run_server():
    print("🚀 Flask + Socket.IO server starting on http://127.0.0.1:5000")
    socketio.run(app, host="0.0.0.0", port=5000, use_reloader=False, debug=False)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    try:
        send_test_sequence()  # 啟動測試序列發送 DMX 數據

        # 您也可以在主線程中，主動向所有客戶端廣播訊息
        # socketio.emit('server_broadcast', {'data': f'This is a broadcast from main thread, count: {count}'})

    except KeyboardInterrupt:
        print("\n🛑 Main thread received KeyboardInterrupt. Shutting down.")
