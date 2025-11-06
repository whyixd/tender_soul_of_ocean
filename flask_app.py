# app.py

from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO
import threading
from time import sleep

from artnet_sender import ArtNetSender

from param_processer import TSOOParamProcesser
from natural_tracker import NaturalTracker
from config import Config


class TSOOFlaskApp:
    def __init__(
        self,
        host="127.0.0.1",
        port=5000,
        artnet_host="127.0.0.1",
        artnet_universe=0,
        artnet_channels=128,
        block_shape=(8, 4),
        block_order=[
            [1, 4, 7, 10, 13, 16],
            [2, 5, 8, 11, 14, 17],
            [3, 6, 9, 12, 15, 18],
        ],
        static_folder="static",
    ):
        # Flask 應用設置
        self.app = Flask(__name__, static_folder=static_folder)
        self.app.config["SEND_FILE_MAX_AGE_DEFAULT"] = (
            0  # Disable caching for development
        )

        # Socket.IO 設置
        self.socketio = SocketIO(
            self.app, cors_allowed_origins="*", async_mode="threading"
        )

        # ArtNet 設置
        self.artnet = ArtNetSender(
            artnet_host,
            universe=artnet_universe,
            # channels=artnet_channels,
            unit_shape=block_shape,
            unit_order=[
                [1, 2, 3, 4],
                [5, 6, 7, 8],
                [9, 10, 11, 12],
                [13, 14, 15, 16],
                [17, 18, 19, 20],
            ],
            artnet_index=0,
        )
        self.artnet2 = ArtNetSender(
            "169.254.55.36",
            universe=artnet_universe,
            # channels=artnet_channels,
            unit_shape=block_shape,
            unit_order=[
                [21, 22, 23, 24],
                [25, 26, 27, 28],
                [29, 30, 31, 32],
                [33, 34, 35, 36],
                [37, 38, 39, 40],
            ],
            artnet_index=1,
        )

        # 服務器配置
        self.host = host
        self.port = port

        # 狀態追蹤
        self.is_running = False
        self.server_thread = None
        self.effect_thread = None

        # 參數處理和自然追蹤
        self.tsoo_param_processor = None
        self.natural_tracker = None

        # 設置路由和事件處理
        self._setup_routes()
        self._setup_socketio_events()
        self._setup_unit_config_api()

    def _setup_routes(self):
        """設置 Flask 路由"""

        @self.app.after_request
        def add_cors_headers(resp):
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
            return resp

        @self.app.route("/")
        def index():
            try:
                return send_from_directory(self.app.static_folder, "index.html")
            except FileNotFoundError:
                # During development, webpack-dev-server serves the file
                # so it's normal that we don't find it
                return "Development mode: Please access through webpack-dev-server", 200
            except Exception as e:
                print(f"Error serving index.html: {e}")
                return "Error serving the page", 500

        @self.app.route("/show-case")
        def show_case():
            try:
                return send_from_directory(self.app.static_folder, "show_case.html")
            except Exception as e:
                print(f"Error serving show_case.html: {e}")
                return "Error serving the page", 500

        @self.app.route("/static/<path:path>")
        def serve_static(path):
            try:
                return send_from_directory(self.app.static_folder, path)
            except Exception as e:
                print(f"Error serving static file {path}: {e}")
                return "File not found", 404

    def _setup_socketio_events(self):
        """設置 Socket.IO 事件處理"""

        @self.socketio.on("connect")
        def handle_connect():
            """當客戶端成功連接時觸發"""
            print("✅ Client connected!")

        @self.socketio.on("disconnect")
        def handle_disconnect():
            """當客戶端斷開連接時觸發"""
            print("❌ Client disconnected!")

        @self.socketio.on("client_message")
        def handle_client_message(json_data):
            """監聽一個名為 'client_message' 的自訂事件"""
            print(f"📬 Received message from client: {json_data['data']}")

            # 向客戶端發送一個回應事件
            response_data = {"message": "Hello from Flask!"}
            self.socketio.emit("server_message", response_data)

    def _setup_unit_config_api(self):
        @self.app.route("/api/unit_config")
        def get_unit_config():
            """提供單元配置的 API 端點"""
            try:
                config = Config(
                    data_dict={"unit_config": {"area_size": (8, 4), "units": []}},
                    config_file_name="config/unit_config.json",
                )

                return config.data_dict, 200
            except Exception as e:
                print(f"Error fetching unit config: {e}")
                return {"status": "error", "message": str(e)}, 500

        @self.app.route("/api/update_unit_config", methods=["POST", "OPTIONS"])
        def update_unit_config():
            """更新單元配置的 API 端點"""
            if request.method == "OPTIONS":
                return ("", 204)  # CORS preflight response
            try:
                data = request.json
                # self.artnet.update_unit_config(data)
                self._save_unit_config(data)
                return {"status": "success"}, 200
            except Exception as e:
                print(f"Error updating unit config: {e}")
                return {"status": "error", "message": str(e)}, 500

    def _save_unit_config(self, data):
        try:
            config = Config(data_dict=data, config_file_name="unit_config.json")
            config.save(data)
            print("Configuration saved successfully.")
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def start_server(self):
        """啟動 Flask 伺服器"""
        if self.is_running:
            print("Server is already running")
            return

        def run_server_thread():
            print(
                f"🚀 Flask + Socket.IO server starting on http://{self.host}:{self.port}"
            )
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                use_reloader=False,
                debug=False,
                allow_unsafe_werkzeug=True,  # For development purposes
            )

        self.server_thread = threading.Thread(target=run_server_thread, daemon=True)
        self.server_thread.start()
        self.is_running = True

        # 啟動 ArtNet
        self.artnet.start()
        self.artnet2.start()

    def stop_server(self):
        """停止 Flask 伺服器"""
        if not self.is_running:
            print("Server is not running")
            return

        # 停止 ArtNet
        self.artnet.stop()
        self.artnet2.stop()

        # Flask 和 SocketIO 沒有優雅的停止方法，因為我們使用 daemon=True
        # 所以當主程序結束時，這些線程會自動終止
        self.is_running = False
        print("Server has been stopped")

    test_thread_event = threading.Event()

    def test_channel_check(self):
        """依序點亮所有通道以檢查 ArtNet 設置"""
        if not self.is_running:
            print("Server must be running to test channels")
            return
        off = 1
        count = 0

        def test_thread():
            nonlocal count, off
            matrix = [0] * 576
            try:
                while not self.test_thread_event.is_set():
                    for i in range(512):

                        matrix[i] = 255 * off  # 點亮當前通道
                        self.socketio.emit("dmx_data", {"value": matrix})
                        self.artnet.set_packet(matrix)
                        count += 1
                        sleep(0.05)  # 每個通道點亮後等待一段時間
                    off = 1 - off  # 切換點亮狀態
            except Exception as e:
                print(f"Error in test thread: {e}")

        test_thread_instance = threading.Thread(target=test_thread, daemon=True)
        test_thread_instance.start()

        return test_thread_instance


# flask_app = TSOOFlaskApp(
#     artnet_host="2.0.0.100",
#     artnet_universe=0,
#     artnet_channels=512,
#     block_order=[[1, 4, 7, 10, 13, 16], [2, 5, 8, 11, 14, 17], [3, 6, 9, 12, 15, 18]],
#     block_shape=(8, 6),
# )

# flask_app.start_server()
# test_thread = flask_app.test_channel_check()


# import sys

# try:
#     while True:
#         sleep(1)
# except KeyboardInterrupt:
#     print("Interrupted by user")
#     flask_app.test_thread_event.set()
#     test_thread.join(timeout=1)
#     flask_app.stop_server()
#     sys.exit(0)
