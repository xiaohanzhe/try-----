# -*- coding: utf-8 -*-
"""中文分词接入层（jieba → `conversation_focus.set_segmenter`）
==============================================================

第十二轮：用户要求"接入 jieba 分词库"。第十一轮已经把**注入点**准备好了
（`conversation_focus.set_segmenter(fn)` + 三层择优），本模块只做一件事：
**把 jieba 包装成一个安全的 segmenter 函数交给它**，并保证 jieba 出任何问题
（没装 / 字典加载失败 / 调用抛异常）都**静默回落内置词法**，绝不打断对话。

为什么单独一层，而不是直接在 `conversation_focus` 里 `import jieba`：

1. **`conversation_focus` 不许有硬依赖**。它被话题锚（对话注意力）和记忆抽词两处
   共用，是"抽不到词整条链路哑掉"的关键模块。jieba 只是**可选的更好边界判断**，
   没有它也必须能跑（打包/换机器/用户没装）。
2. **jieba 初始化很贵**（首次 `initialize()` 要建前缀字典，约 1~2 秒、占几十 MB）。
   只在 `main.py` 启动时显式 `install()`，不在 import 期做 —— 这样 G2 回归里的
   各套件（offscrreen 跑、不启动 main）行为**完全确定**，不会被"本机装没装 jieba"影响。
3. 需要一个地方记录**降级事实**（是否启用、引擎是谁、调用/回落计数），
   供自检与日志查看 —— 呼应第八轮教训"防御性 except 必须配异常计数"。

过滤分工：本模块**只把 jieba 的原始词条整理干净**（去空白、丢掉纯标点/纯符号），
长度门槛、停用词、去重一律交给 `conversation_focus._from_segmenter` 处理 ——
保持"停用词表只有一份"（在 `conversation_focus` 里），不搞两套标准。

自定义词表：可选地从数据目录读一份 `jieba_userdict.txt`（每行 `词 [词频 [词性]]`，
jieba 原生格式）。这解决了"内置词法把 `塞尔达` 切成 `塞尔/尔达`"这类**专名词**残渣 ——
用户往这个文件里加一行，下次启动就认得。文件不存在就跳过，不是错误。

本模块 import 时**不做任何磁盘/字典操作**（第五轮冒烟测试会全量 import 所有模块）。
"""
import os
import re
import threading

try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:  # 模块外独立导入时的降级
    import logging
    _log = logging.getLogger(__name__)

ENV_USERDICT = 'RALSEI_JIEBA_USERDICT'
USERDICT_FILENAME = 'jieba_userdict.txt'

# 只保留"含实义字符"的词条：中文、字母、数字。纯标点（如 `……`、`——`）整条丢掉，
# 否则它们长度≥2，会一路穿过 `_from_segmenter` 的长度门槛变成假关键词。
_WORD_RE = re.compile(r'[0-9A-Za-z\u4e00-\u9fff]')

# 词典预热线程（守护线程，失败无副作用）
_preload_thread = None

# 运行状态（供自检/日志观测；不要直接改，用 install()/disable()）
_state = {
    'engine': 'none',      # 'jieba' | 'none'
    'ready': False,        # 分词器当前是否已注入
    'userdict': '',        # 实际加载的用户词表路径（空 = 没加载）
    'calls': 0,            # 分词器被调用次数
    'fallbacks': 0,        # 调用中异常 → 回落的次数
    'error': '',           # 最近一次失败原因（诊断用）
}
_lock = threading.Lock()


def _clean(words):
    """把 jieba 的输出整理成"干净的词条列表"（过滤在 `_from_segmenter` 里做）。"""
    out = []
    for w in words:
        try:
            w = str(w or '').strip()
        except Exception:
            continue
        if w and _WORD_RE.search(w):
            out.append(w)
    return out


def _make_segmenter(jieba_mod):
    """把 jieba 包成 `fn(text) -> list[str]`；内部异常计数后向上抛（由上层回落）。"""
    def _segment(text):
        with _lock:
            _state['calls'] += 1
        try:
            return _clean(jieba_mod.lcut(str(text or '')))
        except Exception:
            with _lock:
                _state['fallbacks'] += 1
            raise
    return _segment


