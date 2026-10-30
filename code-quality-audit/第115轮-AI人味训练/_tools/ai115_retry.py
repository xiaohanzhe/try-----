# -*- coding: utf-8 -*-
"""
第115轮后续 · 复核 AI 全量扫里那 5 例「空 / 被判退」

★ 先说清**探针保真度**问题（自我归因，别甩锅产品）：
  `ai115_sweep.py` 只调了**一次** `_clean_ai_reply`，**没走生产的重试路径**。
  而生产（`chat_with_ai`）是：
      raw → 护栏判退 → **温度 +0.1 + 追加 `_RETRY_NUDGE` 重采样一次** → 采用
  ⇒ 所以"首轮被判退"**不等于**"用户看不到台词"。B2 那条判据据此偏严。

本脚本做两件事（都在**真机实例 + 真 Ollama** 上）：
  1. **归因**：把护栏**逐道闸**拆开跑，指出**具体是哪一道**把这条判退的
     （0a 括号动作 / 0b markdown / 纯标点 / 0c 出戏 / 0c 客服腔 / 1 角色标记 / 2 车轱辘话）。
  2. **复刻生产的重试**：抬温 + `_RETRY_NUDGE` 重发一次 ⇒ 看**用户最终会不会看到台词**。
     这才是"人味与可用性"的真实口径。
"""
import io
import json
import os
import re
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
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')
_SANDBOX = tempfile.mkdtemp(prefix='ai115r_')
os.environ['RALSEI_DATA_DIR'] = _SANDBOX
import data_store  # noqa: E402

try:
    data_store.vault_root = lambda create=True: None
except Exception:  # noqa: BLE001
    pass

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def main():
    say('第115轮后续 · 复核 5 例「空/判退」（含生产重试路径）')
    recs = []
    with io.open(os.path.join(EV, 'ai115_sweep.jsonl'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    bad = [r for r in recs if r.get('kind') == 'B' and r.get('raw')
           and not (r.get('final') or '').strip()]
    say('  JSONL 记录 %d 条 ｜ 判退/空 %d 例：%r'
        % (len(recs), len(bad), [r['id'] for r in bad]))

    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    import types
    import main as M
    from modules import event_speech as ES
    R = M.RalseiPet

    pet = R()
    stub = types.SimpleNamespace()
    stub.AI_REPLY_MAX_CHARS = R.AI_REPLY_MAX_CHARS
    stub._is_repeat_of_recent = types.MethodType(R._is_repeat_of_recent, stub)
    clean = types.MethodType(R._clean_ai_reply, stub)

    def gate_of(raw):
        """逐道闸拆开，指出**第一道**把这条判退的闸。"""
        try:
            t = raw.strip()
            if not t:
                return '0 原始就是空'
            t1 = ES.strip_action_parentheticals(t)
            if not t1:
                return '0a 括号动作旁白（删干净 ⇒ 整条作废）'
            hits_a = ES._ACTION_PAREN_RE.findall(t)
            t2 = R._md_strip_re().sub('', t1).strip()
            t2 = t2.strip('"\'“”「」『』《》').strip()
            if not t2:
                return '0b markdown 剥完为空'
            if not re.search(r'[0-9A-Za-z\u4e00-\u9fff]', t2):
                return '0b2 纯标点（无实义字符）'
            if ES.looks_out_of_character(t2):
                hit = [p for p in ES._OOC_PATTERNS if p in t2.lower()]
                return '0c-出戏（命中 %r）' % (hit,)
            if ES.looks_like_assistant_speak(t2):
                hit = [p for p in ES._BANNED_PATTERNS if p in t2.lower()]
                return '0c-客服腔/套话（命中 %r）' % (hit,)
            m = R._role_marker_re().search(t2)
            if m and m.start() == 0:
                return '1 自问自答角色标记（截完为空）'
            if len(t2) > R.AI_REPLY_MAX_CHARS:
                return '3 只是超长（**不判退**，只截断 ⇒ 不该出现在这）'
            return '?? 未命中任何闸（真 None 应来自 2 车轱辘话，但此处 recent=[]）'
        except Exception as e:  # noqa: BLE001
            return 'EXC %r' % (e,)

    say('\n=== 1. 归因（哪道闸开的）===')
    for r in bad:
        say('\n  --- %s ---' % r['id'])
        say('    raw   = %r' % r['raw'])
        say('    final = %r' % r.get('final'))
        say('    ★ 闸   = %s' % gate_of(r['raw']))

    say('\n=== 2. 复刻生产重试（抬温 + _RETRY_NUDGE 再发一次）===')
    fixed = 0
    for r in bad:
        nid = r['id']
        system = pet.npc_system_prompt(nid)
        if not system:
            say('  %-24s [SKIP] 现在取不到 system' % nid)
            continue
        opts = dict(pet._ai_chat_options())
        try:
            opts['temperature'] = min(1.0, float(opts.get('temperature', 0.85)) + 0.1)
        except Exception:  # noqa: BLE001
            opts['temperature'] = 0.95
        t1 = time.time()
        raw2 = pet.api_client.chat(
            r.get('q') or u'你好，你是谁？',
            system_prompt=system + '\n\n' + R._RETRY_NUDGE, **opts)
        got2 = clean(raw2, recent=[])
        wall = round(time.time() - t1, 1)
        ok = isinstance(got2, str) and got2.strip()
        fixed += 1 if ok else 0
        say('  %-24s %5.1fs  %s' % (nid, wall,
                                   ('救回：%r' % got2[:60]) if ok else
                                   ('**仍判退** raw=%r / 闸=%s'
                                    % ((raw2 or '')[:50], gate_of(raw2 or '')))))
    say('\n=== 3. 结论 ===')
    say('  首轮判退 %d 例 ｜ 走生产重试后救回 **%d** 例 ｜ 仍判退 %d 例'
        % (len(bad), fixed, len(bad) - fixed))
    say('  ★ 口径更正：`ai115_sweep` 的 B2「有人设的全部产出台词」偏严 ——'
        ' 它只看**首轮**，没算生产那条"判退→重采样"。真实口径应以本节的**重试后**为准。')
    return 0


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
            with io.open(os.path.join(EV, 'ai115_retry_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
