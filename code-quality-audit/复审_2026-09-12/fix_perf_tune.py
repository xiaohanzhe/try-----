# -*- coding: utf-8 -*-
"""性能优化微调（第7区块补充）：
1) 窗口枚举缓存 TTL 0.8s→2.0s（与 floor 检查 2s 频率匹配，让高频路径真正吃到缓存）
2) floor_check_interval 1.0s→2.0s（窗口移动跟随 2 秒内响应足够，主线程枚举频率减半）
"""
D = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\desktop_interaction.py"
M = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"


def patch(path, old, new):
    with open(path, "rb") as f:
        raw = f.read()
    crlf = b"\r\n" in raw
    src = raw.decode("utf-8").replace("\r\n", "\n")
    assert old in src, f"NOT FOUND in {path}:\n{old[:150]}"
    assert src.count(old) == 1, f"NOT UNIQUE in {path}:\n{old[:150]}"
    src = src.replace(old, new, 1)
    out = src.replace("\n", "\r\n") if crlf else src
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print(f"patched: {path}")


patch(D,
"""    def get_all_visible_windows(self, use_cache=True, cache_ttl=0.8):""",
"""    def get_all_visible_windows(self, use_cache=True, cache_ttl=2.0):""")

patch(M,
"""        self.floor_check_interval = 1.0  # 楼层检查间隔（秒）""",
"""        self.floor_check_interval = 2.0  # 楼层检查间隔（秒）
        # 性能：楼层检查会全量枚举窗口（win32 跨进程调用，单次可达几十毫秒），
        # 1s 间隔 + nearby 检查让主线程周期性阻塞、鼠标渲染掉帧；2s 间隔配合
        # get_all_visible_windows 的 2s TTL 缓存，主线程枚举频率降一半以上。""")

print("ALL PATCHED OK")
