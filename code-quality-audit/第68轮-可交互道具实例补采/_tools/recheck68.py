# -*- coding: utf-8 -*-
"""第68轮 · 重要核心文件复检（六类判据，落盘留痕）。

覆盖本轮**动过**的、且被别处依赖的文件：
  · `code-quality-audit/regress/run_all.py`            —— 回归入口（加 items_round68 条目 + 改 objects_round44 desc）
  · `code-quality-audit/regress/baseline.json`         —— G2 基线（合并更新 6 个套件）
  · `第44轮.../verify_objects44.py`                     —— 回归锁（数据源升级 + 锚点形态 + C0 + 缺文件守卫）
  · `第67轮.../_tools/check67.py`                       —— 回归锁（真机段关就寝，除墙钟耦合）
  · `第48轮.../verify_items48.py`                       —— 回归锁（E3/E4 升级）
  · `第68轮.../verify_items68.py`                       —— 新回归锁
  · `第68轮.../_tools/disc68.py`                        —— 鉴别力体检脚本
  · `ralsei_pet/modules/item_interact.py`               —— 产品（InspectProp / INSPECT_KINDS）

六类判据：① 可解析（AST，**不产 .pyc**）② 结构 ③ 编码 ④ 恒真判据（AST）⑤ 逐令牌回验 ⑥ 工作区干净
"""
import ast
import io
import json
import os
import re
import subprocess
import sys
import traceback

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND68 = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND68, '..', '..'))
PY = r'C:\Python311\python.exe'
OUT = os.path.join(ROUND68, '_evidence', '核心文件复检68.txt')

R44 = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻')
R48 = os.path.join(ROOT, 'code-quality-audit', '第48轮-道具与背包系统')
R67 = os.path.join(ROOT, 'code-quality-audit', '第67轮-幽灵线接线')
REG = os.path.join(ROOT, 'code-quality-audit', 'regress')

PY_FILES = {
    'run_all': os.path.join(REG, 'run_all.py'),
    'verify_objects44': os.path.join(R44, 'verify_objects44.py'),
    'check67': os.path.join(R67, '_tools', 'check67.py'),
    'verify_items48': os.path.join(R48, 'verify_items48.py'),
    'verify_items68': os.path.join(ROUND68, 'verify_items68.py'),
    'disc68': os.path.join(HERE, 'disc68.py'),
    'item_interact': os.path.join(ROOT, 'ralsei_pet', 'modules', 'item_interact.py'),
}
JSON_FILES = {'baseline': os.path.join(REG, 'baseline.json')}

LINES = []


def say(s=''):
    LINES.append(s)
    print(s)


def read(p):
    return io.open(p, 'r', encoding='utf-8').read()


P = F = 0


def ck(cond, msg):
    global P, F
    if cond:
        P += 1
        say('[PASS] %s' % msg)
    else:
        F += 1
        say('[FAIL] %s' % msg)


