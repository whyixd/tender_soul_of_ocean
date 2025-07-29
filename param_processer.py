import math
import numpy as np
from noise import snoise2, snoise3


class TSOOParamProcesser:
    def __init__(self, interpolation_speed=0.05):
        self.target_tsoo_param = {
            "people_natrual_weight": 0.5,
            "people_natrual_weight_level": 0,
            "people_natrual_weight_level_threshold": [0, 0.3, 0.8, 1],
            "area_people_count": [],
            "people_count_max": 30,  # set by guess
            "wind_speed": 0.0,
            "wind_speed_max": 5.0,  # get from https://www.timeanddate.com/weather/austria/linz/climate
            "wind_angle": 0.0,
            "wind_vector": (0.0, 0.0),  # 風向向量
            "effect_angle": 0.0,  # 風向角度
            "effect_vector": (0.0, 0.0),  # 風向向量
        }
        self.previous_tsoo_param = self.target_tsoo_param.copy()
        self.interper_tsoo_param = self.target_tsoo_param.copy()

        # 插值速度控制（值越大，过渡越快）
        self.interpolation_speed = interpolation_speed

    def caculate_param(self):
        # 保存当前参数为上一次参数
        self.previous_tsoo_param = self.target_tsoo_param.copy()

        total_people = sum(self.target_tsoo_param["area_people_count"])
        people_count_normalized = normalize(
            total_people, 0, self.target_tsoo_param["people_count_max"]
        )
        wind_speed_normalized = normalize(
            self.target_tsoo_param["wind_speed"],
            0,
            self.target_tsoo_param["wind_speed_max"],
        )
        # print(
        #     f"People count normalized: {people_count_normalized} Wind speed normalized: {wind_speed_normalized}"
        # )
        self.target_tsoo_param["people_natrual_weight"] = round(
            combine_normalize(people_count_normalized, wind_speed_normalized), 2
        )
        threshold = self.target_tsoo_param["people_natrual_weight_level_threshold"]
        for idx, t in enumerate(threshold):
            if self.target_tsoo_param["people_natrual_weight"] <= t:
                self.target_tsoo_param["people_natrual_weight_level"] = idx
                break
        people_vector = calculate_balanced_vector(
            self.target_tsoo_param["area_people_count"], normalize=True
        )
        people_vector = (round(people_vector[0], 2), round(people_vector[1], 2))
        # print(f"People vector: {people_vector}")
        # 將風向角度轉換為和 people_vector 相同的坐標系（0度為上方，90度為右方）
        # wind_vector = angle_to_vector_new_coordinate(self.tsoo_param["wind_angle"])
        wind_vector = angle_to_vector(self.target_tsoo_param["wind_angle"])
        self.target_tsoo_param["wind_vector"] = (
            round(wind_vector[0], 2),
            round(wind_vector[1], 2),
        )
        vector_combined = normalize_vector(
            (people_vector[0] + wind_vector[0], people_vector[1] + wind_vector[1])
        )
        self.target_tsoo_param["effect_vector"] = (
            round(vector_combined[0], 2),
            round(vector_combined[1], 2),
        )

    def update_area_people_count(self, area, count):
        if area < len(self.target_tsoo_param["area_people_count"]):
            self.target_tsoo_param["area_people_count"][area] = count
        else:
            self.target_tsoo_param["area_people_count"].append(count)

    def update_wind_speed(self, speed):
        self.target_tsoo_param["wind_speed"] = speed

    def update_wind_angle(self, angle):
        self.target_tsoo_param["wind_angle"] = angle

    def get_tsoo_param(self):
        self.caculate_param()
        return self.target_tsoo_param

    def calculate_interpolation(self):
        """计算从previous到target的插值"""
        # 对每个数值类型的参数进行插值
        for key, target_value in self.target_tsoo_param.items():
            if key in self.interper_tsoo_param:
                prev_value = self.interper_tsoo_param[key]

                # 根据不同类型进行不同的插值
                if isinstance(target_value, (int, float)) and isinstance(
                    prev_value, (int, float)
                ):
                    if key == "people_natrual_weight_level":
                        continue
                    # 数值类型插值
                    self.interper_tsoo_param[key] = self._interpolate_value(
                        prev_value, target_value
                    )
                    if target_value - self.interper_tsoo_param[key] < 0.01:
                        self.interper_tsoo_param[key] = target_value
                elif (
                    isinstance(target_value, tuple)
                    and isinstance(prev_value, tuple)
                    and len(target_value) == 2
                    and len(prev_value) == 2
                ):
                    # 二维向量插值
                    x = self._interpolate_value(prev_value[0], target_value[0])
                    y = self._interpolate_value(prev_value[1], target_value[1])
                    self.interper_tsoo_param[key] = (x, y)
                    if target_value[0] - x < 0.01:
                        x = target_value[0]
                    if target_value[1] - y < 0.01:
                        y = target_value[1]

                else:
                    # 其他类型直接使用目标值
                    self.interper_tsoo_param[key] = target_value
            else:
                # 如果previous中没有该键，直接使用目标值
                self.interper_tsoo_param[key] = target_value

        return self.interper_tsoo_param

    def _interpolate_value(self, prev, target):
        """计算单个数值的插值"""
        if prev == target:
            return target

        # 线性插值: current = current + (target - current) * speed
        return prev + (target - prev) * self.interpolation_speed

    def get_interpolated_param(self):
        """获取当前插值后的参数"""
        self.calculate_interpolation()
        return self.interper_tsoo_param

    def __init__(self, interpolation_speed=0.05):
        self.target_tsoo_param = {
            "people_natrual_weight": 0.5,
            "people_natrual_weight_level": 0,
            "people_natrual_weight_level_threshold": [0, 0.3, 0.8, 1],
            "area_people_count": [],
            "people_count_max": 30,  # set by guess
            "wind_speed": 0.0,
            "wind_speed_max": 5.0,  # get from https://www.timeanddate.com/weather/austria/linz/climate
            "wind_angle": 0.0,
            "wind_vector": (0.0, 0.0),  # 風向向量
            "effect_angle": 0.0,  # 風向角度
            "effect_vector": (0.0, 0.0),  # 風向向量
        }
        self.previous_tsoo_param = self.target_tsoo_param.copy()
        self.interper_tsoo_param = self.target_tsoo_param.copy()

        # 插值速度控制（值越大，过渡越快）
        self.interpolation_speed = interpolation_speed

        # 儲存之前的梯度遮罩，用於在梯度向量變化時保留之前的效果
        self.previous_gradient_mask = None
        # 記憶因子：控制新舊梯度遮罩的混合比例，值越大表示越傾向於保留舊的梯度效果
        self.gradient_memory_factor = 0.6

    def shifting_basic(
        self,
        width,
        height,
        scale=10.0,
        z=0.0,
        gradient_vector=(1, 0),
    ):
        """
        生成 3D Perlin 噪聲並進行平移，z 參數控制噪聲的時間維度
        gradient_vector: 梯度向量，格式為 (x, y)，用於指定梯度的方向和強度
                         向量的方向決定梯度方向，向量的長度影響梯度強度
        """
        x = np.linspace(0, width / scale, width)
        y = np.linspace(0, height / scale, height)
        X, Y = np.meshgrid(x, y)

        self.get_interpolated_param()  # 確保使用最新的插值參數
        # 使用插值后的参数而不是目标参数
        # v = self.interper_tsoo_param["effect_vector"]
        ws = self.interper_tsoo_param["wind_speed"]
        offset = (3 * z * ws, 0.1 * z * ws)
        # 使用固定的 z 值或傳入的 z 值來生成第三維度
        Z = np.zeros((height, width))
        for i in range(height):
            for j in range(width):
                Z[i, j] = snoise3(
                    X[i, j] + offset[0],
                    Y[i, j] + offset[1],
                    z,
                    octaves=6,
                    persistence=0.05,
                    lacunarity=2.0,
                )
        Z = (Z - np.min(Z)) / (np.max(Z) - np.min(Z))
        Z = 0.5 - Z

        # 創建當前梯度遮罩
        current_gradient_mask = np.ones((height, width))

        gradient_vector = (gradient_vector[0], gradient_vector[1] * -1)  # 反轉 y 軸方向
        # 使用向量來創建梯度
        vec_x, vec_y = gradient_vector
        # 創建歸一化的座標網格
        norm_x = np.linspace(0, 1, width)
        norm_y = np.linspace(0, 1, height)
        norm_X, norm_Y = np.meshgrid(norm_x, norm_y)

        # 計算向量的方向上的投影 (點積)
        # 假設向量的原點在 (0,0)，目標是產生從原點向著向量方向的梯度
        vec_len = np.sqrt(vec_x**2 + vec_y**2)
        if vec_len > 0:
            unit_vec_x, unit_vec_y = vec_x / vec_len, vec_y / vec_len
            # 計算每個點到直線的投影距離
            projection = norm_X * unit_vec_x + norm_Y * unit_vec_y

            # 標準化投影值到 [0,1] 範圍
            min_proj = np.min(projection)
            max_proj = np.max(projection)
            if max_proj > min_proj:
                current_gradient_mask = (projection - min_proj) / (max_proj - min_proj)

            # 調整梯度強度 (向量長度作為強度)
            current_gradient_mask = np.power(current_gradient_mask, vec_len)

        # 如果存在之前的梯度遮罩，則將其與當前梯度遮罩混合
        gradient_mask = current_gradient_mask
        if self.previous_gradient_mask is not None:
            # 混合新舊梯度遮罩，保留舊梯度的高值區域
            # 使用元素級別的最大值來確保高值被保留
            memory_mask = np.maximum(
                self.previous_gradient_mask, current_gradient_mask
            ) * self.gradient_memory_factor + current_gradient_mask * (
                1 - self.gradient_memory_factor
            )
            gradient_mask = memory_mask

        # 保存當前梯度遮罩以供下次使用
        self.previous_gradient_mask = gradient_mask.copy()

        # 應用梯度遮罩到噪聲
        Z = Z * gradient_mask

        Z = np.interp(Z, (0, 1), (0, 255)).astype(np.uint8)

        return Z


