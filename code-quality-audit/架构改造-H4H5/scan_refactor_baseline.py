# -*- coding: utf-8 -*-
"""H4/H5 架构改造 —— 基线量化（只读，不修改任何被审查文件）

产出：
  1. main.py RalseiPet 类的 self.<attr> 属性全集与高频属性
  2. RalseiPet 方法清单（名 / 起止行 / 行数），按行数降序 —— 定位上帝类的真实"重量块"
  3. sprite_loader.animation_mapping 的键数、文件名总数
  4. 校验映射中引用的每个帧文件是否真实存在（H5 的核心风险面）
"""
import ast
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
SPRITE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'sprite_loader.py')
ASSETS = os.path.join(ROOT, 'deltarune_ralsei')

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_evidence')
os.makedirs(out_dir, exist_ok=True)
report = []


def emit(s=''):
    report.append(s)
    print(s)


# ---------- 1/2. main.py ----------
src = open(MAIN, encoding='utf-8').read()
tree = ast.parse(src)
lines = src.splitlines()

pet = None
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'RalseiPet':
        pet = node
        break
assert pet is not None, 'RalseiPet not found'

methods = []
for node in pet.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        start = node.lineno
        end = max(getattr(n, 'lineno', start) for n in ast.walk(node))
        methods.append((node.name, start, end, end - start + 1))

emit('=== RalseiPet 规模 ===')
emit('类起始行: %d' % pet.lineno)
emit('直接方法数: %d' % len(methods))
emit('main.py 总行数: %d' % len(lines))
total_method_lines = sum(m[3] for m in methods)
emit('方法体总行数: %d (占全文 %.1f%%)' % (total_method_lines, 100.0 * total_method_lines / len(lines)))

emit()
emit('=== 最重的 25 个方法（行数降序）===')
emit('%-42s %7s %7s %7s' % ('method', 'start', 'end', 'lines'))
for name, s, e, n in sorted(methods, key=lambda x: -x[3])[:25]:
    emit('%-42s %7d %7d %7d' % (name, s, e, n))

# 私有方法群聚（_xxx），通常已是"半模块化"的信号
underscore = [m for m in methods if m[0].startswith('_')]
emit()
emit('=== 下划线开头方法 %d 个（半模块化信号）===' % len(underscore))

# self.<attr> 读取与写入
reads, writes = {}, {}
for node in ast.walk(pet):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'self':
        if isinstance(node.ctx, ast.Store):
            writes[node.attr] = writes.get(node.attr, 0) + 1
        else:
            reads[node.attr] = reads.get(node.attr, 0) + 1

all_attrs = sorted(set(reads) | set(writes), key=lambda a: -(reads.get(a, 0) + writes.get(a, 0)))
emit()
emit('=== self 属性云 ===')
emit('不同属性名总数: %d' % len(all_attrs))
emit('被写入(Store)过的属性数: %d' % len(writes))
emit('只在方法内读、从未写 self 的属性数(可能来自其他对象或误用): %d'
     % len([a for a in reads if a not in writes]))
emit()
emit('%-34s %7s %7s' % ('attr', 'read', 'write'))
for a in all_attrs[:60]:
    emit('%-34s %7d %7d' % (a, reads.get(a, 0), writes.get(a, 0)))

# 跨方法共享可变状态：被 3 个以上方法写入的属性 = 拆分时的"真耦合点"
hot = [a for a in all_attrs if writes.get(a, 0) >= 3]
emit()
emit('被 >=3 处写入的属性（跨方法共享可变状态，拆分真耦合点）: %d 个' % len(hot))
emit(', '.join(hot[:80]))

with open(os.path.join(out_dir, 'main_class_profile.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))

# ---------- 3/4. sprite_loader mapping ----------
s_src = open(SPRITE, encoding='utf-8').read()
s_tree = ast.parse(s_src)
mapping = None
for node in ast.walk(s_tree):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Attribute) and t.attr == 'animation_mapping' and isinstance(node.value, ast.Dict):
                mapping = node.value
if mapping is None:
    print('!! animation_mapping 未能静态解析')
    sys.exit(0)

keys = []
files = []
for k, v in zip(mapping.keys, mapping.values):
    if isinstance(k, ast.Str):
        keys.append(k.s)
    try:
        files.extend(ast.literal_eval(v))
    except Exception:
        pass

disk = set()
if os.path.isdir(ASSETS):
    for fn in os.listdir(ASSETS):
        if fn.lower().endswith('.png'):
            disk.add(fn)

missing = sorted({f for f in files if f not in disk})
unused = sorted(disk - set(files))

r2 = []
r2.append('=== sprite_loader.animation_mapping 基线 ===')
r2.append('mapping 键（动画组）数: %d' % len(keys))
r2.append('引用的帧文件条目数（含重复引用）: %d' % len(files))
r2.append('去重后引用的帧文件数: %d' % len(set(files)))
r2.append('素材目录 PNG 实际数量: %d' % len(disk))
r2.append('')
r2.append('!! mapping 引用但磁盘不存在的文件: %d 个（会渲染成灰块占位帧）' % len(missing))
for m in missing:
    r2.append('   MISSING  ' + m)
r2.append('')
r2.append('?? 磁盘存在但未被 mapping 引用: %d 个' % len(unused))
for u in unused[:60]:
    r2.append('   UNUSED   ' + u)
if len(unused) > 60:
    r2.append('   ... 其余 %d 个见 _evidence/sprite_mapping_gap.json' % (len(unused) - 60))

with open(os.path.join(out_dir, 'sprite_mapping_gap.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(r2))
with open(os.path.join(out_dir, 'sprite_mapping_gap.json'), 'w', encoding='utf-8') as f:
    json.dump({'keys': keys, 'missing': missing, 'unused': unused,
               'referenced_unique': sorted(set(files)), 'disk_count': len(disk)},
              f, ensure_ascii=False, indent=1)

print('\n'.join(r2))
print('\n[ok] 产物写入 %s' % out_dir)
