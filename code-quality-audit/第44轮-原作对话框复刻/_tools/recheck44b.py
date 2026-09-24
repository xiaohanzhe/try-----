# -*- coding: utf-8 -*-
"""第44轮续 · 核心文件复检（动效接入 + objects 加固）。

复检对象（本轮真正改过、且被别处依赖的文件）
  1. ralsei_pet/modules/scene_render.py     —— 生产渲染层（main.py 依赖）
  2. ralsei_pet/src/main.py                 —— 生产主程序（改 1 处调用）
  3. code-quality-audit/regress/run_all.py  —— 回归调度器（判据坏了会假装通过）
  4. code-quality-audit/第44轮.../verify_anim44.py     —— 新回归锁
  5. code-quality-audit/第44轮.../gen_objects44.py     —— 数据生成器
  6. ralsei_pet/assets/scenes/_sprite_anim.json        —— 新数据资产
  7. ralsei_pet/assets/scenes/_zone.*.json + <sid>.json —— 数据载体（抽查）

六类判据见 skill `core-file-recheck`。
"""
import io
import json
import os
import re
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))          # .../第44轮.../_tools
BASE = os.path.join(HERE, '..')                            # .../第44轮...
ROOT = os.path.join(BASE, '..', '..')                      # = 仓库根
OUT = os.path.join(BASE, '_evidence', '核心文件复检44b.txt')

L = []


def w(s=''):
    L.append(str(s))


PY = sys.executable

TARGETS = [
    os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_render.py'),
    os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    os.path.join(BASE, 'verify_anim44.py'),
    os.path.join(HERE, 'gen_objects44.py'),
]
JSONS = [
    os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_sprite_anim.json'),
]


