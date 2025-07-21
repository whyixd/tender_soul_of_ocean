# app.py

from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import threading
from time import sleep

from artnet_sender import ArtNetSender

# 建立 Flask app
app = Flask(__name__, static_folder="static")

# 【關鍵】設定 Socket.IO，並允許所有來源的跨域請求，這在開發時非常重要
# In a real production app, you'd want to restrict cors_allowed_origins
socketio = SocketIO(app, cors_allowed_origins="*")

artnet = ArtNetSender("127.0.0.1", universe=0, channels=128)
artnet.block_shape = (8, 4)
artnet.block_order = [[1, 4], [2, 3]]  #
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
    off = 1
    print("🚀 Starting test sequence...")
    artnet.set_packet(matrix)  # 設定初始數據包
    artnet.send(remap=True)  # 初始發送一次
    socketio.emit("dmx_data", {"value": matrix})  # 初始發

    while True:
        matrix[count] = 255 * off
        count = (count + 1) % 128
        socketio.emit("dmx_data", {"value": matrix})
        if count == 0:
            off = 1 - off
        artnet.set_packet(matrix)
        artnet.send(remap=True)
        sleep(0.1)


# --- Flask 路由 ---


@app.route("/")
def index():
    """主路由，回傳 Webpack 打包好的 index.html"""
    return send_from_directory(app.static_folder, "index.html")


def run_server():
    print("🚀 Flask + Socket.IO server starting on http://127.0.0.1:5000")
    socketio.run(app, host="0.0.0.0", port=5000, use_reloader=False)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    try:
        send_test_sequence()  # 啟動測試序列發送 DMX 數據

        # 您也可以在主線程中，主動向所有客戶端廣播訊息
        # socketio.emit('server_broadcast', {'data': f'This is a broadcast from main thread, count: {count}'})

    except KeyboardInterrupt:
        print("\n🛑 Main thread received KeyboardInterrupt. Shutting down.")
