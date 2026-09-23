# -*- coding: utf-8 -*-
"""第 38 轮开局复检（六类判据）。

按 skill `core-file-recheck` 的口径：**判据自己也会说谎 —— 报红先怀疑判据**。
本脚本只读被检文件，不改任何东西；结果落盘到 _evidence/复检_第38轮开局.txt。
"""
import io
import json
import os
import re
import subprocess
import sys
import traceback

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
R38 = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查')
TOOLS = os.path.join(R38, '_tools')
EV = os.path.join(R38, '_evidence')
DR = r'E:\Download\_tmp\dr_out'
DRW = r'E:\Download\_tmp\drw'
MEM = os.path.join(ROOT, '.workbuddy', 'memory', '2026-09-23.md')
PY = r'C:\Python311\python.exe'

RESULT = []
OUT = []


def w(s=''):
    OUT.append(str(s))
    print(s)


def check(name, ok, detail=''):
    RESULT.append((bool(ok), name, str(detail)))
    w('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                   ('  <- ' + str(detail)) if detail else ''))


def read(p, mode='r'):
    with io.open(p, mode, encoding=None if 'b' in mode else 'utf-8') as fh:
        return fh.read()


try:
    # ==================================================================
    # 1. 可编译 / 可解析
    # ==================================================================
    w('=== 1. 可编译 / 可解析 ===')
    pys = sorted(f for f in os.listdir(TOOLS) if f.endswith('.py'))
    w('  本轮新增 .py：%d 个 %s' % (len(pys), pys))
    bad_py = []
    for f in pys:
        r = subprocess.run([PY, '-m', 'py_compile', os.path.join(TOOLS, f)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            bad_py.append('%s: %s' % (f, r.stderr.strip()[:200]))
    check('1.1 全部新增 .py 可编译', not bad_py, bad_py)

    jsons = sorted(f for f in os.listdir(EV) if f.endswith('.json'))
    bad_js = []
    for f in jsons:
        try:
            json.loads(read(os.path.join(EV, f)))
        except Exception as e:
            bad_js.append('%s: %s' % (f, e))
    check('1.2 _evidence 下全部 .json 可解析', not bad_js, bad_js)
    w('  本轮新增 .json：%s' % jsons)

    # 记忆文件：markdown 代码围栏成对
    ms = read(MEM)
    check('1.3 记忆日志代码围栏成对（``` 计数为偶）',
          ms.count('```') % 2 == 0, 'count=%d' % ms.count('```'))

    # csx 括号/引号粗检
    csx = read(r'E:\Download\_tmp\dump_roomname.csx')
    check('1.4 csx 花括号配平', csx.count('{') == csx.count('}'),
          '%d vs %d' % (csx.count('{'), csx.count('}')))
    w('')

    # ==================================================================
    # 2. 结构自检（Edit 最容易在这里翻车）
    # ==================================================================
    w('=== 2. 结构自检 ===')
    check('2.1 记忆日志含第 38 轮章节',
          '## 第三十八轮' in ms)
    glued = [i for i, l in enumerate(ms.split('\n'), 1)
             if '##' in l and not l.lstrip().startswith('##') and not l.lstrip().startswith('>')]
    check('2.2 记忆日志无「标题被粘到上一行」', not glued, glued)
    for k in ('### A.', '### B.', '### C.'):
        if k not in ms:
            check('2.3 第 38 轮小节 %s 存在' % k, False, 'missing')
    check('2.3 第 38 轮三个小节齐全',
          all(k in ms for k in ('### A.', '### B.', '### C.')))
    # 新增小节是否挤掉了原有的四个「待裁定」项
    check('2.4 第 37 轮的待裁定项仍在（未被 Edit 覆盖）',
          '**平铺画布口径**' in ms and '**`bg` 字段尚无渲染层消费**' in ms)
    w('')

    # ==================================================================
    # 3. 编码
    # ==================================================================
    w('=== 3. 编码 ===')
    targets = [MEM] + [os.path.join(TOOLS, f) for f in pys] + \
              [os.path.join(EV, f) for f in os.listdir(EV)]
    bom, fffd = [], []
    for p in targets:
        if not os.path.isfile(p):
            continue
        b = read(p, 'rb')
        if b[:3] == b'\xef\xbb\xbf':
            bom.append(os.path.basename(p))
        if b'\xef\xbf\xbd' in b:
            fffd.append(os.path.basename(p))
    check('3.1 无 BOM', not bom, bom)
    check('3.2 无 U+FFFD 替换字符', not fffd, fffd)
    check('3.3 被检文件数 > 0', len(targets) > 0, len(targets))
    w('  被检文件 %d 个' % len(targets))
    w('')

    # --- 4. 恒真判据复查（走 AST，不走字符串正则 —— 字符串正则会被自己的判据文案命中）---
    w('=== 4. 恒真判据复查 ===')
    import ast
    fake = []
    for f in pys:
        if f == 'recheck38.py':
            continue          # 本文件自带判据文案，扫它会自指
        src = read(os.path.join(TOOLS, f))
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = getattr(fn, 'id', None) or getattr(fn, 'attr', None)
            if name not in ('check', 'ok'):
                continue
            args = node.args
            # 第二位置参数（或 ok() 的第一参数）是字面量 True / 真值常量 → 恒真
            idx = 1 if name == 'check' else 0
            if len(args) > idx and isinstance(args[idx], ast.Constant) \
                    and args[idx].value is True:
                fake.append('%s:%d' % (f, node.lineno))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert) and isinstance(node.test, ast.Constant):
                fake.append('%s:%d assert 常量' % (f, node.lineno))
    check('4.1 其余 .py 里无恒真判据（AST 判据，排除本复检脚本自身）',
          not fake, fake)
    w('  （注：audit_data 3.7 是弱判据 —— 只验数据形态、验不了匹配时的大小写归一，'
      '已单列为待修项）')
    w('')

    # ==================================================================
    # 5. 逐令牌回验（本轮所有对外声称的数字/标识符）
    # ==================================================================
    w('=== 5. 逐令牌回验（重算，不靠"文件里有"）===')
    PAIRS = [('ch1', 'chapter1_windows'), ('ch2', 'chapter2_windows'),
             ('ch3', 'chapter3_windows'), ('ch4', 'chapter4_windows'),
             ('ch5', 'chapter5_windows')]

    rooms = {}
    for ch, folder in PAIRS:
        d = json.loads(read(os.path.join(DR, folder, 'rooms_map.json')))
        rs = d.get('rooms') if isinstance(d, dict) else d
        rooms[ch] = [r for r in rs if isinstance(r, dict)]
    got = {ch: len(v) for ch, v in rooms.items()}
    claimed = {'ch1': 147, 'ch2': 278, 'ch3': 246, 'ch4': 328, 'ch5': 252}
    check('5.1 五章 room 数 = 147/278/246/328/252', got == claimed,
          '实得 %s' % got)
    check('5.2 合计 1251', sum(got.values()) == 1251, sum(got.values()))

    # 登记场景数
    # ⚠️ 判据修正：`_index.json` 磁盘上是三级嵌套（chapters→areas→scenes），
    #    扁平 `scenes` 是 `load_index()` **构建**出来的，裸 JSON 里没有。
    #    （初版判据直接读 `raw['scenes']` ⇒ 恒 0 ⇒ 假红。属"判据自己说谎"。）
    IDX = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_index.json')
    idx_raw = json.loads(read(IDX))
    nested = 0
    for c in (idx_raw.get('chapters') or {}).values():
        for a in (c.get('areas') or {}).values():
            nested += len(a.get('scenes') or {})
    check('5.3 _index.json 三级嵌套里的场景 = 88（含 desktop）', nested == 88,
          nested)
    check('5.3b 裸 JSON 无顶层 scenes 键（扁平表由 load_index 构建）',
          'scenes' not in idx_raw, sorted(idx_raw)[:8])
    n_file = len([f for f in os.listdir(os.path.dirname(IDX))
                  if f.endswith('.json') and not f.startswith('_')])
    check('5.4 场景 JSON 文件数 = 88', n_file == 88, n_file)

    # scr_roomname 分支数
    br = {}
    for ch, folder in PAIRS:
        t = read(os.path.join(DRW, folder, '_roomname_code.txt'))
        br[ch] = len(re.findall(r'if \(arg0 == \d+\)', t))
    check('5.5 scr_roomname 分支 = 20/20/9/20/26',
          br == {'ch1': 20, 'ch2': 20, 'ch3': 9, 'ch4': 20, 'ch5': 26}, br)
    check('5.6 分支合计 95 / 减 5 个 --- = 90 个官方地点',
          sum(br.values()) == 95, sum(br.values()))

    # 用产品函数重算分类（不用我自己的正则，改用与 classify_rooms 一致的规则，
    # 但**单独再算一遍**，比对已落盘结果）
    sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
    import scene_system as S            # noqa: E402
    i2 = S.load_index()
    reg_ids = set()
    for sid, e in (i2.get('scenes') or {}).items():
        rid = (e or {}).get('original_room_id')
        if rid is not None:
            reg_ids.add((str(e.get('chapter_id')), rid))
    w('  登记的 (chapter, original_room_id) 对 = %d' % len(reg_ids))
    check('5.7 登记的场景都带回溯 id（除 desktop）', len(reg_ids) == 87,
          len(reg_ids))

    # ch2 多登记的 199/200、ch5 漏登记的 5 个 —— 用原始数据复核
    orig = json.loads(read(os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes',
                                        '_original_rooms.json')))
    for ch in ('ch2', 'ch5'):
        # ⚠️ 初版写成 ch + '_windows' ⇒ 'ch2_windows'（真目录是 chapter2_windows）
        #    ⇒ FileNotFoundError 让后面 8 项全没跑。这是**真 bug**，不是判据问题。
        t = read(os.path.join(DRW, dict(PAIRS)[ch], '_roomname_code.txt'))
        script_ids = set(int(x) for x in re.findall(r'if \(arg0 == (\d+)\)', t))
        our_ids = set(int(r['id']) for r in
                      ((orig['chapters'].get(ch)) or {}).get('rooms') or [])
        extra = sorted(our_ids - script_ids)
        missing = sorted(script_ids - our_ids)
        if ch == 'ch2':
            check('5.8 ch2 多登记 = [199, 200]', extra == [199, 200], extra)
            check('5.9 ch2 无漏登记', missing == [], missing)
        else:
            check('5.10 ch5 漏登记 = [205, 222, 224, 225, 230]',
                  missing == [205, 222, 224, 225, 230], missing)
            check('5.11 ch5 无多登记', extra == [], extra)

    # bg 目录体积
    bgdir = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'bg')
    nbg = len(os.listdir(bgdir))
    szbg = sum(os.path.getsize(os.path.join(bgdir, f)) for f in os.listdir(bgdir))
    check('5.12 bg 目录 = 88 文件 / 2,115,135 B',
          nbg == 88 and szbg == 2115135, '%d / %d' % (nbg, szbg))

    # 代码瑕疵三条
    MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
    rt = read(os.path.join(MOD, 'scene_routing.py'))
    check('5.13 _FALLBACK_PRIORITY 定义后未被使用',
          len(re.findall(r'_FALLBACK_PRIORITY', rt)) == 1,
          len(re.findall(r'_FALLBACK_PRIORITY', rt)))
    ctl = read(os.path.join(MOD, 'scene_controller.py'))
    # ⚠️ 判据修正：初版断言"只出现 1 次"，但那一行里 `self.refresh_objects()` 与
    #    `hasattr(self, 'refresh_objects')` 共出现 **2 次** ⇒ 假红。
    #    真正要守的是：**全仓没有 `def refresh_objects`** ⇒ 该 hasattr 恒假。
    n_occ = len(re.findall(r'refresh_objects', ctl))
    has_def = 'def refresh_objects' in ctl
    proj_def = []
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'ralsei_pet')):
        for fn in files:
            if fn.endswith('.py'):
                fp = os.path.join(dirpath, fn)
                if 'def refresh_objects' in read(fp):
                    proj_def.append(os.path.relpath(fp, ROOT))
    check('5.14 全仓无 `def refresh_objects` ⇒ hasattr 恒假、scene_objects 恒为 []',
          (not has_def) and (not proj_def),
          'occurrences=%d def_in_ctl=%s defs=%s' % (n_occ, has_def, proj_def))
    check('5.14b refresh_objects 只在 scene_controller 那一行出现（2 次）',
          n_occ == 2, n_occ)
    main_src = read(os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'))
    body = re.search(r'# ========== 场景系统 状态字段（P0）==========(.*?)\n\n    # 帧动画',
                     main_src, re.S)
    nf = len(re.findall(r'self\.(_scene_\w+|_routes_loaded|current_scene|scene_objects)\s*=',
                        body.group(1) if body else ''))
    check('5.15 main.py 场景状态字段预声明 = 9（文档写 6，已列为待修）',
          nf == 9, nf)
    check('5.16 main.py 里 self.scene.<方法>() 调用点 = 0',
          len(re.findall(r'self\.scene\.\w+\s*\(', main_src)) == 0)
    w('')

    # ==================================================================
    # 6. 状态干净
    # ==================================================================
    w('=== 6. 状态干净 ===')
    r = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                       capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    w('  git status --porcelain 行数 = %d' % len(lines))
    for l in lines:
        w('    %s' % l)
    # 判据：不得出现 ralsei_pet/ 下的修改（本轮只读审查，不该动产品文件）
    prod = [l for l in lines if 'ralsei_pet/' in l and not l.startswith('?? ')]
    check('6.1 没有修改任何 ralsei_pet/ 下的已跟踪文件', not prod, prod)
    newok = all(l.startswith('?? ') or 'memory/2026-09-23.md' in l
                or '_tools' in l or '_evidence' in l for l in lines)
    check('6.2 改动只落在记忆日志 + 本轮新增目录', newok)
    w('')

    # ==================================================================
    # 7. 异常复核：ch5 的 scr_get_room_list 条目数反了常
    # ==================================================================
    w('=== 7. 异常复核（ch5 scr_get_room_list = 277 > ch5 room 数 252）===')
    t5 = read(os.path.join(DRW, 'chapter5_windows', '_roomname_code.txt'))
    blocks = re.split(r'function (\w+)\(', t5)
    fns = re.findall(r'function (\w+)\(', t5)
    w('  文件里的 function 名 = %s' % fns)
    for i in range(1, len(blocks) - 1, 2):
        nm = blocks[i]
        body = blocks[i + 1]
        n = len(re.findall(r'new scr_room\(', body))
        if n:
            w('  %s() 里 new scr_room 条目 = %d' % (nm, n))
    n5 = len(re.findall(r'new scr_room\(', t5))
    check('7.1 ch5 文件里 new scr_room 总条目 = 277', n5 == 277, n5)

    # ★ 异常定性：ch5 有 252 个 room，却列出 277 个 scr_room 条目
    #   ⇒ scr_get_room_list 不是"本章房间清单"。看 ch2 是不是同一个数。
    n2 = len(re.findall(r'new scr_room\(',
                        read(os.path.join(DRW, dict(PAIRS)['ch2'],
                                          '_roomname_code.txt'))))
    check('7.2 ch2 与 ch5 的 scr_get_room_list 条目数相同 ⇒ 它是跨章共享的 id 注册表',
          n2 == n5, 'ch2=%d ch5=%d' % (n2, n5))
    check('7.3 它比 ch5 实际 room 数(252)多 ⇒ 不能当"本章房间全集"用',
          n5 > len(rooms['ch5']), '%d vs %d' % (n5, len(rooms['ch5'])))
    # arg0 对齐：抽 5 个 id 核对 scr_roomname 的 arg0 是不是 rooms_map 下标
    spot = [(45, 'room_castle_town'), (114, 'room_cc_1f'), (126, 'room_cc_throneroom')]
    names1 = [str(r.get('name') or '') for r in rooms['ch1']]
    bad = [(i, w2, names1[i]) for i, w2 in spot if names1[i] != w2]
    check('7.4 scr_roomname(arg0) 的 arg0 == rooms_map 下标（ch1 抽 3 点）',
          not bad, bad)
    w('')

except Exception:
    w('')
    w('!!! 复检脚本自己崩了 —— 这看起来像"没跑"，实际是异常 !!!')
    w(traceback.format_exc())
    RESULT.append((False, '复检脚本自身未抛异常', 'traceback 见上'))

# ======================================================================
fails = [r for r in RESULT if not r[0]]
w('=' * 62)
w('合计 %d 项：PASS=%d FAIL=%d' % (len(RESULT), len(RESULT) - len(fails), len(fails)))
if fails:
    w('')
    w('--- FAIL 明细 ---')
    for _, n, d in fails:
        w('  FAIL: %s  %s' % (n, d))

os.makedirs(EV, exist_ok=True)
p = os.path.join(EV, '复检_第38轮开局.txt')
with io.open(p, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(OUT) + '\n')
print('written:', p)
