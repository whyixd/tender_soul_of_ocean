import math


class TSOOParamProcesser:
    def __init__(self):
        self.tsoo_param = {
            "people_natrual_weight": 0.5,
            "people_natrual_weight_level": 0,
            "people_natrual_weight_level_threshold": [0, 0.3, 0.8, 1],
            "area_people_count": [],
            "people_count_max": 30,  # set by guess
            "wind_speed": 0.0,
            "wind_speed_max": 5.0,  # get from https://www.timeanddate.com/weather/austria/linz/climate
            "wind_angle": 0.0,
            "effect_angle": 0.0,  # 風向角度
        }

    def caculate_param(self):
        total_people = sum(self.tsoo_param["area_people_count"])
        people_count_normalized = normalize(
            total_people, 0, self.tsoo_param["people_count_max"]
        )
        wind_speed_normalized = normalize(
            self.tsoo_param["wind_speed"], 0, self.tsoo_param["wind_speed_max"]
        )
        print(
            f"People count normalized: {people_count_normalized} Wind speed normalized: {wind_speed_normalized}"
        )
        self.tsoo_param["people_natrual_weight"] = combine_normalize(
            people_count_normalized, wind_speed_normalized
        )
        threshold = self.tsoo_param["people_natrual_weight_level_threshold"]
        for idx, t in enumerate(threshold):
            if self.tsoo_param["people_natrual_weight"] <= t:
                self.tsoo_param["people_natrual_weight_level"] = idx
                break
        vector = calculate_balanced_vector(
            self.tsoo_param["area_people_count"], normalize=True
        )
        print(f"計算出的向量: {vector}")
        self.tsoo_param["effect_angle"] = vector_to_angle(*vector)

    def update_area_people_count(self, area, count):
        if area < len(self.tsoo_param["area_people_count"]):
            self.tsoo_param["area_people_count"][area] = count
        else:
            self.tsoo_param["area_people_count"].append(count)

    def update_wind_speed(self, speed):
        self.tsoo_param["wind_speed"] = speed

    def update_wind_angle(self, angle):
        self.tsoo_param["wind_angle"] = angle

    def get_tsoo_param(self):
        self.caculate_param()
        return self.tsoo_param


def normalize(value, min_value, max_value):
    """Normalize a value to a range [0, 1]."""
    return (value - min_value) / (max_value - min_value)


def combine_normalize(v1, v2):
    return (v1 - v2 + 1) / 2


def calculate_balanced_vector(
    values: list[int], normalize: bool = False
) -> tuple[float, float]:
    if len(values) != 4:
        raise ValueError("輸入的列表長度必須為 4")
    v00, v01, v10, v11 = values

    # x 分量：右邊的權重總和 - 左邊的權重總和
    vx = (v01 + v11) - (v00 + v10)

    # y 分量：上面的權重總和 - 下面的權重總和
    vy = (v00 + v01) - (v10 + v11)

    if normalize:
        magnitude = math.sqrt(vx**2 + vy**2)
        if magnitude == 0:
            return (0.0, 0.0)
        return (vx / magnitude, vy / magnitude)

    return (vx, vy)


def vector_to_angle(vx, vy):
    """將向量轉換為角度"""
    if vx == 0 and vy == 0:
        return 0.0
    radians = math.atan2(vy, vx)  # 返回弧度
    degrees = math.degrees(radians)  # 轉換為角度
    return (degrees + 360) % 360  # 確保角度在 [0, 360) 範圍內


tsoo_param_processor = TSOOParamProcesser()
tsoo_param_processor.tsoo_param["area_people_count"] = [10, 10, 0, 0]
tsoo_param_processor.tsoo_param["wind_speed"] = 2.5

tsoo_param_processor.caculate_param()
print(f"Initial TSOO parameters: {tsoo_param_processor.get_tsoo_param()}")
# print(tsoo_param_processor.get_tsoo_param())