def main():
    say('== 第68轮 重要核心文件复检 ==')
    say('ROOT = %s' % ROOT)

    # ---------- ① 可解析（AST，不产 .pyc）----------
    say('')
    say('== ① 可解析（AST）/ JSON 可加载 ==')
    for nm, p in PY_FILES.items():
        try:
            ast.parse(read(p))
            ck(True, 'R1a %s 语法可解析' % nm)
        except Exception as e:
            ck(False, 'R1a %s 语法错误: %r' % (nm, e))
    for nm, p in JSON_FILES.items():
        try:
            json.load(io.open(p, 'r', encoding='utf-8'))
            ck(True, 'R1b %s JSON 可加载' % nm)
        except Exception as e:
            ck(False, 'R1b %s JSON 坏: %r' % (nm, e))
    # 负控制：故意坏一个，确认 ast.parse 真会抛
    try:
        ast.parse('def f(:\n')
        ck(False, 'R1c 负控制失败：坏语法居然被接受')
    except SyntaxError:
        ck(True, 'R1c 负控制：坏语法确实被 ast.parse 拒绝')

    # ---------- ② 结构自检 ----------
    say('')
    say('== ② 结构自检 ==')
    run_all_src = read(PY_FILES['run_all'])
    n_suites = len(re.findall(r"\n        'id': '", run_all_src))
    ck(n_suites == 58, 'R2a run_all.py SUITES 条目数 = %d（期望 58）' % n_suites)
    ck("'id': 'items_round68'" in run_all_src, 'R2b items_round68 条目在位')
    # items_round68 必须 offscreen=False 且**不**进 HERMETIC_IDS（纯数据/纯函数）
    blk = run_all_src.split("'id': 'items_round68'", 1)[1][:400]
    ck("'offscreen': False" in blk, 'R2c items_round68 是 offscreen=False')
    herm = run_all_src.split('HERMETIC_IDS = frozenset(', 1)[1].split('})', 1)[0]
    ck('items_round68' not in herm, 'R2d items_round68 **不**在 HERMETIC_IDS（与 items_round48 同款）')
    # 每个条目四字段齐（id/script/offscreen/desc）
    for k in ('id', 'script', 'offscreen', 'desc'):
        ck(run_all_src.count("'%s':" % k) >= n_suites,
           "R2e 每个套件条目都有 '%s'（%d >= %d）" % (k, run_all_src.count("'%s':" % k), n_suites))

    v44 = read(PY_FILES['verify_objects44'])
    for sec in ('A 结构不变量', 'B 真值锚点', 'C 覆盖与守恒', 'D 负控制'):
        ck(sec in v44, 'R2f verify_objects44 章节在位：%s' % sec)
    v68 = read(PY_FILES['verify_items68'])
    for seg in ('def seg_a', 'def seg_b', 'def seg_c', 'def seg_d', 'def seg_e', 'def seg_f'):
        ck(seg in v68, 'R2g verify_items68 段在位：%s' % seg)
    # check67：关就寝必须在 update_movement 之前（顺序反了就不生效）
    c67 = read(PY_FILES['check67'])
    i_bed = c67.find('pet.BEDTIME_ENABLED = False')
    i_um = c67.find('pet.update_movement()')
    ck(i_bed != -1 and i_um != -1 and i_bed < i_um,
       'R2h check67 关就寝在 update_movement 之前（%d < %d）' % (i_bed, i_um))

    # ---------- ③ 编码 ----------
    say('')
    say('== ③ 编码（无 BOM / 无 U+FFFD）==')
    for nm, p in list(PY_FILES.items()) + list(JSON_FILES.items()):
        raw = io.open(p, 'rb').read()
        bom = raw[:3] == b'\xef\xbb\xbf'
        fffd = b'\xef\xbf\xbd' in raw
        ck((not bom) and (not fffd), 'R3 %s 无 BOM(%s) 无 U+FFFD(%s)' % (nm, bom, fffd))

    # ---------- ④ 恒真判据复查（AST）----------
    say('')
    say('== ④ 恒真判据复查（AST：常量 True 必须有同名守卫分支）==')
    CK = ('check', 'ok', 'ck', 'expect', 'verify')

    def const_true_lines(tree):
        out = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and len(n.args) >= 2:
                fn = getattr(n.func, 'id', None) or getattr(n.func, 'attr', None)
                if fn in CK and isinstance(n.args[1], ast.Constant) and n.args[1].value is True:
                    nm = n.args[0].value if isinstance(n.args[0], ast.Constant) else None
                    out.append((n.lineno, nm))
        return out

    def guarded_lines(tree):
        s = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.If):
                for st in n.orelse:
                    s |= {x.lineno for x in ast.walk(st) if hasattr(x, 'lineno')}
        return s

    # 文本 oracle：探针夹具 = 被 `redirect_stdout` 包住 + 紧跟 `PASS.pop()` 摘记账。
    #   ★ 不能用"名字前缀 __probe"自证（那是拿同一套机制放行自己）；
    #     必须**另找两条独立证据**（上下文里的 redirect_stdout 与 PASS.pop()）。
    _cache = {}

    def _is_probe_fixture(path, ln):
        lines2 = _cache.setdefault(path, read(path).split('\n'))
        seg = '\n'.join(lines2[max(0, ln - 7):min(len(lines2), ln + 6)])
        return ('redirect_stdout' in seg) and ('PASS.pop()' in seg)

    # 负控制夹具自证：这段**故意没有** redirect_stdout / PASS.pop() ⇒ 必须判"不是探针"
    _FAKE = "def f():\n    ok('X 恒真假绿', True)\n"
    _fl = _FAKE.split('\n')
    _fake_is_probe = ('redirect_stdout' in _FAKE) and ('PASS.pop()' in _FAKE)
    ck(_fake_is_probe is False, 'R4-neg 负控制：伪恒真行不被判成探针（豁免不是一刀切）')

    for nm in ('verify_objects44', 'verify_items68', 'verify_items48', 'check67'):
        path = PY_FILES[nm]
        src = read(path)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            ck(False, 'R4 %s 无法解析' % nm)
            continue
        guard = guarded_lines(tree)
        hits = [(ln, nm2) for ln, nm2 in const_true_lines(tree) if ln not in guard]
        calls = re.findall(r"(?:check|ok|ck)\s*\(\s*'([^']*)'\s*,\s*([^,\)]+)", src)
        seen = {}
        for name2, arg in calls:
            seen.setdefault(name2, set()).add(arg.strip())
        alltrue = {k for k, v in seen.items() if v == {'True'}}
        bad = [(ln, n2) for ln, n2 in hits
               if n2 in alltrue and not _is_probe_fixture(path, ln)]
        ck(not bad, 'R4 %s 无恒真判据（可疑=%s）' % (nm, bad or '无'))

    # ---------- ⑤ 逐令牌回验 ----------
    say('')
    say('== ⑤ 逐令牌回验（本轮改/加的可检索令牌）==')
    TOK = [
        ('3197', PY_FILES['verify_objects44'], 'EXPECT_TOTAL'),
        ('615', PY_FILES['verify_objects44'], '场景数（docstring）'),
        ('537', PY_FILES['verify_objects44'], 'EXPECT_ZONE_WITH_OBJ'),
        ('78', PY_FILES['verify_objects44'], 'EXPECT_FILE_WITH_OBJ'),
        ('1251', PY_FILES['verify_items68'], 'A2 原作房间总数'),
        ('INSPECT_KINDS', PY_FILES['item_interact'], '产品接线'),
        ('InspectProp', PY_FILES['item_interact'], '产品类'),
        ('INSPECT_KINDS', PY_FILES['verify_items68'], 'D5 判据'),
        ('items_round68', PY_FILES['run_all'], '套件注册'),
        ('BEDTIME_ENABLED', PY_FILES['check67'], '关就寝'),
        ('inst68.json', PY_FILES['verify_objects44'], '数据源'),
        ('3197', PY_FILES['run_all'], 'objects_round44 desc 新数'),
        ('等价性', PY_FILES['verify_items68'], 'A1 核心判据'),
    ]
    lost = []
    for tok, path, why in TOK:
        if tok not in read(path):
            lost.append('%s（%s）' % (tok, why))
    ck(not lost, 'R5 逐令牌回验：全部命中（丢=%s）' % (lost or '无'))

    # ---------- ⑥ 工作区干净 ----------
    say('')
    say('== ⑥ 工作区（git status --porcelain -z，quotepath=false）==')
    try:
        r = subprocess.run(['git', '-c', 'core.quotepath=false', 'status', '--porcelain', '-z'],
                           cwd=ROOT, capture_output=True)
        blob = r.stdout.decode('utf-8', 'surrogateescape')
        parts = [x for x in blob.split('\0') if x]
        paths = []
        i = 0
        while i < len(parts):
            seg = parts[i]
            if len(seg) >= 4 and seg[2] == ' ':
                paths.append(seg[3:])
                if seg[:2].strip().startswith('R'):
                    i += 1
            i += 1
        octal = [p for p in paths if re.search(r'\\[0-7]{3}', p)]
        ck(not octal, 'R6a 解析结果里无 \\3xx 八进制残留（%d 个）' % len(octal))
        bad_prefix = [p for p in paths
                      if not (p.startswith('code-quality-audit/') or p.startswith('ralsei_pet/'))]
        ck(not bad_prefix, 'R6b 变更全部落在仓库内的预期目录（意外=%s）' % (bad_prefix[:5] or '无'))
        junk = [p for p in paths if re.search(r'\.(off|bak|tmp)$', p) or 'ZZ' in p]
        ck(not junk, 'R6c 无体检残留（.off/.bak/*ZZ*）：%s' % (junk[:5] or '无'))
        say('     变更文件 %d 个' % len(paths))
        for p in paths:
            say('       %s' % p)
    except Exception as e:
        ck(False, 'R6 git status 失败: %r' % (e,))

    # ---------- ⑦ 真跑一遍改过的锁 ----------
    say('')
    say('== ⑦ 改过的锁真跑一遍（与基线比对）==')
    for only in ('check67', 'items_round68', 'objects_round44', 'items_round48'):
        rr = subprocess.run([PY, os.path.join(REG, 'run_all.py'), '--only', only],
                            cwd=ROOT, capture_output=True)
        txt = rr.stdout.decode('utf-8', 'replace')
        ck('IDENTICAL' in txt and '【问题】' not in txt,
           'R7 %s 与基线 IDENTICAL' % only)

    say('')
    say('================ 复检结果：PASS=%d FAIL=%d ================' % (P, F))
    if F:
        say('!! 有 FAIL，见上 !!')
    io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(LINES) + '\n')
    return 1 if F else 0


if __name__ == '__main__':
    try:
        code = main()
    except Exception:
        tb = traceback.format_exc()
        say('!! 复检脚本自身异常 !!')
        say(tb)
        io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(LINES) + '\n')
        code = 2
    sys.exit(code)
