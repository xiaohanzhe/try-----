# -*- coding: utf-8 -*-
"""第57轮 · 7B 模型运转 / 并发上限 回归锁（`check57`）。

用户口径（逐字，本套件的唯一真源）
--------------------------------
「然后再次复检全部，尤其是那些7B模型的运转与多个同时运转且不特别影响性能的最大是多少」

本套件要钉住的**三条结论**（它们都是实测得出的，不是猜的）
--------------------------------------------------------
① **Ollama（纯 CPU）对并发请求是串行的，零并行**。
   判据：每波并发 `wall ≈ Σ(各请求 prefill + decode)`（误差 < 10%）。
   为什么不用 `Σ total`：`total` 含**排队等待**，串行/并行下 `max(total)` 都等于 wall，
   **那个判据没有鉴别力**（本套件第一版就写错过，见 C2b 负控制）。
② **单请求速率与并发数无关**（冷 prefill ≈ 27~29 ms/token、decode ≈ 145~161 ms/token，
   跨 N=2..6 恒定）⇒ "并发数"不降低单请求性能，只让**等待**线性增长。
③ **真正决定首字的是 KV 前缀缓存是否命中**（热 0.06 ms/token ↔ 冷 27.7 ms/token，差 460 倍）；
   实测前缀缓存容量 ≥ 6（13 人档见 C7b），但 **`keep_alive` 默认 5 分钟卸载模型 ⇒ 缓存全丢**。

四段
----
  A 配置锚点（App 实际用的句柄 / 注册表的模型策略 / 人设量级）
  B 产品接线事实（请求怎么发出去的、有几条路径、**有没有并发闸**）
  C 实测判据（读 `_evidence/*.json`，可复跑、不进真机、不联网）
  D 结论与天花板（打印；不做环境耦合的硬断言）

设计纪律（沿用本项目）
---------------------
* **能读文件就不联网**；`_evidence` 里的 JSON 是**已跑过的实测产物**，这里只做断言；
* 每条结论都配**负控制**（把判据写窄/写反必须报红）；
* 阈值取**宽区间**（别人换机器跑也应是同一量级），只锁"结构"不锁"具体秒数"。
"""
import ast
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src')
MODULES = os.path.join(PET, 'modules')
EVID = os.path.join(HERE, '_evidence')
NPC_DIR = os.path.join(PET, 'assets', 'npc')
PERSONA_DIR = os.path.join(NPC_DIR, 'persona')

FAILS = []
N = [0]


