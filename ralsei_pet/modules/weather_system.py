import time
try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:  # 模块外独立导入时的降级
    import logging
    _log = logging.getLogger(__name__)

import random
import datetime
import os
import socket

class WeatherSystem:
    """天气系统：优先读 Windows 自带的 Bing Weather 缓存，失败则本地推断。

    优先级：
    1. 检查联网（连 www.bing.com:80 判断是否有网）
    2. 有网 → 读 %LOCALAPPDATA%\\Packages\\Microsoft.BingWeather_*\\LocalState\\Cache\\*.db
       从 current_conditions / weather_snapshot 表读当前天气
    3. 没网 / 读缓存失败 → 基于本地季节+时段推断天气（同一天稳定，不依赖网络）
    """

    def __init__(self, update_interval=3600):
        self.current_weather = "sunny"
        self.last_update_time = 0
        # 修复：原先硬编码 3600 不可配置（测试/演示时无法缩短周期）。
        # 改为构造参数，非法值（<=0 / 非数字）回退默认 1 小时。
        try:
            update_interval = int(update_interval)
        except (TypeError, ValueError):
            update_interval = 3600
        self.update_interval = update_interval if update_interval > 0 else 3600
        self._last_date = None  # 记录上次更新的日期，同一天天气保持稳定

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

    # ----------------------------------------------------- 季节与本地推断

    def _get_season(self, month):
        """根据月份返回季节。"""
        if month in (3, 4, 5):
            return "spring"
        elif month in (6, 7, 8):
            return "summer"
        elif month in (9, 10, 11):
            return "autumn"
        else:
            return "winter"

    def _infer_weather(self):
        """基于季节+时段推断天气，用日期做种子保证同一天稳定。"""
        now = datetime.datetime.now()
        season = self._get_season(now.month)
        hour = now.hour
        is_daytime = 6 <= hour < 18

        season_probs = {
            "spring": [("sunny", 0.35), ("cloudy", 0.30), ("rainy", 0.20), ("windy", 0.15)],
            "summer": [("sunny", 0.45), ("cloudy", 0.20), ("rainy", 0.15), ("stormy", 0.15), ("windy", 0.05)],
            "autumn": [("sunny", 0.30), ("cloudy", 0.30), ("windy", 0.20), ("rainy", 0.20)],
            "winter": [("sunny", 0.25), ("cloudy", 0.30), ("snowy", 0.25), ("windy", 0.15), ("rainy", 0.05)],
        }

        probs = season_probs[season]
        if not is_daytime:
            adjusted = []
            for weather, p in probs:
                if weather == "sunny":
                    adjusted.append((weather, p * 0.4))
                elif weather in ("rainy", "stormy", "snowy"):
                    adjusted.append((weather, p * 1.3))
                else:
                    adjusted.append((weather, p))
            # 修复：调整后做归一化，确保概率和为1。
            # 之前的实现概率和<1，多余的概率全部落入末尾的sunny fallback，
            # 导致夜间晴天概率反而更高，与设计意图相反。
            total = sum(p for _, p in adjusted)
            if total > 0:
                probs = [(w, p / total) for w, p in adjusted]
            else:
                probs = adjusted

        seed = int(f"{now.year}{now.month:02d}{now.day:02d}")
        rng = random.Random(seed)
        r = rng.random()
        cumulative = 0.0
        for weather, p in probs:
            cumulative += p
            if r <= cumulative:
                return weather
        return "sunny"

    # ----------------------------------------------------- 联网检查

    @staticmethod
    def _is_online():
        """快速判断是否有网：尝试连 www.bing.com:80，超时 1.5s 算没网。"""
        try:
            sock = socket.create_connection(("www.bing.com", 80), timeout=1.5)
            sock.close()
            return True
        except (socket.error, OSError):
            return False

    # ----------------------------------------------------- Windows Bing Weather 缓存读取

    @staticmethod
    def _map_windows_weather(raw):
        """把 Windows 天气缓存里的字符串（英文）映射成我们的天气枚举。"""
        if not raw:
            return None
        r = raw.lower().strip()

        if any(k in r for k in ("sunny", "clear", "fair")):
            return "sunny"
        if any(k in r for k in ("cloud", "cloudy", "overcast", "partly", "mostly")):
            return "cloudy"
        # 修复：判定顺序错误——"shower" 同时出现在 "Snow Showers" 里，
        # 而 rain 分支原来写在 snow 之前，导致 Windows 天气缓存里常见的
        # "Snow Showers" 被判成下雨（Ralsei 会说"下雨了…湿漉漉的"并变成不开心）。
        # 先判雪，再判雨。
        if any(k in r for k in ("snow", "snowy", "flurry", "blizzard", "sleet")):
            return "snowy"
        if any(k in r for k in ("rain", "rainy", "shower", "drizzle", "light rain")):
            return "rainy"
        if any(k in r for k in ("wind", "breezy", "windy", "gust")):
            return "windy"
        if any(k in r for k in ("storm", "thunder", "t-storm", "tornado", "hurricane")):
            return "stormy"
        return None

    def _try_read_windows_cache(self):
        """尝试读取 Windows Bing Weather 的 SQLite 缓存，返回枚举天气或 None。"""
        try:
            import sqlite3
        except Exception:
            return None

        try:
            local_appdata = os.environ.get("LOCALAPPDATA")
            if not local_appdata:
                return None
            packages_dir = os.path.join(local_appdata, "Packages")
            if not os.path.isdir(packages_dir):
                return None

            # 找 BingWeather 目录（版本号不同，文件夹名带 _ 后缀）
            weather_dir = None
            for name in os.listdir(packages_dir):
                if name.lower().startswith("microsoft.bingweather"):
                    p = os.path.join(packages_dir, name, "LocalState", "Cache")
                    if os.path.isdir(p):
                        weather_dir = p
                        break
            if not weather_dir:
                return None

            # 在 Cache 目录里找 .db 文件，挑最新的
            db_files = []
            for fn in os.listdir(weather_dir):
                full = os.path.join(weather_dir, fn)
                if os.path.isfile(full) and fn.endswith(".db"):
                    try:
                        mtime = os.path.getmtime(full)
                        db_files.append((mtime, full))
                    except Exception as e:
                        _log.debug("weather_system 防御性异常（已忽略）: %s", e)
            if not db_files:
                return None
            db_files.sort(reverse=True)
            db_path = db_files[0][1]

            # 读 SQLite：先看看里面有什么表
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            weather_value = None
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]

                # 常见的几种表结构，一个个试
                for table in tables:
                    t = table.lower()
                    try:
                        if "current_conditions" in t or "weather_snapshot" in t:
                            cur.execute(f"SELECT * FROM \"{table}\" LIMIT 1")
                            row = cur.fetchone()
                            if row:
                                # 注意：sqlite3.Row 按列名索引区分大小写，不能用 lower() 后的列名
                                # 直接索引（会 IndexError 被吞，导致 Windows 天气缓存永远读不到）。
                                # 遍历 description 拿原始列名做不区分大小写的关键词匹配。
                                for d in cur.description:
                                    raw_col = d[0]
                                    key = raw_col.lower()
                                    if any(kk in key for kk in ("weather", "condition", "description", "sky")):
                                        raw_v = row[raw_col]
                                        mapped = self._map_windows_weather(str(raw_v))
                                        if mapped:
                                            weather_value = mapped
                                            break
                            if weather_value:
                                break
                        if not weather_value and ("response" in t or "weather" in t):
                            cur.execute(f"SELECT * FROM \"{table}\" LIMIT 2")
                            rows = cur.fetchall()
                            for row in rows:
                                for idx, desc in enumerate(cur.description):
                                    key = desc[0].lower()
                                    if any(kk in key for kk in ("weather", "condition", "description")):
                                        raw_v = row[idx]
                                        mapped = self._map_windows_weather(str(raw_v))
                                        if mapped:
                                            weather_value = mapped
                                            break
                                if weather_value:
                                    break
                    except Exception:
                        continue
                    if weather_value:
                        break
            finally:
                try:
                    conn.close()
                except Exception as e:
                    _log.debug("weather_system 防御性异常（已忽略）: %s", e)
            return weather_value
        except Exception:
            return None

    # ----------------------------------------------------- 主更新入口

    def update_weather(self):
        """更新天气：先查网 → 读Windows缓存 → 失败回退本地推断。"""
        current_time = time.time()
        if current_time - self.last_update_time > self.update_interval:
            now = datetime.datetime.now()
            today = now.date()

            try:
                online = self._is_online()
            except Exception:
                online = False

            chosen = None
            if online:
                chosen = self._try_read_windows_cache()

            if chosen is None:
                # 未联网 / 缓存读取失败 → 本地推断
                if self._last_date != today:
                    chosen = self._infer_weather()
                    self._last_date = today
                else:
                    chosen = self.current_weather  # 当天保持稳定

            self.current_weather = chosen
            self.last_update_time = current_time

    def get_weather_response(self):
        self.update_weather()
        return self.weather_responses.get(self.current_weather, self.weather_responses["sunny"])

    def get_current_weather(self):
        self.update_weather()
        return self.current_weather

    def set_location(self, location):
        """触发一次重新读取（清空时间戳）。"""
        self.last_update_time = 0
        self._last_date = None
        self.update_weather()

    def set_api_key(self, api_key):
        """保留接口（不需要API key，走Windows缓存+本地推断）。"""
        pass
