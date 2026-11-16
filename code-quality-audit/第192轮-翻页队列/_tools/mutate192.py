# -*- coding: utf-8 -*-
u"""第192轮 · 变异测试（`check192` 的 38 条判据到底有没有鉴别力）。

## 纪律（每条都强制）

1. **每条变异必须被"针对的那一条"抓住**：期望红项逐条出现在该次输出的 `[FAIL]` 里。
2. **红数必须 `0 < 红数 < 38`** —— 红 0 = 判据恒真（变异做了等于没做）；
   红 38 = 变异把文件改崩了，那不是"抓到"、是"什么都没证明"（第178轮 M3 / 第182轮同款）。
3. **锚点必须恰好命中 1 次**（源文件是纯 CRLF，`_lf()` 归一后再比）。
4. **整文件还原并核 sha1**：每次变异跑完把原文写回，sha1 必须逐字回到 `ORIG_SHA`。
5. **双跑一致**：同一条变异跑两遍，红集合必须完全相同（防"偶发假红"）。

## 无害变异（M25）

故意只改一句注释，期望 **红数 == 0**。它不是"抓到的越多越好"，
而是反过来证明"这套判据不会因为无关改动乱叫" —— 缺了它，
上面 24 条全绿也可能只是"判据对什么都红"。

不联网、零外部盘。
"""
import hashlib
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
DU_PY = os.path.join(REPO, 'ralsei_pet', 'modules', 'dialogue_ui.py')
CHECK = os.path.join(HERE, 'check192.py')
PY = sys.executable
TOTAL = 38