def check(name, cond, extra=''):
    N[0] += 1
    if cond:
        print('[PASS] %s %s' % (name, extra))
    else:
        print('[FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def read_text(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def read_json(p, default=None):
    try:
        return json.loads(read_text(p))
    except Exception:
        return default


def _nz(t):
    """纳秒 → 秒。"""
    return (t or 0) / 1e9


print('=' * 78)
print('【A】配置锚点 —— App 到底在用哪个模型')
print('=' * 78)

_cfg = read_json(os.path.join(PET, 'config.json'), {})
_api = _cfg.get('api') if isinstance(_cfg, dict) else {}
_api = _api if isinstance(_api, dict) else {}

check('A1  config.json 的 api.model == ralsei:v4（这是 NPC 与 Ralsei 共用的那个 7B 句柄）',
      _api.get('model') == 'ralsei:v4', '实际=%r' % _api.get('model'))
check('A2  api.enabled 为真（否则下面的接线断言都是空谈）', bool(_api.get('enabled')),
      'enabled=%r' % _api.get('enabled'))
check('A3  走的是流式（本项目"首字铁律"的前提）', bool(_api.get('stream')),
      'stream=%r' % _api.get('stream'))
_t = _api.get('timeout')
check('A4  timeout >= 60s（★冷 prefill 70~110s ⇒ 老默认 30s 会把正常请求判成超时）',
      isinstance(_t, (int, float)) and _t >= 60, 'timeout=%r' % _t)

_reg = read_json(os.path.join(NPC_DIR, '_registry.json'), {})
_npcs = _reg.get('npcs') or []
_pol = _reg.get('model_policy') or {}
check('A5  注册表 35 条 NPC 的 model 字段**全为 None**（= 跟随 App 配置，不各自常驻）',
      len(_npcs) >= 30 and all(n.get('model') is None for n in _npcs),
      'n=%d 非 None 的=%r' % (len(_npcs),
                             [n.get('id') for n in _npcs if n.get('model') is not None]))
check('A6  model_policy 的 main / plain 都是 None（第55轮最终口径）',
      _pol.get('main') is None and _pol.get('plain') is None,
      'main=%r plain=%r' % (_pol.get('main'), _pol.get('plain')))
check('A7  model_policy 的 note 里点明了"再建一个 7B = 各常驻一份 4.7GB"这条理由',
      '常驻' in str(_pol.get('note') or ''),
      'note 前 40 字=%r' % str(_pol.get('note') or '')[:40])

_files = sorted(f for f in os.listdir(PERSONA_DIR) if f.endswith('.txt')) \
    if os.path.isdir(PERSONA_DIR) else []
_lens = [len(read_text(os.path.join(PERSONA_DIR, f))) for f in _files]
# ⚠️ 判据修正记录（第64轮）：A8 / A9 原先**写死 13 份**（第55/62轮时的真实份数）。
#    第64轮把用户 30 万字原文里其余 37 份一并入仓（13 → 50）⇒ 写死份数 = 过窄判据。
#    改法（保留鉴别力，不靠"改成 50"这种同样会过期的写法）：
#      A8  份数**下限** ≥ 13（不许被削）+ **每条 registry persona 都真在磁盘上**
#          （后者才是"A5 的跟随配置要有东西可跟"的硬约束）；
#      A9  字数量级区间**放宽上限**到 12000 —— 实测 50 份的分布是 min=3033 /
#          max=10920（`ut_flowey`，Undertale 那份最长）/ 中位=6248，
#          没有一份 < 2500 ⇒ 下限 2000 仍然有鉴别力（砍到空壳会被抓到）。
_persona_refs = [n.get('persona') for n in _npcs if n.get('persona')]
_missing_p = [p for p in _persona_refs
              if p != '../ralsei_persona.md'
              and not os.path.isfile(os.path.join(NPC_DIR, p))]
check('A8  人设份数 ≥ 13 且注册表里每条 persona 都在磁盘上（不写死份数）',
      len(_files) >= 13 and not _missing_p,
      'n=%d 缺失=%r' % (len(_files), _missing_p))
check('A9  人设字数量级 2000~12000（★C 段的 token 就是由这些字产生的；'
      '第64轮最长 ut_flowey=10920）',
      bool(_lens) and all(2000 <= x <= 12000 for x in _lens),
      'min=%d max=%d avg=%d' % (min(_lens), max(_lens), sum(_lens) // len(_lens)))


print()
print('=' * 78)
print('【B】产品接线事实 —— 请求怎么发出去的、有没有闸')
print('=' * 78)


def _main_src():
    return read_text(os.path.join(SRC, 'main.py'))


_msrc = _main_src()
_mtree = ast.parse(_msrc)


def _find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


_cw = _find_func(_mtree, 'chat_with_ai')
check('B1  main.chat_with_ai 存在（唯一的对话出口）', _cw is not None)

# ★ 每次请求都新开线程 ⇒ 多路请求天然并发打到 Ollama
_thr = 0
if _cw is not None:
    for node in ast.walk(_cw):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == 'Thread':
                _thr += 1
            if isinstance(f, ast.Name) and f.id == 'Thread':
                _thr += 1
check('B2  chat_with_ai 里新开了线程（= 每个请求各飞各的，客户端不排队）',
      _thr >= 1, 'threading.Thread 出现 %d 次' % _thr)

# ★★ 本项是"如实登记"而不是"要求存在"：截至第57轮，产品里**没有**全局并发闸，
#    多路请求全靠 Ollama 自己排队。这条判据保证"以后真加了闸，这里会亮"。
_gate_words = ('Semaphore', 'BoundedSemaphore')
_gate_hits = []
for _d in (SRC, MODULES):
    for _fn in sorted(os.listdir(_d)):
        if not _fn.endswith('.py'):
            continue
        _s = read_text(os.path.join(_d, _fn))
        _t = ast.parse(_s)
        for node in ast.walk(_t):
            if isinstance(node, ast.Attribute) and node.attr in _gate_words:
                _gate_hits.append('%s:%s' % (_fn, node.attr))
            if isinstance(node, ast.Name) and node.id in _gate_words:
                _gate_hits.append('%s:%s' % (_fn, node.id))
print('  · 如实登记 B3：全项目并发闸（Semaphore）出现 %d 处 %s'
      % (len(_gate_hits), _gate_hits if _gate_hits else '（当前**没有**全局串行闸）'))
# ⚠️ 这里**故意不做 check**：写成 `check('B3 ...', True)` 就是一条恒真判据
#    （看着在守、其实没守）—— 本项目铁律「恒真判据比不写还危险」。
#    "有没有闸"是**现状登记**，不是"应有约束"：真加了闸，这行数字会变，
#    由 §B 的其余判据（B2 新开线程 / B6 调用点数）继续守住结构。

# ChatScheduler（第46轮产物）仍是"零接线"：它有"同一时刻只有一个伙伴在生成"的设计
# ⇒ 这**正是**产品缺的那道闸，如实登记它没接上。
_comp_src = read_text(os.path.join(MODULES, 'companion_roster.py'))
check('B4  ChatScheduler 确实存在于 companion_roster（第46轮的调度器）',
      'class ChatScheduler' in _comp_src)
check('B5  ★ ChatScheduler 在 main.py 里**零引用**（P3 未授权 ⇒ 那道闸没接上）',
      'ChatScheduler' not in _msrc)

# 请求源清单：AST 扫 chat_with_ai 的调用点
_call_sites = []
for node in ast.walk(_mtree):
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == 'chat_with_ai':
            _call_sites.append(getattr(node, 'lineno', -1))
check('B6  chat_with_ai 的调用点 >= 4 处（NPC说话 / 跟随决策 / 自主开口 / 事件台词 等）',
      len(_call_sites) >= 4, '行号=%s' % sorted(_call_sites))

# ai_driver 的自保：_busy（防自己重入）+ 让路给对话框（_ai_inflight）
_ad = read_text(os.path.join(MODULES, 'ai_driver.py'))
check('B7  ai_driver 有自保：`_busy` 防重入', '_busy' in _ad)
check('B8  ai_driver 会**让路给正在回复的对话**（查 dialogue_ui 的 _ai_inflight）',
      '_ai_inflight' in _ad)
check('B9  event_speech 路径有 `_event_speaking` 自保', '_event_speaking' in _msrc)


print()
print('=' * 78)
print('【C】实测判据 —— 读 _evidence（可复跑，不联网、不进真机）')
print('=' * 78)

_conc = read_json(os.path.join(EVID, 'conc_same_model.json'))
check('C0  并发实测证据在位（conc_same_model.json）', isinstance(_conc, dict))
_waves = (_conc or {}).get('waves') or []
check('C1  证据里至少有 N=1 / 2 / 3 / 4 / 6 五档',
      len({w.get('n') for w in _waves}) >= 5,
      '档位=%s' % sorted({w.get('n') for w in _waves}))


def _pure(row):
    """该请求的**纯处理**时间 = prefill + decode（不含排队等待）。"""
    return _nz(row.get('prompt_eval_duration')) + _nz(row.get('eval_duration'))


# ★★ 判据 C2：wall ≈ Σ(纯处理) ⇒ 串行
_ratios = []
for w in _waves:
    rows = [r for r in (w.get('rows') or []) if r and not r.get('err')]
    if not rows or not w.get('wall'):
        continue
    s = sum(_pure(r) for r in rows)
    _ratios.append((w['n'], w['wall'], s, abs(s - w['wall']) / w['wall']))
check('C2  ★ wall ≈ Σ(各请求 prefill+decode)，相对误差 < 10% ⇒ **串行，零并行**',
      bool(_ratios) and all(r[3] < 0.10 for r in _ratios),
      '; '.join('N=%d wall=%.1f Σ纯=%.1f 偏差=%.1f%%' % (n, wl, s, e * 100)
                for n, wl, s, e in _ratios))

# C2b 负控制：合成一份"**并行**"的依据（wall 取 max(纯处理) 而不是 Σ），
#       C2 那条判据在这份数据上**必须判否** —— 这才叫"有鉴别力"。
#       ⚠️ 只对"请求数 >= 3"的档有意义：N=2 时 Σ 与 max 本来就接近（只有一个冷请求），
#          区分不出串行/并行 —— 拿它做负控制会得出"判据没鉴别力"的假结论。
#       ⚠️ 也**不能**拿 `max(total)` 比：`total` 含排队等待，串行时 max(total) 恰好 == wall，
#          那个口径下 C2 与负控制会同时为真（本套件第一版就是这么写错的）。
_par = []
for w in _waves:
    rows = [r for r in (w.get('rows') or []) if r and not r.get('err')]
    if len(rows) < 3:
        continue
    s = sum(_pure(r) for r in rows)
    fake = max(_pure(r) for r in rows)
    if fake > 0:
        _par.append(abs(s - fake) / fake)
check('C2b 负控制：合成"并行"依据（wall=max 纯处理）时，C2 的误差判据必须判否',
      bool(_par) and any(x > 0.10 for x in _par),
      '并行口径偏差=%s' % ['%.0f%%' % (x * 100) for x in _par])

# ★ 判据 C3/C4：冷热两档的 prefill 速率
_cold, _hot, _dec = [], [], []
for w in _waves:
    for r in (w.get('rows') or []):
        if not r or r.get('err'):
            continue
        pt = r.get('prompt_eval_count') or 0
        if pt:
            mst = (r.get('prompt_eval_duration') or 0) / 1e6 / pt
            (_hot if mst < 5.0 else _cold).append(mst)
        et = r.get('eval_count') or 0
        if et >= 10:
            _dec.append((r.get('eval_duration') or 0) / 1e6 / et)

check('C3  冷 prefill 速率落在 15~45 ms/token（实测 27.2~28.6）',
      len(_cold) >= 4 and all(15 <= x <= 45 for x in _cold),
      'n=%d 区间=[%.2f, %.2f]' % (len(_cold), min(_cold), max(_cold)))
check('C4  热（命中缓存）prefill 速率 < 5 ms/token（实测 0.04~1.2）',
      len(_hot) >= 4 and all(x < 5.0 for x in _hot),
      'n=%d 区间=[%.3f, %.3f]' % (len(_hot), min(_hot), max(_hot)))
check('C5  ★ 冷 / 热的比值 > 10（这就是"首字铁律"的量化根据）',
      bool(_cold) and bool(_hot) and (min(_cold) / max(_hot)) > 10,
      '比 = %.0f 倍' % (min(_cold) / max(_hot)))
check('C6  decode 速率落在 100~250 ms/token（实测 145~161，与并发数无关）',
      len(_dec) >= 6 and all(100 <= x <= 250 for x in _dec),
      'n=%d 区间=[%.1f, %.1f]' % (len(_dec), min(_dec), max(_dec)))

# ★ 判据 C7：前缀缓存容量（第 2 轮仍然全热 ⇒ 前缀被保住了）
_pc = read_json(os.path.join(EVID, 'prefix_cache.json'))
_rounds = (_pc or {}).get('rounds') or []
_r2 = _rounds[1] if len(_rounds) >= 2 else []
check('C7  前缀缓存实测：第 2 轮 6 个不同前缀**全部命中** ⇒ 容量 ≥ 6',
      bool(_r2) and all(x.get('hot') for x in _r2) and len(_r2) >= 6,
      '第2轮 %d 条，热的=%d' % (len(_r2), sum(1 for x in _r2 if x.get('hot'))))


def _best_rounds(path):
    j = read_json(os.path.join(EVID, path))
    rs = (j or {}).get('rounds') or []
    return rs[1] if len(rs) >= 2 else []


_r2_13 = _best_rounds('prefix_cache_13.json')
_n_hot_13 = sum(1 for x in _r2_13 if x.get('hot'))
check('C7b 13 人档（若已跑）：第 2 轮命中数 == 13 ⇒ 容量 ≥ 13',
      (not _r2_13) or (len(_r2_13) == 13 and _n_hot_13 == 13),
      '第2轮 %d 条，热的=%d%s' % (len(_r2_13), _n_hot_13,
                                '（该档未跑，跳过）' if not _r2_13 else ''))


print()
print('=' * 78)
print('【D】结论（打印；不做环境耦合的硬断言）')
print('=' * 78)
print('  · 服务端**真正并行**的请求数 = OLLAMA_NUM_PARALLEL = **1**（官方默认，纯 CPU）')
print('  · 并发 N 个请求 ⇒ **排队**，第 k 个的等待 ≈ 前 k-1 个的纯处理时间之和')
print('  · 单请求速率**不因并发而变**（C3/C6 已证）⇒ "并发"不损性能，只加等待')
print('  · 单请求耗时（缓存热）= prefill 0.2s + 48tok×155ms ≈ **7~8s**')
print('  · 单请求耗时（缓存冷）= 2533tok×27.7ms ≈ **70s**（人设越大越久，3905tok ⇒ 108s）')
print('  · 前缀缓存容量 ≥ 6（C7）；但 **keep_alive 默认 5 分钟卸载 ⇒ 缓存全丢 ⇒ 回到冷**')

print()
print('-' * 78)
print('结果：PASS=%d FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
if FAILS:
    print('失败项：%s' % FAILS)
sys.exit(1 if FAILS else 0)
