from person_tracker import PersonTracker
from mock_person_tracker import MockPersonTracker

# from mock_person_tracker import MockPersonTracker
from param_processer import TSOOParamProcesser
from natural_tracker import NaturalTracker
from time import sleep
from flask_app import TSOOFlaskApp
import time
import threading
from config import Config

from multiprocessing import Queue, Process
from pythonosc import udp_client
from config import Config


def send_osc_message(
    client: udp_client.SimpleUDPClient, tsoo_param: TSOOParamProcesser
):
    param = tsoo_param.target_tsoo_param
    inter_param = tsoo_param.interper_tsoo_param
    # -------------------composite--------------------#
    client.send_message(
        "/whyixd/composite/weight",
        param["people_natrual_weight"],
    )
    client.send_message(
        "/whyixd/composite/level",
        param["people_natrual_weight_level"],
    )
    client.send_message(
        "/whyixd/composite/threshold",
        param["people_natrual_weight_level_threshold"],
    )
    client.send_message(
        "/whyixd/composite/interper/weight", inter_param["people_natrual_weight"]
    )

    # ---------------------people---------------------#
    client.send_message("/whyixd/people/counts", param["area_people_count"])
    client.send_message(
        "/whyixd/people/vector",
        param["people_vector"],
    )
    client.send_message("/whyixd/people/interper/vector", inter_param["people_vector"])
    # ---------------------light----------------------#
    client.send_message(
        "/whyixd/light/vector",
        param["effect_vector"],
    )
    client.send_message("/whyixd/light/interper/vector", inter_param["effect_vector"])
    # ---------------------wind-----------------------#
    client.send_message("/whyixd/wind/speed", param["wind_speed"])
    # client.send_message("/whyixd/wind/speed/normalized", param["wind_speed_normalized"])
    client.send_message("/whyixd/wind/angle", param["wind_angle"])
    client.send_message(
        "/whyixd/wind/vector",
        param["wind_vector"],
    )
    client.send_message("/whyixd/wind/interper/speed", inter_param["wind_speed"])
    # client.send_message(
    #     "/whyixd/wind/interper/speed/normalized", inter_param["wind_speed_normalized"]
    # )
    client.send_message("/whyixd/wind/interper/angle", inter_param["wind_angle"])
    client.send_message("/whyixd/wind/interper/vector", inter_param["wind_vector"])
    # ---------------------


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
):
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
    osc_client = udp_client.SimpleUDPClient(
        address=osc_config["address"], port=osc_config["port"]
    )
    param_processor = TSOOParamProcesser(interpolation_speed=0.005)
    param_processor.wind_speed_factor = general_config.get("wind_speed_factor", 10)
    natural_tracker = NaturalTracker()

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
    matrix = [0] * 128

    time_val = 0
    off = 1

    print("🚀 Starting test sequence...")
    # flask_app.artnet.set_packet(matrix)  # 設定初始數據包
    flask_app.socketio.emit("dmx_data", {"value": matrix})  # 初始發送
    last_data_update_time = 0
    last_matrix_update_time = 0
    person_conut_cache =[0,0,0,0]
    try:
        while True:  # 主循環
            # 1. 即時更新 people_counts
            try:
                if not people_queue.empty():
                    people_counts = people_queue.get_nowait()
                    print(f"Effect process - Person in area: {people_counts}")
                    param_processor.target_tsoo_param["area_people_count"] = people_counts
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
                    print("Effect process: parameters recalculated (natural_data updated)")
                    param_processor.params_updated = True
            except Exception as e:
                print(f"Error updating natural data: {e}")

            # effect
            if time.time() - last_matrix_update_time > 0.03:
                try:
                    # 使用新的組合效果方法，避免梯度遮罩影響雨滴效果
                    # matrix_data = param_processor.get_combined_effects(
                    #     16,
                    #     8,
                    #     scale=7,
                    #     z=time_val,
                    #     gradient_vector=(
                    #         param_processor.target_tsoo_param["effect_vector"][0] * 5,
                    #         param_processor.target_tsoo_param["effect_vector"][1] * 5,
                    #     ),
                    # )
                    basic, mask, rain = param_processor.get_effects_separately(
                        16,
                        8,
                        scale=7,
                        z=time_val,
                        gradient_vector=(
                            param_processor.target_tsoo_param["effect_vector"][0] * 5,
                            param_processor.target_tsoo_param["effect_vector"][1] * 5,
                        ),
                    )
                    matrix_data = basic
                    matrix = matrix_data.flatten().tolist()

                    time_val += 0.002

                    flask_app.socketio.emit("dmx_data", {"value": matrix})
                    flask_app.socketio.emit(
                        "tsoo_param", param_processor.interper_tsoo_param
                    )
                    send_osc_message(osc_client, param_processor)
                    osc_client.send_message("/whyixd/light/dmx", matrix)
                    # count += 1

                    flask_app.artnet.set_packet(
                        matrix, general_config.get("light_intensity", 2)
                    )
                except Exception as e:
                    print(f"Error in effect : {e}")
                finally:
                    last_matrix_update_time = time.time()
                    time.sleep(0.01)

    except KeyboardInterrupt:
        print("Effect thread interrupted")
    finally:
        flask_app.stop_server()
        print("Effect thread shutting down ...")


