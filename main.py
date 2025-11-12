from person_tracker import PersonTracker
from mock_person_tracker import MockPersonTracker
from rtsp_person_tracker import RTSPPersonTracker

# from mock_person_tracker import MockPersonTracker
from param_processer import TSOOParamProcesser
from natural_tracker import NaturalTracker
from time import sleep
from flask_app import TSOOFlaskApp
import time
import threading
from config import Config

from multiprocessing import Queue, Process
from config import Config
from osc_reciver import OSCReceiver
from osc_sender import OSCSender
import numpy as np

from param_processer import ease_in_out_circ

from mixer_sound_scheduler import MixerSoundScheduler
import traceback
import asyncio



# 將 effect_thread 函數移到 main() 外部，並接收所需的參數
def effect_process(
    artnet_host,
    artnet_universe,
    artnet_channels,
    block_shape,
    block_order,
    people_queue,
    update_signal_queue,
    osc_config,
    general_config,
    # update_person_track_data=lambda data: None,
):
    print("block_order:", block_order)
    # 創建自己的對象實例，而不是使用主進程的實例
    flask_app = TSOOFlaskApp(
        host="127.0.0.1",
        port=5000,
        artnet_host=artnet_host,
        artnet_universe=artnet_universe,
        artnet_channels=artnet_channels,
        block_shape=block_shape,
        block_order=block_order,
    )
    osc_sender = OSCSender(
        address=osc_config["address"], port=osc_config["port"]
    )
    osc_receiver = OSCReceiver(ip="0.0.0.0", port=57121)
    osc_receiver.start()
    param_processor = TSOOParamProcesser(interpolation_speed=0.005)
    param_processor.wind_speed_factor = general_config.get("wind_speed_factor", 10)
    natural_tracker = NaturalTracker()
    # flask_app.update_person_track_data = update_person_track_data
    # print(f"Effect process received person track data: {data}")

    # 初始化參數
    param_processor.target_tsoo_param["area_people_count"] = [0, 0, 0, 0]

    # 設置回調函數，當可以更新參數時通知主進程
    def on_fade_out_done():
        try:
            if not update_signal_queue.full():
                update_signal_queue.put_nowait(True)
                print("Signal sent: Parameter update allowed")
        except Exception as e:
            print(f"Error sending update signal: {e}")

    # 設置回調函數
    param_processor.on_basic_fade_out_done = on_fade_out_done

    # 啟動服務
    flask_app.start_server()

    # effect
    matrix = [0] * artnet_channels

    time_val = 0
    off = 1

    print("🚀 Starting test sequence...")
    # flask_app.artnet.set_packet(matrix)  # 設定初始數據包
    flask_app.socketio.emit("dmx_data", {"value": matrix})  # 初始發送
    last_pluck_trigger_time = 0
    last_matrix_update_time = 0
    last_glitch_update_time = 0
    last_pos_update_time = 0
    last_param_update_time = 0

    try:
        while True:  # 主循環
            try:
                # print(f"Rain : {intensity}")
                if not osc_receiver.received.empty():
                    address, args, trigger = osc_receiver.received.get_nowait()
                    intensity = trigger

                    intensity = ease_in_out_circ(
                        min(max((trigger - 0.004) / 0.2, 0), 1)
                    )
                    param_processor.target_tsoo_param["rain_intensity"] = intensity

            except Exception as e:
                print(f"Error getting data from OSC receiver: {e}")
            try:
                if not people_queue.empty():
                    people_data = people_queue.get_nowait()
                    people_counts = people_data["counts"]
                    # people_counts = [6,0,0,0]
                    people_pos = people_data["pos"]
                    # print(f"Effect process - Person in area: {people_counts}")
                    param_processor.target_tsoo_param["area_people_count"] = (
                        people_counts
                    )
                    param_processor.target_tsoo_param["person_pos"] = people_pos

                    # 不做 caculate_param()，只更新人數
            except Exception as e:
                print(f"Error getting data from queue: {e}")
            # 2. 只在允許參數更新時才更新 natural_data 與計算參數
            try:
                if not update_signal_queue.empty():
                    update_signal_queue.get_nowait()  # 清掉信號
                    natural_data = natural_tracker.update()
                    print(f"Natural data: {natural_data}")
                    if natural_data[0] == 0:
                        natural_data[0] = 1
                    param_processor.update_wind_speed(natural_data[0])
                    param_processor.update_wind_angle(natural_data[2])
                    param_processor.caculate_param()
                    print(
                        "Effect process: parameters recalculated (natural_data updated)"
                    )
                    param_processor.params_updated = True
            except Exception as e:
                print(f"Error updating natural data: {e}")
            if time.time() - last_glitch_update_time > 0.04:
                try:
                    if param_processor.glitch_frame is not None:

                        glitchA = flask_app.artnet.packet_remap(param_processor.glitch_frame)
                        glitchB = flask_app.artnet2.packet_remap(param_processor.glitch_frame)
                        osc_sender.send_message("/whyixd/light/glitchA", glitchA)
                        osc_sender.send_message("/whyixd/light/glitchB", glitchB)
                        
                except:
                    pass
                finally:
                    last_glitch_update_time = time.time()
            if time.time() - last_pos_update_time > 0.1:
                try:
                    osc_sender.send_positions(
                        param_processor.target_tsoo_param["person_pos"]
                    )
                except Exception as e:
                    print(f"Error sending position update: {e}")
                finally:
                    last_pos_update_time = time.time()
            # effect
            if time.time() - last_matrix_update_time > 0.03:
                try:
                    # 使用新的組合效果方法，避免梯度遮罩影響雨滴效果
                    matrix_data = param_processor.get_combined_effects(
                        8 * 8,
                        4 * 5,
                        scale=7,
                        z=time_val,
                        gradient_vector=(
                            param_processor.target_tsoo_param["effect_vector"][0] * 5,
                            param_processor.target_tsoo_param["effect_vector"][1] * 5,
                        ),
                    )
                    # basic, mask, rain = param_processor.get_effects_separately(
                    #     16,
                    #     8,
                    #     scale=7,
                    #     z=time_val,
                    #     gradient_vector=(
                    #         param_processor.target_tsoo_param["effect_vector"][0] * 5,
                    #         param_processor.target_tsoo_param["effect_vector"][1] * 5,
                    #     ),
                    # )
                    # matrix_data = basic
                    # print(matrix_data.shape)
                    matrix = matrix_data.flatten().tolist()

                    time_val += 0.002

                    flask_app.socketio.emit("dmx_data", {"value": matrix})
                    flask_app.socketio.emit(
                        "tsoo_param", param_processor.interper_tsoo_param
                    )
                    if time.time() - last_param_update_time > 1:
                        flask_app.socketio.emit(
                            "tsoo_param_target", param_processor.target_tsoo_param
                        )
                        last_param_update_time = time.time()
                        osc_sender.send_parameters(param_processor)
                    # osc_sender.send_message("/whyixd/light/dmx", matrix)

                    # count += 1

                    # flask_app.artnet.set_packet(
                    #     matrix, general_config.get("light_intensity", 2)
                    # )
                    
                    matrixA =flask_app.artnet.packet_remap(matrix)
                    matrixB =flask_app.artnet2.packet_remap(matrix)
                    matrix_all =matrixA+matrixB

                    osc_sender.send_message("/whyixd/light/dmx", matrix_all)
                    flask_app.artnet.set_packet(matrix)
                    flask_app.artnet2.set_packet(matrix)
                except Exception as e:
                    print(f"Error in effect : {traceback.format_exc()}")
                finally:
                    last_matrix_update_time = time.time()
                    time.sleep(0.001)

    except KeyboardInterrupt:
        print("Effect thread interrupted")
    finally:
        flask_app.stop_server()
        osc_receiver.stop()
        print("Effect thread shutting down ...")


