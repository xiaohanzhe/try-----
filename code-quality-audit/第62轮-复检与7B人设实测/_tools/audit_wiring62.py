#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 普查 C：接线普查 —— 零引用模块 / 异常吞没 / 静默降级。

要回答的是用户口径里最贵的那个坑："**函数写对了 ≠ 产品用上了**"。

★ 分层判据（本工具 v2 修正了 v1 的范围缺陷）：
  引用分两级统计 ——
    **产品层**：`ralsei_pet/**` 里对它的 import（决定"用户用不用得上"）
    **审查层**：`code-quality-audit/**` 里对它的 import（说明它"被锁住了"）
  v1 只扫 `ralsei_pet/`，于是 `companion_roster.py` / `scene_walk.py` 被误报成
  "连字符串都没人提"；实际上它们被第46/45轮的锁引用着 —— 差别很大：
  **只有审查层引用 = "有锁但没接线"，是最危险的一类**（锁让人以为功能上了线）。

段落：
  C-I   模块级孤儿（分产品层/审查层）
  C-II  孤儿模块的公共函数是否被别处按名提到
  C-III 异常吞没：`except: pass`（真正的"什么都不做"）
  C-IV  静默降级：main.py 里的 hasattr 守卫

只用 AST，不 import 任何项目模块。
用法：C:\\Python311\\python.exe audit_wiring60.py
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
PRODUCT = os.path.join(REPO, 'ralsei_pet')
OUT = os.path.join(ROUND, '_evidence')
SKIP_DIRS = {'__pycache__', '.git', 'assets', 'config', 'logs', 'tests',
             'diag_frames', 'diag_frames2', 'diag_frames3', '_evidence',
             '_out', '_tools'}

SCRATCH_PREFIX = ('test_', 'diag', 'monitor_', 'probe_', 'tmp_')
SCRATCH_EXACT = {'main_simple', 'runtime_exercise', 'patch_memory_defense',
                 'patch_single_instance', 'scan_patterns'}

# 已知的"零接线"模块 —— 每条**必须**写理由与授权状态，否则白名单就成了藏污纳垢处。
KNOWN_UNWIRED = {
    'pet_interaction': {
        'tier': 'product',
        'reason': '第11轮登记：365 行手势/情绪交互模块，全模块零接线',
        'status': '待用户裁定（删除 vs 接线）',
    },
    'companion_roster': {
        'tier': 'product',
        'reason': '第46轮 P0~P2 骨架三模块之一；产品层 import = 0（只有第46轮的锁在引用）',
        'status': 'P3 接线已获授权（第二批），尚未施工',
    },
    'scene_walk': {
        'tier': 'product',
        'reason': '第45/47轮房间内行走层；产品层 import = 0（只有第45/47轮的锁在引用）',
        'status': 'P1 待办：①意图接 AI + ④逐门执行 未施工',
    },
}


def check(cond, msg):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', msg))
    return bool(cond)


def walk_py(root):
    out = []
    if not os.path.isdir(root):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith('.py'):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def is_scratch(stem):
    if stem in SCRATCH_EXACT:
        return True
    return any(stem.startswith(p) for p in SCRATCH_PREFIX)


def refs_from(files, trees_idx):
    """收集这批文件里的引用。返回 (import短名 -> [文件], 字符串字面量 -> [文件])。

    ★ 必须同时收字符串字面量：本项目多处用**路径**引用模块而不是 import，
      例如 `spec_from_file_location('scene_walk_under_test', MOD)` / `MOD = os.path.join(..., 'scene_walk.py')`。
      只看 import 会把"有锁但没接线"误判成"连锁都没有"——两者性质差很远。
    """
    imp, lit = {}, {}
    for p in files:
        info = trees_idx.get(p)
        if not info:
            continue
        stem, tree, src = info
        rel = os.path.relpath(p, REPO).replace('\\', '/')
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ''
                for a in node.names:
                    imp.setdefault(a.name, []).append(rel)
                if mod:
                    imp.setdefault(mod.split('.')[-1], []).append(rel)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    imp.setdefault(a.name.split('.')[-1], []).append(rel)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                s = node.value.strip()
                if s.endswith('.py'):
                    s = s[:-3]
                if s.isidentifier():
                    lit.setdefault(s, []).append(rel)
    return imp, lit


def noop_only(handler):
    """handler 的 body 是不是"什么都不做"（只有 pass / 空字符串字面量 / ...）。"""
    for b in handler.body:
        if isinstance(b, ast.Pass):
            continue
        if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant):
            continue
        return False
    return True


