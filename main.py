from person_tracker import PersonTracker
from param_processer import TSOOParamProcesser
from natural_tracker import NaturalTracker
import logging
from time import sleep
from flask_app import TSOOFlaskApp
import time
import threading
import multiprocessing as mp
from multiprocessing import Queue, Process


# 将 effect_thread 函数移到 main() 外部，并接收所需的参数
def effect_process(
    artnet_host,
    artnet_universe,
    artnet_channels,
    block_shape,
    block_order,
    people_queue,
    update_signal_queue,
):
    # 创建自己的对象实例，而不是使用主进程的实例
    flask_app = TSOOFlaskApp(
        host="127.0.0.1",
        port=5000,
        artnet_host=artnet_host,
        artnet_universe=artnet_universe,
        artnet_channels=artnet_channels,
        block_shape=block_shape,
        block_order=block_order,
    )
    param_processor = TSOOParamProcesser()
    natural_tracker = NaturalTracker()

    # 初始化参数
    param_processor.target_tsoo_param["area_people_count"] = [0, 0, 0, 0]

    # 设置回调函数，当可以更新参数时通知主进程
    def on_fade_out_done():
        try:
            if not update_signal_queue.full():
                update_signal_queue.put_nowait(True)
                print("Signal sent: Parameter update allowed")
        except Exception as e:
            print(f"Error sending update signal: {e}")

    # 设置回调函数
    param_processor.on_basic_fade_out_done = on_fade_out_done

    # 启动服务
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

    try:
        while True:  # 主循環

            # 每秒更新一次數據

            # 仅在可以更新参数时更新人员数据
            if True:
                # 检查队列中是否有新的人员追踪数据
                try:
                    if not people_queue.empty():
                        # 非阻塞方式获取数据

                        people_counts = people_queue.get_nowait()
                        print(f"Effect process - Person in area: {people_counts}")
                        param_processor.target_tsoo_param["area_people_count"] = (
                            people_counts
                        )
                        natural_data = natural_tracker.update()
                        print(f"Natural data: {natural_data}")
                        if natural_data[0] == 0:
                            natural_data[0] = 1
                        param_processor.update_wind_speed(natural_data[0])
                        param_processor.update_wind_angle(natural_data[2])

                        param_processor.caculate_param()

                        print(f"Effect process received people counts: {people_counts}")

                        # 标记参数已更新
                        param_processor.params_updated = True
                except Exception as e:
                    print(f"Error getting data from queue: {e}")

            # effect
            if time.time() - last_matrix_update_time > 0.03:
                try:
                    basic = param_processor.shifting_basic(
                        16,
                        8,
                        scale=7,
                        z=time_val,
                        gradient_vector=(
                            param_processor.target_tsoo_param["effect_vector"][0] * 5,
                            param_processor.target_tsoo_param["effect_vector"][1] * 5,
                        ),
                    )
                    matrix = basic.flatten().tolist()

                    time_val += 0.002

                    # natural_data = natural_tracker.update()
                    # print(f"Natural data: {natural_data}")
                    # if natural_data[0] == 0:
                    #     natural_data[0] = 1
                    # param_processor.update_wind_speed(natural_data[0])
                    # param_processor.update_wind_angle(natural_data[2])

                    # param_processor.caculate_param()
                    flask_app.socketio.emit("dmx_data", {"value": matrix})
                    flask_app.socketio.emit(
                        "tsoo_param", param_processor.interper_tsoo_param
                    )
                    # count += 1

                    flask_app.artnet.set_packet(matrix, 0.5)
                except Exception as e:
                    print(f"Error in effect : {e}")
                finally:
                    last_matrix_update_time = time.time()
                    # 避免进程消耗过多 CPU
                    time.sleep(0.01)

    except KeyboardInterrupt:
        print("Effect thread interrupted")
    finally:
        flask_app.stop_server()
        print("Effect thread shutting down ...")


def main():
    # 主进程的设置
    # flask_app = TSOOFlaskApp(
    #     host="127.0.0.1",
    #     port=5000,
    #     artnet_host="2.56.31.102",
    #     artnet_universe=0,
    #     artnet_channels=128,
    #     block_shape=(8, 4),
    #     block_order=[[1, 3], [2, 4]],
    # )
    # param_processor = TSOOParamProcesser()

    # 创建一个队列用于在进程之间传递人员追踪数据
    people_queue = Queue(maxsize=5)  # 限制队列大小，防止内存溢出

    # 创建一个新的队列，用于接收参数可以更新的信号
    update_signal_queue = Queue(maxsize=1)

    person_tracker = PersonTracker(
        video_source="people_top.mp4",  # or 0 for webcam
        width=1280,
        height=720,
    )
    # 使用新方法，在背景執行 tracking 和 display
    person_tracker.start_all_in_background()

    sleep(2)  # 等待追蹤器初始化
    # natural_tracker = NaturalTracker()

    # 获取必要的参数以启动效果进程
    artnet_host = "2.56.31.102"
    # artnet_host = "127.0.0.1"；
    artnet_universe = 0
    artnet_channels = 128
    block_shape = (8, 4)
    block_order = [[1, 3], [2, 4]]

    # 创建并启动效果进程
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
        ),
    )
    effect_thread_instance.start()

    # 输出主进程中的线程
    for thread in threading.enumerate():
        print(thread.name)

    try:
        # 主进程监视用户输入和更新人员追踪数据
        last_people_data_update = 0
        can_update_params = False
        while True:
            current_time = time.time()

            # 检查是否收到可以更新参数的信号
            try:
                if not update_signal_queue.empty():
                    can_update_params = update_signal_queue.get_nowait()
                    print("Received signal: Parameter update allowed")
            except Exception as e:
                print(f"Error checking update signal: {e}")

            # 每5秒更新一次人员追踪数据，但只有在收到信号时才发送到队列
            if current_time - last_people_data_update >= 0.1:
                last_people_data_update = current_time

                # 获取最新的人员追踪数据
                people_counts = person_tracker.inside_area_counts
                # print(f"Main process - Person in area: {people_counts}")

                # 仅在允许更新参数时才将数据发送到队列
                if can_update_params:
                    # 尝试将数据放入队列，但不阻塞
                    try:
                        if not people_queue.full():
                            people_queue.put_nowait(people_counts)
                            print("Person data sent to effect process")
                            can_update_params = (
                                False  # 重置标志，直到收到下一个更新信号
                            )
                        else:
                            # 队列已满，可以选择清空队列或忽略这次更新
                            # 这里选择清空队列后再放入新数据
                            try:
                                while not people_queue.empty():
                                    people_queue.get_nowait()
                                people_queue.put_nowait(people_counts)
                                print(
                                    "Person data sent to effect process (after queue clear)"
                                )
                                can_update_params = (
                                    False  # 重置标志，直到收到下一个更新信号
                                )
                            except:
                                pass
                    except Exception as e:
                        print(f"Error putting data to queue: {e}")

            # 减少 CPU 使用率
            time.sleep(0.1)  # 更小的睡眠时间，以便更频繁地检查

    except KeyboardInterrupt:
        print("Main program interrupted")
    finally:
        person_tracker.stop()
        # 终止效果进程
        effect_thread_instance.terminate()
        effect_thread_instance.join()
        print("Shutting down ...")


if __name__ == "__main__":
    main()
