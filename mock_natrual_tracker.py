import requests


class MockNaturalTracker:
    def wind_speed_convert_to_ms(wind_speed):
        return round(wind_speed / 3.6, 2)  # Convert m/s to km/h

    def __init__(self):
        """Data structure is  [wind_speed, wind_level, wind_direction, wind_direction_compass]"""
        self.data = [0, 0, 0, ""]
        self.data_path = "mock_natural_tracker_data.json"

        self.api_key = "AIzaSyD7GaoNhtXfLjZAADbLBmXaXQV3S8wi2Y8"
        self.location = [25.0423, 121.5389]

        self.uri = f"https://weather.googleapis.com/v1/currentConditions:lookup?key={self.api_key}&location.latitude={self.location[0]}&location.longitude={self.location[1]}"

    def update(self):

        response = requests.get(self.uri).json()
        natural_data = [
            MockNaturalTracker.wind_speed_convert_to_ms(
                response["wind"]["speed"]["value"]
            ),
            0,
            response["wind"]["direction"]["degrees"],
            response["wind"]["direction"]["cardinal"],
        ]
        self.data = natural_data
        return natural_data

    def get_data(self):
        return self.data

    # def start_continuous_update(self, interval=1, print_data=True):
    #     pass


# mock_natural_tracker = MockNaturalTracker()

# data = mock_natural_tracker.update()
# print(data)