def main():
    w('=== 第44轮续 核心文件复检 ===')
    w('时间：%s' % __import__('time').strftime('%Y-%m-%d %H:%M:%S'))
    w('')
    fails = []

    def C(cid, ok, msg):
        w('[%s] %-6s %s' % ('PASS' if ok else 'FAIL', cid, msg))
        if not ok:
            fails.append((cid, msg))

    # ============ 1. 可编译 / 可解析 ============
    # ★ 用 `ast.parse` 而不是 `py_compile`：后者会在 `__pycache__/` 里**写 .pyc**，
    #   而本仓库历史上就跟踪着 2 个 .pyc（见记忆"恒假判据"实例）⇒ 复检动作
    #   本身污染了工作区，还差点混进提交。`ast.parse` 只读不写，语义等价
    #   （都验证"能解析"），且无副作用。这是"复检不许改变被测状态"的原则。
    w('--- 1. 可编译 / 可解析 ---')
    import ast as _ast
    for p in TARGETS:
        rel = os.path.relpath(p, ROOT)
        if not os.path.isfile(p):
            C('1', False, '缺失 %s' % rel)
            continue
        try:
            _ast.parse(io.open(p, 'r', encoding='utf-8').read())
            C('1', True, '%s ast.parse 通过（只读，不产 .pyc）' % rel)
        except SyntaxError as e:
            C('1', False, '%s 语法错误 %s' % (rel, e))
    for p in JSONS:
        rel = os.path.relpath(p, ROOT)
        try:
            with io.open(p, 'r', encoding='utf-8') as fh:
                json.load(fh)
            C('1', True, '%s json.load 通过' % rel)
        except Exception as e:
            C('1', False, '%s json 解析失败 %r' % (rel, e))

    # ============ 2. 结构自检 ============
    w('')
    w('--- 2. 结构自检 ---')
    # 2a scene_render 必须同时有 _anim_frame_index 与 plan_frame
    sr = io.open(TARGETS[0], 'r', encoding='utf-8').read()
    C('2a', 'def _anim_frame_index(' in sr and 'def plan_frame(' in sr,
      'scene_render 两个关键函数都在')
    C('2b', sr.count('_anim_frame_index') >= 3,
      'scene_render 引用 _anim_frame_index 次数 = %d（定义1+调用≥1+注释）'
      % sr.count('_anim_frame_index'))
    # 2c main.py 真把 tick 传进去了
    mp = io.open(TARGETS[1], 'r', encoding='utf-8').read()
    C('2c', 'tick=int(time.time() * 1000)' in mp,
      'main.py 真把毫秒 tick 传给 plan_frame')
    # 2d run_all 两个新套件都登记且进 HERMETIC
    ra = io.open(TARGETS[2], 'r', encoding='utf-8').read()
    C('2d', "'objects_round44', 'anim_round44'," in ra,
      'run_all HERMETIC_IDS 含 two new ids')
    C('2e', "'id': 'anim_round44'," in ra and "'id': 'objects_round44'," in ra,
      'run_all SUITES 两个 id 都在')
    # 2f 新锁的输出口径必须能被 run_all 计数（它按行首 `[PASS]` 统计）
    #   ★ 判据修正史（重要教训）：
    #     ① 初版查源码里有精确串 `print('[%s] %s  %s'` —— 太窄，报红。
    #     ② 二版查源码里有 `'[PASS] '` —— **仍然报红**，因为文件里 `'PASS'`
    #        与 `'FAIL'` 是分开的字面量，运行时才拼成 `[PASS] x`。
    #   ⇒ 根本错在**拿源码字面量去代替产物输出**。正确做法是**真跑一次锁**，
    #     数它的输出行（这才是 run_all 真正消费的东西）。这同时满足
    #     "复检要验行为，不只验文本"。
    va = io.open(TARGETS[3], 'r', encoding='utf-8').read()
    src_ok = ("'[%s] %s  %s'" in va and "'PASS'" in va and "'FAIL'" in va)
    r2 = subprocess.run([PY, TARGETS[3]], cwd=ROOT, capture_output=True)
    out2 = r2.stdout.decode('utf-8', 'replace')
    n_pass = sum(1 for ln in out2.splitlines() if ln.startswith('[PASS]'))
    n_fail = sum(1 for ln in out2.splitlines() if ln.startswith('[FAIL]'))
    C('2f', src_ok and r2.returncode == 0 and n_pass > 0 and n_fail == 0,
      "verify_anim44 真跑：rc=%d 输出 [PASS]=%d [FAIL]=%d"
      "（run_all 按行首 [PASS] 计数 ⇒ 口径一致）"
      % (r2.returncode, n_pass, n_fail))
    # 2g 结构粘连检查：Python 里不应有 'def ' 出现在行中间
    glued = [i for i, l in enumerate(sr.split('\n'), 1)
             if 'def ' in l and not l.lstrip().startswith('def ')
             and not l.lstrip().startswith('#')]
    C('2g', not glued, 'scene_render 无粘连的 def（可疑行 %s）' % glued[:3])

    # ============ 3. 编码 ============
    w('')
    w('--- 3. 编码 ---')
    for p in TARGETS + JSONS:
        rel = os.path.relpath(p, ROOT)
        b = io.open(p, 'rb').read()
        bom = b[:3] == b'\xef\xbb\xbf'
        fffd = b'\xef\xbf\xbd' in b
        C('3', not bom and not fffd,
          '%s BOM=%s U+FFFD=%s' % (rel, bom, fffd))

    # ============ 4. 恒真判据复查 ============
    w('')
    w('--- 4. 恒真判据复查 ---')
    patterns = [
        (r'check\([^,]+,\s*True\s*[,)]', 'check(x, True)'),
        (r'assert\s+True\b', 'assert True'),
        (r'if\s+\w+\s+or\s+True\b', 'x or True'),
        (r'check\([^,]+,\s*1\s*[,)]', 'check(x, 1)'),
    ]
    for p in [TARGETS[2], TARGETS[3], TARGETS[4]]:
        rel = os.path.relpath(p, ROOT)
        t = io.open(p, 'r', encoding='utf-8').read()
        hits = []
        for rx, nm in patterns:
            for m in re.finditer(rx, t):
                ln = t[:m.start()].count('\n') + 1
                hits.append('%s@%d' % (nm, ln))
        C('4', not hits, '%s 无恒真判据写法（%s）' % (rel, hits[:5] or '无'))

    # ============ 5. 逐令牌回验 ============
    w('')
    w('--- 5. 逐令牌回验（本轮引入的关键令牌必须都在）---')
    # 本轮引入/依赖的令牌：(文件, 必须出现的令牌)
    token_checks = [
        (TARGETS[0], ['_anim_frame_index', 'anim_frame', 'anim_frames',
                      'frame_ms', "'%s_%d.png'", 'tick']),
        (TARGETS[1], ['tick=int(time.time() * 1000)']),
        (TARGETS[2], ['anim_round44', 'objects_round44', 'verify_anim44.py']),
        (TARGETS[3], ['_sprite_anim.json', 'frame_ms', 'default_30fps',
                      'A4', 'B1', 'B3', 'C1', 'C2']),
        (TARGETS[4], ['load_sprite_anim', 'sprite_anim', 'anim_total',
                      "'base': 'objs/%s' % spr", 'default_30fps']),
    ]
    for p, toks in token_checks:
        rel = os.path.relpath(p, ROOT)
        t = io.open(p, 'r', encoding='utf-8').read()
        lost = [k for k in toks if k not in t]
        C('5', not lost, '%s 令牌全在（丢 %s）' % (rel, lost or '无'))

    # 5b 数据令牌：_sprite_anim.json 的 6 个多帧 sprite 名字都在
    try:
        d = json.load(io.open(JSONS[0], 'r', encoding='utf-8'))
        sp = d.get('sprites') or {}
        want = ['spr_savepoint', 'spr_susier_plain', 'spr_krisu_bright',
                'spr_darkdoor', 'spr_shortcut_door', 'spr_giantdarkdoor']
        lost = [k for k in want if k not in sp]
        C('5b', not lost,
          '_sprite_anim.json 6 个多帧 sprite 全在（丢 %s，实有 %d）'
          % (lost or '无', len(sp)))
        # 数值令牌：全部 frame_ms == 33.3，fps == 30
        bad = [(k, v.get('frame_ms')) for k, v in sp.items()
               if abs(float(v.get('frame_ms') or 0) - 33.3) > 0.11]
        C('5c', not bad and d.get('fps') == 30,
          '数值令牌（fps=30、frame_ms=33.3±0.11）全对（异常 %s）' % (bad or '无'))
    except Exception as e:
        C('5b', False, '_sprite_anim.json 读取失败 %r' % (e,))
        C('5c', False, '同上')

    # ============ 6. 状态干净 ============
    w('')
    w('--- 6. 状态与回归 ---')
    # 6a 本轮改过的生产文件是否只有预期的 2 个
    #   ★ 判据修正：初版把 `src/__pycache__/main.cpython-311.pyc` 也算作"生产改动"
    #     —— 那是**本脚本第 1 步 py_compile 自己生成的**，不是我的编辑。
    #     真正该守的是「**手写源码**只改了那 2 个」（记忆：判据报红先怀疑判据）。
    r = subprocess.run(['git', 'status', '--porcelain'],
                       cwd=ROOT, capture_output=True)
    st = r.stdout.decode('utf-8', 'replace').splitlines()
    prod_changed = [l[3:].strip() for l in st
                    if l[3:].strip().startswith('ralsei_pet/')
                    and 'assets/scenes/' not in l
                    and '__pycache__' not in l
                    and not l[3:].strip().endswith('.pyc')]
    C('6a', sorted(prod_changed) == sorted([
        'ralsei_pet/modules/scene_render.py', 'ralsei_pet/src/main.py']),
      '生产**手写源码**改动恰为 2 个（scene_render.py + main.py）；实测 %s'
      % prod_changed)

    # 6b 回复检：能编译 + 关键函数签名在位（AST 级）
    try:
        import ast
        tree = ast.parse(sr)
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(n.name)
        C('6b', '_anim_frame_index' in names and 'plan_frame' in names,
          'scene_render AST 函数表含两者')
        # plan_frame 有 tick 形参
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name == 'plan_frame':
                args = [a.arg for a in n.args.args]
                C('6c', 'tick' in args, 'plan_frame 形参含 tick（%s）' % args)
    except Exception as e:
        C('6b', False, 'AST 解析失败 %r' % (e,))
        C('6c', False, '同上')

    w('')
    w('=== 结论：PASS=%d FAIL=%d ===' % (len(L) - sum(1 for x in L if x.startswith('[FAIL]')),
                                          len(fails)))
    if fails:
        w('')
        w('--- FAIL 明细 ---')
        for cid, msg in fails:
            w('  [%s] %s' % (cid, msg))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return 1 if fails else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        tb = traceback.format_exc()
        with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('!! 复检脚本自身崩溃：\n' + tb)
        print(tb)
        sys.exit(2)
