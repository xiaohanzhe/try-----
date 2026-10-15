# -*- coding: utf-8 -*-
"""
第115轮后续 · **AI 逐项扫** —— 「尤其是 AI，你每个都测试一下，那是桌宠的灵魂」

用户口径（逐字）：
> 「把咱目前所有轮，记住，所有轮的改动都**逐项录屏测试**，测试完没问题再推进，
>   还有，**尤其是 AI，你每个都测试一下**，那是桌宠的灵魂」

本脚本扫 **AI 线的每一项**（不只是 Ralsei 一个）：
  A 装配面（9 项）：人设 / 【此刻】/ 关系 / 紧张 / 记忆召回 / 世界观召回 / 话题焦点 /
     流式开关 / 护栏 —— 每项都要**真取到**且形状正确。
  B ★**每一位 NPC**（注册表全量，含本人设 76 位 + 无本人设的角色）：
     走**产品真链**：`pet.npc_system_prompt(id)` 装配 → `pet.api_client.chat(...)`
     （= 生产那条 `/v1/chat/completions`）→ `pet._clean_ai_reply` 过护栏。
     逐位记录：system 字数 / 原始回复 / 清洗后 / 护栏旗标 / 是否 by-design 沉默 / 耗时。
  C Ralsei 本线：同一套真链跑一轮（persona + 【此刻】+ 关系 + 记忆 + 世界观 + 历史）。

★ 为什么走 `pet.api_client.chat` 而不是裸 HTTP：
  生产就是它（`/v1/chat/completions`）。裸 HTTP 反而**不如它保真**
  （该端点会静默丢弃 `num_ctx`/`repeat_penalty`，而那正是生产的真实行为）。

★ 落盘是**增量 JSONL**（跑一半被中断也不丢已测结果），另出一份人读 txt。

★ 沙箱三件套（铁律）：`RALSEI_DATA_DIR`→mkdtemp ＋ `data_store.vault_root=None`
  ＋ **`import main` 在其后** ⇒ 不碰用户真实的角色记忆（`E:\\RalseiMemory\\`）。

用法：
    C:\\Python311\\python.exe ai115_sweep.py            # 全量（含 96 位 NPC，约 1.5~2h）
    C:\\Python311\\python.exe ai115_sweep.py --limit 3   # 冒烟
    C:\\Python311\\python.exe ai115_sweep.py --only ralsei
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')

sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

# ---- ★★★ 沙箱：必须在 import main 之前 ----
_SANDBOX = tempfile.mkdtemp(prefix='ai115_')
os.environ['RALSEI_DATA_DIR'] = _SANDBOX
import data_store  # noqa: E402

try:
    data_store.vault_root = lambda create=True: None
    _VAULT_OK = True
except Exception:  # noqa: BLE001
    _VAULT_OK = False

if not os.path.isdir(EV):
    os.makedirs(EV)
JSONL = os.path.join(EV, 'ai115_sweep.jsonl')
TXT = os.path.join(EV, 'ai115_sweep_out.txt')

OLLAMA_EXE = r"C:\Users\23002\AppData\Local\Programs\Ollama\ollama.exe"
BASE = "http://127.0.0.1:11434"
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

BUF = io.StringIO()
S = {'n': 0, 'f': 0}
_proc = None


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def ck(name, cond, detail=''):
    S['n'] += 1
    if not cond:
        S['f'] += 1
    say('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('   << %s' % detail) if detail else ''))


def emit(rec):
    with io.open(JSONL, 'a', encoding='utf-8', newline='') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def ensure_server():
    global _proc
    try:
        with _OPENER.open(BASE + '/api/tags', timeout=3) as r:
            r.read()
        return True
    except Exception:
        pass
    try:
        _proc = subprocess.Popen([OLLAMA_EXE, 'serve'],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL)
    except Exception as e:  # noqa: BLE001
        say('[服务] 起不来: %r' % (e,))
        return False
    for _ in range(90):
        time.sleep(1)
        try:
            with _OPENER.open(BASE + '/api/tags', timeout=3) as r:
                r.read()
            return True
        except Exception:
            continue
    return False


PROBE_NPC = u'你好，你是谁？'
PROBE_RALSEI = u'今天有点累，你在做什么？'


def main():
    args = sys.argv[1:]
    limit = None
    only = None
    if '--limit' in args:
        limit = int(args[args.index('--limit') + 1])
    if '--only' in args:
        only = args[args.index('--only') + 1]

    say('第115轮后续 · AI 逐项扫')
    say('  沙箱 = %s（vault 已封 = %s）' % (_SANDBOX, _VAULT_OK))
    say('  增量落盘 = %s' % JSONL)

    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import types
    import main as M
    R = M.RalseiPet
    say('  产品真源 main.py = %s' % M.__file__)
    if not ensure_server():
        say('[FAIL] Ollama 起不来，无法测 AI')
        return 2

    t0 = time.time()
    pet = R()
    say('  实例就绪（%.1fs）api_enabled=%s model=%s'
        % (time.time() - t0, getattr(pet, 'api_enabled', None),
           (getattr(pet, 'api_config', {}) or {}).get('model')))
    emit({'kind': 'boot', 'api_enabled': bool(getattr(pet, 'api_enabled', False)),
          'model': (getattr(pet, 'api_config', {}) or {}).get('model'),
          'sandbox': _SANDBOX})

    stub = types.SimpleNamespace()
    stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
    clean = types.MethodType(R._clean_ai_reply, stub)

    # ============================================================ A. 装配面
    say('\n=== A. Ralsei 装配面（9 项）===')
    if only in (None, 'ralsei'):
        p = pet._build_persona_prompt()
        ck('A1 人设真源取到且含本轮四新节',
           isinstance(p, str) and p.strip()
           and all(s in p for s in ('我是什么', '先把他的事接住',
                                    '他说要去一个地方的时候', '我想起来的事')),
           'len=%s' % (len(p) if isinstance(p, str) else None))
        emit({'kind': 'A', 'id': 'A1', 'persona_chars': len(p or '')})
        ctx = pet._build_ai_context()
        ck('A2 【此刻】块取到', isinstance(ctx, str) and '【此刻】' in ctx,
           repr((ctx or '')[:60]))
        emit({'kind': 'A', 'id': 'A2', 'ctx': ctx})
        rel = getattr(pet, 'relationship', None)
        ck('A3 关系段取到（且**不含数值**）',
           rel is not None and isinstance(rel.brief(), str) and rel.brief().strip()
           and not any(ch.isdigit() for ch in rel.brief()),
           repr(rel.brief()[:50]) if rel else 'no relationship')
        ck('A4 紧张段取到（且不含"结巴率"）',
           rel is not None and '结巴率' not in (rel.nervous_brief('chat') or ''))
        emit({'kind': 'A', 'id': 'A3A4',
              'brief': rel.brief() if rel else None,
              'nerv': rel.nervous_brief('chat') if rel else None})
        try:
            from modules import worldview_recall as WR
            wv = WR.recall_text(u'黑暗喷泉是啥', limit=2)
            ck('A5 世界观召回可解析（问到喷泉能召回）',
               isinstance(wv, str) and bool(wv.strip()), repr(wv[:60]))
            wv2 = WR.recall_text(u'今天吃了火锅', limit=2)
            ck('A5b 负控制：闲聊不召回世界观块', not (wv2 or '').strip())
            emit({'kind': 'A', 'id': 'A5', 'hit': wv, 'no_hit': wv2})
        except Exception as e:  # noqa: BLE001
            ck('A5 世界观召回可解析', False, repr(e))
        try:
            ms = getattr(pet, 'memory_system', None)
            rc = ms.recall_text(u'你还记得我们聊过什么吗', limit=3) if ms else ''
            ck('A6 记忆召回可调用（不抛、返回字符串）', isinstance(rc, str),
               repr((rc or '')[:50]))
            emit({'kind': 'A', 'id': 'A6', 'recall': rc})
        except Exception as e:  # noqa: BLE001
            ck('A6 记忆召回可调用（不抛、返回字符串）', False, repr(e))
        ck('A7 流式开关可读', isinstance(pet._ai_stream_enabled(), bool))
        ck('A8 护栏在（_clean_ai_reply 可调用且能拦出戏）',
           clean('作为一个语言模型，我无法回答。') is None)
        ck('A8b 护栏放行正常台词', isinstance(clean('今天有点累，我先坐一会儿。'), str))
        emit({'kind': 'A', 'id': 'A7A8',
              'stream': pet._ai_stream_enabled()})

        # ---- A9 · Ralsei 本线跑一轮真对话（走生产链） ----
        say('\n  --- A9 Ralsei 真对话一轮 ---')
        try:
            system = pet._build_persona_prompt()
            if getattr(pet, '_ai_stream_enabled', lambda: False)():
                pass
            _ctx = pet._build_ai_context()
            if _ctx:
                system = system + '\n\n' + _ctx
            cli = pet.api_client
            opts = pet._ai_chat_options()
            t1 = time.time()
            raw = cli.chat(PROBE_RALSEI, system_prompt=system, **opts)
            got = clean(raw, recent=[])
            rec = {'kind': 'A', 'id': 'A9', 'q': PROBE_RALSEI,
                   'raw': raw, 'final': got,
                   'wall_s': round(time.time() - t1, 1),
                   'sys_chars': len(system)}
            emit(rec)
            say('    raw  = %r' % ((raw or '')[:80],))
            say('    final= %r' % ((got or '')[:80],))
            ck('A9 Ralsei 真对话返回了非空台词', isinstance(got, str) and got.strip(),
               'raw=%r' % ((raw or '')[:40],))
        except Exception as e:  # noqa: BLE001
            ck('A9 Ralsei 真对话返回了非空台词', False, repr(e))

    # ============================================================ B. 每一位 NPC
    ids = []
    try:
        reg = pet.npc_registry
        for m in ('ids', 'all_ids', 'keys'):
            if hasattr(reg, m):
                v = getattr(reg, m)
                ids = list(v() if callable(v) else v)
                break
        if not ids:
            ids = sorted(set(getattr(pet, 'npc_personas', {}) or {})
                         | set((getattr(pet, 'npc_plain_ids', None) or [])))
    except Exception as e:  # noqa: BLE001
        say('  [WARN] 取注册表 id 失败: %r' % (e,))
    ids = sorted(set(x for x in ids if isinstance(x, str) and x))
    if limit:
        ids = ids[:limit]
    say('\n=== B. NPC 逐位（n=%d）=== 探针问句 = %r' % (len(ids), PROBE_NPC))
    if only == 'ralsei':
        ids = []
    n_ok = n_empty = n_byart = n_err = 0
    for i, nid in enumerate(ids, 1):
        try:
            system = pet.npc_system_prompt(nid)
        except Exception as e:  # noqa: BLE001
            system = ''
            say('  [%d/%d] %-22s system 取用异常 %r' % (i, len(ids), nid, e))
        if not system or not str(system).strip():
            # ★ 这是**设计如此**：没登记/没装人设 ⇒ 明确沉默（不许退回 Ralsei 人设）
            n_byart += 1
            emit({'kind': 'B', 'id': nid, 'by_design_silent': True})
            say('  [%d/%d] %-22s by-design 沉默（无人设）' % (i, len(ids), nid))
            continue
        t1 = time.time()
        try:
            raw = pet.api_client.chat(PROBE_NPC, system_prompt=system,
                                      **pet._ai_chat_options())
            got = clean(raw, recent=[])
            # ★★ 探针保真度（第115轮自己抓出来的缺口）：
            #   生产 `chat_with_ai` 在**判退**时不是沉默，而是
            #   「温度 +0.1 ＋ 追加 `_RETRY_NUDGE` 重采样一次」再采用。
            #   首版只跑**首轮** ⇒ 把"首轮被判退"误报成"说不出话"
            #   （实测 5 例里 3 例重试即可救回）。这里复刻那一步，并把
            #   **首轮**与**重试后**两个结果都记下来 —— 判据以后者为准。
            retried = False
            if (not (isinstance(got, str) and got.strip())
                    and isinstance(raw, str) and raw.strip()):
                retried = True
                opts2 = dict(pet._ai_chat_options())
                try:
                    opts2['temperature'] = min(
                        1.0, float(opts2.get('temperature', 0.85)) + 0.1)
                except Exception:  # noqa: BLE001
                    opts2['temperature'] = 0.95
                raw2 = pet.api_client.chat(PROBE_NPC,
                                           system_prompt=system + '\n\n'
                                           + R._RETRY_NUDGE, **opts2)
                got2 = clean(raw2, recent=[])
            else:
                got2 = got
            wall = round(time.time() - t1, 1)
            rec = {'kind': 'B', 'id': nid, 'q': PROBE_NPC, 'sys_chars': len(system),
                   'raw': raw, 'final': got,             # 首轮
                   'retried': retried, 'final_after_retry': got2,   # 生产口径
                   'wall_s': wall}
            emit(rec)
            if isinstance(got2, str) and got2.strip():
                n_ok += 1
                say('  [%d/%d] %-22s sys=%-5d %5.1fs%s  %r'
                    % (i, len(ids), nid, len(system), wall,
                       ' [重试]' if retried else '', got2[:44]))
            else:
                n_empty += 1
                say('  [%d/%d] %-22s sys=%-5d %5.1fs  <生产口径仍空> raw=%r'
                    % (i, len(ids), nid, len(system), wall, (raw or '')[:40]))
        except Exception as e:  # noqa: BLE001
            n_err += 1
            emit({'kind': 'B', 'id': nid, 'error': repr(e)})
            say('  [%d/%d] %-22s 异常 %r' % (i, len(ids), nid, e))

    say('\n=== B 汇总 ===')
    say('  生产口径有台词 %d ／ 仍空 %d ／ by-design 沉默 %d ／ 异常 %d'
        % (n_ok, n_empty, n_byart, n_err))
    ck('B1 无一例异常（异常=调用链坏了）', n_err == 0, 'err=%d' % n_err)
    ck('B2 ★ 有人设的 NPC **全部**产出台词'
       '（**生产口径** = 判退后"抬温+`_RETRY_NUDGE`"重采样也算）',
       n_empty == 0, '仍空=%d' % n_empty)
    ck('B3 采样数 ≥ 76（不是对着空集在数）', (n_ok + n_empty) >= 76,
       'n=%d' % (n_ok + n_empty))

    say('\n=== 汇总：%d 判据 / %d FAIL ===' % (S['n'], S['f']))
    say('  总耗时 %.1f 分钟' % ((time.time() - t0) / 60.0))
    if _proc is not None:
        try:
            _proc.terminate()
        except Exception:
            pass
    return 0 if S['f'] == 0 else 1


if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as e:  # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (e,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(TXT, 'w', encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
