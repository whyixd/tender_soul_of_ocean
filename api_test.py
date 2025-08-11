import requests


def test_api_response():
    api_key = "AIzaSyD7GaoNhtXfLjZAADbLBmXaXQV3S8wi2Y8"
    latitude = 25.0423
    longitude = 121.5389
    uri = f"https://weather.googleapis.com/v1/currentConditions:lookup?key={api_key}&location.latitude={latitude}&location.longitude={longitude}"
    response = requests.get(uri)
    # assert response.status_code == 200
    # assert "expected_key" in response.json()
    return response.json()


print(test_api_response())
