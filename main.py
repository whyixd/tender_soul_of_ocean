from person_tracker import PersonTracker
from param_processer import TSOOParamProcesser
from natural_tracker import NaturalTracker
import logging
from time import sleep


def main():
    person_tracker = PersonTracker(
        video_source="people_top.mp4",  # or 0 for webcam
        width=1280,
        height=720,
    )
    # 使用新方法，在背景執行 tracking 和 display
    person_tracker.start_all_in_background()
    natural_tracker = NaturalTracker()

    try:
        while True:
            print(f"Person in area:{person_tracker.inside_area_counts}")
            print(f"Natural data: {natural_tracker.update()}")
            sleep(1)
    except KeyboardInterrupt:
        print("Main program interrupted")
    finally:
        person_tracker.stop()
        print("Shutting down ...")


if __name__ == "__main__":
    main()
