# -*- coding: utf-8 -*-
"""第109轮 · 变异测试：把 `check109` 守的每条防线**逐条拆掉**，确认它真报红。

★ 铁律（记忆里的血泪）：「**夹具不保真 = 报假问题**；**破坏必报红**」——
  一条判据如果"拆了产品也照样 PASS"，那它就是**恒真判据**，比不写更危险。

本工具的做法与纪律（与 `mutate108.py` 同源）：
  · 每次都把产品文件**复制到临时区**（绝不动工作区原文件）；
  · 在临时副本上做**定点变异**，跑 `check109`（用 `RALSEI_MUT_ROOT` 指向临时区）；
  · 断言该变异**使 FAIL 数上升**（且上升的正是预期那条判据）；
  · ★★ **变异锚点纪律**（第107轮教训，本工具直接复用）：
      禁 `replace(old, new, 1)` + 禁"全文唯一"假设。
      必须**先框函数体（缩进判边界）再在体内找**，否则会打在注释/文档串上 = 静默失效。
  · ★★ **负控制不能只拆一半**（第95.13 教训）：多道防线须**同拆**才复现。

跑法：
    C:\\Python311\\python.exe mutate109.py
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
PY = sys.executable

FILES = {
    'main': os.path.join('ralsei_pet', 'src', 'main.py'),
    'canvas': os.path.join('ralsei_pet', 'modules', 'scene_canvas.py'),
}


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return f.read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def _func_span(src, name):
    """★★ 框出函数体的**字符区间**（缩进判边界）—— 变异锚点的唯一正解（见 mutate108）。"""
    m = re.search(r'(?m)^([ \t]*)def\s+' + re.escape(name) + r'\s*\(', src)
    if not m:
        return None
    indent = m.group(1)
    start = m.start()
    pos = src.find('\n', m.end())
    if pos < 0:
        return (start, len(src))
    i = pos + 1
    end = len(src)
    while i < len(src):
        j = src.find('\n', i)
        if j < 0:
            j = len(src)
        line = src[i:j]
        if line.strip():
            _ind = len(line) - len(line.lstrip(' \t'))
            if _ind <= len(indent):
                end = i
                break
        i = j + 1
    return (start, end)


def _replace_in_span(src, span, old, new, expect=1):
    """在 `span` 区间内替换 `old` → `new`；★ **找不到/数量不符就报错，不静默**。"""
    if span is None:
        raise AssertionError('函数体定位失败')
    a, b = span
    seg = src[a:b]
    n = seg.count(old)
    if n != expect:
        raise AssertionError('区间内 "%s" 出现 %d 次（期望 %d）' % (old[:50], n, expect))
    seg2 = seg.replace(old, new)
    return src[:a] + seg2 + src[b:]


# ★ 类级常量/模块级常量不在函数体内 ⇒ 需要"整文件唯一锚点"的变异体单独处理：
#   用 `_replace_unique`（**先自证唯一**，不唯一就报错，绝不静默打第一处）。
def _replace_unique(src, old, new, expect=1):
    n = src.count(old)
    if n != expect:
        raise AssertionError('全文 "%s" 出现 %d 次（期望 %d）' % (old[:50], n, expect))
    return src.replace(old, new)


def _run_check(root):
    """跑 check109（用临时区的产品文件），返回 (fail_count, output)。"""
    cp = os.path.join(HERE, 'check109.py')
    env = dict(os.environ)
    env['RALSEI_MUT_ROOT'] = root
    p = subprocess.run([PY, cp], cwd=os.path.join(root, 'ralsei_pet'),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       env=env, timeout=300)
    out = p.stdout.decode('utf-8', 'replace')
    m = re.search(r'PASS (\d+) 项 · FAIL (\d+) 项', out)
    if m:
        return int(m.group(2)), out
    m2 = re.search(r'FAIL (\d+)', out)
    return (int(m2.group(1)) if m2 else 999), out


# ---------------------------------------------------------------------------
# 变异体定义： (ID, 描述, 文件键, 函数名(或 None=整文件唯一锚点), old, new, 期望命中的判据前缀[, expect_n])
# ★ `函数名=None` ⇒ 走 `_replace_unique`（用于常量赋值这类不在函数体内的锚点）。
# ---------------------------------------------------------------------------
MUTANTS = [
    # ---- A 机制存在且被消费 ----
    ('M1', u'宿主不再把 `_advance_scene_transition` 挂在 `update_movement`（A4/A5 应报红）',
     'main', 'update_movement',
     'self._advance_scene_transition(current_time * 1000.0)',
     'pass  # mutated', ('A4', 'A5')),
    # ---- B 时序常量 = 原作换算值 ----
    # ★★ 负控制"拆干净"：只改常量不改用法，B1 单独报红。
    ('M2', u'淡出时长改错值（B1 应报红）',
     'main', None, 'SCENE_FADE_OUT_MS = 267.0', 'SCENE_FADE_OUT_MS = 300.0', ('B1',)),
    ('M3', u'淡入时长改错值（B2 应报红）',
     'main', None, 'SCENE_FADE_IN_MS = 417.0', 'SCENE_FADE_IN_MS = 400.0', ('B2',)),
    # ---- C 阶段序：先置 α=1 再换房 ----
    # ★ 把"到点置 α=1 再 swap"改成"先 swap 再置 α=1" ⇒ C1 报红（顺序反 = 先换房后变黑）。
    ('M4', u'淡出到点**先换房后置黑**（C1 应报红 —— 顺序反了）',
     'main', '_advance_scene_transition',
     '                    canvas.set_transition_alpha(1.0)\n'
     '                    self._do_scene_transition_swap(st)',
     '                    self._do_scene_transition_swap(st)\n'
     '                    canvas.set_transition_alpha(1.0)',
     ('C1',)),
    # ---- D 换房真调 switch ----
    ('M5', u'换房那一拍**不调** `switch`（D1/D2 应报红 —— 过渡结束场景没变）',
     'main', '_do_scene_transition_swap',
     'ok = bool(scene.switch(target))', 'ok = True  # mutated', ('D1', 'D2')),
    # ---- E 画布遮罩 ----
    # ★★ E3 守的是"paint_on 先于 fillRect"⇒ 直接**删掉遮罩块里的 fillRect**
    #   （E3 会因找不到 fillRect 报红；E4 也报红）。
    #   ⚠️ 锚点修正（首轮 [SKIP]）：遮罩块在 **`scene_canvas.py` 的 `paintEvent`**
    #     里，不在 `main.py` —— 首轮 `fkey` 误写 'main' ⇒ 全文 count=0。
    ('M6', u'`paintEvent` 删掉遮罩绘制（E3/E4 应报红）',
     'canvas', None,
     '            if self._transition_alpha > 0.0:\n'
     '                _tc = QColor(TRANSITION_COLOR)\n'
     '                _tc.setAlphaF(self._transition_alpha)\n'
     '                p.fillRect(self.rect(), QBrush(_tc))\n',
     '            pass  # mutated\n',
     ('E3', 'E4')),
    # ---- F 默认零回归 ----
    # ★★ 把守卫恒真 ⇒ 正常态也填黑（F1 应报红；E3 仍 PASS 因为 fillRect 还在 paint_on 后）。
    ('M7', u'`paintEvent` 遮罩守卫恒真 ⇒ 正常态也全黑（F1 应报红）',
     'canvas', None,
     '            if self._transition_alpha > 0.0:\n'
     '                _tc = QColor(TRANSITION_COLOR)',
     '            if True:\n'
     '                _tc = QColor(TRANSITION_COLOR)',
     ('F1',)),
    # ---- E2 α 钳位 ----
    # ★★ 拆干净：**两段**钳位同拆（`if a < 0.0 ... if a > 1.0`）⇒ E2 应报红。
    ('M8', u'`set_transition_alpha` 去掉 [0,1] 钳位（E2 应报红）',
     'canvas', 'set_transition_alpha',
     '        if a < 0.0:\n'
     '            a = 0.0\n'
     '        elif a > 1.0:\n'
     '            a = 1.0\n',
     '        pass  # mutated\n',
     ('E2',)),
    # ---- G2 容错：异常分支必把 α 归 0 ----
    # ★★ 拆干净：把 except 里的 `canvas.set_transition_alpha(0.0)` 删掉 ⇒ G2 应报红。
    ('M9', u'`_advance_scene_transition` 异常分支不归零（G2 应报红 —— 全黑卡死）',
     'main', '_advance_scene_transition',
     '            try:\n'
     '                canvas.set_transition_alpha(0.0)\n'
     '            except Exception:\n'
     '                pass\n',
     '            pass  # mutated\n',
     ('G2',)),
    # ---- H 可关开关 + 入口接线 ----
    ('M10', u'过渡开关改成 False 常量（H1 应报红 —— 关不掉就说明开关没接）',
     'main', None, 'SCENE_TRANSITION_ENABLED = True',
     'SCENE_TRANSITION_ENABLED = False', ('H1',)),
    # ★★ 入口不接线：`travel_to_scene` 不再调 `request_scene_transition`（H3 应报红）。
    #   ⚠️ 锚点修正（连栽两次，都是"括号配对"）：
    #      ① 初版 `and False  # mutated:` —— 注释吞掉行尾 `):` ⇒ 语法非法；
    #      ② 二版 `and False):` —— 原串**自带** `request_scene_transition(` 的
    #         左括号，替换后 `)` 失去配对 ⇒ `SyntaxError: unmatched ')'`。
    #      ⇒ 三版 `and (False):`：**自带配对括号**，整体语法合法。
    #      （教训：变异锚点若跨越"函数调用的括号"，替换串必须自带配对的括号。）
    ('M11', u'`travel_to_scene` 不再走过渡（H3 应报红 —— "函数写对了、产品用不上"）',
     'main', 'travel_to_scene',
     'and self.request_scene_transition(\n'
     '                        target_sid, on_done=self._travel_after_transition):',
     'and (False):',
     ('H3',)),
    # ---- D2 换房后重算明/暗世界 ----
    ('M12', u'换房后不重算明/暗世界（D2 应报红）',
     'main', '_do_scene_transition_swap',
     '                    self._possession_sync_world()',
     '                    pass  # mutated', ('D2',)),
]


def main():
    print('=' * 72)
    print('第109轮 · 变异测试（每条防线逐条拆，确认真报红）')
    print('=' * 72)
    tmp = tempfile.mkdtemp(prefix='mut109_')
    try:
        # ① 先把产品文件复制到临时区（保留相对路径，供 RALSEI_MUT_ROOT 解析）
        for _k, _rel in FILES.items():
            _src = os.path.join(ROOT, _rel)
            _dst = os.path.join(tmp, _rel)
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            shutil.copy2(_src, _dst)
        _base_fail, _base_out = _run_check(tmp)
        print(u'\n[基线] 未变异 ⇒ FAIL=%d（期望 0）' % _base_fail)
        if _base_fail != 0:
            print(u'[FATAL] 基线就不干净 ⇒ 变异测试无意义。输出尾部：')
            print(_base_out[-2500:])
            return 2

        hits = 0
        bad = []
        for _row in MUTANTS:
            mid, desc, fkey, fname, old, new, expect = _row[:7]
            _exp_n = _row[7] if len(_row) > 7 else 1
            _src_orig = _read(os.path.join(ROOT, FILES[fkey]))
            _dst = os.path.join(tmp, FILES[fkey])
            try:
                if fname is None:
                    mutated = _replace_unique(_src_orig, old, new, expect=_exp_n)
                else:
                    span = _func_span(_src_orig, fname)
                    mutated = _replace_in_span(_src_orig, span, old, new, expect=_exp_n)
            except AssertionError as e:
                bad.append((mid, u'锚点不可用: %s' % e))
                print(u'[SKIP] %s %s  <- 锚点不可用: %s' % (mid, desc, e))
                continue
            _write(_dst, mutated)
            n, out = _run_check(tmp)
            _write(_dst, _src_orig)   # 还原：下一个变异体从干净起点开始
            if n > _base_fail:
                _hit = False
                for _pfx in expect:
                    for _l in out.split('\n'):
                        if _l.startswith('[FAIL]') and _pfx in _l:
                            _hit = True
                            break
                    if _hit:
                        break
                if _hit:
                    hits += 1
                    print(u'[HIT ] %s FAIL=%d（基线 %d）· 命中 %s  <- %s'
                          % (mid, n, _base_fail, '/'.join(expect), desc))
                else:
                    bad.append((mid, u'报红但**不是预期判据**（期望 %s）' % ('/'.join(expect),)))
                    print(u'[MISS] %s FAIL=%d 报了红，但不是预期判据 %s' % (mid, n, '/'.join(expect)))
            else:
                bad.append((mid, u'不报红（FAIL 仍 %d）⇒ 该判据**没鉴别力**' % n))
                print(u'[DEAD] %s FAIL=%d（基线 %d）**没报红** ⇒ 判据是恒真的！  <- %s'
                      % (mid, n, _base_fail, desc))

        print(u'\n' + '=' * 72)
        print(u'变异测试：%d/%d 命中' % (hits, len(MUTANTS)))
        if bad:
            print(u'未命中 / 有问题的变异体：')
            for mid, why in bad:
                print(u'  · %s: %s' % (mid, why))
        print('=' * 72)
        return 0 if hits == len(MUTANTS) else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
