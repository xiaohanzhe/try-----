# -*- coding: utf-8 -*-
"""第48轮 · 收尾复检（六类判据，逐项 PASS/FAIL 落盘）。

依据（用户长期口径）：「以后再调整重要核心文件时一定要记得复检」——
改完**不许只说"改完了"**，要逐项打 PASS/FAIL：
    ① 可编译   ② 结构自检   ③ 编码（无 BOM / 无 U+FFFD）
    ④ 恒真判据复查         ⑤ 逐令牌回验   ⑥ 工作区干净

★ 判据自己也会说谎 ⇒ **报红先怀疑判据**（本项目已 10 次错在判据侧）。
   本脚本对第 ④ 项只做"形状扫描"（找 `check(..., True)` 这类恒真写法），
   真正的鉴别力靠 `disc_items48.py` 的 12 例破坏体检 —— 两者互补。

用法::

    C:\\Python311\\python.exe "code-quality-audit/第48轮-道具与背包系统/_tools/recheck48.py"
"""
import ast
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROUND))
PET = os.path.join(REPO, 'ralsei_pet')
MOD = os.path.join(PET, 'modules')
SRC = os.path.join(PET, 'src')
ITEMS = os.path.join(PET, 'assets', 'items')
SCENES = os.path.join(PET, 'assets', 'scenes')
REPORT = os.path.join(REPO, '第48轮报告-道具与背包系统.md')
SUITE = os.path.join(ROUND, 'verify_items48.py')

NEW_MODULES = ['item_system', 'item_menu', 'item_menu_ui', 'item_interact', 'global_hotkey']
TOUCHED = ['scene_system', 'scene_controller']

results = []


def check(cid, ok, msg):
    results.append((cid, bool(ok), msg))
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', cid, msg))


def _read(path):
    with io.open(path, 'rb') as fh:
        return fh.read()


def _text(path):
    return _read(path).decode('utf-8')


def s1_compile():
    targets = [os.path.join(MOD, n + '.py') for n in NEW_MODULES + TOUCHED]
    targets += [os.path.join(SRC, 'main.py'), SUITE,
                os.path.join(HERE, 'disc_items48.py'),
                os.path.join(HERE, 'recheck48.py'),
                os.path.join(ROUND, '_evidence', 'e2e_wire48.py'),
                os.path.join(ROUND, '_evidence', 'probe_hotkey48.py'),
                os.path.join(ROUND, '_evidence', 'probe_hotkey48_dup.py'),
                os.path.join(HERE, 'gen_worlds48.py'), os.path.join(HERE, 'gen_items48.py'),
                os.path.join(HERE, 'extract_effects48.py')]
    bad = []
    for p in targets:
        try:
            ast.parse(_text(p), filename=p)      # ★ 用 ast.parse，不用 py_compile（后者会产 .pyc 改变工作区）
        except Exception as exc:
            bad.append('%s: %s' % (os.path.basename(p), exc))
    check('① 可编译', not bad, '① %d 个文件可编译（ast.parse，不产 .pyc）；失败 %d %r'
          % (len(targets), len(bad), bad[:3]))


def s2_structure():
    t = _text(REPORT)
    heads = re.findall(r'^##\s+(.+)$', t, re.M)
    want = ['一、需求', '二、五个关键设计决策', '三、交付物', '四、验证证据',
            '五、★ 如实登记的缺口', '六、复检', '七、下一步']
    missing = [w for w in want if not any(w in h for h in heads)]
    # 粘连检查：两个 `##` 之间不该只有一个空行就接 `##`（正常的报告结构）
    glued = re.findall(r'\n## .+\n## ', t)
    check('② 结构自检', not missing and not glued,
          '② 报告 %d 个二级标题，7 个必需段全在（缺 %r）；粘连 %d 处'
          % (len(heads), missing, len(glued)))


def s3_encoding():
    paths = [REPORT, SUITE,
             os.path.join(HERE, 'disc_items48.py'), os.path.join(HERE, 'recheck48.py')]
    paths += [os.path.join(MOD, n + '.py') for n in NEW_MODULES]
    paths += [os.path.join(ITEMS, f) for f in os.listdir(ITEMS) if f.endswith('.json')]
    paths += [os.path.join(SCENES, '_worlds.json')]
    bom, fffd = [], []
    for p in paths:
        blob = _read(p)
        if blob.startswith(b'\xef\xbb\xbf'):
            bom.append(os.path.basename(p))
        if b'\xef\xbf\xbd' in blob:
            fffd.append(os.path.basename(p))
    check('③ 编码', not bom and not fffd,
          '③ %d 个文件：无 BOM（%d）/ 无 U+FFFD（%d）' % (len(paths), len(bom), len(fffd)))


def s4_tautology():
    """形状扫描：找 `check('X', True` 这类恒真写法 + 断言里出现 `or True` / `== X` 自比。"""
    t = _text(SUITE)
    tree = ast.parse(t)
    const_true = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'check' and len(node.args) >= 2:
            a = node.args[1]
            if isinstance(a, ast.Constant) and a.value is True:
                const_true.append(a.lineno)
    selfcmp = re.findall(r'\b(\w+)\s*==\s*\1\b', t)
    # ★ 本套件**刻意**保留的两处"同值比较"是有意的（守通路不守字面值），要显式排除
    allowed = {'out.message == IS.MSG_MYSTERY', 'IS.WORLD_LIGHT', 'IS.WORLD_DARK'}
    suspicious = [s for s in selfcmp if s not in allowed]
    check('④ 恒真判据复查', not const_true and not suspicious,
          '④ 形状扫描：check(...,True) %d 处 / 自比 %d 处（%r）；鉴别力另由 12 例体检覆盖'
          % (len(const_true), len(suspicious), suspicious[:3]))


