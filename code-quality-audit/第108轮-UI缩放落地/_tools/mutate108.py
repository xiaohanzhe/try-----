# -*- coding: utf-8 -*-
"""第108轮 · 变异测试：把 `check108` 守的每条防线**逐条拆掉**，确认它真报红。

★ 铁律（记忆里的血泪）：「**夹具不保真 = 报假问题**；**破坏必报红**」——
  一条判据如果"拆了产品也照样 PASS"，那它就是**恒真判据**，比不写更危险。

本工具的做法与纪律：
  · 每次都把产品文件**复制到临时区**（绝不动工作区原文件）；
  · 在临时副本上做**定点变异**，跑 `check108`（用 `--root` 指向临时区）；
  · 断言该变异**使 FAIL 数上升**（且上升的正是预期那条判据）；
  · ★★ **变异锚点纪律**（第107轮教训）：禁 `replace(old, new, 1)` + 禁"全文唯一"假设。
    必须**先框函数体（缩进判边界）再在体内找**，否则会打在注释/文档串上 = 静默失效。

跑法：
    C:\\Python311\\python.exe mutate108.py
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
    'dui': os.path.join('ralsei_pet', 'modules', 'dialogue_ui.py'),
    'menu': os.path.join('ralsei_pet', 'modules', 'item_menu_ui.py'),
    'box': os.path.join('ralsei_pet', 'modules', 'dr_textbox.py'),
}


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return f.read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def _func_span(src, name):
    """★★ 框出函数体的**字符区间**（缩进判边界）—— 变异锚点的唯一正解。

    为什么不能用 `src.find(name)` 之后随便 `replace(..., 1)`：
      ① 目标串可能在**别处**（注释里/文档串里）先出现 ⇒ 打在注释上 = 静默失效；
      ② 同名函数可能在别处（不同类）也有 ⇒ "全文唯一"是**假设**，不是事实。
    ⇒ 先定位 `def <name>(`，再从它的行首缩进**向后扫到第一个同级或更浅缩进的行**，
      得到函数体区间；之后的替换**只在区间内**做（`_replace_in_span`）。
    """
    m = re.search(r'(?m)^([ \t]*)def\s+' + re.escape(name) + r'\s*\(', src)
    if not m:
        return None
    indent = m.group(1)
    start = m.start()
    # 逐行往后扫，找第一个"非空且缩进 <= 函数缩进"的行 = 函数结束
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
        raise AssertionError('区间内 "%s" 出现 %d 次（期望 %d）' % (old[:40], n, expect))
    seg2 = seg.replace(old, new)
    return src[:a] + seg2 + src[b:]


def _run_check(root):
    """跑 check108（用临时区的 main.py 等），返回 (fail_count, output)。"""
    cp = os.path.join(HERE, 'check108.py')
    env = dict(os.environ)
    env['RALSEI_MUT_ROOT'] = root
    p = subprocess.run([PY, cp], cwd=os.path.join(root, 'ralsei_pet'),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       env=env, timeout=300)
    out = p.stdout.decode('utf-8', 'replace')
    m = re.search(r'FAIL (\d+) 项', out)
    n = int(m.group(1)) if m else (0 if 'FAIL 0 项' in out or 'PASS' in out
                                   and 'FAIL' not in out else -1)
    if m is None:
        m2 = re.search(r'PASS (\d+) 项 · FAIL (\d+) 项', out)
        n = int(m2.group(2)) if m2 else 999
    return n, out


# ---------------------------------------------------------------------------
# 变异体定义： (ID, 描述, 文件键, 函数名, old, new, 期望命中的判据前缀)
# ---------------------------------------------------------------------------
MUTANTS = [
    ('M1', u'宿主不再调 `ui_scale()`（A2 应报红）',
     'main', '_apply_ui_scale', 's = float(self.ui_scale())', 's = 1.0', ('A2',)),
    ('M2', u'`set_pet_scale` 尾部删掉下发行（B2 应报红）',
     'main', 'set_pet_scale', 'self._apply_ui_scale()', 'pass  # mutated', ('B2',)),
    # ★ M3 期望面扩为 (B2b, B3)：如实记录**判据间耦合** —— `init_systems` 里删掉
    #   下发行后，B2b（该行存在）与 B3（启动序里 `_apply_ui_scale` 在末位）
    #   会**同时**报红（同一处改动、两条判据各守一个侧面），这不是掩盖。
    ('M3', u'`init_systems` 里删掉下发行（B2b/B3 应报红）',
     'main', 'init_systems', 'self._apply_ui_scale()', 'pass  # mutated',
     ('B2b', 'B3')),
    # ★ M4 锚点修正：产品写的是 `base[key]`（不是 `base.get('inset', 34)`）
    #   —— 初版锚点串在区间内出现 0 次（我凭记忆写的形态，不是产品真身）。
    ('M4', u'DialogueUI 不记基准（C2 应报红）',
     'dui', 'apply_ui_scale', 'float(base[key])', 'float(0)', ('C2',)),
    ('M5', u'DialogueUI 去掉 NaN 检查（D1b 应报红）',
     'dui', 'apply_ui_scale', 'if s != s or s <= 0.0:', 'if False:', ('D',)),
    # ★ M6 锚点修正：该串在 `add_dialogue` 体内出现 **2** 次（用户分支 + NPC 分支）
    #   ⇒ `expect=2`（如实计数，不改成只打一处 —— 只打一处仍会报红，但掩盖了
    #     "两个分支都要缩"这一事实）。
    ('M6', u'HTML 字号改回硬编码（E1b/E1c 应报红）',
     'dui', 'add_dialogue', '{self._html_pt(10)}pt', '10pt', ('E1',), 2),
    # ★ M7 锚点修正：`_content_scale` 在 `paintEvent` 体内出现 2 次
    #   （`getattr` 的字符串 + 注释里的提到）⇒ 换**整串精确锚点**，
    #   只打真正的消费点（`getattr(self, '_content_scale', None)`）。
    ('M7', u'框体绘制不消费倍率（F3 应报红）',
     'box', 'paintEvent', "getattr(self, '_content_scale', None)",
     "getattr(self, '_not_used_scale', None)", ('F3',)),
    # ★ M8 锚点修正：`_m(BAND)` 在体内出现 **2** 次（`top` / `left` 两个分支
    #   各一次）⇒ `expect=2`（两处都是真实防线：任一处漏缩 = 该向边框不缩）。
    ('M8', u'`paint_dark_box_scaled` 不缩带厚（F6 应报红）',
     'box', 'paint_dark_box_scaled', "_m(BAND)", "BAND", ('F6',), 2),
    ('M9', u'菜单不遍历已有行重设字号（E7 应报红）',
     'menu', 'apply_ui_scale', 'for marker, text in self._rows:', 'for marker, text in []:', ('E7',)),
    ('M10', u'菜单 `_pt` 不走基准（C2b 应报红）',
     'menu', '_pt', 'raw = float(base[key]) if isinstance(base, dict) else float(fallback)',
     'raw = float(fallback)', ('C2b', 'E6')),
]


def main():
    print('=' * 72)
    print('第108轮 · 变异测试（每条防线逐条拆，确认真报红）')
    print('=' * 72)
    tmp = tempfile.mkdtemp(prefix='mut108_')
    try:
        # ① 先跑一遍**未变异**的基线（在临时副本上，验夹具本身能全绿）
        for _k, _rel in FILES.items():
            _src = os.path.join(ROOT, _rel)
            _dst = os.path.join(tmp, _rel)
            os.makedirs(os.path.dirname(_dst), exist_ok=True)
            shutil.copy2(_src, _dst)
        # modules 下其它文件也要有（check108 只读那四个，但 import 可能拖别的）
        _base_fail, _base_out = _run_check(tmp)
        print(u'\n[基线] 未变异 ⇒ FAIL=%d（期望 0）' % _base_fail)
        if _base_fail != 0:
            print(u'[FATAL] 基线就不干净 ⇒ 变异测试无意义。输出尾部：')
            print(_base_out[-2000:])
            return 2

        hits = 0
        bad = []
        for _row in MUTANTS:
            mid, desc, fkey, fname, old, new, expect = _row[:7]
            # ★ 可选第 8 项：`expect_n`（锚点出现次数，默认 1）—— 如实计数
            _exp_n = _row[7] if len(_row) > 7 else 1
            _src_orig = _read(os.path.join(ROOT, FILES[fkey]))
            _dst = os.path.join(tmp, FILES[fkey])
            try:
                span = _func_span(_src_orig, fname)
                mutated = _replace_in_span(_src_orig, span, old, new, expect=_exp_n)
            except AssertionError as e:
                # ★ 锚点找不到/数量不符 ⇒ 如实报"夹具不保真"，不算通过
                bad.append((mid, u'锚点不可用: %s' % e))
                print(u'[SKIP] %s %s  <- 锚点不可用: %s' % (mid, desc, e))
                continue
            _write(_dst, mutated)
            n, out = _run_check(tmp)
            # 还原该文件（下一个变异体要干净的起点）
            _write(_dst, _src_orig)
            if n > _base_fail:
                # 再确认命中的是**预期那条**判据
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
                    print(u'[MISS] %s FAIL=%d 报了红，但不是预期判据 %s'
                          % (mid, n, '/'.join(expect)))
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
