# -*- coding: utf-8 -*-
"""资源引用审计：对话表情键 / 动画名 / 事件名 是否有对应实现或素材"""
import ast, os, sys, re, json

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
PROJ = os.path.dirname(ROOT)
FACE_DIR = os.path.join(PROJ, 'ralsei_face')
SPR_DIR = os.path.join(PROJ, 'deltarune_ralsei')

faces = {f[:-4] for f in os.listdir(FACE_DIR) if f.endswith('.png')}
sprites = sorted(os.listdir(SPR_DIR))

files = []
for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT)):
    if '__pycache__' in dirpath: continue
    for fn in filenames:
        if fn.endswith('.py') and not fn.startswith(('test_','diag')):
            files.append(os.path.join(dirpath, fn))

# ---------- 1) 表情键审计 ----------
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT,'modules'))
os.chdir(ROOT)
import importlib
dialogue_ui_src = open(os.path.join(ROOT,'modules','dialogue_ui.py'), encoding='utf-8').read()
face_map = {}
m = re.search(r'_FACE_MAP\s*=\s*\{(.*?)\n\s*\}', dialogue_ui_src, re.S)
if m:
    for k, v in re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group(1)):
        face_map[k] = v
print("=== _FACE_MAP 条目数:", len(face_map))
bad_map = {k: v for k, v in face_map.items() if v not in faces}
print("=== _FACE_MAP 指向不存在素材的条目:", bad_map if bad_map else "无")

# 收集调用点里的表情键
face_args = []
anim_args = []
event_args = []
for path in files:
    src = open(path, encoding='utf-8', errors='replace').read()
    try: tree = ast.parse(src)
    except SyntaxError: continue
    rel = os.path.relpath(path, ROOT)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fname = ''
            try: fname = ast.unparse(node.func)
            except Exception: pass
            short = fname.split('.')[-1]
            if short in ('add_dialogue','show_dialogue','set_face','_add_dialogue'):
                for i, a in enumerate(node.args):
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        # add_dialogue(speaker, text, face) -> 第3个; show_dialogue(text, face) -> 第2个
                        if short in ('add_dialogue','_add_dialogue') and i == 2:
                            face_args.append((rel, node.lineno, a.value))
                        if short == 'show_dialogue' and i == 1:
                            face_args.append((rel, node.lineno, a.value))
                        if short == 'set_face' and i == 0:
                            face_args.append((rel, node.lineno, a.value))
                for kw in node.keywords:
                    if kw.arg == 'face' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        face_args.append((rel, node.lineno, kw.value.value))
            if short == 'change_animation' or short == 'play_animation_once':
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    anim_args.append((rel, node.lineno, node.args[0].value))
            if short == 'react_to_event' or short == 'trigger_event':
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    event_args.append((rel, node.lineno, node.args[0].value, short))

print()
print("=== 表情键调用点:", len(face_args), "个")
bad_faces = {}
for rel, ln, key in face_args:
    resolved = face_map.get(key, 'face_' + key)
    if resolved not in faces:
        bad_faces.setdefault(key, []).append(f"{rel}:{ln}")
print("=== 解析后素材不存在的表情键:", json.dumps(bad_faces, ensure_ascii=False, indent=1) if bad_faces else "无 ✅")
unknown_keys = sorted({k for _,_,k in face_args if k not in face_map})
print("=== 不在 _FACE_MAP 中的表情键:", unknown_keys if unknown_keys else "无")

# ---------- 2) 动画名审计 ----------
# 从 sprite_loader 里解析 animation_mapping 的键
sl_src = open(os.path.join(ROOT,'modules','sprite_loader.py'), encoding='utf-8').read()
anim_keys = set(re.findall(r"['\"]([a-z0-9_]+)['\"]\s*:", sl_src))
print()
print("=== 动画名调用点:", len(anim_args), "个")
bad_anims = {}
for rel, ln, a in anim_args:
    if a in anim_keys: continue
    # 也检查是否有直接的素材前缀存在
    if any(s.startswith('spr_ralsei_' + a + '_') or s.startswith('spr_' + a + '_') for s in sprites):
        continue
    bad_anims.setdefault(a, []).append(f"{rel}:{ln}")
print("=== 可能不存在的动画名（需人工确认）:", json.dumps(bad_anims, ensure_ascii=False, indent=1) if bad_anims else "无 ✅")

# ---------- 3) 事件名审计 ----------
emo_src = open(os.path.join(ROOT,'modules','emotion_system.py'), encoding='utf-8').read()
handled = set(re.findall(r"event_type\s*==\s*['\"]([a-z0-9_]+)['\"]", emo_src))
handled |= set(re.findall(r"event\s*==\s*['\"]([a-z0-9_]+)['\"]", emo_src))
petai_src = open(os.path.join(ROOT,'modules','pet_ai.py'), encoding='utf-8').read()
handled |= set(re.findall(r"event_type\s*==\s*['\"]([a-z0-9_]+)['\"]", petai_src))
print()
triggered = {}
for rel, ln, name, fn in event_args:
    triggered.setdefault(name, []).append((rel, ln, fn))
unhandled = {k: [f"{a}:{b}" for a,b,c in v] for k, v in triggered.items() if k not in handled}
print("=== 触发的事件总数:", len(triggered), "；emotion/pet_ai 已处理分支:", len(handled))
print("=== 触发但无处理分支的事件:")
for k, v in sorted(unhandled.items()):
    print(f"   {k}  <- {', '.join(v[:4])}")
