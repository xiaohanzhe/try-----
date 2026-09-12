# -*- coding: utf-8 -*-
import sys, os, json, tempfile, shutil
ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
sys.path.insert(0, os.path.join(ROOT, 'modules'))
tmp = tempfile.mkdtemp(); os.chdir(tmp)
from config_manager import ConfigManager
bad_cases = ['{"version":"1.0","api":"oops"}', '{"version":"1.0","api":5}',
             '{"version":"1.0","api":["x"]}', '{"version":"1.0","movement":"x"}',
             '{"version":"1.0","api":{"base_url":null}}']
for i, content in enumerate(bad_cases):
    p = os.path.join(tmp, f"c{i}.json")
    open(p, "w", encoding="utf-8").write(content)
    try:
        cm = ConfigManager(p) if 'config_file' in ConfigManager.__init__.__code__.co_varnames else None
    except TypeError:
        cm = None
    try:
        cm = ConfigManager(config_file=p)
    except Exception:
        cm = None
    try:
        if cm is None:
            cm = ConfigManager(p)
        cfg = cm.get_api_config()
        print(f"OK   {content[:42]:44s} -> base_url={cfg.get('base_url')!r}")
    except Exception as e:
        print(f"FAIL {content[:42]:44s} -> {type(e).__name__}: {e}")
print()
print("=== 非 dict 节点不再被 set() 抹掉 ===")
p = os.path.join(tmp, "d.json")
json.dump({"version": "1.0", "api": "IMPORTANT-USER-VALUE", "movement": {"speed": 3}}, open(p, "w", encoding="utf-8"))
cm = ConfigManager(p)
try:
    r = cm.set("movement.speed", 5)
    print("set 返回", r, "movement 节现在是", cm.get("movement"))
except Exception as e:
    print("set 异常:", type(e).__name__, e)
print("磁盘内容 api 节 =", json.load(open(p, encoding="utf-8")).get("api"))
