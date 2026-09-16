# -*- coding: utf-8 -*-
"""第十二轮验证：jieba 分词接入 + "E 盘是最终存储、本地只作中转站"。

为什么有这一轮
--------------
用户两条要求：
  1. **接入 jieba 分词库**（第十一轮预留了 `conversation_focus.set_segmenter` 注入点）；
  2. 确认并落实一条原则：**"所有它产生的文件，本地最多算是中转站，只有在 E 盘才是
     最终储存的地方。"** —— 第九轮只把 `memory.json` 放到了 E 盘（`E:\\RalseiMemory`），
     而 `logs/` `config.json` `customization_config.json` `entertainment_data.json`
     `growth_data.json` 全都还在程序目录里堆着。

实测发现（这轮最该记住的事）
----------------------------
**E 盘会掉线。** 开工时它还挂着（卷标「肖翰哲」，被识别成 Fixed），中途 `Get-Volume`
只剩 C/D、`Get-Disk` 只有一块 NVMe —— 它是**外接盘**。所以"本地中转站"不是洁癖，
是**可用性必需**：没有它，E 盘一拔程序就写不了数据。
（第九轮把它判成"Fixed 固定盘、可安全当下载目录"，那个结论不完整，本报告里更正。）

分组
----
  A jieba 接入（可用性 / 注入 / 碎片对比 / 回落 / 标点过滤 / 缓存与词表路径 / 计数）
  B data_store（env 覆盖 / staging 位置 / artifact 解析 / 收编模板 / 迁移五条安全约定）
  C 接线（7 类运行时产物全部落在数据根内 + 两种导入顺序 + 仓库模板未被搬走）
  D 回归守卫（初始化环不许复活 / 重入护栏 / 失败不缓存 / main 接线 / 源码级约束）

全程把 RALSEI_DATA_DIR / RALSEI_MEMORY_DIR / RALSEI_DESKTOP 指向临时目录 ——
**绝不碰真机数据**。必须用 C:\\Python311\\python.exe 运行。
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
APP = os.path.join(ROOT, 'ralsei_pet')
TMP = tempfile.mkdtemp(prefix='ralsei_g12_')

# —— 环境隔离：绝不碰真机 ——
os.environ['RALSEI_DESKTOP'] = os.path.join(TMP, 'Desktop')
os.environ['RALSEI_DATA_DIR'] = os.path.join(TMP, 'staging')
os.environ.pop('RALSEI_MEMORY_DIR', None)
os.environ['RALSEI_MEMORY_DEVICE'] = 'off'        # 默认"E 盘不在线"
os.makedirs(os.environ['RALSEI_DESKTOP'], exist_ok=True)

if MODS not in sys.path:
    sys.path.insert(0, MODS)

import data_store                       # noqa: E402
import text_segmenter                   # noqa: E402
import conversation_focus as CF         # noqa: E402

PASS, FAIL = [], []


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('[PASS] ' if cond else '[FAIL] ') + name +
          ('' if cond else '   <<< ' + str(detail)))


def section(title):
    print('')
    print('=== %s ===' % title)


def code_only(path):
    """剥注释与字符串的源码（tokenize 不产空白 token → ' '.join 保分隔）。"""
    return _tokens(path, strip_string=True)


def code_no_comment(path):
    """只剥注释、**保留字符串字面量** —— needle 里带字面量时用这个。"""
    return _tokens(path, strip_string=False)


def _tokens(path, strip_string):
    out = []
    try:
        with open(path, 'rb') as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type == tokenize.COMMENT:
                    continue
                if strip_string and tok.type == tokenize.STRING:
                    continue
                out.append(tok.string)
    except Exception:
        return ''
    return ' '.join(out)


def has(src, needle):
    import re
    return re.sub(r'\s+', '', needle) in re.sub(r'\s+', '', src)


# ============================================================ A jieba
section('A jieba 分词接入')

st0 = text_segmenter.status()
ok('A1 install() 返回状态字典且永不抛（无 jieba 也安全）',
   isinstance(text_segmenter.install(), dict), st0)

st = text_segmenter.status()
JIEBA_OK = bool(st.get('enabled'))
ok('A2 本机 jieba 已接入（status.enabled=True）', JIEBA_OK, st)
ok('A3 注入后 conversation_focus 的 _SEGMENTER 非 None',
   (CF._SEGMENTER is not None) if JIEBA_OK else True, CF._SEGMENTER)

# 内置词法基准（先摘掉分词器再测）
text_segmenter.disable()
ok('A4 disable() 后回到内置词法（_SEGMENTER 为 None）', CF._SEGMENTER is None, CF._SEGMENTER)

BUILTIN = {}
for s in ('我明天想写点代码', '今天想聊聊塞尔达这游戏的剧情',
          '学习编程需要花不少时间', '今天下雨会有点冷吧',
          '刚喝了杯咖啡感觉还行', '明天开会吗'):
    BUILTIN[s] = CF.extract_keywords(s)

text_segmenter.install()
SEG = {}
for s in BUILTIN:
    SEG[s] = CF.extract_keywords(s)

if JIEBA_OK:
    frag = ('习编', '习编程', '编程需', '程需', '少时', '少时间',
            '咖啡感', '啡感', '天下', '天开', '尔达')
    left = sorted({w for s in SEG for w in SEG[s] if w in frag})
    ok('A5 接入 jieba 后残渣碎片清零（内置词法有、jieba 没有）', not left, left)

    ok('A6 「塞尔达」不再被切成 塞尔/尔达',
       ('塞尔达' in SEG['今天想聊聊塞尔达这游戏的剧情'])
       and ('尔达' not in SEG['今天想聊聊塞尔达这游戏的剧情']),
       SEG['今天想聊聊塞尔达这游戏的剧情'])

    b = BUILTIN['学习编程需要花不少时间']
    a = SEG['学习编程需要花不少时间']
    ok('A7 长句词条数显著下降（%d → %d）' % (len(b), len(a)), len(a) < len(b), (b, a))

    n_b = sum(len(v) for v in BUILTIN.values())
    n_a = sum(len(v) for v in SEG.values())
    ok('A8 六句词条总数下降（%d → %d）' % (n_b, n_a), n_a < n_b, (n_b, n_a))

    ok('A9 「咖啡」不再拖出 咖啡感/啡感',
       '咖啡' in SEG['刚喝了杯咖啡感觉还行']
       and not ({'咖啡感', '啡感'} & set(SEG['刚喝了杯咖啡感觉还行'])),
       SEG['刚喝了杯咖啡感觉还行'])

ok('A10 分词器输出里没有纯标点（「……」这类不再穿过长度门槛）',
   not any(w.strip('…—。，、！？：；') == '' for s in SEG.values() for w in s),
   SEG)

ok('A11 词典缓存在数据根内（不再堆 %TEMP%）',
   text_segmenter.default_cache_path().startswith(data_store.data_root(create=False)[0]),
   text_segmenter.default_cache_path())
ok('A12 用户词表路径在数据根内',
   text_segmenter.default_userdict_path().startswith(data_store.data_root(create=False)[0]),
   text_segmenter.default_userdict_path())

st2 = text_segmenter.status()
ok('A13 有调用计数与回落计数（防御性 except 必须配计数）',
   isinstance(st2.get('calls'), int) and isinstance(st2.get('fallbacks'), int)
   and st2['calls'] > 0, st2)
ok('A14 describe() 给出可读中文状态', '分词引擎' in text_segmenter.describe(),
   text_segmenter.describe())

# 分词器抛异常 → 上层回落内置词法（不许崩）
_orig = CF._SEGMENTER


def _boom(_t):
    raise RuntimeError('boom')


CF.set_segmenter(_boom)
try:
    got = CF.extract_keywords('我明天想写点代码')
    ok('A15 分词器抛异常时静默回落内置词法（不崩、不空）',
       isinstance(got, list) and len(got) > 0, got)
except Exception as e:
    ok('A15 分词器抛异常时静默回落内置词法（不崩、不空）', False, e)

CF.set_segmenter(None)
ok('A16 分词器返回空 → 同样回落内置（不返回空）',
   len(CF.extract_keywords('我明天想写点代码')) > 0)
CF.set_segmenter(_orig)

# ============================================================ B data_store
section('B data_store：最终存储 / 本地中转站')

root, kind = data_store.data_root(create=True)
ok('B1 RALSEI_DATA_DIR 覆盖生效', os.path.abspath(root) == os.path.abspath(os.environ['RALSEI_DATA_DIR']),
   (root, kind))
ok('B2 无设备时 active_kind=staging', kind == data_store.KIND_STAGING, kind)

os.environ.pop('RALSEI_DATA_DIR', None)
stg = data_store.staging_root(create=True)
ok('B3 默认中转站在 LOCALAPPDATA 下（不落程序目录）',
   'RalseiPet' in stg and os.path.abspath(stg) != os.path.abspath(APP), stg)
os.environ['RALSEI_DATA_DIR'] = os.path.join(TMP, 'staging')

p = data_store.artifact_path(os.path.join('logs', 'x.log'))
ok('B4 artifact_path 拼接正确且建父目录',
   p.endswith(os.path.join('logs', 'x.log')) and os.path.isdir(os.path.dirname(p)), p)

q = data_store.artifact_path(os.path.join('nope', 'y.txt'), ensure_dir=False)
ok('B5 ensure_dir=False 只算路径、不建目录', not os.path.isdir(os.path.dirname(q)), q)

# 收编历史模板：复制、不覆盖
_cfg = data_store.app_file('config.json')
_src_cfg = os.path.join(APP, 'config.json')
ok('B6 app_file 把程序目录的模板收编一份到数据根',
   os.path.exists(_cfg) and os.path.exists(_src_cfg)
   and os.path.getsize(_cfg) == os.path.getsize(_src_cfg), _cfg)

marker = '{"_probe": "user-edited"}'
with io.open(_cfg, 'w', encoding='utf-8') as f:
    f.write(marker)
_again = data_store.app_file('config.json')
with io.open(_again, 'r', encoding='utf-8') as f:
    content = f.read()
ok('B7 已存在时不覆盖（绝不拿模板盖掉用户配置）', content == marker, content)
ok('B8 程序目录里的模板仍在（只复制、不搬走，git 不出现"删默认配置"）',
   os.path.exists(_src_cfg))

# ---- 迁移：staging → vault ----
_stg = os.path.join(TMP, 'mig_staging')
_vlt = os.path.join(TMP, 'mig_vault')
os.environ['RALSEI_DATA_DIR'] = _stg
os.environ['RALSEI_MEMORY_DIR'] = _vlt
os.makedirs(os.path.join(_stg, 'logs'), exist_ok=True)
os.makedirs(_stg, exist_ok=True)


def _w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(text)


_w(os.path.join(_stg, 'config.json'), 'staging-config')
_w(os.path.join(_stg, 'logs', 'a.log'), 'log-a')
_w(os.path.join(_stg, 'sub', 'deep.txt'), 'deep')

rep = data_store.migrate_from_staging()
moved = set(rep.get('moved') or [])
ok('B9 vault 在线 → 中转站文件全部搬入（含子目录）',
   {'config.json', os.path.join('logs', 'a.log'), os.path.join('sub', 'deep.txt')} <= moved, rep)
ok('B10 搬完源文件已删（copy→校验→删源）',
   not os.path.exists(os.path.join(_stg, 'config.json'))
   and not os.path.exists(os.path.join(_stg, 'logs', 'a.log')), rep)
ok('B11 目标内容正确', os.path.exists(os.path.join(_vlt, 'sub', 'deep.txt')), rep)
ok('B12 空目录被清掉（但绝不递归硬删）', not os.path.isdir(os.path.join(_stg, 'logs')), rep)

# 目标更新 → 留新的，落选者挪 .old
os.makedirs(_stg, exist_ok=True)
_w(os.path.join(_stg, 'config.json'), 'staging-newer')
os.utime(os.path.join(_vlt, 'config.json'), (time.time() - 3600, time.time() - 3600))
rep2 = data_store.migrate_from_staging()
with io.open(os.path.join(_vlt, 'config.json'), 'r', encoding='utf-8') as f:
    kept = f.read()
ok('B13 两边同名时留新的（新内容胜出）', kept == 'staging-newer', kept)
ok('B14 落选者挪成 .old 留档（不丢数据）',
   os.path.exists(os.path.join(_vlt, 'config.json.old')), rep2)

# 源比目标旧 → 目标（vault）胜出，落选的**源**也要留档成 .old 并清出"中转站"。
# 若只是 skip：中转站会永远残留这份文件、staging_has_data() 恒为 True，
# "本地只作中转站"就落空了（E 盘真机确认时实测到 logs/ralsei_pet.log 卡在这里）。
os.makedirs(_stg, exist_ok=True)
_w(os.path.join(_stg, 'only-old.txt'), 'from-staging-old')
_w(os.path.join(_vlt, 'only-old.txt'), 'vault-newer')
_old_t = time.time() - 7200
os.utime(os.path.join(_stg, 'only-old.txt'), (_old_t, _old_t))
rep2b = data_store.migrate_from_staging()


def _read(p):
    try:
        with io.open(p, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


ok('B19 源比目标旧 → 目标胜出 + 落选源留档 .old + 中转站不再残留',
   _read(os.path.join(_vlt, 'only-old.txt')) == 'vault-newer'
   and _read(os.path.join(_vlt, 'only-old.txt.old')) == 'from-staging-old'
   and not os.path.exists(os.path.join(_stg, 'only-old.txt')), rep2b)

# vault 离线 → 不动数据
os.environ.pop('RALSEI_MEMORY_DIR', None)
os.environ['RALSEI_MEMORY_DEVICE'] = 'off'
os.makedirs(_stg, exist_ok=True)
_w(os.path.join(_stg, 'keepme.txt'), 'keep')
rep3 = data_store.migrate_from_staging()
ok('B15 vault 离线时不搬运、数据原样保留',
   os.path.exists(os.path.join(_stg, 'keepme.txt')) and not rep3.get('moved'), rep3)

# 被占用的文件 → 跳过而不是报错/重复
os.environ['RALSEI_MEMORY_DIR'] = _vlt
os.environ.pop('RALSEI_MEMORY_DEVICE', None)
_locked = os.path.join(_stg, 'locked.txt')
_w(_locked, 'locked-data')
_fh = io.open(_locked, 'r')
try:
    import msvcrt
    msvcrt.locking(_fh.fileno(), msvcrt.LK_NBLCK, 1)
except Exception:
    pass
rep4 = data_store.migrate_from_staging()
_fh.close()
ok('B16 源文件被占用 → 记入 skipped 且不产生重复副本',
   any('locked.txt' in s for s in (rep4.get('skipped') or []))
   and not os.path.exists(os.path.join(_vlt, 'locked.txt')), rep4)

# 中转站即最终存储 → 不动
os.environ['RALSEI_MEMORY_DIR'] = _stg
rep5 = data_store.migrate_from_staging()
ok('B17 中转站与最终存储是同一个目录时拒绝搬运',
   bool(rep5.get('errors')) and not rep5.get('moved'), rep5)

os.environ['RALSEI_DATA_DIR'] = os.path.join(TMP, 'staging')
os.environ.pop('RALSEI_MEMORY_DIR', None)
os.environ['RALSEI_MEMORY_DEVICE'] = 'off'
d = data_store.describe()
ok('B18 describe() 暴露两种存储与在线状态',
   all(k in d for k in ('vault_dir', 'vault_online', 'staging_dir', 'active_dir', 'active_kind')), d)

# ============================================================ C 接线
section('C 接线：运行时产物是否都进数据根')

DATA_ROOT = data_store.data_root(create=False)[0]
import types                                    # noqa: E402
stub = types.SimpleNamespace()

paths = {}
try:
    from config_manager import ConfigManager
    paths['config.json'] = ConfigManager().config_file
except Exception as e:
    paths['config.json'] = 'ERR %s' % e
try:
    from customization_system import CustomizationSystem
    paths['customization_config.json'] = CustomizationSystem(stub).config_path
except Exception as e:
    paths['customization_config.json'] = 'ERR %s' % e
try:
    from entertainment_system import EntertainmentSystem
    paths['entertainment_data.json'] = EntertainmentSystem(stub).entertainment_data_path
except Exception as e:
    paths['entertainment_data.json'] = 'ERR %s' % e
try:
    from social_growth_system import SocialGrowthSystem
    paths['growth_data.json'] = SocialGrowthSystem(stub).growth_data_path
except Exception as e:
    paths['growth_data.json'] = 'ERR %s' % e
try:
    import logger_utils
    paths['logs/'] = logger_utils.get_log_dir()
except Exception as e:
    paths['logs/'] = 'ERR %s' % e

for name in ('config.json', 'customization_config.json', 'entertainment_data.json',
             'growth_data.json', 'logs/'):
    v = paths.get(name, '')
    ok('C1 产物在数据根内：%s' % name, isinstance(v, str) and v.startswith(DATA_ROOT), v)

# 两种导入顺序都要正确（初始化环的回归锁）。
# **必须有鉴别力**：让"正确的 vault 路径"和"错误的中转站路径"是**两个不同目录**，
# 否则断言恒真。第十二轮初版就踩了这个坑 —— 环境里 RALSEI_DATA_DIR 把中转站钉成了
# 数据根、又把设备强制关掉，于是无论有没有环，日志目录都等于同一个值，弱断言永远 PASS，
# 间接环（logger_utils → data_store → memory_store → logger_utils）因此漏网。
# 这里用 RALSEI_MEMORY_DIR 模拟"E 盘在线"，其路径刻意与 staging 不同。
_VAULT_SIM = os.path.join(TMP, 'vault_sim')
_ENV_V = dict(os.environ)
_ENV_V['RALSEI_MEMORY_DIR'] = _VAULT_SIM       # 模拟在线 vault（优先级高于设备开关）
_ENV_V.pop('RALSEI_MEMORY_DEVICE', None)
_EXPECT_LOGDIR = os.path.abspath(os.path.join(_VAULT_SIM, 'logs'))


def _child_logdir(tag, first):
    body = ['import sys, io, os', 'sys.path.insert(0, r"%s")' % MODS,
            'import %s' % first, 'import logger_utils',
            'io.open(r"%s", "w", encoding="utf-8").write(logger_utils.get_log_dir())'
            % os.path.join(TMP, 'order_%s.txt' % tag)]
    p = subprocess.run([sys.executable, '-c', '\n'.join(body)],
                       capture_output=True, env=_ENV_V)
    got = ''
    try:
        with io.open(os.path.join(TMP, 'order_%s.txt' % tag), 'r', encoding='utf-8') as f:
            got = f.read()
    except Exception:
        pass
    return p, got


for _tag, _first in (('ds_first', 'data_store'), ('lg_first', 'logger_utils')):
    _p, _got = _child_logdir(_tag, _first)
    ok('C2 先 import %s：日志目录仍落在 vault 而非中转站' % _first,
       _p.returncode == 0 and os.path.abspath(_got) == _EXPECT_LOGDIR,
       (_p.returncode, 'got=%s' % _got, 'expect=%s' % _EXPECT_LOGDIR,
        _p.stderr.decode('utf-8', 'replace')[:200]))

_bad = []
for fn in sorted(os.listdir(MODS)):
    if fn.endswith('.py') and not fn.startswith('_'):
        try:
            __import__(fn[:-3])
        except Exception as e:
            _bad.append('%s: %s' % (fn, e))
ok('C3 全量模块导入零失败', not _bad, _bad)

ok('C4 仓库里的 config.json 模板仍在（迁移没把它搬走）', os.path.exists(os.path.join(APP, 'config.json')))
ok('C5 memory_store 的桌面兜底语义未被改动（仍是 <桌面>/memory）',
   os.path.abspath(data_store._memory_store().fallback_dir())
   == os.path.abspath(os.path.join(os.environ['RALSEI_DESKTOP'], 'memory')),
   data_store._memory_store().fallback_dir())

# ============================================================ D 回归守卫
section('D 回归守卫（源码级）')

_src_ds = code_only(os.path.join(MODS, 'data_store.py'))
_src_ds_nc = code_no_comment(os.path.join(MODS, 'data_store.py'))
_src_lg = code_only(os.path.join(MODS, 'logger_utils.py'))
_src_ll = code_only(os.path.join(MODS, 'lazy_log.py'))
_src_ms = code_only(os.path.join(MODS, 'memory_store.py'))
_src_main = code_no_comment(os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'))

ok('D0 助手自检：含字面量的 needle 只有 code_no_comment 才找得到',
   (not has(_src_ds, "artifact_path('logs')")) or has(_src_ds_nc, "artifact_path"),
   'needle 里带引号时 code_only 会漏')

ok('D1 底层模块（data_store / memory_store）走共享惰性日志器 lazy_log',
   has(_src_ds, 'from lazy_log import LazyLogger')
   and has(_src_ms, 'from lazy_log import LazyLogger')
   and has(_src_ll, 'class LazyLogger') and has(_src_ll, 'def __getattr__'), '')
ok('D11 memory_store 不在 import 期 import logger_utils（间接环回归锁）',
   not has(_src_ms, 'import logger_utils'), '改回模块级 get_logger 会重现 E 盘日志目录被钉到中转站')
ok('D12 lazy_log 模块顶层不碰 logger_utils（惰性才成立）',
   'logger_utils' not in _src_ll.split('def ')[0], '')
ok('D2 logger_utils 有重入护栏 _initializing',
   has(_src_lg, '_initializing') and has(_src_lg, '_init_logging_impl'), '')
ok('D3 _log_dir 解析失败时**不缓存**兜底值（否则会永久钉错目录）',
   has(_src_lg, 'return _FALLBACK_LOG_DIR') and '_LOG_DIR = _FALLBACK_LOG_DIR' not in _src_lg, '')
ok('D4 main.py 启动时接入分词器', has(_src_main, 'text_segmenter.install()'), '')
ok('D5 main.py 启动时做数据回迁', has(_src_main, 'migrate_from_staging()'), '')
ok('D6 main.py 崩溃日志走 data_store', has(_src_main, 'data_store.artifact_path'), '')
ok('D7 迁移铁律：先 copy → 校验长度 → 才删源',
   has(_src_ds, 'os.path.getsize(src) != os.path.getsize(dst)') and has(_src_ds, 'os.remove(src)'), '')
ok('D8 迁移铁律：被占用的源文件先探测再动目标（不产生重复副本）',
   has(_src_ds, 'def _movable'), '')
ok('D9 data_store 在 import 期不碰磁盘（data_root 不在模块顶层调用）',
   'data_root(create=' not in _src_ds.split('def ')[0], '')
ok('D10 四个数据模块都改用 data_store.app_file',
   all(has(code_only(os.path.join(MODS, f)), 'data_store.app_file') for f in
       ('config_manager.py', 'customization_system.py',
        'entertainment_system.py', 'social_growth_system.py')), '')

# ============================================================ 收尾
print('')
print('=' * 62)
print('第十二轮自检：%d PASS / %d FAIL' % (len(PASS), len(FAIL)))
for f in FAIL:
    print('  FAIL: ' + f)
print('=' * 62)

try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass

sys.exit(1 if FAIL else 0)
