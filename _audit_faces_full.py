# -*- coding: utf-8 -*-
"""全量表情键审计：
1. 解析 dialogue_ui._FACE_MAP（AST）
2. 解析 emotion_system.get_face_for_emotion 内的 face_map（AST，取其所有值）
3. 扫描所有 .py 中 add_dialogue(...) / set_face(...) 的字符串字面量参数
4. 用 _resolve_face_name 的复刻逻辑解析，核对 ralsei_face/*.png 是否存在
"""
import ast, os, json

ROOT = os.path.dirname(os.path.abspath(__file__))
PET = os.path.join(ROOT, 'ralsei_pet')
FACE_DIR = os.path.join(ROOT, 'ralsei_face')

available = set()
for fn in os.listdir(FACE_DIR):
    if fn.lower().endswith('.png'):
        available.add(os.path.splitext(fn)[0])

def read(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()

# ---- 1. _FACE_MAP ----
du = os.path.join(PET, 'modules', 'dialogue_ui.py')
tree = ast.parse(read(du))
FACE_MAP = {}
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == '_FACE_MAP' and isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                        FACE_MAP[k.value] = v.value

# ---- 2. emotion_system face_map 的值 ----
es = os.path.join(PET, 'modules', 'emotion_system.py')
tree2 = ast.parse(read(es))
EMO_VALUES = []
for node in ast.walk(tree2):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == 'face_map' and isinstance(node.value, ast.Dict):
                for v in node.value.values:
                    if isinstance(v, ast.Dict):
                        for vv in v.values:
                            if isinstance(vv, ast.Constant) and isinstance(vv.value, str):
                                EMO_VALUES.append(vv.value)

def resolve(face_type):
    if not face_type:
        return 'face_normal'
    if isinstance(face_type, str) and face_type.endswith('.png'):
        return os.path.splitext(os.path.basename(face_type))[0]
    if isinstance(face_type, str) and face_type.startswith('face_'):
        return face_type
    if face_type in FACE_MAP:
        return FACE_MAP[face_type]
    return 'face_' + face_type

def check(name):
    return name in available

# ---- 3. 扫描所有调用 ----
CALL_FUNCS = {'add_dialogue': 2, 'set_face': 0, 'show_dialogue': 1}  # 函数名 -> face 参数位置(0-based)
findings = []   # (file, lineno, func, raw, resolved, ok)
for dirpath, _, filenames in os.walk(PET):
    if '__pycache__' in dirpath:
        continue
    for fn in filenames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            t = ast.parse(read(fp))
        except Exception:
            continue
        for node in ast.walk(t):
            if not isinstance(node, ast.Call):
                continue
            name = None
            if isinstance(node.func, ast.Attribute):
                name = node.func.attr
            elif isinstance(node.func, ast.Name):
                name = node.func.id
            if name not in CALL_FUNCS:
                continue
            pos = CALL_FUNCS[name]
            face = None
            if len(node.args) > pos and isinstance(node.args[pos], ast.Constant) and isinstance(node.args[pos].value, str):
                face = node.args[pos].value
            else:
                for kw in node.keywords:
                    if kw.arg == 'face_type' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        face = kw.value.value
            if face is None:
                continue
            r = resolve(face)
            findings.append((os.path.relpath(fp, ROOT), node.lineno, name, face, r, check(r)))

# ---- 4. _FACE_MAP 值 ----
map_bad = [(k, v) for k, v in FACE_MAP.items() if not check(v)]
emo_bad = sorted({v for v in EMO_VALUES if not check(resolve(v))})
call_bad = [f for f in findings if not f[5]]
call_bad_unique = {}
for f in call_bad:
    call_bad_unique.setdefault(f[3], []).append((f[0], f[1]))

out = []
out.append("== 表情素材总数: %d ==" % len(available))
out.append("== _FACE_MAP 条目: %d, 其中指向缺失素材: %d ==" % (len(FACE_MAP), len(map_bad)))
for k, v in map_bad:
    out.append("   [MAP坏] %r -> %r (缺)" % (k, v))
out.append("== emotion face_map 去重值: %d, 解析后缺失: %d ==" % (len(set(EMO_VALUES)), len(emo_bad)))
for v in emo_bad:
    out.append("   [EMO坏] %r -> %r (缺)" % (v, resolve(v)))
out.append("== 调用点字面量: %d, 解析后缺失: %d ==" % (len(findings), len(call_bad)))
out.append("---- 缺失明细（按原始 face 参数聚合）----")
for raw, locs in sorted(call_bad_unique.items()):
    out.append("   raw=%r -> resolved=%r  出现 %d 次:" % (raw, resolve(raw), len(locs)))
    for fp, ln in locs[:8]:
        out.append("        %s:%d" % (fp, ln))
out.append("---- 全部调用点（前 80，供核对）----")
for f in findings[:80]:
    flag = 'OK ' if f[5] else 'BAD'
    out.append("   [%s] %s:%d %s(%r) -> %s" % (flag, f[0], f[1], f[2], f[3], f[4]))

with open(os.path.join(ROOT, '_audit_faces_full_out.txt'), 'w', encoding='utf-8') as f:
    f.write("\n".join(out))
print("done, findings=%d, bad=%d" % (len(findings), len(call_bad)))