def main():
    osc_config = {"address": "127.0.0.1", "port": 5005}
    osc_config_instance = Config(osc_config, "osc_config.json")
    osc_config = osc_config_instance.load()

    general_config = {
        "artnet_target": "2.0.0.105",
        "light_intensity": 1,
        "wind_speed_factor": 10,  # 默認風速因子
    }
    general_config_instance = Config(general_config, "general_config.json")
    general_config = general_config_instance.load()
    # 創建一個隊列用於在進程之間傳遞人員追蹤數據
    people_queue = Queue(maxsize=5)  # 限制隊列大小，防止內存溢出

    # 創建一個新的隊列，用於接收參數可以更新的信號
    update_signal_queue = Queue(maxsize=1)

    # person_tracker = MockPersonTracker(
    #     video_source="people_top.mp4",  # or 0 for webcam
    #     width=640,
    #     height=360,
    # )
    person_tracker = PersonTracker(
        video_source="people_top.mp4",  # or 0 for webcam
        width=640,
        height=360,
    )
    # 使用新方法，在背景執行 tracking 和 display
    person_tracker.start_all_in_background()

    sleep(10)  # 等待追蹤器初始化
    # natural_tracker = NaturalTracker()

    # 獲取必要的參數以啟動效果進程
    # artnet_host = "2.56.31.102"
    artnet_host = general_config.get("artnet_target", "2.0.0.100")
    # artnet_host = "127.0.0.1"；
    artnet_universe = 0
    artnet_channels = 128
    block_shape = (8, 4)
    block_order = [[1, 3], [2, 4]]

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
        ),
    )
    effect_thread_instance.start()

    # 輸出主進程中的線程
    for thread in threading.enumerate():
        print(thread.name)

    try:
        # 主進程監視用戶輸入和更新人員追蹤數據
        last_people_data_update = 0
        while True:
            current_time = time.time()

            # 每1秒更新一次人員追蹤數據
            if current_time - last_people_data_update >= 0.5:
                last_people_data_update = current_time

                # 獲取最新的人員追蹤數據
                people_counts = person_tracker.inside_area_counts

                # 嘗試將數據放入隊列，但不阻塞
                try:
                    if not people_queue.full():
                        people_queue.put_nowait(people_counts)
                        print("Person data sent to effect process")
                    else:
                        # 隊列已滿，清空後再放入新數據
                        try:
                            while not people_queue.empty():
                                people_queue.get_nowait()
                            people_queue.put_nowait(people_counts)
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
        # 終止效果進程
        # effect_thread_instance.terminate()
        effect_thread_instance.join()
        print("Shutting down ...")


if __name__ == "__main__":
    main()
