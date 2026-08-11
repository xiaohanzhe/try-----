import requests
import json
import time

class WeatherSystem:
    def __init__(self):
        self.current_weather = "sunny"
        self.weather_api_key = "YOUR_API_KEY"  # 需要替换为实际的API密钥
        self.location = "Beijing"  # 可以根据IP自动获取或让用户设置
        self.last_update_time = 0
        self.update_interval = 3600  # 每小时更新一次
        
        # 天气与反应的映射
        self.weather_responses = {
            "sunny": {
                "mood": "happy",
                "dialogue": "今天天气真好呀！阳光明媚的，要不要一起出去走走？",
                "animation": "dance"
            },
            "cloudy": {
                "mood": "normal",
                "dialogue": "今天有点多云呢... 不过没关系，我们可以在室内玩！",
                "animation": "idle"
            },
            "rainy": {
                "mood": "sad",
                "dialogue": "下雨了... 外面湿漉漉的，我们还是待在屋里吧。",
                "animation": "idle"
            },
            "snowy": {
                "mood": "excited",
                "dialogue": "下雪啦！雪真的好漂亮啊！我们去堆雪人吧！",
                "animation": "dance"
            },
            "windy": {
                "mood": "surprised",
                "dialogue": "今天风好大呀！要小心别被风吹走了！",
                "animation": "idle"
            },
            "stormy": {
                "mood": "scared",
                "dialogue": "外面好像有暴风雨... 好可怕，我能靠近你一点吗？",
                "animation": "idle"
            },
        }
        
    def update_weather(self):
        # 更新天气信息
        current_time = time.time()
        if current_time - self.last_update_time > self.update_interval:
            try:
                # 使用OpenWeatherMap API获取天气（示例）
                # url = f"http://api.openweathermap.org/data/2.5/weather?q={self.location}&appid={self.weather_api_key}&units=metric"
                # response = requests.get(url)
                # data = json.loads(response.text)
                # weather_main = data["weather"][0]["main"].lower()
                
                # 暂时使用模拟数据
                weather_main = "sunny"  # 模拟晴天
                self.current_weather = weather_main
                self.last_update_time = current_time
            except Exception as e:
                print(f"更新天气失败: {e}")
        
    def get_weather_response(self):
        # 获取当前天气对应的反应
        self.update_weather()
        return self.weather_responses.get(self.current_weather, self.weather_responses["sunny"])
        
    def get_current_weather(self):
        # 获取当前天气
        self.update_weather()
        return self.current_weather
        
    def set_location(self, location):
        # 设置位置
        self.location = location
        self.last_update_time = 0  # 立即更新天气
        self.update_weather()
        
    def set_api_key(self, api_key):
        # 设置API密钥
        self.weather_api_key = api_key
        self.last_update_time = 0  # 立即更新天气
        self.update_weather()