def main():
    osc_config = {"address": "127.0.0.1", "port": 5005}
    osc_config_instance = Config(osc_config, "config/osc_config.json")
    osc_config = osc_config_instance.load()
    
    def on_open():
        print("Mixer opened")
    def on_close():
        print("Mixer closed")

    general_config = {
        "artnet_target": "2.0.0.100",
        "light_intensity": 1,
        "wind_speed_factor": 10,  # 默認風速因子
        "mixer_activate_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],  # 預設啟動時間
        "mixer_osc_ip": "127.0.0.1"  # Mixer OSC IP
    }
    general_config_instance = Config(general_config, "config/general_config.json")
    general_config = general_config_instance.load()
    
    # 創建並設置 MixerSoundScheduler
    mixer_scheduler = MixerSoundScheduler(
        osc_ip=general_config.get("mixer_osc_ip", osc_config["address"]),
        activate_hours=general_config.get("mixer_activate_hours", [9,18])
    )

    # 創建一個隊列用於在進程之間傳遞人員追蹤數據
    people_queue = Queue(maxsize=5)  # 限制隊列大小，防止內存溢出

    # 創建一個新的隊列，用於接收參數可以更新的信號
    update_signal_queue = Queue(maxsize=1)

    person_tracker = MockPersonTracker(
        video_source="people_top.mp4",  # or 0 for webcam
        width=640,
        height=360,
    )
    # person_tracker = PersonTracker(
    #     video_source="people_top.mp4",  # or 0 for webcam
    #     width=640,
    #     height=360,
    # )
    ffmpeg_opts = {
        "rtsp_transport": "tcp",
        "fflags": "nobuffer",
        "flags": "low_delay",
        "max_delay": "500000",
        "stimeout": "5000000",
        "reorder_queue_size": "0",
        "probesize": "320000",
        "analyzeduration": "0",
    }
    # person_tracker = RTSPPersonTracker(
    #     sources={
    #         # "cam A (top)": "rtsp://2.0.0.79:554/user=admin_password=tlJwpbo6_channel=1_stream=0&onvif=0.sdp?real_st",
    #         "cam B (desk)": "rtsp://2.0.0.78:554/user=admin_password=tlJwpbo6_channel=1_stream=0&onvif=0.sdp?real_st",
    #         # "cam C (main)": "rtsp://2.0.0.77:554/user=admin_password=tlJwpbo6_channel=0_stream=0&onvif=0.sdp?real_st",
    #     },
    #     ffmpeg_options=ffmpeg_opts,
    # )
    # 使用新方法，在背景執行 tracking 和 display
    person_tracker.start_all_in_background()

    # person_tracker.start()

    # sleep(10)  # 等待追蹤器初始化
    # natural_tracker = NaturalTracker()

    # 獲取必要的參數以啟動效果進程
    # artnet_host = "2.56.31.102"
    artnet_host = general_config.get("artnet_target", "2.0.0.100")
    # artnet_host = "127.0.0.1"；
    artnet_universe = 0
    artnet_channels = 512
    block_shape = (8, 4)
    block_order = [[1, 3], [2, 4]]
    person_data = [0] * 4

    # 創建並啟動效果進程
    effect_thread_instance = Process(
        target=effect_process,
        args=(
            artnet_host,
            artnet_universe,
            artnet_channels,
            block_shape,
            block_order,
            people_queue,
            update_signal_queue,
            osc_config,
            general_config,  # 默認值為1
            # update_person_track_data,
        ),
    )
    effect_thread_instance.start()

    # 在背景線程中啟動 MixerSoundScheduler
    mixer_thread = threading.Thread(target=mixer_scheduler.run_blocking)
    mixer_thread.daemon = True
    mixer_thread.start()
    print("MixerSoundScheduler started in background")

    

    try:
        # 主進程監視用戶輸入和更新人員追蹤數據
        last_people_data_update = 0
        while True:
            current_time = time.time()

            # 每0.1秒更新一次人員追蹤數據
            if current_time - last_people_data_update >= 0.05:
                last_people_data_update = current_time

                # 獲取最新的人員追蹤數據
                people_counts = person_tracker.inside_area_counts
                person_pos = person_tracker.person_pos
                # people_counts = person_data

                # 嘗試將數據放入隊列，但不阻塞
                try:
                    if not people_queue.full():
                        people_queue.put_nowait(
                            {"counts": people_counts, "pos": person_pos}
                        )
                        # print("Person data sent to effect process")
                    else:
                        # 隊列已滿，清空後再放入新數據
                        try:
                            while not people_queue.empty():
                                people_queue.get_nowait()
                            people_queue.put_nowait(
                                {"counts": people_counts, "pos": person_pos}
                            )
                            print(
                                "Person data sent to effect process (after queue clear)"
                            )
                        except:
                            pass
                except Exception as e:
                    print(f"Error putting data to queue: {e}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Main program interrupted")
    finally:
        person_tracker.stop()
        mixer_scheduler.stop()
        print("Stopping mixer scheduler...")
        # 終止效果進程
        # effect_thread_instance.terminate()
        effect_thread_instance.join()
        print("Shutting down ...")


if __name__ == "__main__":
    main()