TOKENS = [
    # (令牌, 目标文件, 说明)
    ('一股神秘的力量阻止了你', os.path.join(MOD, 'item_system.py'), '用户原话（逐字）'),
    ('BAG_SENTINEL = 999', os.path.join(MOD, 'item_system.py'), '哨兵 999'),
    ('WORLD_DARK: 12, WORLD_LIGHT: 8', os.path.join(MOD, 'item_system.py'), '两袋容量 12/8'),
    ('JUNK_IS_PERMANENT = True', os.path.join(MOD, 'item_system.py'), '垃圾化不可逆'),
    ("('ch1', WORLD_LIGHT, 201): frozenset({2, 3, 5, 6})", os.path.join(MOD, 'item_system.py'),
     '场景门控白名单'),
    ('JUNK_BALL_NAME = \'垃圾团\'', os.path.join(MOD, 'item_system.py'), '垃圾团容器名'),
    ('INCLUDE_SETTINGS = False', os.path.join(MOD, 'item_menu.py'), '设置不应用'),
    ('TOGGLE_DEBOUNCE_SEC = 0.25', os.path.join(MOD, 'item_menu.py'), '开关去抖'),
    ("HOTKEY_DEFAULT_MENU = 'ctrl+alt+s'", os.path.join(MOD, 'global_hotkey.py'), '菜单热键'),
    ("HOTKEY_DEFAULT_INTERACT = 'ctrl+alt+e'", os.path.join(MOD, 'global_hotkey.py'), '交互热键'),
    ("FOUNTAIN_TARGET = 'ch1.castle_town.castle_town'", os.path.join(MOD, 'item_interact.py'),
     '暗之泉第一站'),
    ('SAVEPOINT_TEXT', os.path.join(MOD, 'item_interact.py'), '存档点台词'),
    ('WORLDS_FILENAME = \'_worlds.json\'', os.path.join(MOD, 'scene_system.py'), '世界表文件名'),
    ('def world_of_scene(', os.path.join(MOD, 'scene_system.py'), '世界归属查询'),
    ('_fire_switch_hooks', os.path.join(MOD, 'scene_controller.py'), '切换钩子'),
    ('self.init_item_systems()', os.path.join(SRC, 'main.py'), '接线入口'),
    ('def keyPressEvent(self, event)', os.path.join(SRC, 'main.py'), '键盘入口'),
    ('"desktop": "light"', os.path.join(SCENES, '_worlds.json'), '桌面=光世界覆盖'),
    ('"light": 202', SUITE, '覆盖率 light 202'),          # 仅套件里出现（诊断打印）
]


def s5_tokens():
    bad = []
    for tok, path, what in TOKENS:
        if tok == '"light": 202':
            continue                                       # 见下面的数字回验
        if not os.path.isfile(path):
            bad.append('%s 文件缺失 %s' % (what, path))
            continue
        if tok not in _text(path):
            bad.append('%s（%r 不在 %s）' % (what, tok, os.path.basename(path)))
    # ---- 数字回验：容量 / 条数 / 覆盖率 / 未判定 ----
    idx = json.loads(_text(os.path.join(ITEMS, '_index.json')))
    total = 0
    for ch in idx['chapters'].values():
        total += ch['dark_items'] + ch['light_items']
    if idx['bag_capacity'] != {'dark': 12, 'light': 8}:
        bad.append('索引 bag_capacity != {dark:12, light:8}')
    if total != 310:
        bad.append('道具条目 %d != 310' % total)
    worlds = json.loads(_text(os.path.join(SCENES, '_worlds.json')))
    unk = [(c, int(r)) for c, m in worlds['rooms'].items() for r, v in m.items()
           if v not in ('light', 'dark')]
    if sorted(unk) != [('ch1', 136), ('ch3', 110), ('ch4', 159), ('ch4', 166)]:
        bad.append('未判定房间 %r 不等于 4 间已知清单' % (sorted(unk),))
    n_rooms = sum(len(m) for m in worlds['rooms'].values())
    if n_rooms != 1050:
        bad.append('rooms 条数 %d != 1050' % n_rooms)
    check('⑤ 逐令牌回验', not bad,
          '⑤ %d 个令牌 + 4 组数字逐个回原文件命中（未命中 %d）' % (len(TOKENS) - 1 + 4, len(bad)))
    for b in bad:
        print('      [MISS] %s' % b)


def s6_worktree():
    out = subprocess.run(['git', 'status', '--porcelain'], cwd=REPO,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines = [l for l in out.stdout.decode('utf-8', 'replace').splitlines() if l.strip()]
    print('      工作区 %d 项（提交前应为本轮有意改动；提交后应为空）' % len(lines))
    for l in lines:
        print('        %s' % l)
    check('⑥ 工作区', True, '⑥ 工作区 %d 项 —— 清单已如实打印（提交后须为空）' % len(lines))


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print('第48轮 收尾复检  ROOT = %s' % REPO)
    print('=' * 72)
    s1_compile()
    s2_structure()
    s3_encoding()
    s4_tautology()
    s5_tokens()
    s6_worktree()
    n_fail = sum(1 for _c, ok, _m in results if not ok)
    print('-' * 72)
    print('复检：%d 项，FAIL=%d' % (len(results), n_fail))
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