def normalize(value, min_value, max_value):
    """Normalize a value to a range [0, 1]."""
    return (value - min_value) / (max_value - min_value)


def normalize_vector(vector):
    """Normalize a 2D vector to unit length."""
    magnitude = math.sqrt(vector[0] ** 2 + vector[1] ** 2)
    if magnitude == 0:
        return (0.0, 0.0)
    return (vector[0] / magnitude, vector[1] / magnitude)


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
    """將向量轉換為角度（標準數學坐標系）"""
    if vx == 0 and vy == 0:
        return 0.0
    radians = math.atan2(vx, vy)  # 返回弧度
    degrees = math.degrees(radians)  # 轉換為角度
    return (degrees + 360) % 360  # 確保角度在 [0, 360) 範圍內


def vector_to_angle_new_coordinate(vx, vy):
    """將向量轉換為角度（新坐標系，0度在上方，90度在右方）"""
    if vx == 0 and vy == 0:
        return 0.0
    radians = math.atan2(vx, vy)  # 返回弧度
    degrees = math.degrees(radians)  # 轉換為角度
    # 調整角度，使0度指向上方（90度順時針旋轉）
    adjusted_degrees = (degrees + 90) % 360
    return adjusted_degrees  # 確保角度在 [0, 360) 範圍內


