# -*- coding: utf-8 -*-
"""记忆的"存放位置"层（MemoryStore）
=====================================

用户要求（第九轮）："记忆就储存在肖翰哲（E)里面就好（如果没检测到该设备那就临时
存储在桌面上的 memory 文件夹里，等下次检测到这个设备接入后再把东西放进去，
同时把桌面上的多余的记忆清除）"

于是本模块只做一件事：**决定 memory.json 该放在哪、以及什么时候把桌面上的临时
副本搬进正式设备**。记忆模型本身（片段 / 关键记忆 / 遗忘 / 回忆）不在这里，
在 `memory_system.py`。

位置优先级：
  1. `RALSEI_MEMORY_DIR` 环境变量（测试/高级用户强制指定，优先级最高）
  2. 卷标含"肖翰哲"的驱动器根目录下的 `RalseiMemory\\`（即用户的 E 盘）
  3. 桌面兜底：`<桌面>\\memory\\`

"搬进去"（migrate）的安全约定 —— 这是本模块唯一会删东西的地方，所以：
  · **只碰两个文件名**：`memory.json` 与它的半成品 `memory.json.tmp`；
  · **先写成功、校验通过，再删源**（copy → verify → delete），任何一步失败就保留
    源文件不删（宁可多留一份，也不丢记忆）；
  · 两边都有内容时不覆盖丢数据：保留 `saved_at` 较新的一份，另一份挪到
    `memory.old.json` 留档；源目录清空后**只在确实空了**才删掉空目录。

本模块 import 时**不做任何磁盘操作**（第五轮冒烟测试会全量 import 所有模块）。
"""
import json
import os
import shutil
import time

# 惰性日志器（勿改回模块级 get_logger）：本模块被 data_store.vault_root() 反向 import，
# 若在 import 期就去要 logger，会形成
#     logger_utils → data_store → memory_store → logger_utils
# 的间接环，把日志目录永久钉到中转站（详见 modules/lazy_log.py 与
# code-quality-audit/第十二轮/probe_cycle2.py）。
try:
    from lazy_log import LazyLogger
except ImportError:            # 包内导入（modules/ 不在 sys.path 上时）
    from .lazy_log import LazyLogger

_log = LazyLogger(__name__)

# 卷标命中即认为是"主人的记忆盘"。真实卷标是"肖翰哲"，这里放宽到包含匹配，
# 免得用户后来把盘改名成"肖翰哲(E)"或"肖翰哲的U盘"就认不出来了。
DEVICE_LABEL_HINTS = ('肖翰哲', 'ralsei', 'RALSEI')
# 设备上的存放目录名（与桌面兜底的 memory 区分开，便于用户认出来是程序建的）
DEVICE_SUBDIR = 'RalseiMemory'
# 桌面兜底目录名：用户原话就是"桌面上的 memory 文件夹"
FALLBACK_DIRNAME = 'memory'
MEMORY_FILENAME = 'memory.json'
ROLLBACK_FILENAME = 'memory.old.json'

ENV_DIR = 'RALSEI_MEMORY_DIR'
ENV_DESKTOP = 'RALSEI_DESKTOP'
ENV_NO_DEVICE = 'RALSEI_MEMORY_DEVICE'   # 置为 'off' → 强制走桌面兜底（测试/用户偏好）


# --------------------------------------------------------------------- 设备探测
def _volume_label(root):
    """取驱动器卷标；非 Windows / 失败一律返回空串（绝不抛）。"""
    try:
        import ctypes
        from ctypes import wintypes
        vol = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        serial = wintypes.DWORD()
        maxlen = wintypes.DWORD()
        flags = wintypes.DWORD()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root), vol, 261, ctypes.byref(serial),
            ctypes.byref(maxlen), ctypes.byref(flags), fs, 261)
        return vol.value if ok else ''
    except Exception:
        return ''


def list_drive_roots():
    """列出本机所有盘符根（如 ['C:\\\\', 'D:\\\\', ...]）；失败返回 []。"""
    try:
        import ctypes
        import string
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        out = []
        for i, ch in enumerate(string.ascii_uppercase):
            if mask & (1 << i):
                root = ch + ':\\'
                if os.path.exists(root):
                    out.append(root)
        return out
    except Exception:
        return []


