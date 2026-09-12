# -*- coding: utf-8 -*-
"""customization_system.py 修复（第5区块）：原子写 + 加载类型防御"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\customization_system.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

def patch(old, new):
    global src
    assert old in src, f"NOT FOUND:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE:\n{old[:200]}"
    src = src.replace(old, new, 1)

# ---- 1) save_config 原子写：先写临时文件再 os.replace，
#      避免中途崩溃/断电留下损坏 JSON（下次启动配置全部丢失回退默认）。 ----
patch(
"""    def save_config(self):
        \"\"\"保存自定义配置\"\"\"
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.customization_data, f, ensure_ascii=False, indent=2)
            _log.debug("成功保存自定义配置: %s", self.config_path)
        except Exception as e:
            _log.warning("保存自定义配置失败: %s", e)""",
"""    def save_config(self):
        \"\"\"保存自定义配置\"\"\"
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            # 修复：原实现直接写目标文件，写入中途崩溃/断电会留下损坏的 JSON，
            # 下次启动 load_config 失败 → 用户全部自定义配置静默回退默认。
            # 改为"临时文件 + os.replace"原子替换，任何时刻目标文件要么是旧的
            # 完整配置、要么是新的完整配置，绝不会是半截 JSON。
            tmp_path = self.config_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.customization_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.config_path)
            _log.debug("成功保存自定义配置: %s", self.config_path)
        except Exception as e:
            _log.warning("保存自定义配置失败: %s", e)
            try:
                if os.path.exists(self.config_path + ".tmp"):
                    os.remove(self.config_path + ".tmp")
            except Exception:
                pass""")

# ---- 2) _merge_config 类型防御：损坏配置（列表/字符串/None）直接忽略，
#      不破坏默认值。 ----
patch(
"""    def _merge_config(self, base, update):
        \"\"\"递归合并配置\"\"\"
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value""",
"""    def _merge_config(self, base, update):
        \"\"\"递归合并配置\"\"\"
        # 修复：损坏的配置文件可能是列表/字符串/None，update.items() 会
        # AttributeError 导致整个加载失败（默认值全丢）。非 dict 直接忽略。
        if not isinstance(update, dict):
            _log.warning("自定义配置片段不是对象，已忽略: %r", update)
            return
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value""")

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("customization_system.py patched OK")