def angle_to_vector(angle):
    """將角度轉換為向量（標準數學坐標系，0度在右方）"""
    radians = math.radians(angle)  # 轉換為弧度
    return (math.sin(radians), math.cos(radians))  # 返回 (vx, vy) 向量


def angle_to_vector_new_coordinate(angle):
    """將角度轉換為向量（新坐標系，0度在上方，90度在右方）"""
    # 將角度調整為標準坐標系（90度順時針旋轉）
    adjusted_angle = (angle + 90) % 360
    radians = math.radians(adjusted_angle)  # 轉換為弧度
    return (math.sin(radians), math.cos(radians))  # 返回 (vx, vy) 向量


# tsoo_param_processor = TSOOParamProcesser()
# tsoo_param_processor.tsoo_param["area_people_count"] = [5, 0, 0, 0]
# tsoo_param_processor.tsoo_param["wind_speed"] = 2.5

# tsoo_param_processor.caculate_param()
# print(f"Initial TSOO parameters: {tsoo_param_processor.get_tsoo_param()}")
# # print(tsoo_param_processor.get_tsoo_param())

# 使用示例
# if __name__ == "__main__":
#     import time

#     # 创建参数处理器
#     tsoo_param_processor = TSOOParamProcesser(interpolation_speed=0.05)
#     tsoo_param_processor.target_tsoo_param["area_people_count"] = [5, 0, 0, 0]
#     tsoo_param_processor.target_tsoo_param["wind_speed"] = 2.5

#     # 初始化参数
#     params = tsoo_param_processor.get_tsoo_param()
#     print(f"Initial target parameters: {params}")

#     # 模拟主循环
#     for i in range(10):
#         # 获取插值后的参数
#         interp_params = tsoo_param_processor.get_interpolated_param()
#         print(
#             f"Step {i}: Target wind_speed: {params['wind_speed']}, Interpolated: {interp_params['wind_speed']}"
#         )

#         # 更新目标参数
#         if i == 5:
#             tsoo_param_processor.update_wind_speed(4.0)
#             params = tsoo_param_processor.get_tsoo_param()
#             print(f"Updated target wind speed to {params['wind_speed']}")

#         time.sleep(0.5)  # 模拟主循环中的其他操作
