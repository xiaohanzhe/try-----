# -*- coding: utf-8 -*-
"""第58轮 · 模型常驻（keep_alive）与启动预热 回归锁（`check58`）。

背景（第57轮留下的待裁定项 + 用户口径）
--------------------------------------
第57轮把"7B 并发"实测完，报告 §7 留了三项待裁定。用户口径：
「按照你的来就好，没办法裁定的告诉我」
⇒ 本轮**自己裁定并落地**前两项，第三项明确不做的理由写进报告。

 ① `keep_alive` —— **做**。但做法不是"把值调长"，而是先搞清楚它到底在哪条通路上生效。
 ② 全局并发闸（`ChatScheduler` / `Semaphore(1)`）—— **不做**（Ollama 已串行，见报告）。
 ③ `OLLAMA_NUM_PARALLEL` —— **不动**（第57轮结论：调高只是把"排队"变成"抢 CPU"）。

本套件钉住的**四条实测事实**（全部有 `_evidence/*.json` 可复跑）
--------------------------------------------------------------
① **兼容端点 `/v1/chat/completions` 静默丢弃 `keep_alive`**：
   设 30m 之后 `ollama ps` 的 expires_at 增量仍是 300s，与"不传"那档**完全相等**（|Δ|=0s）。
   （同型已知：该端点还丢 `num_ctx` / `repeat_penalty` —— 这是第三个字段。）
② **`keep_alive` 黏在"模型载入实例"上**：原生端点设过之后，每个请求（普通对话也算）
   都用它刷新截止时刻；静置时窗口真的在倒计时，而随便来一个请求就跳回去。
   ⇒ **不需要周期性心跳**，只要在"新载入"时设一次。（这条把方案从"心跳"降成"看门狗"。）
③ **模型一卸载，前缀缓存全丢**：同一个人设前缀
   冷 55.79s（2371 token，23.5 ms/token）→ 热 0.149s（**快 375 倍**）→ 卸载后 61.07s。
   这条是 keep_alive 值得接线的**唯一依据**（第57轮只是按官方文档推断，本轮直接实测）。
④ **兼容端点不截断长提示词**（`prompt_tokens` == 原生 `prompt_eval_count` == 2371），
   而且它会回 `prompt_tokens_details.cached_tokens` —— 产品通路上可以直接读缓存命中。
   ⇒ 顺带更正了 main.py / modelfile 里那条**已过期**的"~2050 截断"注释。

五段
----
  A 配置锚点（新配置项是否到位、默认值是否符合用户"选项非硬性"口径）
  B 实测证据（读 `_evidence/*.json`；不联网、不进真机、不碰 Ollama）
  C 产品接线（AST：三个 create_client 点是否都同步了看门狗、是否鸭子类型、退出是否停）
  D 行为判据（**离线喂假 client** 调 `WarmKeeper.tick()`：边沿语义/不重复发包/失败不假装成功）
  E 反向判据（结构性去重 + 防空转：不许把 keep_alive 塞进兼容端点 payload）

设计纪律（沿用本项目）
---------------------
* **能上 AST 就上 AST**，不 import 产品（`main.py` 一导入就要 Qt）；
* 每条结论都配**正/负控制**：负控制不是"再跑一遍"，而是"把依据换成假的、判据必须翻脸"；
* **阈值取宽区间**（换机器也应是同一量级），只锁结构不锁具体秒数；
* `[PASS]` 必须是**字面量**（`run_all.py:1279` 按 `\\[PASS\\]|\\[\\s*OK\\s*\\]` 计数）。
"""
import ast
import io
import json
import os
import sys
import threading
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PET, 'src')
MODULES = os.path.join(PET, 'modules')
EVID = os.path.join(HERE, '_evidence')
NATIVE = '/api/chat'          # 原生端点后缀（判据里当字面量用）

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
    with io.open(p, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def ev(name):
    """读 `_evidence` 里的实测产物；缺失返回 None（判据会因此报红，而不是静默跳过）。"""
    p = os.path.join(EVID, name)
    if not os.path.isfile(p):
        return None
    try:
        return json.loads(read_text(p))
    except Exception:                                             # noqa: BLE001
        return None


def main_src():
    return read_text(os.path.join(SRC, 'main.py'))


def api_src():
    return read_text(os.path.join(MODULES, 'api_client.py'))


def cfg():
    return json.loads(read_text(os.path.join(PET, 'config.json')))


def call_names(node):
    """收集 node 子树里所有 Call 的"末段名字"（`self._sync_warm_keeper()` → `_sync_warm_keeper`）。"""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                out.append(f.attr)
            elif isinstance(f, ast.Name):
                out.append(f.id)
    return out


def funcdefs(tree):
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


print('=' * 78)
print('第58轮 · 模型常驻（keep_alive）与启动预热')
print('=' * 78)

# ============================================================ A 配置锚点
print()
print('--- A 配置锚点（新配置项 + 默认值口径）---')
c = None
try:
    c = cfg()
except Exception as e:                                            # noqa: BLE001
    check('A0 ralsei_pet/config.json 可解析', False, repr(e))
else:
    check('A0 ralsei_pet/config.json 可解析', True)

api = (c or {}).get('api') or {}
st = (c or {}).get('startup') or {}

ka = api.get('keep_alive')
check('A1 api.keep_alive 是非空字符串（值=%r）' % (ka,),
      isinstance(ka, str) and bool(ka.strip()))
check('A2 api.keep_warm 为 True（保温默认开 —— 它只在 App 运行时生效，'
      '且用户走开后会自动过期还内存）', api.get('keep_warm') is True)
poll = api.get('keep_warm_poll')
check('A3 api.keep_warm_poll 是 >=5 的数（= %r）' % (poll,),
      isinstance(poll, (int, float)) and not isinstance(poll, bool) and poll >= 5)
# ★ 这条是"冷 prefill 比对话超时长"的直接后果：实测 55.8~64.3s。
#   老默认 30s 会把一次**正常**请求判成超时 —— 那是"假失败"，最难查。
to = api.get('timeout')
check('A4 api.timeout >= 60（冷 prefill 实测 55.8~64.3s；30s 会假超时）值=%r' % (to,),
      isinstance(to, (int, float)) and to >= 60)
# ★ 用户口径：自启/预热是**选项非硬性** ⇒ 默认必须是 false，且必须是 bool 而不是缺失。
check('A5 startup.prewarm 存在且是 bool 且默认 False（用户口径：选项非硬性）值=%r'
      % (st.get('prewarm'),), isinstance(st.get('prewarm'), bool)
      and st.get('prewarm') is False)
pt = st.get('prewarm_timeout')
check('A6 startup.prewarm_timeout >= 120 值=%r' % (pt,),
      isinstance(pt, (int, float)) and pt >= 120)
# ★ 把结论写在配置自己的注释里 —— 否则下一个人看到"keep_alive 设了却不生效"会重复踩。
_ka_c = api.get('keep_alive_comment') or ''
check('A7 keep_alive 的注释里必须写明"只有原生端点认"（含 %r）' % NATIVE,
      NATIVE in _ka_c)

# ============================================================ B 实测证据
print()
print('--- B 实测证据（读 _evidence/*.json；不联网、不碰 Ollama）---')
p1 = ev('keep_alive_probe.json')
p2 = ev('keepalive_semantics.json')
p3 = ev('cache_survives_unload.json')
p4 = ev('compat_truncation.json')
p5 = ev('keepalive_reset.json')

check('B0 五份实测证据都在（probe / semantics / cache / truncation / reset）',
      all(x is not None for x in (p1, p2, p3, p4, p5)))

if p1:
    dd, cd_ = p1.get('default_delta_s'), p1.get('compat_delta_s')
    check('B1 ★ 兼容端点丢弃 keep_alive：Δ 与"不传"档无差别（|差| < 60s）',
          dd is not None and cd_ is not None and abs(cd_ - dd) < 60,
          '默认 %.0fs vs 带字段 %.0fs（|Δ差|=%.0fs）'
          % (dd or -1, cd_ or -1, abs((cd_ or 0) - (dd or 0))))
    nd = p1.get('native_delta_s')
    check('B2 正控制：原生端点**确实**能改窗口（480 < Δ < 900，实得 %s）'
          % (('%.0f' % nd) if nd else '?',), nd is not None and 480 < nd < 900)
    check('B3 keep_alive=0 真的卸载（否则 ps 读数不可信）',
          p1.get('unload_worked') is True)

if p2:
    # ⚠️ semantics 探针里 `mark()` **直接把 Δ 浮点数**写进 steps（不是字典）——
    #    这里必须按真实形状读。判据读错形状会崩，而不是报红（本轮实测踩到）。
    stp = p2.get('steps') or {}
    q3 = stp.get('Q3_compat_after')
    q4 = stp.get('Q4_after_idle70')
    q5 = stp.get('Q5_compat_refresh')
    _num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    check('B4 ★ keep_alive 黏住：普通请求沿用黏住值（Q3 ≈ 600s，实得 %s）'
          % (('%.0f' % q3) if _num(q3) else '?',), _num(q3) and 540 < q3 < 660)
    check('B5 静置时窗口**真在倒计时**（鉴别力：排除"读数恒 600"）',
          _num(q3) and _num(q4) and q4 < q3 - 30,
          '%.0fs → %.0fs' % (q3 or -1, q4 or -1))
    check('B6 ★ 普通请求**会给续期**（Q5 跳回 ≈600s）',
          _num(q4) and _num(q5) and q5 > q4 + 30,
          '%.0fs → %.0fs' % (q4 or -1, q5 or -1))
    check('B7 黏住 + 普通请求续期 ⇒ **不需要周期心跳**（"看门狗"方案的直接依据）',
          p2.get('sticky_true') is True
          and p2.get('refresh_by_normal_request') is True)

cold = hot = after = tok = None
if p3:
    s = p3.get('steps') or {}
    cold = (s.get('S1 冷（首次喂入）') or {}).get('_pe_s')
    hot = (s.get('S2 热（立刻重发同前缀）') or {}).get('_pe_s')
    after = (s.get('S4 卸载后重发同前缀') or {}).get('_pe_s')
    tok = (s.get('S1 冷（首次喂入）') or {}).get('_pe_tok')
    check('B8 同前缀冷 prefill 真是"大"（> 10s，实得 %s）'
          % (('%.2fs' % cold) if cold else '?',), cold is not None and cold > 10.0)
    check('B9 热 ≪ 冷（差 > 10 倍）', bool(cold) and hot is not None
          and hot < cold / 10.0, '热 %.3fs vs 冷 %.2fs（%s token）'
          % (hot or -1, cold or -1, tok))
    check('B10 ★★ 卸载后回到冷（|差|/冷 < 25%）⇒ **缓存随卸载全丢**',
          bool(cold) and after is not None and abs(after - cold) / cold < 0.25,
          '卸载后 %.2fs vs 冷 %.2fs' % (after or -1, cold or -1))
    # 负控制：把"卸载后"换成"热"的值 ⇒ B10 的判据必须翻脸。
    # 不做这一步，B10 只证明"数字能对上"，不证明它**能识别出**缓存存活的情形。
    if cold:
        rel_hot = abs((hot or 0) - cold) / cold
        check('B11 负控制：合成"缓存存活"的依据 ⇒ B10 判据必须判否',
              not (rel_hot < 0.25),
              '（热 %.3fs 与冷 %.2fs 相对差 %.0f%% ≫ 25%%）'
              % (hot or -1, cold, rel_hot * 100))

if p4:
    cu = (p4.get('compat_usage') or {}).get('prompt_tokens')
    nu = p4.get('native_prompt_eval_count')
    check('B12 ★ 兼容端点**不截断**长提示词'
          '（usage.prompt_tokens == 原生 prompt_eval_count）',
          bool(cu) and bool(nu) and abs(cu - nu) <= 2,
          'compat=%s vs native=%s' % (cu, nu))
    # ★ 判据必须读**成对**的冷/热两个读数：
    #   冷 = 0 是**正确值**（首次喂入确实没有可复用前缀），不是"字段坏了"。
    #   只有"热 > 0"才证明该字段真的反映缓存状态。
    #   ⚠️ 本轮首跑只读冷读数 ⇒ 假报红（判据侧问题，不是产品问题）。
    cold_ct = (((p4.get('compat_usage') or {}).get('prompt_tokens_details')
                or {}).get('cached_tokens'))
    warm_ct = [(((u or {}).get('prompt_tokens_details') or {})
                .get('cached_tokens'))
               for u in (p4.get('compat_usage_warm') or [])]
    check('B13 ★ 兼容端点会回 cached_tokens：冷=0 **且** 热>0（成对才有鉴别力）',
          cold_ct == 0 and any(isinstance(x, int) and x > 0 for x in warm_ct),
          'cold=%s warm=%s' % (cold_ct, warm_ct))
    # 负控制：合成"截断到 2050"的依据 ⇒ B12 判据必须判否。
    check('B14 负控制：合成"截断到 2050"的依据 ⇒ B12 判据必须判否',
          not (bool(cu) and bool(nu) and abs(2050 - nu) <= 2),
          '（2050 vs native=%s）' % nu)

if p5:
    b = ((p5.get('steps') or {}).get('B 兼容端点**不带** keep_alive') or {}).get('delta_s')
    check('B15 交叉印证：另一个探针里，兼容请求**没**把窗口打回 300s（Δ > 1700）',
          b is not None and b > 1700, 'Δ=%s' % (('%.0f' % b) if b else '?'))

# ============================================================ C 产品接线（AST）
print()
print('--- C 产品接线（AST，不 import main）---')
mt = at = None
try:
    mt = ast.parse(main_src(), 'main.py')
    at = ast.parse(api_src(), 'api_client.py')
    check('C0 main.py / api_client.py 可解析', True)
except SyntaxError as e:
    check('C0 main.py / api_client.py 可解析', False, repr(e))

if mt is not None:
    # C1 真 import 了 WarmKeeper（不是只写注释）
    imported = False
    for n in ast.walk(mt):
        if isinstance(n, ast.ImportFrom) and (n.module or '').endswith('api_client'):
            if any(a.name == 'WarmKeeper' for a in n.names):
                imported = True
    check('C1 main.py 真从 modules.api_client import 了 WarmKeeper', imported)

    # C2 create_client 的**每个**调用点所在函数里，都必须调过 _sync_warm_keeper
    fn_with_create, fn_with_sync = [], []
    for fn in funcdefs(mt):
        names = call_names(fn)
        if 'create_client' in names:
            fn_with_create.append(fn.name)
            if '_sync_warm_keeper' in names:
                fn_with_sync.append(fn.name)
    all_calls = len([x for x in call_names(mt) if x == 'create_client'])
    check('C2 ★ create_client 的三个调用点所在函数里都调过 _sync_warm_keeper（%s）'
          % (sorted(fn_with_create),),
          all_calls == 3 and len(fn_with_create) == 3
          and sorted(fn_with_create) == sorted(fn_with_sync),
          'create_client=%d 处 / 同步=%d 处' % (all_calls, len(fn_with_sync)))
    check('C3 _sync_warm_keeper 真被调用 >= 3 次（三个 create_client 点）',
          len([x for x in call_names(mt) if x == '_sync_warm_keeper']) >= 3,
          '调用 %d 次' % len([x for x in call_names(mt) if x == '_sync_warm_keeper']))

    # C4 鸭子类型而非 isinstance —— 用户 register_provider 的实现也要能用
    sync_fn = None
    for fn in funcdefs(mt):
        if fn.name == '_sync_warm_keeper':
            sync_fn = fn
    if sync_fn is None:
        check('C4 _sync_warm_keeper 是真函数定义', False)
    else:
        seg = ast.get_source_segment(main_src(), sync_fn) or ''
        check('C4 ★ _sync_warm_keeper 用鸭子类型（hasattr 两个保温方法）',
              'hasattr' in seg and 'loaded_models' in seg
              and 'ensure_keep_alive' in seg)
        # ⚠️ 判据必须写**窄**：函数里对**配置值**用 isinstance 是合法防御
        #    （`isinstance(cfg, dict)` / `isinstance(ka, str)`），不该报红。
        #    真正要禁的只有一条：拿 isinstance 卡 **client**（那会把
        #    register_provider 注册的用户实现挡在门外）。
        check('C4b ★ 反向：它**没有**拿 isinstance 卡 client'
              '（否则 register_provider 的自定义实现永远拿不到保温）',
              'isinstance(cli' not in seg and 'isinstance(self.api_client' not in seg,
              '（函数内 isinstance 用法数=%d，只应出现在配置值校验处）'
              % seg.count('isinstance'))

    # C5 退出时必须停（守护线程但会真的发 HTTP 请求）
    cl_fn = None
    for fn in funcdefs(mt):
        if fn.name == 'cleanup_on_exit':
            cl_fn = fn
    if cl_fn is None:
        check('C5 cleanup_on_exit 里停掉看门狗', False, '找不到 cleanup_on_exit')
    else:
        seg = ast.get_source_segment(main_src(), cl_fn) or ''
        check('C5 cleanup_on_exit 里真的停掉看门狗（出现 _warm_keeper 与 .stop()）',
              '_warm_keeper' in seg and '.stop()' in seg)

    # C6 预热真的被调度（不是死配置）
    #   ⚠️ `QTimer.singleShot(1500, self._prewarm_ai_cache)` 的第二个参数是
    #      **Attribute 引用**、不是 Call 节点 ⇒ `call_names()` 抓不到（本轮踩到）。
    #      必须直接看 singleShot 的实参形状。
    def _single_shot_callbacks(tree):
        out = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr == 'singleShot':
                for a in n.args:
                    if isinstance(a, ast.Attribute):
                        out.append(a.attr)
                    elif isinstance(a, ast.Name):
                        out.append(a.id)
        return out

    _cb = _single_shot_callbacks(mt)
    check('C6 ★ startup.prewarm 真的接线了（singleShot 调度 _prewarm_ai_cache）',
          '_prewarm_ai_cache' in _cb)
    check('C6b 鉴别力：main.py 的 singleShot 有多处回调，**只有一处**是预热调度'
          '（否则 C6 只是在查"singleShot 存在与否"）',
          len(_cb) >= 2 and _cb.count('_prewarm_ai_cache') == 1,
          '回调 = %s' % _cb)
    check('C7 _prewarm_ai_cache 与 _sync_warm_keeper 都是**真函数定义**（AST）',
          {'_prewarm_ai_cache', '_sync_warm_keeper'} <= {fn.name for fn in funcdefs(mt)})
    # C7b 反向：`prewarm` 必须读的是**配置**（不是写死的 True）
    msrc = main_src()
    check('C7b 反向：预热开关读的是配置项（"startup.prewarm" 字面量在 main.py 里）',
          'startup.prewarm' in msrc)

if at is not None:
    # C8 传输层：chat() 支持按请求超时（预热必须能要更长的预算）
    chat_fn = None
    for fn in ast.walk(at):
        if isinstance(fn, ast.ClassDef) and fn.name == 'HTTPLocalAI':
            for m in fn.body:
                if isinstance(m, ast.FunctionDef) and m.name == 'chat':
                    chat_fn = m
    seg = ast.get_source_segment(api_src(), chat_fn) if chat_fn else ''
    check('C8 chat() 支持按请求超时（kwargs.pop("timeout") 且传给 _post_json）',
          "kwargs.pop('timeout'" in seg and 'timeout=_timeout' in seg)
    pj = None
    for fn in ast.walk(at):
        if isinstance(fn, ast.FunctionDef) and fn.name == '_post_json':
            pj = fn
    args = [a.arg for a in (pj.args.args if pj else [])]
    check('C9 反向：_post_json 的 timeout 必须是**可选**的'
          '（否则老三个调用点全要被改）',
          args[:3] == ['self', 'url', 'body'] and 'timeout' in args, '%s' % args)

    # C10 保温能力在 HTTPLocalAI 上（协议端口）
    mnames = set()
    for fn in ast.walk(at):
        if isinstance(fn, ast.ClassDef) and fn.name == 'HTTPLocalAI':
            mnames = {m.name for m in fn.body if isinstance(m, ast.FunctionDef)}
    check('C10 ★ HTTPLocalAI 上真的有三个保温端口'
          '（native_chat_endpoint / loaded_models / ensure_keep_alive）',
          {'loaded_models', 'ensure_keep_alive', 'native_chat_endpoint'} <= mnames,
          '%s' % sorted(mnames & {'loaded_models', 'ensure_keep_alive',
                                  'native_chat_endpoint'}))

# ============================================================ D 行为判据（离线）
print()
print('--- D 行为判据（离线喂假 client，真调 WarmKeeper.tick）---')
sys.path.insert(0, PET)
_WK = None
try:
    from modules.api_client import WarmKeeper as _WK
    check('D0 能导入 WarmKeeper', True)
except Exception as e:                                            # noqa: BLE001
    check('D0 能导入 WarmKeeper', False, repr(e))


class FakeClient:
    """假 client：完全离线，只记账、不联网。

    ★ 用**真** `WarmKeeper` 调 `tick()`，只把"外部世界"替换掉 ——
      符合本项目"能 import 的别重写、不得不重写必须锁等价"的口径：
      被测的是产品逻辑本身，不是我的复制品。

    `seq` 是每次 `loaded_models()` 的应答序列，**用完重复最后一个**
    （模拟"模型一直载入着"这种常态）。`probe_none=True` 模拟"探测不通"
    （非 Ollama 后端 / 服务没开）—— 它与 `[]`（Ollama 在但没载入）语义不同。
    """

    def __init__(self, seq=None, ka_ok=True, probe_none=False):
        self.enabled = True
        self._seq = list(seq if seq is not None else [])
        self._last = self._seq[0] if self._seq else []
        self._ka_ok = ka_ok
        self._probe_none = probe_none
        self.ps_calls = 0
        self.ka_calls = []

    def loaded_models(self):
        self.ps_calls += 1
        if self._probe_none:
            return None
        if self._seq:
            self._last = self._seq.pop(0)
        return self._last

    def ensure_keep_alive(self, keep_alive):
        self.ka_calls.append(keep_alive)
        return self._ka_ok


if _WK is not None:
    # D1 空 ps ⇒ unloaded，且**绝不**主动拉起模型（不许占用户内存）
    f = FakeClient(seq=[])
    k = _WK(f, keep_alive='30m', interval=5)
    r = k.tick()
    check('D1 ps 为空 ⇒ "unloaded" 且一次都不发保温请求（不主动拉起模型）',
          r == 'unloaded' and f.ka_calls == [],
          'act=%r ka_calls=%d' % (r, len(f.ka_calls)))

    # D2 载入 ⇒ armed 一次，且用的就是配置里的 keep_alive
    f = FakeClient(seq=[['ralsei:v4']])
    k = _WK(f, keep_alive='30m', interval=5)
    r = k.tick()
    check('D2 模型新载入 ⇒ "armed"，且 keep_alive 用了配置值',
          r == 'armed' and f.ka_calls == ['30m'] and k.armed_count == 1,
          'act=%r ka=%s count=%d' % (r, f.ka_calls, k.armed_count))

    # D3 ★ 再 tick ⇒ idle，**不再发包**（这就是"不是周期心跳"的行为证据）
    r2 = k.tick()
    check('D3 ★ 第二次 tick ⇒ "idle" 且**不重复发包**（证明不是周期心跳）',
          r2 == 'idle' and f.ka_calls == ['30m'] and k.armed_count == 1,
          'act=%r ka_calls=%d' % (r2, len(f.ka_calls)))

    # D4 边沿：卸载 → 再载入 ⇒ 必须重新 arm
    #    （否则"卸载后重载"那一次的窗口会一直停在服务器默认 5 分钟）
    f = FakeClient(seq=[[], ['ralsei:v4']])
    k = _WK(f, keep_alive='30m', interval=5)
    ra, rb, rc = k.tick(), k.tick(), k.tick()
    check('D4 ★ 边沿识别：卸载后再载入 ⇒ 重新 arm（arm 计数 1，且前后状态对）',
          ra == 'unloaded' and rb == 'armed' and rc == 'idle'
          and k.armed_count == 1 and len(f.ka_calls) == 1,
          'acts=%r/%r/%r arms=%d' % (ra, rb, rc, k.armed_count))
    # 负控制：把"卸载"那一步去掉（序列直接就是载入）⇒ **不该**出现两次 arm
    f2 = FakeClient(seq=[['ralsei:v4']])
    k2 = _WK(f2, keep_alive='30m', interval=5)
    k2.tick(); k2.tick(); k2.tick()
    check('D4b 负控制：全程一直载入 ⇒ 只 arm **一次**（连发就是 bug）',
          k2.armed_count == 1 and len(f2.ka_calls) == 1,
          'arms=%d ka_calls=%d' % (k2.armed_count, len(f2.ka_calls)))

    # D5 探测不通（非 Ollama 后端 / 服务没开）⇒ 只记失败、**绝不发包**
    f = FakeClient(probe_none=True)
    k = _WK(f, keep_alive='30m', interval=5)
    acts = [k.tick() for _ in range(5)]
    check('D5 ★★ 探测不通 ⇒ 一律 "probe_fail" 且**一次都不发包**'
          '（非 Ollama 后端必须能安静退让）',
          set(acts) == {'probe_fail'} and k._fails == 5 and f.ka_calls == []
          and k.armed_count == 0,
          'acts=%s fails=%d ka_calls=%d' % (sorted(set(acts)), k._fails,
                                            len(f.ka_calls)))

    # D6 负控制：设 keep_alive 失败时**不许假装成功**（否则会永远不再补设）
    f = FakeClient(seq=[['m']], ka_ok=False)
    k = _WK(f, keep_alive='30m', interval=5)
    r = k.tick()
    check('D6 ★ 负控制：设 keep_alive 失败 ⇒ 返回 "idle" 且**不置 armed**',
          r == 'idle' and k.armed_count == 0,
          'act=%r arms=%d' % (r, k.armed_count))
    r2 = k.tick()
    check('D6b 失败之后**下轮会再试**（不是一次失败就永久放弃）',
          r2 == 'idle' and len(f.ka_calls) == 2, 'ka_calls=%d' % len(f.ka_calls))

    # D7 轮询间隔必须被钳住（否则 interval=0 会变成忙等死循环）
    k = _WK(FakeClient(), keep_alive='30m', interval=0.01)
    check('D7 轮询间隔被钳到 >= 5s（防 interval=0 变忙等）', k.interval >= 5.0,
          'interval=%s' % k.interval)

    # D8 生命周期：start() 幂等，且 stop() 后线程真的结束
    k = _WK(FakeClient(seq=[]), keep_alive='30m', interval=5)
    k.start()
    k.start()
    check('D8 start() 幂等（只起一个线程）',
          k._thread is not None and k._thread.is_alive())
    k.stop()
    time.sleep(0.2)
    check('D8b stop() 之后线程已结束（不留守护线程继续发包）',
          k._thread is None and not any(
              t.name == 'WarmKeeper' and t.is_alive() for t in threading.enumerate()))

# ============================================================ E 反向判据
print()
print('--- E 反向判据（结构去重 / 防空转）---')
n_defined, parse_fail = 0, 0
for r, _d, fs in os.walk(PET):
    for f in fs:
        if not f.endswith('.py'):
            continue
        p = os.path.join(r, f)
        try:
            tree = ast.parse(read_text(p), p)
        except SyntaxError:
            parse_fail += 1
            continue
        n_defined += sum(1 for n in tree.body
                         if isinstance(n, ast.ClassDef) and n.name == 'WarmKeeper')
check('E1 WarmKeeper 全项目**只定义一次**（不许在 main.py 里复制一份）',
      n_defined == 1, '定义处=%d（另有 %d 个文件没解析成功）' % (n_defined, parse_fail))

asrc = api_src()
_pay = None
for n in ast.walk(ast.parse(asrc, 'api_client.py')):
    if isinstance(n, ast.FunctionDef) and n.name == '_chat_payload':
        _pay = n
_seg = ast.get_source_segment(asrc, _pay) if _pay else ''
check('E2 ★ 防空转：**不许**把 keep_alive 塞进兼容端点 payload'
      '（实测该字段被静默丢弃 ⇒ 塞了就是"写了但没人读"）',
      bool(_pay) and 'keep_alive' not in _seg)
check('E3 keep_alive 只出现在"走原生端点"的那条路径上'
      '（api_client 里同时存在 native_chat_endpoint 与 keep_alive）',
      'keep_alive' in asrc and 'native_chat_endpoint' in asrc)

check('E4 keep_alive 的取值来自**配置**而不是写死（api_client 用 self.keep_alive，'
      'main 从 cfg 取）', 'self.keep_alive' in asrc
      and "cfg.get('keep_alive'" in main_src())

gsrc = ''
try:
    gsrc = read_text(os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'))
except Exception:                                                 # noqa: BLE001
    pass
_herm = gsrc.split('HERMETIC_IDS')[1][:2000] if 'HERMETIC_IDS' in gsrc else ''
check('E5 本套件**不**登记进 HERMETIC_IDS（它不建 RalseiPet，是纯只读套件）',
      'check58' not in _herm and 'model_conc58' not in _herm)

print()
print('=' * 78)
print('合计：PASS=%d FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
if FAILS:
    print('失败项：')
    for f in FAILS:
        print('  -', f)
print('=' * 78)
sys.exit(1 if FAILS else 0)
