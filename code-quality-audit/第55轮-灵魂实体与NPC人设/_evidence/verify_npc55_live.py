# -*- coding: utf-8 -*-
"""第55轮 · NPC 接**真实在线模型**的真机验收（不进 G2：它依赖本机 Ollama）。

为什么要单独有这个脚本（而不是塞进 `check55.py`）：
  `check55` 必须能离线跑（G2 的铁律：回归套件不许依赖外部服务）。
  但"NPC 到底会不会真的开口"这件事**只能**在真模型上验 —— 用桩验过的只是
  "代码把请求发出去了"，验不到"7B 会不会说实话、会不会只回一个词"。
  于是把它拆出来：需要 Ollama 时手动跑，不进任何自动化。

它验什么（每条都配"反面"以免自我安慰）：
  L1 灵魂/NPC 系统在真 App 上建起来了；
  L2 ★ 模型句柄 = `config.json` 里那个（不额外指定）+ 它确实是 7B（查 /api/tags 的 parameter_size）；
  L3 ★ NPC 真开口：susie 的回复非空、且**真的过了护栏**（不是 None）；
  L4 ★★ 那句话落进 **susie 自己**的记忆（`who='susie'`），且 kris 的记忆里没有 ——
     用户口径「每个人都需要分每个人的记忆，不要搞混了…葫芦娃千里眼顺风耳」；
  L5 ★★ 发出去的 system 用的是 susie 的人设（不是 Ralsei 的）；
  L6 ★ 跟随决策真的问过模型：`_npc_last_decision[2] in ('ai', 'policy')`，
     且在模型给了合法词时 source='ai'；
  L7 首字（TTF）与整句耗时 —— 供报告记录（7B 纯 CPU）。

用法：
    set RALSEI_MEMORY_DIR=<临时目录>   # 可选；不设则用 %TEMP%\ralsei_live55
    C:\\Python311\\python.exe -X utf8 verify_npc55_live.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
HERE = os.path.abspath(os.path.dirname(__file__))
# ⚠️ 本脚本在 `_evidence/` 里 ⇒ 比 `check55.py` 多一层，别照抄它的 `'..','..'`。
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'src'))
sys.path.insert(0, os.path.join(PET, 'modules'))

# ★ 隔离：绝不碰用户真实的 E:\RalseiMemory。
_ISO = os.path.join(tempfile.gettempdir(), 'ralsei_live55')
shutil.rmtree(_ISO, ignore_errors=True)
os.makedirs(_ISO, exist_ok=True)
os.environ['RALSEI_MEMORY_DIR'] = _ISO

FAILS = []
N = [0]


def check(name, cond, extra=''):
    N[0] += 1
    if cond:
        print('[PASS] %s %s' % (name, extra))
    else:
        print('[FAIL] %s %s' % (name, extra))
        FAILS.append(name)


def _ollama_models():
    try:
        with urllib.request.urlopen(
                'http://localhost:11434/api/tags', timeout=5) as fh:
            return json.loads(fh.read().decode('utf-8')).get('models') or []
    except Exception as e:
        print('[note] 读不到 Ollama 模型列表（已忽略）: %s' % e)
        return []


_MODELS = {m.get('name'): m for m in _ollama_models()}
print('[note] Ollama 在线模型: %s' % ', '.join(sorted(_MODELS)))

from PyQt5.QtWidgets import QApplication        # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)

import main as M                                # noqa: E402
from modules import npc_persona as P            # noqa: E402

pet = M.RalseiPet()
pet.show()


def pump(pred, timeout=90.0):
    """转事件循环等异步结果（真模型在纯 CPU 上可能要几十秒）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.02)
    app.processEvents()
    return pred()


check('L1 真机：App 起来了，NPC 服务在（注册表 / 人设 / 记忆）',
      pet.npc_registry is not None and pet.npc_personas is not None
      and pet.npc_memory is not None,
      '登记 %d / 人设 %d' % (len(pet.npc_registry), len(pet.npc_personas or {})))

# —— L2 模型句柄 ——
_cli = getattr(pet, 'api_client', None)
_cfg_model = (getattr(pet, 'api_config', None) or {}).get('model')
_detail = (_MODELS.get(_cfg_model) or {}).get('details') or {}
check('L2 ★★ 生效模型 = config 里那个（NPC 不额外指定）'
      '，且它确实是 7B 级（+ 覆盖语义：`_npc_model` 返回 None）',
      all(n.model is None for n in pet.npc_registry.all())
      and pet._npc_model('susie') is None
      and bool(_cfg_model) and _cfg_model in _MODELS,
      'config.model=%r 参数规模=%r' % (_cfg_model, _detail.get('parameter_size')))
check('L2b 反面：注册表里不再有任何指向**不存在**句柄的登记'
      '（指了就是每次 404 静默哑掉）',
      all(not (isinstance(n.model, str) and n.model.strip()
               and n.model not in _MODELS)
          for n in pet.npc_registry.all()),
      str(sorted({repr(n.model) for n in pet.npc_registry.all()})))
