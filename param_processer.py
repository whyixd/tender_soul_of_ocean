import math
import numpy as np
from noise import snoise2, snoise3
from scipy.ndimage import gaussian_filter
import random


def draw_circle(center_x, center_y, radius, shape):
    """
    Generate coordinates of pixels on the circle circumference.

    Parameters:
    center_x, center_y: Center coordinates of the circle
    radius: Radius of the circle
    shape: Shape of the image (height, width)

    Returns:
    rr, cc: Row and column coordinates of pixels on the circle circumference
    """
    height, width = shape

    # Create coordinate arrays
    y, x = np.ogrid[:height, :width]

    # Calculate distance from center
    dist_from_center = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)

    # Find pixels on the circle circumference (within a small tolerance)
    # Use a tolerance to account for discrete pixel positions
    tolerance = 0.5
    mask = np.abs(dist_from_center - radius) <= tolerance

    # Get row and column indices
    rr, cc = np.where(mask)

    return rr, cc


class TSOOParamProcesser:
    def __init__(self, interpolation_speed=0.2):
        self.target_tsoo_param = {
            "people_natrual_weight": 0.5,
            "people_natrual_weight_level": 0,
            "people_natrual_weight_level_threshold": [0, 0.3, 0.8, 1],
            "area_people_count": [],
            "people_count_max": 30,  # set by guess
            "people_vector": (0.0, 0.0),  # 人數向量
            "wind_speed": 0.0,
            "wind_speed_max": 5.0,  # get from https://www.timeanddate.com/weather/austria/linz/climate
            "wind_angle": 0.0,
            "wind_vector": (0.0, 0.0),  # 風向向量
            "effect_angle": 0.0,  # 風向角度
            "effect_vector": (0.0, 0.0),  # 風向向量
        }
        self.previous_tsoo_param = self.target_tsoo_param.copy()
        self.interper_tsoo_param = self.target_tsoo_param.copy()

        # 噪聲生成和淡出控制參數
        self.noise_duration = 5.0  # 噪聲持續時間（秒）
        self.fade_duration = 1.0  # 淡出持續時間（秒）
        self.fade_in_duration = 1.0  # 淡入持續時間（秒）
        self.current_noise_time = 0.0  # 當前噪聲生成的時間
        self.fade_factor = 0.0  # 當前淡出因子，1.0 表示完全顯示，0.0 表示完全淡出
        self.should_update_vector = False  # 是否應該更新風向向量
        self.last_update_time = 0.0  # 上次更新風向向量的時間
        self.cached_wind_vector = (0.0, 0.0)  # 緩存的風向向量，用於平滑過渡
        self.fade_state = "FADE_IN"  # 淡入淡出狀態：FADE_IN, NORMAL, FADE_OUT
        self.on_basic_fade_out_done = None

        # 用於通知外部系統何時可以更新參數
        self.can_update_params = False  # 是否可以更新參數
        self.params_updated = False  # 參數是否已經更新
        self.previous_tsoo_param = self.target_tsoo_param.copy()
        self.interper_tsoo_param = self.target_tsoo_param.copy()

        # 插值速度控制（值越大，过渡越快）
        self.interpolation_speed = interpolation_speed
        self.wind_speed_factor = 10

        # 儲存之前的梯度遮罩，用於在梯度向量變化時保留之前的效果
        self.previous_gradient_mask = None
        # 儲存上一次的梯度向量，用於計算向量變化的幅度和方向
        self.previous_gradient_vector = None
        # 記憶因子：控制新舊梯度遮罩的混合比例，值越大表示越傾向於保留舊的梯度效果
        self.gradient_memory_factor = 0.6
        # 梯度向量變化的最大允許速度（每幀）
        self.max_vector_change_rate = 0.15

    def caculate_param(self):
        # 保存當前參數為上一次參數
        # self.previous_tsoo_param = self.target_tsoo_param.copy()

        total_people = sum(self.target_tsoo_param["area_people_count"])
        people_count_normalized = normalize(
            total_people, 0, self.target_tsoo_param["people_count_max"]
        )
        wind_speed_normalized = normalize(
            self.target_tsoo_param["wind_speed"],
            0,
            self.target_tsoo_param["wind_speed_max"],
        )
        self.target_tsoo_param["wind_speed"] = wind_speed_normalized
        # self.target_tsoo_param["wind_speed_normalized"] = wind_speed_normalized
        # -----------------------------IMPORTANT-----------------------------------#
        self.target_tsoo_param["people_natrual_weight"] = round(
            combine_normalize(people_count_normalized, wind_speed_normalized), 2
        )
        # -----------------------------IMPORTANT-----------------------------------#
        threshold = self.target_tsoo_param["people_natrual_weight_level_threshold"]
        for idx, t in enumerate(threshold):
            if self.target_tsoo_param["people_natrual_weight"] <= t:
                self.target_tsoo_param["people_natrual_weight_level"] = idx - 1
                break

        # 計算區域人數向量
        people_vector = calculate_balanced_vector(
            self.target_tsoo_param["area_people_count"], normalize=True
        )
        people_vector = (round(people_vector[0], 2), round(people_vector[1], 2))
        self.target_tsoo_param["people_vector"] = people_vector
        # 計算風向向量
        wind_vector = angle_to_vector(self.target_tsoo_param["wind_angle"])
        self.target_tsoo_param["wind_vector"] = (
            round(wind_vector[0], 2),
            round(wind_vector[1], 2),
        )

        # vector_combined = normalize_vector(
        #     (-people_vector[0] + wind_vector[0]*2, -people_vector[1] + wind_vector[1]*2)
        # )
        vector_combined = normalize_vector(
            (-people_vector[0], -people_vector[1])
        )
        if vector_combined == (0.0, 0.0):
            vector_combined = normalize_vector(wind_vector)
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
        """計算從previous到target的插值"""
        # 對每個數值類型的參數進行插值
        for key, target_value in self.target_tsoo_param.items():
            if key in self.interper_tsoo_param:
                prev_value = self.interper_tsoo_param[key]

                # 根據不同類型進行不同的插值
                if isinstance(target_value, (int, float)) and isinstance(
                    prev_value, (int, float)
                ):
                    if key == "people_natrual_weight_level":
                        continue
                    # 數值類型插值
                    self.interper_tsoo_param[key] = self._interpolate_value(
                        prev_value,
                        target_value,
                        interpolation_speed=self.interpolation_speed,
                    )
                    if abs(target_value - self.interper_tsoo_param[key]) < 0.01:
                        self.interper_tsoo_param[key] = target_value
                elif (
                    isinstance(target_value, tuple)
                    and isinstance(prev_value, tuple)
                    and len(target_value) == 2
                    and len(prev_value) == 2
                ):
                    # 二维向量插值
                    fix_interprolation_speed = self.interpolation_speed
                    if key == "wind_vector":
                        fix_interprolation_speed = 0.01
                    x = self._interpolate_value(
                        prev_value[0],
                        target_value[0],
                        interpolation_speed=fix_interprolation_speed,
                    )
                    y = self._interpolate_value(
                        prev_value[1],
                        target_value[1],
                        interpolation_speed=fix_interprolation_speed,
                    )
                    self.interper_tsoo_param[key] = (x, y)
                    if abs(target_value[0] - x) < 0.01:
                        x = target_value[0]
                    if abs(target_value[1] - y) < 0.01:
                        y = target_value[1]
                    self.interper_tsoo_param[key] = (x, y)

                else:
                    # 其他类型直接使用目标值
                    self.interper_tsoo_param[key] = target_value
            else:
                # 如果previous中没有该键，直接使用目标值
                self.interper_tsoo_param[key] = target_value

        return self.interper_tsoo_param

    def _interpolate_value(self, prev, target, interpolation_speed=1):
        """计算单个数值的插值"""
        if prev == target:
            return target

        # 线性插值: current = current + (target - current) * speed
        return prev + (target - prev) * interpolation_speed

    def get_interpolated_param(self):
        """獲取當前插值後的參數"""
        self.calculate_interpolation()
        return self.interper_tsoo_param

    def shifting_basic(
        self,
        width,
        height,
        scale=0.1,
        z=0.0,
        gradient_vector=(1, 0),
        delta_time=0.016,  # 假設每幀 16ms，即約 60fps
    ):
        """
        生成 3D Perlin 噪聲並進行平移，z 參數控制噪聲的時間維度
        gradient_vector: 梯度向量，格式為 (x, y)，用於指定梯度的方向和強度
                         向量的方向決定梯度方向，向量的長度影響梯度強度
        delta_time: 上一幀到當前幀的時間間隔（秒）
        """
        self.get_interpolated_param()  # 確保使用最新的插值參數
        effect_vector = self.interper_tsoo_param["effect_vector"]
        x = np.linspace(0, width / scale * abs(effect_vector[0]), width)
        y = np.linspace(0, height / scale * abs(effect_vector[1]), height)
        X, Y = np.meshgrid(x, y)

        # 更新噪聲時間和淡出因子
        self.current_noise_time += delta_time

        # 根據當前狀態處理淡入淡出
        if self.fade_state == "FADE_IN":
            # 淡入階段
            fade_in_progress = min(self.current_noise_time / self.fade_in_duration, 1.0)
            self.fade_factor = fade_in_progress

            # 當完全淡入時，切換到正常顯示狀態
            if fade_in_progress >= 1.0:
                self.fade_factor = 1.0
                self.fade_state = "NORMAL"
                # 重置參數更新標誌
                self.params_updated = False
                self.can_update_params = False

        elif self.fade_state == "NORMAL":
            # 正常顯示階段
            self.fade_factor = 1.0

            # 檢查是否需要開始淡出
            if self.current_noise_time >= self.noise_duration:
                self.fade_state = "FADE_OUT"

        elif self.fade_state == "FADE_OUT":
            # 淡出階段
            fade_out_progress = min(
                (self.current_noise_time - self.noise_duration) / self.fade_duration,
                1.0,
            )
            self.fade_factor = max(0, 1.0 - fade_out_progress)

            # 設定可以更新參數的標誌
            # 當淡出到一定程度時(例如80%淡出)，通知外部可以更新參數
            if fade_out_progress >= 1.0 and not self.can_update_params:
                self.can_update_params = True
                if self.on_basic_fade_out_done:
                    self.on_basic_fade_out_done()
                self.noise_duration = random.randrange(
                    3, 10
                )  # 隨機設定下一次噪聲持續時間
                self.fade_duration = (
                    random.randrange(10, 20) / 10
                )  # 隨機設定下一次淡出持續時間
                self.fade_in_duration = (
                    random.randrange(20, 25) / 10
                )  # 隨機設定下一次淡入持續時間
                print(
                    f"下一次噪聲持續時間: {self.noise_duration} 秒 淡出持續時間: {self.fade_duration} 秒 淡入持續時間: {self.fade_in_duration} 秒"
                )
            # 當完全淡出時，更新風向向量並重置狀態
            if self.fade_factor <= 0:

                # 更新緩存的風向向量，只有在參數已更新的情況下
                if self.params_updated:
                    self.cached_wind_vector = self.interper_tsoo_param["wind_vector"]
                    self.last_update_time = z

                # 重置狀態
                self.current_noise_time = 0.0
                self.fade_factor = 0.0  # 確保完全透明
                self.fade_state = "FADE_IN"  # 切換到淡入狀態
                self.can_update_params = False  # 重置可更新標誌

        # 使用緩存的風向向量或當前的風向向量
        # if self.cached_wind_vector == (0.0, 0.0):
        #     wv = self.interper_tsoo_param["wind_vector"]
        #     self.cached_wind_vector = wv
        # else:
        #     wv = self.cached_wind_vector
        wv = self.target_tsoo_param["wind_vector"]
        ws = self.target_tsoo_param["wind_speed"] * self.wind_speed_factor

        # 使用相對時間計算位移，避免大跳變
        relative_time = z - self.last_update_time
        # 將風向向量納入噪聲位移計算
        offset = (relative_time * ws * wv[0], relative_time * ws * wv[1])

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

        # 漸進式改變梯度向量，防止突變
        if self.previous_gradient_vector is not None:
            prev_x, prev_y = self.previous_gradient_vector
            target_x, target_y = gradient_vector

            # 計算向量變化的距離
            vector_diff = math.sqrt((target_x - prev_x) ** 2 + (target_y - prev_y) ** 2)

            # 如果變化太大，則限制變化幅度
            if vector_diff > self.max_vector_change_rate:
                # 計算向量變化的方向
                if vector_diff > 0:
                    dx = (target_x - prev_x) / vector_diff * self.max_vector_change_rate
                    dy = (target_y - prev_y) / vector_diff * self.max_vector_change_rate
                else:
                    dx, dy = 0, 0

                # 應用有限的變化
                actual_x = prev_x + dx
                actual_y = prev_y + dy
                gradient_vector = (actual_x, actual_y)

        # 保存當前梯度向量，以便下次比較
        self.previous_gradient_vector = gradient_vector

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
            # 使用平方根而非直接指數，使變化更溫和
            current_gradient_mask = np.power(current_gradient_mask, np.sqrt(vec_len))

        # 如果存在之前的梯度遮罩，則將其與當前梯度遮罩混合
        gradient_mask = current_gradient_mask
        if self.previous_gradient_mask is not None:
            # 混合新舊梯度遮罩，採用更柔和的過渡方式
            # 使用加權平均而非最大值，並應用高斯模糊使邊緣更平滑

            # 首先進行基本的混合，使用更高的記憶因子使過渡更平滑
            enhanced_memory_factor = np.clip(self.gradient_memory_factor + 0.1, 0, 0.9)
            memory_mask = (
                self.previous_gradient_mask * enhanced_memory_factor
                + current_gradient_mask * (1 - enhanced_memory_factor)
            )

            # 創建一個差異遮罩，找出變化較大的區域
            diff_mask = np.abs(self.previous_gradient_mask - current_gradient_mask)

            # 在差異較大的區域應用更多的模糊效果，使過渡更加柔和
            # 使用高斯濾波進行模糊處理
            from scipy.ndimage import gaussian_filter

            # 對邊緣區域進行平滑處理，根據差異程度調整模糊強度
            sigma = 0.3 + diff_mask.mean() * 2  # 動態調整模糊程度
            smoothed_mask = gaussian_filter(memory_mask, sigma=sigma)

            # 為了防止暴漲，額外對結果進行非線性調整
            # 使用閾值限制每幀的最大變化幅度
            max_change_per_frame = 0.1  # 每幀的最大變化幅度
            change_mask = np.abs(smoothed_mask - self.previous_gradient_mask)
            # 任何超過閾值的變化都會被限制
            excess_mask = np.clip(change_mask - max_change_per_frame, 0, 1)
            # 應用限制，從平滑的遮罩中減去過量的變化
            if excess_mask.max() > 0:
                normalized_excess = excess_mask / excess_mask.max()
                smoothed_mask = smoothed_mask - normalized_excess * excess_mask

            # 根據差異程度融合原始遮罩和平滑遮罩
            blend_factor = np.clip(diff_mask * 3, 0, 0.8)  # 控制融合比例
            gradient_mask = (
                memory_mask * (1 - blend_factor) + smoothed_mask * blend_factor
            )

        # 保存當前梯度遮罩以供下次使用
        self.previous_gradient_mask = gradient_mask.copy()

        # 保存原始噪声（未应用梯度遮罩）
        Z_original = Z.copy()

        # 應用梯度遮罩到噪聲
        Z = Z * gradient_mask

        # 應用淡出效果
        Z = Z * self.fade_factor

        Z = np.interp(Z, (0, 1), (0, 255)).astype(np.uint8)

        return Z

    def get_combined_effects(
        self, width, height, scale=7, z=0.0, gradient_vector=(1, 0), delta_time=0.016
    ):
        """
        獲取組合效果，讓梯度遮罩不影響雨滴效果
        """
        # 獲取基礎效果（帶梯度遮罩）
        basic_effect = self.shifting_basic(
            width, height, scale, z, gradient_vector, delta_time
        )

        # 獲取雨滴效果（獨立不受梯度影響）
        rain_drop_effect = self.rain_drop_effect(width, height)

        # 智能組合：雨滴效果採用加法混合，但不受梯度遮罩影響
        # 可以根據需要調整雨滴的強度
        rain_intensity = 0.0  # 可調整雨滴強度

        # 將雨滴效果疊加到基礎效果上
        # 使用 np.clip 確保數值不會超出範圍
        combined = np.clip(
            basic_effect.astype(np.float32)
            + rain_drop_effect.astype(np.float32) * rain_intensity,
            0,
            255,
        )

        return combined.astype(np.uint8)

    def get_effects_separately(
        self, width, height, scale=7, z=0.0, gradient_vector=(1, 0), delta_time=0.016
    ):
        """
        分別獲取基礎噪聲、梯度遮罩和雨滴效果，提供更大的組合靈活性
        返回: (基礎噪聲, 梯度遮罩, 雨滴效果)
        """
        # 獲取基礎噪聲（調用 shifting_basic 但修改其返回邏輯）
        # 暫時保存當前的 previous_gradient_mask
        temp_previous_mask = self.previous_gradient_mask

        # 獲取基礎效果以計算梯度遮罩
        _ = self.shifting_basic(width, height, scale, z, gradient_vector, delta_time)

        # 獲取計算好的梯度遮罩
        current_gradient_mask = self.previous_gradient_mask.copy()

        # 恢復 previous_gradient_mask（因為 shifting_basic 會修改它）
        # self.previous_gradient_mask = temp_previous_mask

        # 重新生成基礎噪聲（不應用梯度遮罩）
        self.get_interpolated_param()
        effect_vector = self.interper_tsoo_param["effect_vector"]
        x = np.linspace(0, width / scale * abs(effect_vector[0]), width)
        y = np.linspace(0, height / scale * abs(effect_vector[1]), height)
        X, Y = np.meshgrid(x, y)

        wv = self.target_tsoo_param["wind_vector"]
        ws = self.target_tsoo_param["wind_speed"] * self.wind_speed_factor
        relative_time = z - self.last_update_time
        offset = (relative_time * ws * wv[0], relative_time * ws * wv[1])

        # 生成基礎噪聲
        Z_basic = np.zeros((height, width))
        for i in range(height):
            for j in range(width):
                Z_basic[i, j] = snoise3(
                    X[i, j] + offset[0],
                    Y[i, j] + offset[1],
                    z,
                    octaves=6,
                    persistence=0.05,
                    lacunarity=2.0,
                )
        Z_basic = (Z_basic - np.min(Z_basic)) / (np.max(Z_basic) - np.min(Z_basic))
        Z_basic = 0.5 - Z_basic
        Z_basic = np.interp(Z_basic, (0, 1), (0, 255)).astype(np.uint8)

        # 獲取雨滴效果
        rain_effect = self.rain_drop_effect(width, height, z=relative_time)

        return Z_basic, current_gradient_mask, rain_effect

    class RainDrop:
        def __init__(self, x, y, radius, expansion_rate):
            self.x = x
            self.y = y
            self.radius = radius
            self.expansion_rate = expansion_rate
            self.end_radius = 5  # 最大半徑

    rain_drops = []

    def rain_drop_effect(self, width, height, z=0.0):

        Z = np.zeros((height, width))
        # 隨機生成雨滴
        if len(self.rain_drops) < 2:
            self.rain_drops.append(
                self.RainDrop(
                    random.randint(0, width - 1),
                    random.randint(0, height - 1),
                    random.uniform(0.1, 2),  # 隨機半徑
                    random.uniform(0.08, 0.2),  # 隨機擴展速度
                )
            )
        # 從後往前遍歷，避免在刪除元素時影響索引
        for idx in range(len(self.rain_drops) - 1, -1, -1):
            drop = self.rain_drops[idx]
            if drop.radius > drop.end_radius:
                # 如果半徑超過最大值，則移除雨滴
                self.rain_drops.pop(idx)
            else:
                rr, cc = draw_circle(drop.x, drop.y, drop.radius, Z.shape)
                value = 0.6 - (drop.radius / drop.end_radius)
                Z[rr, cc] = value  # 在雨滴位置生成圓點
                # 擴展雨滴半徑
                drop.radius += drop.expansion_rate

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
        raise ValueError(f"輸入的列表長度必須為 4 ，{values}")
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