def main():
    prod_files = walk_py(PRODUCT)
    audit_files = walk_py(AUDIT)
    trees_idx = {}
    for p in prod_files + audit_files:
        stem = os.path.splitext(os.path.basename(p))[0]
        try:
            src = io.open(p, encoding='utf-8').read()
            trees_idx[p] = (stem, ast.parse(src), src)
        except Exception as e:
            print('      ! 解析失败 %s :: %s' % (p, e))

    prod_refs, prod_lits = refs_from(prod_files, trees_idx)
    audit_refs, audit_lits = refs_from(audit_files, trees_idx)

    print('=' * 72)
    print('普查 C —— 接线 / 孤儿 / 异常吞没 / 静默降级')
    print('=' * 72)
    print('产品层 %d 个 .py；审查层 %d 个 .py' % (len(prod_files), len(audit_files)))
    ok = True
    ok &= check(len(prod_files) >= 40 and len(audit_files) >= 60,
                'C0 两侧都扫到足够文件（产品 %d / 审查 %d）' % (len(prod_files), len(audit_files)))

    # ---------------- C-I 模块级 ----------------
    print()
    print('--- C-I 模块级：谁引用它 ---')
    unwired, scratch, wired = [], [], []
    for p in prod_files:
        stem = os.path.splitext(os.path.basename(p))[0]
        if stem == '__init__':
            continue
        rel = os.path.relpath(p, REPO).replace('\\', '/')
        pr = [u for u in prod_refs.get(stem, []) if u != rel]
        ar = [u for u in audit_refs.get(stem, []) if u != rel]
        pl = [u for u in prod_lits.get(stem, []) if u != rel]
        al = [u for u in audit_lits.get(stem, []) if u != rel]
        rec = {'module': stem, 'path': rel, 'product_refs': pr, 'audit_refs': ar,
               'product_lits': pl, 'audit_lits': al}
        # ★★ 只有 **import** 才算接线。
        #   字符串字面量**不算** —— 反例（本工具 v3 踩过）：`pet_interaction` 是
        #   事件类型名（`event_type == 'pet_interaction'`），拿字符串当接线证据
        #   会把它误判成"已接上"。同理 `'scene_walk.py'` 这种路径串只能说明
        #   "某个锁在引用它"，必须单列成"弱提及"，不参与接线判定。
        if pr:
            wired.append(rec)
        elif is_scratch(stem):
            scratch.append(rec)
        else:
            unwired.append(rec)

    print('      产品层有引用的：%d 个' % len(wired))
    print('      开发残留（test_/diag/monitor_ 等，不判红）：%d 个' % len(scratch))
    print('        %s' % ', '.join(r['module'] for r in scratch))
    print('      ★ 产品层 import = 0 的模块（真·孤儿）：%d 个' % len(unwired))
    for r in unwired:
        lock = len(r['audit_refs']) + len(r['audit_lits'])
        print('        %s' % r['path'])
        print('            ├─ 产品层 import 0 处' +
              ('；★ 产品层有 %d 处**字符串提及**（多为事件名/命名撞车，不构成接线）：%s'
               % (len(r['product_lits']), r['product_lits'][:2]) if r['product_lits'] else ''))
        if lock:
            print('            └─ **审查层引用 %d 处**（有锁但没接线！）：%s'
                  % (lock, (r['audit_refs'] + r['audit_lits'])[:3]))
        else:
            print('            └─ 审查层 0 处 —— 连锁都没有')

    names = sorted(r['module'] for r in unwired)
    registered = [m for m in names if m in KNOWN_UNWIRED]
    unregistered = [m for m in names if m not in KNOWN_UNWIRED]
    ok &= check('pet_interaction' in names,
                'C1 正控制：已知孤儿 pet_interaction.py 必须被抓到（抓到=%s）' % registered)
    ok &= check(not unregistered,
                'C2 产品层孤儿全部已登记（未登记 %d 个：%s）' % (len(unregistered), unregistered))
    # 白名单不许变质：每条必须写理由与状态
    bad_entries = [k for k, v in KNOWN_UNWIRED.items() if not v.get('reason') or not v.get('status')]
    ok &= check(not bad_entries, 'C2b 白名单每条都写了理由与授权状态（缺 %s）' % bad_entries)
    # 白名单不许"挂着不动"：清单里的模块必须真的还是零接线
    stale = [k for k in KNOWN_UNWIRED if k not in names]
    ok &= check(not stale,
                'C2c 白名单不含"其实已经接上了"的过期条目（过期 %s）—— 防白名单变成永久免死金牌' % stale)
    # 有锁没接线的必须显式列出
    locked_only = [r['module'] for r in unwired if (r['audit_refs'] or r['audit_lits'])]
    print('      ★★ 只被审查层引用（有锁、没接线）共 %d 个：%s' % (len(locked_only), locked_only))

    # ---------------- C-II 孤儿模块的公共函数 ----------------
    print()
    print('--- C-II 函数级：孤儿模块的公共定义在**产品层**是否被按名提到 ---')
    print('      ⚠ 这是**弱判据**：只证明"这个名字在**别的**产品文件里出现过"，不证明"就是它"。')
    print('        名字撞车（另有同名定义/同名局部变量）会给出假阳性 ⇒ 只当线索，不当结论。')
    # ★ 必须排除该孤儿模块**自己的文件**：把自身内部的引用算进来会让判据变成恒真。
    file_idents = {}
    for p in prod_files:
        info = trees_idx.get(p)
        if not info:
            continue
        rel = os.path.relpath(p, REPO).replace('\\', '/')
        ids = set()
        for node in ast.walk(info[1]):
            if isinstance(node, ast.Name):
                ids.add(node.id)
            elif isinstance(node, ast.Attribute):
                ids.add(node.attr)
        file_idents[rel] = ids
    for r in unwired:
        p = os.path.join(REPO, r['path'].replace('/', os.sep))
        info = trees_idx.get(p)
        if not info:
            print('      ! 定位失败（路径分隔符）：%s' % p)
            continue
        tree = info[1]
        pubs = [n.name for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and not n.name.startswith('_')]
        elsewhere = set()
        for rel, ids in file_idents.items():
            if rel != r['path']:
                elsewhere |= ids
        hit = [n for n in pubs if n in elsewhere]
        print('      %-46s 公共定义 %2d 个；名字在**别的产品文件**里出现过 %d 个 %s'
              % (r['path'], len(pubs), len(hit), ('→ ' + str(hit[:6])) if hit else ''))

    # ---------------- C-III 异常吞没 ----------------
    print()
    print('--- C-III 异常吞没：except 分支"什么都不做" ---')
    swallow = []
    for p, (stem, tree, src) in trees_idx.items():
        rel = os.path.relpath(p, REPO).replace('\\', '/')
        lines = src.split('\n')
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for h in node.handlers:
                if noop_only(h):
                    swallow.append({'path': rel, 'line': h.lineno, 'bare': h.type is None,
                                    'code': lines[h.lineno - 1].strip()[:120]})
    bare = [s for s in swallow if s['bare']]
    prod_swallow = [s for s in swallow if s['path'].startswith('ralsei_pet/')]
    print('      全仓 %d 处；其中产品层 %d 处；裸 `except:` %d 处'
          % (len(swallow), len(prod_swallow), len(bare)))
    for s in prod_swallow[:12]:
        print('        产品层 %s:%d  %s' % (s['path'], s['line'], s['code']))
    for s in bare[:8]:
        print('        裸 except %s:%d  %s' % (s['path'], s['line'], s['code']))
    ok &= check(not bare, 'C3 全仓没有裸 `except:`（实际 %d 处）—— 它会连 KeyboardInterrupt 一起吞' % len(bare))
    ok &= check(len(prod_swallow) < 60,
                'C4 产品层静默吞异常处数在可解释范围（实际 %d 处，<60）' % len(prod_swallow))

    # ---------------- C-IV 静默降级 ----------------
    print()
    print('--- C-IV 静默降级：产品层 hasattr 守卫（功能可能悄悄不生效）---')
    guards = {}
    for p, (stem, tree, src) in trees_idx.items():
        if not p.startswith(PRODUCT):
            continue
        rel = os.path.relpath(p, REPO).replace('\\', '/')
        lines = src.split('\n')
        g = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == 'hasattr':
                g.append({'line': node.lineno,
                          'code': lines[node.lineno - 1].strip()[:130]})
        if g:
            guards[rel] = g
    tot = sum(len(v) for v in guards.values())
    print('      产品层 hasattr 共 %d 处，分布在 %d 个文件；前 5：' % (tot, len(guards)))
    for rel in sorted(guards, key=lambda k: -len(guards[k]))[:5]:
        print('        %-52s %d 处' % (rel, len(guards[rel])))
    ok &= check(tot > 0, 'C5 至少有一处 hasattr（否则本段是空扫描）')

    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, 'wiring62.json')
    with io.open(dst, 'w', encoding='utf-8') as f:
        json.dump({'n_product': len(prod_files), 'n_audit': len(audit_files),
                   'unwired': unwired, 'locked_only': locked_only,
                   'scratch': [r['module'] for r in scratch],
                   'swallow_pass': swallow, 'product_swallow': prod_swallow,
                   'hasattr': guards, 'known_unwired': KNOWN_UNWIRED}, f,
                  ensure_ascii=False, indent=1)
    print()
    print('证据：%s' % dst.replace('\\', '/'))
    print('=' * 72)
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
