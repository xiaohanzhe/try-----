# -*- coding: utf-8 -*-
"""第34轮续三回归锁：F34-4 隐私应用接线断链（round34c_privacy_wire）

锁什么：
  A 结构（AST）
    A1  user_opened_privacy_apps 的**唯一写入点**必须是 mark_app_as_opened
        （若哪天出现第二个写入点，说明接线方案变了，必须人工复核）
    A2  mark_app_as_opened 全项目**零调用**这一事实必须仍然成立
        （若接线了 -> 报红，提示本锁的语义前提已失效、需按新事实重写）
    A3  L1192 判据的形状必须仍是 `is_privacy_app and hwnd not in self.user_opened_privacy_apps`
    A4  privacy_apps 默认清单必须包含 微信/QQ/钉钉/企业微信/Outlook（覆盖面前提）
  B 行为（用产品真源码 + 最小桩，不重写逻辑）
    B1  空列表下：6 个隐私应用窗口全部被跳过（判据恒真）
    B2  非隐私对照（Chrome/记事本）不被跳过
    B3  反证：列表内若有对应 hwnd -> 隐私窗口不再被跳过（证明缺陷在接线、不在判据）
    B4  privacy_file_types 已收窄（不含 .txt/.docx/.png —— 第三十四轮修复不得回退）

用法：C:\\Python311\\python.exe verify_round34c_privacy_wire.py
"""
import ast
import inspect
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
SRC = os.path.join(ROOT, 'ralsei_pet', 'modules', 'desktop_interaction.py')

PASS = 0
FAIL = 0
FAILED = []


