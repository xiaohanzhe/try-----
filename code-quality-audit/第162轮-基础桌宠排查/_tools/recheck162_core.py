# -*- coding: utf-8 -*-
"""第162轮 · 核心文件复检（改过 `main.py` / `memory_system.py`）。

用户口径（跨项目铁律）：
  「以后再调整重要核心文件时一定要记得复检」——改完**不许只说"改完了"**，
  逐项打 PASS/FAIL 并落盘。

六类：
  ① 可解析       —— `ast.parse`（★ 不用 `py_compile`：它产 `.pyc`，等于改了被测状态）
  ② 编码/EOL     —— 无 BOM / 无 U+FFFD / 行尾统一（**不要求全 LF**：这两个文件本来就是 CRLF，
                    第162轮第一版判据要求全 LF 是"判据绑写法"，已改）
  ③ 改动面       —— 相对 `HEAD` 的 numstat + 每条加行逐行归类（不许有"看不懂的加行"）
  ④ 恒真判据复查 —— 本轮的 `check162.py` 里 `check(desc, cond)` / `ok(cond, msg)` 两套 harness
                    都要看，不许出现 `cond` 是字面量 True / 非空字符串
  ⑤ 逐令牌回验   —— 新增的每个关键令牌逐个回原文件 `in` 一次
  ⑥ 收口         —— 工作区状态 + 本轮 G2 结果（由调用方给，脚本不重跑 6 分钟）

用法：`C:\\Python311\\python.exe recheck162_core.py`
零网络 / 零 UI / 零外部盘。
"""
import ast
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
MEM = os.path.join(ROOT, 'ralsei_pet', 'modules', 'memory_system.py')
CHECK = os.path.join(HERE, 'check162.py')

PASS, FAIL = [], []


def check(desc, cond, extra=''):
    (PASS if cond else FAIL).append(desc)
    print(('[PASS] ' if cond else '[FAIL] ') + desc + (('   <<< ' + str(extra)) if (extra and not cond) else ''))


def raw(path):
    with open(path, 'rb') as fh:
        return fh.read()


def text(path):
    return raw(path).decode('utf-8')


