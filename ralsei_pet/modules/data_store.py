# -*- coding: utf-8 -*-
"""应用数据存储层（DataStore）—— 决定"宠物产生的文件最终放哪"。
==============================================================

用户原则（第十二轮，原话）：

    "所有他所产生的文件在本地最多算是中转站，只有在 E 盘才是最终储存的地方。"

于是本模块把"数据放哪"拆成两层，别处一律不许再自己拼路径：

  · **最终存储 vault**：卷标命中"肖翰哲"的驱动器下的 ``RalseiMemory\\``（即用户的 E 盘，
    与 `memory_store` 的设备发现逻辑共用同一套判定）；
  · **本地中转站 staging**：``%LOCALAPPDATA%\\RalseiPet\\``（E 盘不在线时的落脚点）。

**读路径永远是 vault 优先**：E 盘在线就直接写 E 盘；E 盘不在就落本地中转站，
等它上线后由 `migrate_from_staging()` 搬过去（copy → 校验长度 → 删源，先写成功再删）。

为什么必须这么设计（实测教训）
------------------------------
E 盘是**外接盘**：本机实测它会掉线（`Get-Volume` 一度只剩 C/D，物理磁盘只有一块 NVMe）。
所以"本地中转站"不是洁癖，而是**可用性必需** —— 没有它，E 盘一拔程序就写不了数据。
（第九轮曾把 E 判成"Fixed 固定盘、可安全当下载目录"，那个结论不完整，此处修正。）

收编历史遗留（adopt_legacy）
----------------------------
早期版本把 `config.json` / `customization_config.json` / `memory.json` / `logs/` 直接写在
程序目录 `ralsei_pet/`。这些文件在仓库里是**被 git 跟踪的默认模板**，所以收编时
**只复制、绝不移动或删除** —— 否则 git 会显示"默认配置被删了"这种假象。

本模块 import 时**不做任何磁盘操作**（第五轮冒烟测试会全量 import 所有模块）；
真正的建目录发生在 `artifact()` / `ensure_artifact()` 被调用的那一刻。
"""
import os
import shutil
import logging


class _LazyLogger(object):
    """**惰性**日志器 —— 刻意不在 import 期去 import `logger_utils`。

    为什么：`logger_utils` 初始化时要解析日志目录，而那个目录正是由本模块决定的
    （`_log_dir()` 内部会 `import data_store`）。如果本模块在 import 期就回头向
    logger 要日志器，就形成 `logger_utils ↔ data_store` 的**初始化环**：那一刻本模块
    还没执行完、`artifact_path` 还不存在，于是日志目录被**永久钉死在"程序目录兜底"**
    上（实测踩过：`logs/` 落到 `ralsei_pet/logs` 而不是数据根）。

    本模块 import 期本来也不打日志，等第一次真写日志时再解析即可 —— 环自然断开。
    """

    _impl = None

    def __getattr__(self, name):
        impl = _LazyLogger._impl
        if impl is None:
            try:
                from logger_utils import get_logger
                impl = get_logger(__name__)
            except Exception:
                impl = logging.getLogger(__name__)
            _LazyLogger._impl = impl
        return getattr(impl, name)


_log = _LazyLogger()


# 程序目录（ralsei_pet/），历史遗留文件都在这里
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 最终存储的目录名（与 memory_store.DEVICE_SUBDIR 保持一致，记忆就住在这个目录里）
VAULT_SUBDIR = 'RalseiMemory'
# 本地中转站的目录名（放在 %LOCALAPPDATA% 下）
STAGING_DIRNAME = 'RalseiPet'

KIND_VAULT = 'vault'
KIND_STAGING = 'staging'

# 测试/高级用户强制指定数据根（优先级最高，直接当最终存储用）
ENV_DATA_DIR = 'RALSEI_DATA_DIR'


# --------------------------------------------------------------------- 根目录解析
def _memory_store():
    """惰性拿 memory_store —— 避免 `logger_utils → data_store → memory_store → logger_utils` 循环。"""
    try:
        import memory_store as ms          # 常规：modules/ 已在 sys.path
        return ms
    except Exception:
        try:
            from . import memory_store as ms   # 包内导入
            return ms
        except Exception:
            return None


def vault_root(create=True):
    """最终存储根（`E:\\RalseiMemory`）；设备不在线返回 None。**绝不抛。**"""
    ms = _memory_store()
    if ms is None:
        return None
    try:
        return ms.find_device_dir(create=create)
    except Exception as e:
        _log.debug("查找最终存储设备失败（已忽略）: %s", e)
        return None


def staging_root(create=True):
    """本地中转站根（`%LOCALAPPDATA%\\RalseiPet`）。**绝不抛。**"""
    forced = os.environ.get(ENV_DATA_DIR)
    if forced:
        base = forced
    else:
        la = os.environ.get('LOCALAPPDATA')
        if not la:
            la = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
        base = os.path.join(la, STAGING_DIRNAME)
    if create:
        try:
            os.makedirs(base, exist_ok=True)
        except Exception as e:
            _log.warning("本地中转站目录创建失败 %s: %s", base, e)
    return base


def data_root(create=True):
    """当前该用的数据根。返回 `(路径, 'vault'|'staging')`。"""
    v = vault_root(create=create)
    if v:
        return v, KIND_VAULT
    return staging_root(create=create), KIND_STAGING