def _load_userdict(jieba_mod, path):
    """加载用户词表；返回实际路径或空串（文件不存在/加载失败都不算错误）。"""
    if not path or not os.path.isfile(path):
        return ''
    try:
        jieba_mod.load_userdict(path)
        return path
    except Exception as e:
        _log.warning("jieba 用户词表加载失败（已忽略）: %s (%s)", path, e)
        return ''


def default_userdict_path():
    """默认用户词表位置：数据目录（E 盘最终存储优先）下的 `jieba_userdict.txt`。"""
    forced = os.environ.get(ENV_USERDICT)
    if forced:
        return forced
    try:
        import data_store
        return data_store.artifact_path(USERDICT_FILENAME, ensure_dir=False)
    except Exception:
        return ''


def default_cache_path():
    """jieba 前缀词典缓存的落点：数据目录（E 盘优先）下的 `cache/jieba.cache`。

    jieba 默认把缓存 dump 到 `%TEMP%\\jieba.cache` —— 那同样是"它产生的文件"，
    按用户原则（本地最多是中转站）一并收进数据目录，顺带让缓存跟着数据走。
    """
    try:
        import data_store
        return data_store.artifact_path(os.path.join('cache', 'jieba.cache'), ensure_dir=True)
    except Exception:
        import tempfile
        return os.path.join(tempfile.gettempdir(), 'jieba.cache')


def install(userdict=None, preload=True):
    """初始化 jieba 并注入 `conversation_focus`；任何失败都只记录、不抛出。

    返回状态 dict（等于 `status()`）。`preload=True` 会在后台线程预热词典，
    避免"用户发的第一句话卡 1~2 秒"。
    """
    global _preload_thread
    try:
        import jieba
    except Exception as e:
        with _lock:
            _state.update({'engine': 'none', 'ready': False,
                           'error': 'jieba 不可用: %s' % e})
        _log.info("未启用 jieba 分词（回落内置词法）: %s", e)
        return status()

    # 词典缓存改到数据目录（必须在 initialize() 之前设，否则缓存会落 %TEMP%）
    try:
        jieba.dt.cache_file = default_cache_path()
    except Exception as e:
        _log.debug("jieba 缓存路径设置失败（将用默认 temp）: %s", e)

    ud = userdict if userdict is not None else default_userdict_path()
    loaded_ud = _load_userdict(jieba, ud)

    try:
        import conversation_focus as _cf
        _cf.set_segmenter(_make_segmenter(jieba))
    except Exception as e:
        with _lock:
            _state.update({'engine': 'none', 'ready': False,
                           'error': '注入失败: %s' % e})
        _log.warning("jieba 分词器注入失败（回落内置词法）: %s", e)
        return status()

    with _lock:
        _state.update({'engine': 'jieba', 'ready': True,
                       'userdict': loaded_ud, 'error': ''})

    if preload:
        _preload_thread = _start_preload(jieba)

    _log.info("已启用 jieba 分词（用户词表: %s）", loaded_ud or '无')
    return status()


def _start_preload(jieba_mod):
    """后台预热 jieba 词典（守护线程，失败无副作用）。"""
    def _work():
        try:
            jieba_mod.initialize()
        except Exception as e:
            _log.debug("jieba 词典预热失败（首次调用时会再试）: %s", e)

    t = threading.Thread(target=_work, name='jieba-preload', daemon=True)
    t.start()
    return t


def disable():
    """撤掉分词器，恢复内置词法（测试/排障用）。"""
    try:
        import conversation_focus as _cf
        _cf.set_segmenter(None)
    except Exception as e:
        _log.debug("撤销分词器失败（已忽略）: %s", e)
    with _lock:
        _state.update({'engine': 'none', 'ready': False})
    return status()


def status():
    """当前状态快照（自检/日志用）。"""
    with _lock:
        snap = dict(_state)
    snap['enabled'] = bool(snap.get('ready'))
    return snap


def describe():
    """给日志看的一行中文描述。"""
    s = status()
    if not s['enabled']:
        return '分词引擎：内置词法（未启用，原因：%s）' % (s.get('error') or '未安装')
    return '分词引擎：jieba（调用 %d 次，回落 %d 次，用户词表：%s）' % (
        s.get('calls', 0), s.get('fallbacks', 0), s.get('userdict') or '无')
