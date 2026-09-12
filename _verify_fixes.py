# -*- coding: utf-8 -*-
"""验证三处修复。"""
import os, sys, json, tempfile, time, traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)
sys.path.insert(0, os.path.join(PET, 'modules'))

out = []
def t(name, fn):
    try:
        r = fn()
        out.append("[PASS] %s -> %s" % (name, r))
    except Exception:
        out.append("[FAIL] %s\n%s" % (name, traceback.format_exc()))

# --- 1. 表情键解析 ---
def _t1():
    from modules.dialogue_ui import _resolve_face_name, _FACE_MAP
    r = _resolve_face_name("encouraging")
    assert r == "face_normal_smile_little", r
    # 未知名仍然走兜底（但 UI 层现在会回退 normal）
    assert _resolve_face_name("totally_unknown_key") == "face_totally_unknown_key"
    return "encouraging->%s, unknown->%s" % (r, _resolve_face_name("totally_unknown_key"))
t("face key resolve", _t1)

# --- 2. has_face ---
def _t2():
    from modules.sprite_loader import SpriteLoader
    s = SpriteLoader()
    ok1 = s.has_face("face_normal")
    ok2 = s.has_face("face_normal_smile_little")
    ok3 = s.has_face("face_encouraging")      # 不存在
    ok4 = s.has_face("")
    assert ok1 and ok2 and not ok3 and not ok4, (ok1, ok2, ok3, ok4)
    return "normal=%s smile_little=%s encouraging=%s empty=%s" % (ok1, ok2, ok3, ok4)
t("SpriteLoader.has_face", _t2)

# --- 3. 配置备份清理 ---
def _t3():
    from modules.config_manager import ConfigManager
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, 'config.json')
    # 直接实例化但绕开加载（用 __new__ 设置必要字段）
    cm = ConfigManager.__new__(ConfigManager)
    cm.config_file = cfg
    cm.config_version = "1.0"
    cm.last_save_time = time.time()
    cm.observers = []
    # 造 15 个旧备份
    for i in range(15):
        with open("%s.backup.%d" % (cfg, 1000 + i), 'w', encoding='utf-8') as f:
            f.write('{}')
    before = len([n for n in os.listdir(d) if n.startswith('config.json.backup.')])
    cm._prune_old_backups()
    after = len([n for n in os.listdir(d) if n.startswith('config.json.backup.')])
    remain = sorted(n for n in os.listdir(d) if n.startswith('config.json.backup.'))
    assert after == 10, after
    assert remain == sorted(remain, key=lambda x: int(x.rsplit('.',1)[-1]), reverse=True)[:10] or True
    # 确认保留的是最大的 10 个时间戳
    ts = sorted(int(n.rsplit('.',1)[-1]) for n in remain)
    assert ts == list(range(1005, 1015)), ts
    return "before=%d after=%d kept=%s" % (before, after, ts)
t("config backup prune", _t3)

# --- 4. 备份写入后自动清理（端到端） ---
def _t4():
    from modules.config_manager import ConfigManager
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, 'config.json')
    cm = ConfigManager.__new__(ConfigManager)
    cm.config_file = cfg
    # 先造 12 个历史备份
    for i in range(12):
        with open("%s.backup.%d" % (cfg, 1000 + i), 'w', encoding='utf-8') as f:
            f.write('{}')
    # 再触发一次真实备份（时间戳为当前时间，必然最新）
    cm._backup_config({"version": "1.0"})
    cnt = len([n for n in os.listdir(d) if n.startswith('config.json.backup.')])
    assert cnt == ConfigManager.MAX_CONFIG_BACKUPS, cnt
    return "备份数=%d (上限 %d)" % (cnt, ConfigManager.MAX_CONFIG_BACKUPS)
t("backup end-to-end", _t4)

with open(os.path.join(ROOT, '_verify_fixes_out.txt'), 'w', encoding='utf-8') as f:
    f.write("\n".join(out))
print("\n".join(out))
