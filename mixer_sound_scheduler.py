import asyncio
import time
import osc_sender

FADE_IN_OSC_ADDRESS = "/audio/mixer/on"
FADE_OUT_OSC_ADDRESS = "/audio/mixer/on"


class MixerSoundScheduler:
    def __init__(self, osc_ip="127.0.0.1", activate_hours=[]):
        self.activate_hours = activate_hours
        self.on_activate = None
        self.on_open = None
        self.on_close = None
        self.last_activation_hour = -1
        self.running = False
        self.open_hour = min(self.activate_hours)
        self.close_hour = max(self.activate_hours)
        print(f"open_hour: {self.open_hour}, close_hour: {self.close_hour}")
        self.update_task = None

        self.osc_sender = osc_sender.OSCSender(osc_ip, 7777)

        

    def send_on(self):
        self.osc_sender.send_message(FADE_IN_OSC_ADDRESS, 1)

    def send_off(self):
        self.osc_sender.send_message(FADE_OUT_OSC_ADDRESS, 0)

    async def start(self):
        self.running = True
        self.update_task = asyncio.create_task(self.check_loop())
        # 等待任务完成（持续运行直到被停止）
        try:
            await self.update_task
        except asyncio.CancelledError:
            print("MixerSoundScheduler task was cancelled")

    def stop(self):
        self.running = False
        if self.update_task:
            self.update_task.cancel()

    def run_blocking(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            print("MixerSoundScheduler interrupted by user")
        except Exception as e:
            print(f"MixerSoundScheduler error: {e}")
        finally:
            self.stop()
            loop.close()
            print("MixerSoundScheduler stopped")

    def check_activation(self):
        current_hour = time.localtime().tm_hour
        if (
            current_hour in self.activate_hours
            and current_hour != self.last_activation_hour
        ):
            self.last_activation_hour = current_hour
            return True
        return False

    async def check_loop(self):
        while self.running:
            if self.check_activation():
                print(f"Mixer activation at hour {self.last_activation_hour}")
                if self.last_activation_hour == self.open_hour:
                    print("Opening mixer...")
                    self.osc_sender.send_message(FADE_IN_OSC_ADDRESS, 1)
                    if self.on_open:
                         self.on_open()
                if self.last_activation_hour == self.close_hour:
                    print("Closing mixer...")
                    self.osc_sender.send_message(FADE_OUT_OSC_ADDRESS, 0)
                    if self.on_close:
                         self.on_close()
            else:
                if self.on_close:
                     self.on_close()
            await asyncio.sleep(5)


async def main():
    mixer_scheduler = MixerSoundScheduler(
        osc_ip="127.0.0.1",
        activate_hours=[17, 18],
    )
    await mixer_scheduler.start()


if __name__ == "__main__":
    mixer = MixerSoundScheduler("2.0.0.17", [1, 22])
    mixer.on_open = lambda: print("Mixer opened callback")
    mixer.on_close = lambda: print("Mixer closed callback")
    mixer.run_blocking()