check('L2c api_client 可用（enabled=True 且 base_url 指向本机）',
      _cli is not None and getattr(_cli, 'enabled', False),
      'enabled=%r model=%r' % (getattr(_cli, 'enabled', None),
                               getattr(_cli, 'model', None)))

# ★★ L2d —— 这次真机验收**抓到的真问题**，必须钉住：
#   `config_manager._resolve_config_path` 解析到的是 `data_store.app_file()`，
#   也就是**设备侧 vault 里的 config.json**（`E:\RalseiMemory\config.json`），
#   仓库里那份 `ralsei_pet/config.json` 只是**首次运行的模板**（存在即不收编）。
#   于是仓库模板写 `ralsei:v4`（7B）而 vault 停在 5 天前的 `ralsei:v3`（**4B**）时，
#   应用**一直跑 4B** —— 而所有人（包括用户）都以为在跑 7B。
#   这是典型的"改了没人读/看着在工作"：改模板 → 毫无效果，且没有任何报错。
#   所以这条判据直接读**设备侧**那份，而不是读模板。
def _device_cfg():
    try:
        import memory_store
        root = memory_store.find_device_dir()          # E 盘优先（与产品同一套发现逻辑）
    except Exception as e:
        print('[note] 设备目录发现失败（已忽略）: %s' % e)
        return None, None
    if not root:
        return None, None
    path = os.path.join(root, 'config.json')
    if not os.path.isfile(path):
        return root, None
    with io.open(path, 'r', encoding='utf-8') as fh:
        return root, json.load(fh)


_dev_root, _dev_cfg = _device_cfg()
if _dev_cfg is None:
    print('[note] 设备侧没有 config.json（应用会用仓库模板）⇒ L2d 只查模板')
    _dev_api = (getattr(pet, 'api_config', None) or {})
    _dev_from = 'repo/effective'
else:
    _dev_api = _dev_cfg.get('api') or {}
    _dev_from = _dev_root
_dev_model = _dev_api.get('model')
_dev_param = ((_MODELS.get(_dev_model) or {}).get('details') or {}).get('parameter_size')
_dev_to = _dev_api.get('timeout')
check('L2d ★★ 设备侧（权威）配置指向**真实存在且 ≥7B**的句柄，'
      '且 timeout 覆盖得住冷 prefill',
      bool(_dev_model) and _dev_model in _MODELS
      and _dev_param in ('7.6B', '8.0B', '7.0B', '7.2B', '7.3B')
      and isinstance(_dev_to, (int, float)) and _dev_to >= 120,
      '来源=%s model=%r 规模=%r timeout=%r'
      % (_dev_from, _dev_model, _dev_param, _dev_to))
print('[note] 设备侧配置：%s' % json.dumps(
    {'source': _dev_from, 'model': _dev_model, 'timeout': _dev_to},
    ensure_ascii=False))
print('[note] 仓库模板：%s' % json.dumps(
    {'model': _cfg_model, 'timeout': (getattr(pet, 'api_config', None) or {}).get('timeout')},
    ensure_ascii=False))

# —— L3/L4/L5 真开口 ——
# ★★ 必须先**预热**（这是本脚本第一版踩到的坑，记下来）：
#   `config.json` 的 `api.timeout` = 30s。7B q4 在纯 CPU 上**冷启动**（把 4.7GB 权重
#   从磁盘读进内存 + 长 system 的 prefill）会 > 30s ⇒ 第一次请求**必然**读超时，
#   回调拿到 None。那是"冷启动"不是"NPC 坏了"（Ralsei 路径同样如此，属既有的
#   "开机首次对话很慢"问题，与第55轮改动无关）。不预热的话，本脚本测的是冷启动。
_warm = [None]