def _is_writable_dir(path):
    """目录可写性探测：能建成、能落一个小文件、能删掉。

    两级判定，**快路径刻意不落任何文件**（第十三轮修复）：
      1. `os.access(path, W_OK)` —— 本机固定盘上可信、零副作用，且**不缓存**，
         所以拔盘/掉线在下次调用依然能被检出来；
      2. 只有快路径给不出结论（返回 False）时才退回"真建一个 `.write_probe`
         再删掉"的老探针，保证判据不比以前更宽松。

    为什么要分两级：`find_device_dir(create=True)` 在**一次启动**里会被调用十几次
    （`data_store` 要解析记忆库 + 7 类运行时产物），老实现每次都真的建/写/删一个
    文件。这不只是浪费 —— 实测这些删除会累积撞上宿主沙箱的"同一轮内同路径删除
    配额"（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`），把正在跑的**整个回归套件进程**
    掐掉，表现为全套件 `exit=1 PASS=0`。第十三轮 G2 全量跑出的 11 个假 DIFF，
    真凶就在这里（`E:\\RalseiMemory\\.write_probe` 单轮被删 50+ 次）。
    """
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return False
    if os.access(path, os.W_OK):
        return True
    try:
        probe = os.path.join(path, '.write_probe')
        with open(probe, 'w', encoding='utf-8') as fh:
            fh.write('ok')
        os.remove(probe)
        return True
    except Exception:
        return False


def find_device_dir(create=True):
    """找到记忆设备目录（如 `E:\\RalseiMemory`）；没插设备返回 None。

    `create=False` 时只探测不建目录（纯查询用，例如"要不要搬家"）。
    """
    forced = os.environ.get(ENV_DIR)
    if forced:
        if create:
            try:
                os.makedirs(forced, exist_ok=True)
            except Exception as e:
                _log.warning("强制指定的记忆目录不可用: %s (%s)", forced, e)
        return forced
    if str(os.environ.get(ENV_NO_DEVICE, '')).strip().lower() in ('off', '0', 'none', 'false'):
        return None      # 强制桌面兜底
    for root in list_drive_roots():
        label = _volume_label(root)
        if not label:
            continue
        # 卷标命中即认为"就是这台设备"；另外允许"上次就是它"的证据：设备根下
        # 已经存在我们的目录（卷标被用户改过也还认得出来）。
        label_hit = any(h.lower() in label.lower() for h in DEVICE_LABEL_HINTS)
        target = os.path.join(root, DEVICE_SUBDIR)
        dir_exists = os.path.isdir(target)
        if not label_hit and not dir_exists:
            continue
        if create:
            if _is_writable_dir(target):
                return target
        else:
            # 纯查询：卷标命中即算"设备在线"（目录可能还没建，属于正常首启）
            return target
    return None


def desktop_dir():
    """桌面目录（兼容 OneDrive 重定向与中文"桌面"）。"""
    forced = os.environ.get(ENV_DESKTOP)
    if forced:
        return forced
    home = os.path.expanduser('~')
    for cand in (os.path.join(home, 'Desktop'),
                 os.path.join(home, 'OneDrive', 'Desktop'),
                 os.path.join(home, '桌面')):
        if os.path.isdir(cand):
            return cand
    return home


def fallback_dir():
    """桌面兜底目录：`<桌面>\\memory`。"""
    return os.path.join(desktop_dir(), FALLBACK_DIRNAME)


def default_memory_dir():
    """当前该用的记忆目录：设备优先，否则桌面兜底。

    返回 `(目录, 是否为设备目录, 设备目录或 None)`。
    """
    dev = find_device_dir(create=True)
    if dev:
        return dev, True, dev
    fb = fallback_dir()
    try:
        os.makedirs(fb, exist_ok=True)
    except Exception as e:
        _log.warning("桌面记忆兜底目录创建失败: %s", e)
    return fb, False, find_device_dir(create=False)


def memory_file_in(directory):
    return os.path.join(directory, MEMORY_FILENAME)


# --------------------------------------------------------------------- 文件搬运
def _read_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _saved_at(data):
    """取记忆文件的"新鲜度"标记：优先 saved_at，退化到 mtime。"""
    if isinstance(data, dict):
        v = data.get('saved_at')
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0