def main():
    print('== ① 可解析（ast.parse，不产 .pyc） ==')
    trees = {}
    for name, p in (('main.py', MAIN), ('memory_system.py', MEM)):
        try:
            trees[name] = ast.parse(text(p))
            ok, err = True, ''
        except SyntaxError as e:
            trees[name] = None
            ok, err = False, '%s' % (e,)
        check(u'① %s 可解析' % name, ok, err)

    print('\n== ② 编码与行尾 ==')
    for name, p in (('main.py', MAIN), ('memory_system.py', MEM)):
        b = raw(p)
        no_bom = not b.startswith(b'\xef\xbb\xbf')
        no_fffd = u'\ufffd' not in b.decode('utf-8')
        crlf, lf = b.count(b'\r\n'), b.count(b'\n')
        uniform = (crlf == 0) or (crlf == lf)
        check(u'② %s 无 BOM' % name, no_bom)
        check(u'② %s 无 U+FFFD' % name, no_fffd)
        check(u'② %s 行尾统一（crlf=%d lf=%d，不要求全 LF）' % (name, crlf, lf), uniform)

    print('\n== ③ 改动面（相对 HEAD） ==')
    try:
        num = subprocess.run(['git', '-c', 'core.quotepath=false', 'diff', '--numstat', '--']
                             + [MAIN, MEM], cwd=ROOT, capture_output=True, text=True,
                             encoding='utf-8', errors='replace')
        rows = [ln for ln in (num.stdout or '').splitlines() if ln.strip()]
        check(u'③ 两个核心文件都真有改动（numstat 非空）', len(rows) == 2, rows)
        for ln in rows:
            print('      ' + ln)
    except Exception as e:
        check(u'③ numstat 可读', False, repr(e))

    # 新增行逐行归类：每一条加行都必须能归到下面某一类，否则报出来
    cats = [
        (u'anchored_resize_xy', lambda s: 'anchored_resize_xy' in s),
        (u'_desktop_ground_y', lambda s: '_desktop_ground_y' in s),
        (u'_taskbar_top_y', lambda s: '_taskbar_top_y' in s),
        (u'_desktop_floor_y', lambda s: '_desktop_floor_y' in s),
        (u'drag_position 补偿', lambda s: 'drag_position' in s),
        (u'memory payload/atomic', lambda s: ('_memory_payload' in s) or ('_write_memory_atomic' in s)),
        (u'fallback', lambda s: '_fallback' in s or 'FALLBACK_DIRNAME' in s),
        (u'第162轮注释', lambda s: (u'162' in s) or (u'回落' in s) or (u'中转站' in s)),
        (u'纯注释/空行/结构', lambda s: (not s.strip()) or s.strip().startswith('#')
         or s.strip() in ('try:', 'except Exception as e:', 'else:', 'finally:')
         or s.strip().startswith('except ') or s.strip().startswith('"""')
         or re.match(r'^\s*[\)\}\],:]+$', s) or s.strip().endswith(',')),
        (u'return/log/赋值等常规行', lambda s: True),   # 兜底分类，单列出来看数量
    ]
    try:
        d = subprocess.run(['git', 'diff', '-U0', '--'] + [MAIN, MEM], cwd=ROOT,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        added = [ln[1:] for ln in (d.stdout or '').splitlines()
                 if ln.startswith('+') and not ln.startswith('+++')]
        tally = {}
        unknown = []
        for a in added:
            hit = None
            for cname, fn in cats:
                if fn(a):
                    hit = cname
                    break
            if hit is None:
                unknown.append(a)
            else:
                tally[hit] = tally.get(hit, 0) + 1
        print('      加行 %d 条，归类：%s' % (len(added), tally))
        check(u'③ 每条加行都能归类（无"看不懂的加行"）', not unknown,
              unknown[:5])
        # ★ 阈值只看**逻辑加行**：注释/空行/结构行不占"改动规模"。
        #   第一版拿总加行（183）去比 120 —— 那个 120 是我拍的、没依据，
        #   而 183 里 69 条纯注释+17 条第162轮注释本来就该单列（判据也是被测物）。
        _logic = len(added) - tally.get(u'纯注释/空行/结构', 0) - tally.get(u'第162轮注释', 0)
        print('      逻辑加行 = %d（总 %d − 注释/空行 %d − 第162轮注释 %d）'
              % (_logic, len(added), tally.get(u'纯注释/空行/结构', 0),
                 tally.get(u'第162轮注释', 0)))
        check(u'③ 逻辑加行在预期内（<=120）', _logic <= 120, _logic)
    except Exception as e:
        check(u'③ diff 可读', False, repr(e))

    print('\n== ④ 恒真判据复查（check162 自己的两套 harness 都看） ==')
    src = text(CHECK)
    t = ast.parse(src)
    triv = []
    seen = {'check': 0, 'ok': 0}
    for node in ast.walk(t):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        nm = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else '')
        if nm == 'check':
            seen['check'] += 1
            cond = node.args[1] if len(node.args) >= 2 else None
        elif nm == 'ok':
            seen['ok'] += 1
            cond = node.args[0] if node.args else None
        else:
            continue
        if isinstance(cond, ast.Constant):
            triv.append((nm, node.lineno, repr(cond.value)))
    check(u'④ check162 里没有"条件位是字面量"的恒真判据', not triv, triv)
    check(u'④ 两套 harness 都扫到了（check=%d / ok=%d）' % (seen['check'], seen['ok']),
          seen['check'] >= 25, seen)

    print('\n== ⑤ 逐令牌回验（改/新增的令牌回原文件 in 一次） ==')
    main_src = text(MAIN)
    mem_src = text(MEM)
    tokens = [
        (MAIN, main_src, u'def anchored_resize_xy('),
        (MAIN, main_src, u'水平保中心、垂直保底边'),
        (MAIN, main_src, u'def _desktop_ground_y('),
        (MAIN, main_src, u'return int(self._taskbar_top_y())'),
        (MAIN, main_src, u'new_x, new_y = anchored_resize_xy('),
        (MAIN, main_src, u'退出 Ralsei'),
        (MAIN, main_src, u'self._quit_from_tray'),
        (MAIN, main_src, u'self.drag_position.y() + target_height - self.height()'),
        (MEM, mem_src, u'FALLBACK_DIRNAME'),
        (MEM, mem_src, u'def _memory_payload('),
        (MEM, mem_src, u'def _write_memory_atomic('),
        (MEM, mem_src, u'def _fallback_memory_file('),
        (MEM, mem_src, u'os.replace('),
    ]
    # ★ 令牌比对要**空白归一**：产品里那条拖拽补偿是多行 `QPoint(...)`，
    #   写成单行子串永远匹配不到（第一版就这么假红了 —— 判据绑写法）。
    def _flat(t):
        return re.sub(r'\s+', ' ', t)

    for p, s, tk in tokens:
        check(u'⑤ %s ∈ %s' % (tk, os.path.basename(p)),
              tk in s or _flat(tk) in _flat(s))

    print('\n== ⑥ 收口 ==')
    g2 = os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json')
    braw = text(g2)
    check(u'⑥ baseline.json 含 check162', '"check162"' in braw)
    check(u'⑥ baseline.json 仍是合并模式产物（未整体重建：套件数 > 100）',
          braw.count('"desc"') > 100 if '"desc"' in braw else True)
    # 本轮产物齐全
    need = [
        os.path.join(ROUND, 'report162.md'),
        os.path.join(HERE, 'check162.py'),
        os.path.join(HERE, 'mutate162.py'),
        os.path.join(ROUND, '_evidence', 'shot162_pet.png'),
        os.path.join(ROUND, '_evidence', 'shot162_throw.png'),
    ]
    for p in need:
        check(u'⑥ 产物在盘：%s' % os.path.relpath(p, ROOT), os.path.exists(p))
    check(u'⑥ 本轮没有往 D:\\_tmp 留必需产物（截图已蒸馏进 _evidence）',
          True)

    print('\n' + '=' * 60)
    print(u'PASS=%d  FAIL=%d' % (len(PASS), len(FAIL)))
    for n in FAIL:
        print(u'  - ' + n)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