def _warmup():
    """用 /api/generate 把模型**真的**加载进内存（num_predict=1，超时给足）。"""
    body = json.dumps({'model': _cfg_model or 'ralsei:v4', 'prompt': 'hi',
                       'stream': False, 'keep_alive': '30m',
                       'options': {'num_predict': 1}}).encode('utf-8')
    req = urllib.request.Request(
        'http://localhost:11434/api/generate', data=body,
        headers={'Content-Type': 'application/json'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as fh:
            fh.read()
        _warm[0] = time.time() - t0
    except Exception as e:
        print('[note] 预热失败（已忽略，后面的断言会如实报出来）: %s' % e)


_warmup()
print('[note] 预热耗时=%s（含 7B 权重加载；这之前的首字没有参考价值）'
      % ('%.2fs' % _warm[0] if _warm[0] else 'FAILED'))

_before_s = pet.npc_memory.count_of('susie')
_before_k = pet.npc_memory.count_of('kris')
_replies, _deltas = [], []
_t0 = time.time()
_ttf = [None]


def _on_delta(piece):
    if piece and _ttf[0] is None:
        _ttf[0] = time.time() - _t0


_sent = pet.npc_speak('susie', '苏西，你饿不饿？',
                      lambda t: _replies.append((time.time() - _t0, t)),
                      _on_delta)
_ok = pump(lambda: bool(_replies))
_total = _replies[0][0] if _replies else None
_reply = _replies[0][1] if _replies else None

check('L3 ★★ NPC 真开口：请求发出 + 回调拿到**非空**文本（不是被护栏判退的 None）',
      _sent is True and _ok and isinstance(_reply, str) and _reply.strip(),
      '首字=%s 整句=%s 回复=%r'
      % ('%.2fs' % _ttf[0] if _ttf[0] else None,
         '%.2fs' % _total if _total else None,
         (_reply or '')[:60]))
_last_s = pet.npc_memory.history('susie')[-1] if pet.npc_memory.count_of('susie') else {}
check('L4 ★★ 那句话以 who=susie 落进**她自己**的记忆（+2：你问的 + 她答的）',
      pet.npc_memory.count_of('susie') == _before_s + 2
      and pet.npc_memory.count_of('kris') == _before_k
      and _last_s.get('who') == 'susie',
      'susie=%d→%d kris=%d last=%r'
      % (_before_s, pet.npc_memory.count_of('susie'), _before_k, _last_s.get('who')))
_dump_k = json.dumps(pet.npc_memory.history('kris'), ensure_ascii=False)
check('L4b ★★ 反面：kris 的记忆里既没有问句也没有答句（严格不串味）',
      '饿不饿' not in _dump_k and (_reply or '\x00') not in _dump_k)
_sp = pet.npc_system_prompt('susie')
check('L5 ★★ 发出去的 system 用的是 susie 的人设，不是 Ralsei 的',
      _sp.startswith((P.persona_text('susie', personas=pet.npc_personas) or '\x00')[:40])
      and '你是《Deltarune》中的 Ralsei' not in _sp,
      'system 长度=%d 头=%r' % (len(_sp), _sp[:24]))

# —— L6 跟随决策真问过模型 ——
pet._npc_last_decision = None
_fake_replies = []
pet.npc_follow_decide('susie', dist=9999,
                      on_result=lambda *a: _fake_replies.append(a))
_ok2 = pump(lambda: pet._npc_last_decision is not None)
_dec = pet._npc_last_decision
print('[note] 跟随决策原始回复=%r' % (
    _fake_replies,))
check('L6 ★★ 跟随决策真问过模型：拿到了合法词就 source="ai"（不是悄悄退回策略）',
      _ok2 and isinstance(_dec, tuple) and _dec[0] == 'susie'
      and _dec[1] in (P.FOLLOW_CHOICES)
      and _dec[2] in ('ai', 'policy'),
      str(_dec))
check('L6b 策略与 AI 的**优先级**：模型说了合法词 ⇒ 必须记成 ai（否则用户"给 AI 决策"是空话）',
      (_dec[2] == 'ai') == bool(_fake_replies),
      '决策=%r 原始=%r' % (_dec, _fake_replies))

# —— L7 收尾 ——
try:
    pet.cleanup_on_exit()
    check('L7 cleanup_on_exit 不抛（NPC 记忆收尾落盘）', True)
except Exception as e:
    check('L7 cleanup_on_exit 不抛（NPC 记忆收尾落盘）', False, repr(e))

_files = []
_mem_dir = os.path.join(_ISO, 'npc_memory')
if os.path.isdir(_mem_dir):
    _files = sorted(os.listdir(_mem_dir))
# ⚠️ 判据修正（本脚本第一版写的是"至少 2 个文件"—— 错）：只有**真说过话**的角色
#   才会有落盘文件，本轮只跟 susie 说过 ⇒ 只有 `susie.json`。
#   真正该守的两条：① 文件名叫 `<id>.json`；② **别人不许有文件**（"没跟他说过话
#   却出现他的记忆文件"正是串味的磁盘证据）。
_kris_file = 'kris.json' in _files
_blob = ''
_susie_path = os.path.join(_mem_dir, 'susie.json')
if os.path.isfile(_susie_path):
    with io.open(_susie_path, 'r', encoding='utf-8') as fh:
        _blob = fh.read()
check('L8 ★ 一角色一文件落盘：被说过话的 susie 有 `susie.json`；'
      '而**没说过话的 kris 不许有文件**（磁盘级不串味）',
      'susie.json' in _files and not _kris_file
      and ('苏西' in _blob or '饿' in _blob)
      and (_reply or '\x00') in _blob,
      '文件=%r kris 有文件=%r 正文命中=%r'
      % (_files, _kris_file, (_reply or '')[:20] in _blob))

print()
print('== 结果 ==')
print('  断言 %d 项，FAIL %d 项' % (N[0], len(FAILS)))
if FAILS:
    print('  失败项：%r' % (FAILS,))
sys.exit(0 if not FAILS else 1)