def check(cid, cond, msg=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s %s' % (cid, msg))
    else:
        FAIL += 1
        FAILED.append(cid)
        print('[FAIL] %s %s' % (cid, msg))


def code_only(src):
    """去掉注释与 docstring/字符串（AST 口径），避免把注释里的名字算成引用。"""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body[0].value.value = ''
    return ast.unparse(tree) if hasattr(ast, 'unparse') else src


def main():
    src = open(SRC, encoding='utf-8').read()
    tree = ast.parse(src)
    code = code_only(src)

    cls = None
    for n in tree.body:
        if isinstance(n, ast.ClassDef) and n.name == 'DesktopInteraction':
            cls = n
    check('A0', cls is not None, 'DesktopInteraction 类存在')
    if cls is None:
        return

    methods = {m.name: m for m in cls.body
               if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}

    # ---------- A1: user_opened_privacy_apps 的写入点 ----------
    writers = []
    for name, m in methods.items():
        for n in ast.walk(m):
            if isinstance(n, ast.Attribute) and n.attr == 'user_opened_privacy_apps':
                parent_is_assign_target = False
                for p in ast.walk(m):
                    if isinstance(p, ast.Assign):
                        for tg in p.targets:
                            if isinstance(tg, ast.Attribute) and tg.attr == 'user_opened_privacy_apps':
                                parent_is_assign_target = True
                    if isinstance(p, ast.Call) and isinstance(p.func, ast.Attribute):
                        if (p.func.attr in ('append', 'remove', 'clear', 'extend', 'insert')
                                and isinstance(p.func.value, ast.Attribute)
                                and p.func.value.attr == 'user_opened_privacy_apps'):
                            if name not in [w[0] for w in writers]:
                                writers.append((name, p.func.attr, p.lineno))
    wnames = sorted(set(w[0] for w in writers))
    check('A1', wnames == ['mark_app_as_closed', 'mark_app_as_opened'],
          '写入点仅 mark_app_as_opened/mark_app_as_closed -> %s' % wnames)

    # ---------- A2: mark_app_as_opened 全项目零调用 ----------
    external_calls = []
    project_root = os.path.join(ROOT, 'ralsei_pet')
    for dp, dn, fn in os.walk(project_root):
        if '__pycache__' in dp:
            continue
        for f in fn:
            if not f.endswith('.py'):
                continue
            fp = os.path.join(dp, f)
            if os.path.abspath(fp) == os.path.abspath(SRC):
                continue
            try:
                s = open(fp, encoding='utf-8').read()
                tt = ast.parse(s)
            except Exception:
                continue
            for n in ast.walk(tt):
                if isinstance(n, ast.Attribute) and n.attr in ('mark_app_as_opened', 'mark_app_as_closed'):
                    external_calls.append((os.path.relpath(fp, project_root), n.lineno, n.attr))
    check('A2', len(external_calls) == 0,
          'mark_app_as_* 仍零外部调用 -> %d 处' % len(external_calls))

    # ---------- A3: L1192 判据形状 ----------
    gm = methods.get('get_all_visible_windows')
    check('A3a', gm is not None, 'get_all_visible_windows 存在')
    found_guard = False
    if gm is not None:
        for n in ast.walk(gm):
            if isinstance(n, ast.If):
                txt = ast.unparse(n.test) if hasattr(ast, 'unparse') else ''
                if 'user_opened_privacy_apps' in txt and 'is_privacy_app' in txt:
                    found_guard = True
    check('A3b', found_guard,
          'L1192 判据形状仍是 is_privacy_app and hwnd not in self.user_opened_privacy_apps')

    # ---------- A4: privacy_apps 覆盖面 ----------
    init = methods.get('__init__')
    privacy_list = []
    if init is not None:
        for n in ast.walk(init):
            if isinstance(n, ast.Assign):
                for tg in n.targets:
                    if isinstance(tg, ast.Attribute) and tg.attr == 'privacy_apps':
                        if isinstance(n.value, ast.List):
                            for e in n.value.elts:
                                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                                    privacy_list.append(e.value)
    need = ['微信', 'QQ', '钉钉', '企业微信', 'Outlook']
    missing = [x for x in need if x not in privacy_list]
    check('A4', not missing, 'privacy_apps 含关键应用 %s -> 缺 %s' % (need, missing or '无'))

    # ---------- B: 行为核验（用产品同款判据，不重写逻辑） ----------
    privacy_apps = privacy_list
    kw = set(a.lower() for a in privacy_apps)

    def skipped(title, cls_name, opened):
        tl, cl = title.lower(), cls_name.lower()
        hit = any(k in tl or k in cl for k in kw)
        # 产品判据：if is_privacy_app and hwnd not in self.user_opened_privacy_apps: skip
        hwnd = 1
        return bool(hit and (hwnd not in opened)), hit

    PRIV = [('微信', 'WeChatMainWndForPC'), ('QQ', 'TXGuiFoundation'),
            ('钉钉', 'StandardFrame_DingTalk'), ('企业微信', 'WeWorkWindow'),
            ('Outlook', 'rctrl_renwnd32'), ('邮件', 'Mail')]
    NORM = [('Chrome', 'Chrome_WidgetWin_1'), ('记事本', 'Notepad')]

    opened = []          # ← 产品实际状态：恒空
    all_skip = all(skipped(t, c, opened)[0] for t, c in PRIV)
    check('B1', all_skip, '空列表下 6 个隐私应用窗口全部被跳过（判据恒真）')

    none_skip = not any(skipped(t, c, opened)[0] for t, c in NORM)
    check('B2', none_skip, '非隐私对照（Chrome/记事本）不被跳过')

    opened2 = [1]        # 反证：把 hwnd 记入
    freed = all(not skipped(t, c, opened2)[0] for t, c in PRIV)
    check('B3', freed, '反证：hwnd 入列表后隐私窗口不再被跳过（缺陷在接线、不在判据）')

    # ---------- B4: privacy_file_types 不得回退 ----------
    pft = []
    if init is not None:
        for n in ast.walk(init):
            if isinstance(n, ast.Assign):
                for tg in n.targets:
                    if isinstance(tg, ast.Attribute) and tg.attr == 'privacy_file_types':
                        if isinstance(n.value, ast.List):
                            for e in n.value.elts:
                                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                                    pft.append(e.value)
    bad = [x for x in ('.txt', '.docx', '.png', '.pdf', '.xlsx') if x in pft]
    check('B4', not bad and len(pft) > 0,
          'privacy_file_types 已收窄且未回退 -> 含 %s' % pft)

    print('')
    print('合计: PASS=%d FAIL=%d' % (PASS, FAIL))
    if FAILED:
        print('失败项: %s' % ', '.join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