def artifact_path(relpath, ensure_dir=True):
    """把相对路径解析成"最终存储里的绝对路径"，并按需建父目录。

    `ensure_dir=False` 用于**只想知道路径、不想建目录**的场合（如探测用户词表在不在）。
    """
    root, _kind = data_root(create=True)
    path = os.path.join(root, relpath)
    if ensure_dir:
        parent = os.path.dirname(path)
        if parent:
            try:
                os.makedirs(parent, exist_ok=True)
            except Exception as e:
                _log.warning("数据目录创建失败 %s: %s", parent, e)
    return path


# 简写别名（写起来短一点）
artifact = artifact_path


def legacy_path(relpath):
    """程序目录里的历史遗留位置（如 `ralsei_pet/config.json`）。"""
    return os.path.join(APP_ROOT, relpath)


def ensure_artifact(relpath, legacy_relpath=None):
    """返回该数据的**正式路径**；若正式位置还没有、程序目录里有历史副本，则先复制过去。

    只复制、绝不移动/删除 —— 程序目录里那份在仓库里是被跟踪的默认模板，
    搬走会让 git 显示"默认配置被删"。复制失败也不抛，调用方拿默认值继续跑。
    """
    dst = artifact_path(relpath)
    try:
        if os.path.exists(dst):
            return dst
    except Exception:
        return dst
    if legacy_relpath:
        src = legacy_path(legacy_relpath)
        if os.path.exists(src):
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                _log.info("已把历史数据收编进最终存储: %s -> %s", src, dst)
            except Exception as e:
                _log.warning("收编历史数据失败（将使用默认值）%s: %s", src, e)
    return dst


def app_file(filename):
    """应用数据文件（如 `config.json`）：正式位置优先，首次运行从程序目录**收编一份副本**。

    只是 `ensure_artifact(filename, filename)` 的语义化写法 —— 让调用点读起来
    像"我要这个文件"，而不是"我要这个路径"。
    """
    return ensure_artifact(filename, filename)


# --------------------------------------------------------------------- 中转站 → 最终存储
def _same(a, b):
    try:
        return os.path.abspath(a) == os.path.abspath(b)
    except Exception:
        return False


def _movable(src):
    """探测源文件能否被搬走。

    Windows 上**正被写入的文件**（典型：日志）无法删除/重命名。先原地改名再改回来，
    失败就说明它被占用 —— 这样能在**动目标之前**就决定跳过，避免"复制成功但源删不掉"
    导致同一份数据在两边各留一个。
    """
    probe = src + '.migprobe'
    try:
        os.rename(src, probe)
    except OSError:
        return False
    try:
        os.rename(probe, src)
    except OSError:
        pass      # 极罕见：回不去就把探针当正式文件留着，至少不丢数据
    return True


def migrate_from_staging(remove_empty_dirs=True):
    """E 盘回来时，把本地中转站里的东西搬进最终存储。

    安全约定（与 `memory_store.migrate_from_fallback` 同一条铁律）：
      1. 先探测源文件**能否搬走**（被占用则跳过，留待下次），再 copy；
      2. copy 后**校验长度一致**，通过之后才删源；任何一步失败就保留源文件；
      3. 目标已存在同名的：比 mtime 留新的，落选的那份挪成 `<名字>.old`；
      4. 只在目录**确实空了**时才删空目录，绝不递归硬删。

    返回动作报告 dict（便于日志与自检）。
    """
    result = {'moved': [], 'skipped': [], 'errors': [],
              'kept': 'target', 'vault': None, 'staging': None}
    st = staging_root(create=True)
    v = vault_root(create=True)
    result['staging'] = st
    result['vault'] = v
    if not v:
        result['errors'].append('最终存储不在线，暂不搬运')
        return result
    if _same(v, st):
        result['errors'].append('中转站即最终存储，无需搬运')
        return result

    for dirpath, _dirs, files in os.walk(st):
        for name in files:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, st)
            if not _movable(src):
                result['skipped'].append('%s（源被占用，留待下次）' % rel)
                continue
            dst = os.path.join(v, rel)
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    try:
                        if os.path.getmtime(src) <= os.path.getmtime(dst):
                            result['skipped'].append(rel)
                            continue
                        shutil.copy2(dst, dst + '.old')   # 目标版更旧 → 先留档
                    except Exception as e:
                        result['errors'].append('%s: 留档失败 %s' % (rel, e))
                        continue
                shutil.copy2(src, dst)
                if os.path.getsize(src) != os.path.getsize(dst):
                    result['errors'].append('%s: 长度校验不一致，保留源文件' % rel)
                    continue
                os.remove(src)
                result['moved'].append(rel)
            except Exception as e:
                result['errors'].append('%s: %s' % (rel, e))

    if remove_empty_dirs:
        # 自底向上删空目录；只删"确实空了"的，且绝不越过中转站根
        for dirpath, _dirs, _files in os.walk(st, topdown=False):
            if _same(dirpath, st):
                continue
            try:
                if not os.listdir(dirpath):
                    os.rmdir(dirpath)
            except Exception:
                pass
    return result


def staging_has_data():
    """中转站里是否还有东西（用来判断"要不要提示用户插 E 盘"）。"""
    st = staging_root(create=False)
    try:
        for _dp, _dirs, files in os.walk(st):
            if files:
                return True
    except Exception:
        pass
    return False


def describe():
    """给日志/自检用的一行状态。"""
    dev = vault_root(create=False)
    st = staging_root(create=False)
    root, kind = data_root(create=False)
    return {
        'vault_dir': dev,
        'vault_online': bool(dev),
        'staging_dir': st,
        'active_dir': root,
        'active_kind': kind,
        'staging_has_data': staging_has_data(),
    }