def _read():
    with io.open(DU_PY, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _lf(s):
    return s.replace(u'\r\n', u'\n')


def _crlf(s):
    return s.replace(u'\n', u'\r\n')


ORIG = _read()
ORIG_SHA = hashlib.sha1(ORIG.encode('utf-8')).hexdigest()


def _restore():
    with io.open(DU_PY, 'w', encoding='utf-8', newline='') as fh:
        fh.write(ORIG)
    now = hashlib.sha1(_read().encode('utf-8')).hexdigest()
    return now == ORIG_SHA


def _run():
    """跑一次 check192，返回 (红项名字前缀集合, 红数, 是否崩溃)。"""
    p = subprocess.run([PY, CHECK], cwd=HERE, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    fails = re.findall(r'^\[FAIL\]\s+([A-Z]\d+[a-z]?)', out, re.M)
    crashed = (u'合计：' not in out)
    return set(fails), len(fails), crashed


# ============================================================ 变异表
# (编号, 说明, old, new, 期望被抓住的判据前缀)
MUTS = []

MUTS.append(('M1', u'`PAGE_DWELL_MS` 2000 -> 500',
             u'    PAGE_DWELL_MS = 2000',
             u'    PAGE_DWELL_MS = 500', ['A2']))

MUTS.append(('M2', u'`_init_state` 删 `self._pages = []`',
             u'        self._pages = []\n        self._page_idx = 0\n'
             u'        #: 前台那一句在 `_pages` 里的下标',
             u'        self._page_idx = 0\n'
             u'        #: 前台那一句在 `_pages` 里的下标', ['A3']))

MUTS.append(('M3', u'`_page_timer` 不再是 singleShot',
             u'        self._page_timer.setSingleShot(True)',
             u'        self._page_timer.setSingleShot(False)', ['A4']))

MUTS.append(('M4', u'`_page_dwell_fire` 不再翻页',
             u'        """静置到点 ⇒ 翻一页（**只走一格**，绝不跳）。"""\n        self.advance_page()',
             u'        """静置到点 ⇒ 翻一页（**只走一格**，绝不跳）。"""\n        return', ['A5']))

MUTS.append(('M5', u'绑一个 `Z` 键（与 R5 附身抢键）',
             u'            if event.key() == Qt.Key_X and self.is_typing',
             u'            if event.key() == Qt.Key_Z:\n'
             u'                return True\n'
             u'            if event.key() == Qt.Key_X and self.is_typing', ['A6']))

MUTS.append(('M6', u'`advance_page` 改成"直接跳到末页"',
             u'            self._page_idx += 1',
             u'            self._page_idx = len(self._pages) - 1', ['B1']))

MUTS.append(('M7', u'`_push_page` 顺手把游标推到末页（新页到达就跳页）',
             u'        self._hist_synced = len(self._pages)\n        self._arm_page_timer()',
             u'        self._hist_synced = len(self._pages)\n'
             u'        self._page_idx = len(self._pages) - 1\n'
             u'        self._arm_page_timer()', ['B3']))

MUTS.append(('M8', u'`_arm_page_timer` 里偷改游标',
             u'                self._page_timer.start(self.PAGE_DWELL_MS)',
             u'                self._page_idx += 1\n'
             u'                self._page_timer.start(self.PAGE_DWELL_MS)', ['B4']))

MUTS.append(('M9', u'`_push_page` 不写 `_history_html`（双轨断一条）',
             u'        self._pages.append(blob)\n        self._history_html += blob',
             u'        self._pages.append(blob)', ['C1']))

MUTS.append(('M10', u'★ `_start_typing` 把打字页提前写进历史（H4b 那种破法）',
             u'            self._typing_page = len(self._pages) - 1\n',
             u'            self._typing_page = len(self._pages) - 1\n'
             u'            self._history_html += self._pages[-1]\n', ['C2', 'C5']))

MUTS.append(('M11', u'`_sync_typing_page_into_history` 不推进 `_hist_synced`',
             u'            self._history_html += self._pages[i]\n'
             u'            self._hist_synced = i + 1',
             u'            self._history_html += self._pages[i]', ['C3']))

MUTS.append(('M12', u'在 `add_dialogue` 里额外补一次同步（不在 commit 时机）',
             u'                self._reset_pages()   # ★ 第192轮：页游标跟着清（游标不清会指到旧页）',
             u'                self._reset_pages()   # ★ 第192轮：页游标跟着清（游标不清会指到旧页）\n'
             u'                self._sync_typing_page_into_history()', ['C4']))

MUTS.append(('M13', u'`current_page_html` 越界不钳',
             u'                i = max(0, min(int(self._page_idx), len(self._pages) - 1))',
             u'                i = int(self._page_idx)', ['D5']))

MUTS.append(('M14', u'`add_narration` 不落页（旁白退化成历史拼接）',
             u'        # ★ 第192轮：旁白**单独一页**（用户：括号换不出表情的就交给旁白）\n'
             u'        self._push_page(blob)',
             u'        # ★ 第192轮：旁白**单独一页**（用户：括号换不出表情的就交给旁白）\n'
             u'        self._history_html += blob', ['D1']))

MUTS.append(('M15', u'单击不再翻页',
             u'            elif self.advance_page():',
             u'            elif False:', ['E1']))

MUTS.append(('M16', u'单击时不再先停打字机（优先级被打乱）',
             u'                self.stop_typing()\n            elif self.advance_page():',
             u'                pass\n            elif self.advance_page():', ['E2']))

MUTS.append(('M17', u'输入框空回车不再翻页',
             u'                    else:\n                        self.advance_page()',
             u'                    else:\n                        pass', ['E3']))

MUTS.append(('M18', u'`hide_dialogue` 不停翻页计时',
             u'        # ★ 第192轮：收起时停掉翻页计时（对话框都看不见了，不该再自己翻页）\n'
             u'        try:\n            self._page_timer.stop()',
             u'        # ★ 第192轮：收起时停掉翻页计时（对话框都看不见了，不该再自己翻页）\n'
             u'        try:\n            pass', ['E5']))

MUTS.append(('M19', u'★ `_typing_own_page` 恒 False（旁白必被前台顶掉）',
             u'            return int(self._page_idx) < int(self._typing_page)',
             u'            return False', ['F1', 'F3']))

MUTS.append(('M20', u'★ 三分支里"只画那一页"改成"前台独占"',
             u'                #   前台先不出现。等游标走到它（`advance_page`）才开打字机。\n'
             u'                pass',
             u'                #   前台先不出现。等游标走到它（`advance_page`）才开打字机。\n'
             u'                html = _typing_div', ['F4']))

MUTS.append(('M21', u'`_reset_pages` 顺手清历史',
             u'        """清空页游标（**不动 `_history_html`** —— 那句留在调用点，A2a/A2b 盯着它）。"""\n'
             u'        self._pages = []',
             u'        """清空页游标（**不动 `_history_html`** —— 那句留在调用点，A2a/A2b 盯着它）。"""\n'
             u'        self._history_html = \'\'\n'
             u'        self._pages = []', ['G1']))

MUTS.append(('M22', u'`_reset_pages` 不清游标',
             u'        self._pages = []\n        self._page_idx = 0\n        self._hist_synced = 0',
             u'        self._pages = []\n        self._hist_synced = 0', ['G2']))

MUTS.append(('M23', u'`advance_page` 走到打字页也不开打',
             u'            if self._page_idx == self._typing_page:\n'
             u'                self._begin_typing_at_page()',
             u'            if self._page_idx == self._typing_page:\n                pass', ['G4']))

MUTS.append(('M24', u'少一处"清历史"跟随点（NPC 那条不清页游标）',
             u'        self._reset_pages()   # ★ 第192轮：一个框只装当前这一条 ⇒ 页游标也必须归零',
             u'        pass   # 少一处跟随点', ['G3']))

# ---- 无害变异：只改注释，期望**红 0**
MUTS.append(('M25', u'【无害】只改一句注释',
             u'    #: ★★★ 第192轮：一框一条。',
             u'    #: 第192轮：一框一条。', []))


def _apply(old, new):
    """把源文件改成变异体。返回 (是否成功, 说明)。"""
    src = _lf(ORIG)
    ol, nl = _lf(old), _lf(new)
    n = src.count(ol)
    if n != 1:
        return False, u'锚点命中 %d 次（期望 1）' % n
    with io.open(DU_PY, 'w', encoding='utf-8', newline='') as fh:
        fh.write(_crlf(src.replace(ol, nl)))
    return True, u'ok'


print(u'=' * 72)
print(u'第192轮 变异测试  dialogue_ui.py sha1=%s' % ORIG_SHA[:16])
print(u'=' * 72)

rows = []
bad = []
for mid, desc, old, new, expect in MUTS:
    ok, msg = _apply(old, new)
    if not ok:
        print(u'[ERROR] %-4s %s  ->  %s' % (mid, desc, msg))
        bad.append((mid, u'锚点失效'))
        _restore()
        continue

    fails1, n1, crash1 = _run()
    fails2, n2, crash2 = _run()
    same = (fails1 == fails2)

    restored = _restore()

    if mid == 'M25':
        pass_ok = (n1 == 0 and n2 == 0 and not crash1)
        tag = u'PASS' if (pass_ok and same and restored) else u'FAIL'
        print(u'[%s] %-4s %-46s 红=%d/%d 双跑一致=%s 还原=%s'
              % (tag, mid, desc, n1, TOTAL, same, restored))
        if tag != u'PASS':
            bad.append((mid, u'无害变异却报红 %d' % n1))
        rows.append((mid, n1, tag))
        continue

    miss = [e for e in expect if e not in fails1]
    in_range = (0 < n1 < TOTAL)
    # ★ "崩"的两种形态要分开：
    #   · 崩了**且红 0** ⇒ 致命（一条 [FAIL] 都打不出来，等于什么都没证明，第178轮 M3 同款）；
    #   · 崩了**但期望的判据先红了** ⇒ 算抓到。典型是 M2：删掉 `self._pages = []` 后
    #     A3 先给出 FAIL，接着 `build_ui` 里 `_push_page` 撞 AttributeError 才崩
    #     —— 那是产品在非法状态下的必然反应，不该反过来判"测试没抓到"。
    crashed_fatal = crash1 and (n1 == 0)
    ok_all = (not crashed_fatal) and in_range and (not miss) and same and restored
    tag = u'PASS' if ok_all else u'FAIL'
    print(u'[%s] %-4s %-46s 红=%d/%d 期望命中=%s 双跑一致=%s 还原=%s%s'
          % (tag, mid, desc, n1, TOTAL,
             u'✓' if not miss else (u'缺 ' + u','.join(miss)), same, restored,
             u' [连带崩，非致命]' if (crash1 and n1 > 0) else u''))
    if tag != u'PASS':
        if crashed_fatal:
            bad.append((mid, u'check192 崩了且一条 [FAIL] 都没打出来'))
        elif not in_range:
            bad.append((mid, u'红数 %d 不在 (0,%d)' % (n1, TOTAL)))
        elif miss:
            bad.append((mid, u'没抓住 ' + ','.join(miss)))
        elif not same:
            bad.append((mid, u'双跑不一致'))
        elif not restored:
            bad.append((mid, u'还原 sha1 不符'))
    rows.append((mid, n1, tag))

# 收尾：确认文件真的回到原样
final_ok = (hashlib.sha1(_read().encode('utf-8')).hexdigest() == ORIG_SHA)
print(u'')
print(u'最终还原 sha1 一致：%s' % final_ok)
print(u'-' * 72)
n_pass = sum(1 for _m, _n, t in rows if t == u'PASS')
print(u'变异 %d/%d 通过' % (n_pass, len(rows)))
if bad:
    print(u'【问题】')
    for mid, why in bad:
        print(u'  - %s: %s' % (mid, why))
if not final_ok:
    print(u'[FATAL] 源文件没还原！')
sys.exit(0 if (not bad and final_ok) else 1)
