from pythonosc.dispatcher import Dispatcher
from pythonosc import osc_server

from multiprocessing import Queue, Process
from threading import Thread


class OSCReceiver:
    def __init__(self, ip="0.0.0.0", port=57121):
        self.dispatcher = Dispatcher()
        self.server = osc_server.ThreadingOSCUDPServer((ip, port), self.dispatcher)
        self.received = Queue()

    def pluck_handler(self, address, args, trigger):
        self.received.put((address, args, trigger))
        # print(f"Received OSC message: {address} {args} {trigger}")

    def ZIGSIM_test_handler(self, address, args, trigger):
        # print("ZIGSIM test received")
        self.received.put((address, args, trigger))
        # print(f"Received OSC message: {address} {args} {trigger}")

    def start(self):
        print(f"Starting OSC server on {self.server.server_address}")
        self.dispatcher.map("/pluck/env", self.pluck_handler, "pluck")
        self.dispatcher.map(
            "/ZIGSIM/miroc/touchcount", self.ZIGSIM_test_handler, "ZIGSIM"
        )
        self.received_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.received_thread.start()

    def stop(self):

        self.server.shutdown()
        print("OSC server stopped")


# osc_receiver = OSCReceiver()

# osc_receiver.start()