def _copy_verified(src, dst):
    """复制并校验（长度一致 + 能解析成 JSON dict）；返回是否成功。"""
    try:
        shutil.copy2(src, dst)
    except Exception as e:
        _log.warning("记忆搬运复制失败 %s -> %s: %s", src, dst, e)
        return False
    try:
        if os.path.getsize(src) != os.path.getsize(dst):
            return False
    except Exception:
        return False
    if os.path.basename(dst) != ROLLBACK_FILENAME and _read_json(dst) is None:
        return False
    return True


def migrate_from_fallback(target_dir):
    """把桌面兜底目录里的记忆搬进 `target_dir`，成功后清掉桌面副本。

    返回一个描述动作的 dict（便于日志/验证）：
      {'moved': bool, 'reason': str, 'kept': 'newer'|'fallback'|'target',
       'removed_fallback_file': bool, 'removed_fallback_dir': bool}
    """
    result = {'moved': False, 'reason': '', 'kept': 'target',
              'removed_fallback_file': False, 'removed_fallback_dir': False}
    fb = fallback_dir()
    src = memory_file_in(fb)
    if not os.path.exists(src):
        result['reason'] = '桌面兜底目录没有记忆文件'
        return result
    if os.path.abspath(target_dir) == os.path.abspath(fb):
        result['reason'] = '目标就是兜底目录，无需搬运'
        return result
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        result['reason'] = '目标目录不可建: %s' % e
        return result

    dst = memory_file_in(target_dir)
    src_data, dst_data = _read_json(src), _read_json(dst)

    if dst_data is not None:
        # 两边都有：留新的，**被淘汰的那份**挪到 memory.old.json 留档（不丢数据）。
        # 注意留档的必须是"落选者"：早期实现错把胜者抄进留档，等于白抄一遍还
        # 覆盖掉了真正的旧数据（自检 M4 抓到）。
        s_new = _saved_at(src_data) or _mtime(src)
        d_new = _saved_at(dst_data) or _mtime(dst)
        if s_new <= d_new:
            # 设备版更新 → 留设备版，把桌面那份留档
            if not _copy_verified(src, os.path.join(target_dir, ROLLBACK_FILENAME)):
                _log.warning("记忆留档失败，为保安全不删桌面副本")
                result['reason'] = '留档失败，保留桌面副本'
                result['kept'] = 'target'
                return result
            result['kept'] = 'target'
        else:
            # 桌面版更新 → 先把设备版留档，再用桌面版覆盖
            if not _copy_verified(dst, os.path.join(target_dir, ROLLBACK_FILENAME)):
                result['reason'] = '留档失败，保留桌面副本'
                result['kept'] = 'target'
                return result
            if not _copy_verified(src, dst):
                result['reason'] = '搬运失败（目标已有文件，未覆盖）'
                result['kept'] = 'target'
                return result
            result['kept'] = 'fallback'
    else:
        if not _copy_verified(src, dst):
            result['reason'] = '搬运复制失败，保留桌面副本'
            return result
        result['kept'] = 'fallback'

    result['moved'] = True

    # 到这里目标侧已经确认写好 → 才动桌面
    try:
        os.remove(src)
        result['removed_fallback_file'] = True
    except Exception as e:
        _log.warning("清理桌面记忆副本失败（不影响已搬运的数据）: %s", e)
        result['reason'] = '已搬入设备，但桌面副本删除失败: %s' % e
        return result

    tmp = src + '.tmp'
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except Exception:
            pass

    # 只在"确实空了"的前提下删掉空目录，绝不递归删
    try:
        if not os.listdir(fb):
            os.rmdir(fb)
            result['removed_fallback_dir'] = True
    except Exception as e:  # 修复：原先静默吞噬
        _log.debug("memory_store 防御性异常（已忽略）: %s", e)
    result['reason'] = '已搬入设备并清理桌面副本'
    return result


def describe():
    """给日志/自检用的一行状态。"""
    dev = find_device_dir(create=False)
    fb = fallback_dir()
    fb_has = os.path.exists(memory_file_in(fb))
    return {
        'device_dir': dev,
        'device_present': bool(dev),
        'fallback_dir': fb,
        'fallback_has_memory': fb_has,
        'active_dir': dev or fb,
        'ts': time.time(),
    }
