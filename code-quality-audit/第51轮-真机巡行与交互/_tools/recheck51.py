# -*- coding: utf-8 -*-
"""第51轮 · 移动参数调整后的逐项复检（用户口径：「调整重要核心文件时一定要记得复检」）

六类判据（见 skill `core-file-recheck`）：
  ① 可编译      ② 结构自检（函数齐全、行号连续）  ③ 编码（无 BOM / 无 U+FFFD / 纯 LF）
  ④ 恒真判据复查（本轮的检查项本身会不会恒真/恒假）
  ⑤ 逐令牌回验（每个改过/保留的字面量逐个回原文件 `in` 一次）
  ⑥ 工作区干净（git status，另在提交环节核对）

★ 特别加一条**回退守卫**：`IDLE_LOOP_MIN_SECONDS = 180.0` 是**用户明确要求**
  （"待机动画要在原地不动3分钟以上才会播放哦"），本轮**不得**被改动。
"""
import ast
import sys
import io
import os
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
P = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

res = []


def chk(name, ok, detail=''):
    res.append((bool(ok), name, detail))


def main():
    raw = open(P, 'rb').read()
    src = raw.decode('utf-8')

    # ① 可编译 / 可解析
    tree = None
    f_src = {}          # ② 里填充：被测两个函数的**函数体源码文本**
    try:
        tree = ast.parse(src)
        chk('① ast.parse 可解析', True)
    except SyntaxError as e:
        chk('① ast.parse 可解析', False, '%s' % e)

    # ② 结构自检
    if tree is not None:
        fns = {n.name: (n.lineno, n.end_lineno)
               for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for f in ('randomize_movement_pattern', 'generate_new_move_target', 'update_movement'):
            chk('② 函数存在 %s' % f, f in fns, str(fns.get(f)))
        # 目标函数里 randint/uniform 调用数（结构完整性：应当仍有 5 档距离）
        def calls_in(fname):
            node = next((n for n in ast.walk(tree)
                         if isinstance(n, ast.FunctionDef) and n.name == fname), None)
            if node is None:
                return (0, 0)
            ri = un = 0
            for n in ast.walk(node):
                if isinstance(n, ast.Call):
                    nm = getattr(n.func, 'attr', None)
                    if nm == 'randint':
                        ri += 1
                    elif nm == 'uniform':
                        un += 1
            return (ri, un)
        ri, un = calls_in('generate_new_move_target')
        chk('② generate_new_move_target 里 randint 调用数 >=5', ri >= 5, 'count=%d' % ri)
        ri2, un2 = calls_in('randomize_movement_pattern')
        chk('② randomize_movement_pattern 里 uniform 调用数 >=6', un2 >= 6, 'count=%d' % un2)

        # 供 ⑤b 用：把被测两个函数的**函数体文本**单独取出来（判定范围必须收窄到函数内）
        _lines = src.split('\n')
        for f in ('randomize_movement_pattern', 'generate_new_move_target'):
            node = next((n for n in ast.walk(tree)
                         if isinstance(n, ast.FunctionDef) and n.name == f), None)
            if node is not None:
                f_src[f] = '\n'.join(_lines[node.lineno - 1:node.end_lineno])
        chk('② 已提取被测函数体文本（供收窄判定用）',
            len(f_src) == 2, 'got=%r' % sorted(f_src.keys()))

    # ③ 编码
    chk('③ 无 UTF-8 BOM', not raw.startswith(b'\xef\xbb\xbf'), raw[:3].hex())
    chk('③ 无 U+FFFD', chr(0xfffd) not in src, 'count=%d' % src.count(chr(0xfffd)))
    chk('③ 行尾为纯 LF（无 CRLF）', b'\r\n' not in raw, 'CR 数=%d' % raw.count(b'\r'))

    # ④ 恒真判据复查：本文件的检查项必须是"能与不能都出现"的可辨别的
    chk('④ 检查项非恒真（自检：对不存在串应判 False）',
        ('__THIS_TOKEN_MUST_NOT_EXIST_51__' in src) is False)

    # ⑤ 逐令牌回验 —— 本轮**新增/修改**的每一个字面量
    new_tokens = [
        'move_distance = random.randint(180, 420)',
        'move_distance = random.randint(150, 340)',
        'move_distance = random.randint(160, 380)',
        'move_distance = random.randint(120, 280)',
        'move_distance = random.randint(150, 360)',
        'move_probability = 0.85',
        'move_probability = 0.5',
        'move_probability = 0.7',
        'move_probability = 0.35',
        'move_probability = 0.55',
        'self.max_idle_duration = random.uniform(2.0, 5.0)',
        'self.max_idle_duration = random.uniform(4.0, 10.0)',
        'self.max_idle_duration = random.uniform(3.0, 7.0)',
        'self.max_idle_duration = random.uniform(5.0, 12.0)',
        'self.max_idle_duration = random.uniform(4.0, 9.0)',
        'if random.random() < 0.75:',
        'if random.random() < 0.45:',
        'if random.random() < 0.5:',
    ]
    miss = [t for t in new_tokens if t not in src]
    chk('⑤ 新增令牌全部存在（%d 项）' % len(new_tokens), not miss, '缺失=%r' % miss)

    # ⑤b 旧值必须**已消失**（防"改了但没改到"）
    # ⚠️ 判据范围必须收窄到**被改的两个函数体内**：第一版用全文 `in` 判，把
    #    `generate_new_move_target` 里合法的"60% 横向移动"(`< 0.6`) 与别处的
    #    `< 0.3` 一并算成"残留" ⇒ **判据过宽造成 3 项误报**（项目教训 §4：
    #    判据过窄会误报，过宽同样要防）。另有 1 项与**新值同字面量**
    #    （`uniform(5.0, 12.0)` 既是 curious 旧值、又是 sad/tired 新值）属自相矛盾，已剔除。
    scope = '\n'.join((f_src.get('generate_new_move_target') or '',
                       f_src.get('randomize_movement_pattern') or ''))
    old_tokens = [
        'move_distance = random.randint(50, 150)',
        'move_distance = random.randint(30, 100)',
        'move_distance = random.randint(100, 300)',
        'move_distance = random.randint(80, 250)',
        'move_probability = 0.3\n',
        'move_probability = 0.2\n',
        'move_probability = 0.4\n',
        'self.max_idle_duration = random.uniform(8.0, 20.0)',
        'self.max_idle_duration = random.uniform(10.0, 25.0)',
        'self.max_idle_duration = random.uniform(6.0, 15.0)',
        'self.max_idle_duration = random.uniform(3.0, 8.0)',
        'if random.random() < 0.2:',
    ]
    left = [t for t in old_tokens if t in scope]
    chk('⑤b 旧值已全部消失（%d 项，限两函数内）' % len(old_tokens), not left, '残留=%r' % left)

    # ★ 关键回退守卫：用户口径不得被改动
    chk('★ 用户口径守卫：IDLE_LOOP_MIN_SECONDS = 180.0 保持原样',
        'IDLE_LOOP_MIN_SECONDS = 180.0' in src)
    chk('★ 用户口径守卫生效（若改成 12 必须报红）',
        'IDLE_LOOP_MIN_SECONDS = 12' not in src)

    # 输出
    print('=' * 74)
    print('第51轮 移动参数调整 · 复检报告')
    print('=' * 74)
    npass = sum(1 for ok, _, _ in res if ok)
    for ok, name, detail in res:
        print('  [%s] %-52s %s' % ('PASS' if ok else 'FAIL', name, detail))
    print('-' * 74)
    print('  PASS=%d  FAIL=%d  文件=%s  行数=%d'
          % (npass, len(res) - npass, os.path.basename(P), src.count('\n') + 1))
    return 0 if npass == len(res) else 1


if __name__ == '__main__':
    sys.exit(main())
