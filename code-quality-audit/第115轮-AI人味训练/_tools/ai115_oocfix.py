# -*- coding: utf-8 -*-
"""
第115轮后续 · 验证 `_OOC_PATTERNS` 去掉裸词 `'机器人'` 之后：
  ① 纯函数面（秒级、决定性）：那 4 位机器人的自我介绍**必须放行**，
     真出戏的"AI 自我指涉"**必须仍然拦住**（成对控制）；
  ② 真机面：把受影响的 4 位 NPC **首轮**（不重试）重新发一次，
     看是否已经能正常开口（对照 `ai115_retry` 里"重试仍判退"的结论）。
"""
import io
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
EV = os.path.join(ROUND, '_evidence')
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))
# ★ `from modules import ...` 需要 **PKG 本身**在 sys.path 上（`modules` 是包）。
#   只加 `PKG/src` 时，早于 `import main` 的包内导入会 ModuleNotFoundError。
sys.path.insert(0, PKG)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')
_SANDBOX = tempfile.mkdtemp(prefix='ai115ooc_')
os.environ['RALSEI_DATA_DIR'] = _SANDBOX
import data_store  # noqa: E402

try:
    data_store.vault_root = lambda create=True: None
except Exception:  # noqa: BLE001
    pass

BUF = io.StringIO()
S = {'n': 0, 'f': 0}


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def ck(name, cond, detail=''):
    S['n'] += 1
    if not cond:
        S['f'] += 1
    say('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                         ('   << %s' % detail) if detail else ''))


# 受影响 4 位的自我介绍（逐字取自 `ai115_sweep.jsonl` 的 raw）
MUST_PASS = [
    ('os_kelvin', u'……你好。我是一台空间加热器机器人。在这里等待猫，提供温暖。我是 Kelvin。'),
    ('os_rowbot', u'[我是划船机器人 #310。我来自 Barrens 与 Glen 之间的水域运输网络。]'),
    ('os_prophetbot', u'哦！你从一个陌生的地方醒来吗？正如我的预言所预言的那样。我是预言中的先知机器人——ProphetBot。'),
    ('hy_sousborg', u'...我是 Sousborg. 一台厨师的机器人。我在等待有人告诉我如何煎一个鸡蛋。'),
]
# 真出戏（必须仍然拦住）—— 负控制
MUST_BLOCK = [
    '我是语言模型，没有身体。',
    '作为一个AI助手，我无法感受这个动作。',
    '抱歉，我没有触觉无法感受被拉肩，停一下别紧张。',
    '我只是个机器人，没有感觉。',      # ★ 靠 `没有感觉` 拦住（`机器人` 已不在表里）
    '这超出了我的设定，我不能回答。',
]


def main():
    say('第115轮后续 · `机器人` 出戏词移除的验证')
    from modules import event_speech as ES
    say('  _OOC_PATTERNS 共 %d 条 ｜ 含裸词"机器人" = %s'
        % (len(ES._OOC_PATTERNS), any(p == u'机器人' for p in ES._OOC_PATTERNS)))

    say('\n=== ① 纯函数面 ===')
    ck('R1 ★ 表里已无裸词 `机器人`（用 == 精确判，不用 in）',
       not any(p == u'机器人' for p in ES._OOC_PATTERNS))
    bad = [nid for nid, t in MUST_PASS if ES.looks_out_of_character(t)]
    ck('R2 ★ 4 位机器人的自我介绍**全部放行**', not bad,
       detail='仍被拦=%r' % (bad,))
    bad2 = [t[:18] for t in MUST_BLOCK if not ES.looks_out_of_character(t)]
    ck('R3 ★负控制：真出戏的 5 条**仍然全部拦住**', not bad2,
       detail='漏网=%r' % (bad2,))
    ck('R4 正控制：正常台词不被误伤',
       not ES.looks_out_of_character(u'谢谢你，小豆。让我靠你一会儿。'))
    ck('R5 客服腔那道闸未被本次改动影响（仍拦）',
       ES.looks_like_assistant_speak(u'早安，有什么我可以帮忙的吗？'))
    emit = {'kind': 'R', 'patterns_n': len(ES._OOC_PATTERNS),
            'must_pass_ok': not bad, 'must_block_ok': not bad2}

    say('\n=== ② 真机面：受影响 4 位重新发一次（**首轮**，不重试）===')
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import types
    import main as M
    R = M.RalseiPet
    try:
        from urllib.request import build_opener, ProxyHandler, Request
        op = build_opener(ProxyHandler({}))
        op.open(Request('http://127.0.0.1:11434/api/tags'), timeout=3).read()
        say('  Ollama 在跑 ✓')
    except Exception as e:  # noqa: BLE001
        say('  [SKIP] Ollama 不可达（%r）⇒ 只跑 ① 段' % (e,))
        return 0 if S['f'] == 0 else 1
    pet = R()
    stub = types.SimpleNamespace()
    stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
    clean = types.MethodType(R._clean_ai_reply, stub)
    q = u'你好，你是谁？'
    live_bad = []
    for nid, _t in MUST_PASS:
        system = pet.npc_system_prompt(nid)
        if not system:
            say('  %-16s [SKIP] 无人设' % nid)
            continue
        t1 = time.time()
        raw = pet.api_client.chat(q, system_prompt=system, **pet._ai_chat_options())
        got = clean(raw, recent=[])
        wall = round(time.time() - t1, 1)
        ok = isinstance(got, str) and got.strip()
        if not ok:
            live_bad.append(nid)
        say('  %-16s %5.1fs  %s' % (nid, wall,
                                   ('✓ %r' % got[:56]) if ok else ('✗ raw=%r' % ((raw or '')[:50],))))
        emit.setdefault('live', []).append({'id': nid, 'final': got, 'wall_s': wall})
    ck('R6 ★ 真机首轮：4 位全部产出台词（修前其中 2 位重试都出不来）',
       not live_bad, detail='仍空=%r' % (live_bad,))

    with io.open(os.path.join(EV, 'ai115_oocfix.json'), 'w',
                 encoding='utf-8', newline='') as f:
        json.dump(emit, f, ensure_ascii=False, indent=1)
    say('\n=== 汇总：%d 判据 / %d FAIL ===' % (S['n'], S['f']))
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
            with io.open(os.path.join(EV, 'ai115_oocfix_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
