# -*- coding: utf-8 -*-
"""H5 S2 抽取器：把 sprite_loader.py 里的硬编码动画表导出成 assets/animations.json。

唯一的真值来源仍然是代码里的 `_builtin_animation_mapping`（原表原样保留，作为兜底），
本脚本只做"代码 → JSON"的单向导出，绝不反向生成代码。

要点：
  - 用 AST 取字面量（`ast.literal_eval`），不执行源码、不 import 项目模块；
  - 字典块内的中文注释按"紧随其后的那个键"归集，写进 `meta.comments` 保留；
  - **不写生成时间戳**（否则每次导出都产生 git diff，比对就失去意义）；
  - 输出风格：每个动画组的 frames 保持单行，方便 diff 与人工核对。

用法：
  python extract_animations_json.py            # 导出到 ralsei_pet/assets/animations.json
  python extract_animations_json.py --stdout   # 只打印，不落盘
  python extract_animations_json.py --check    # 只校验"现有 JSON 与代码是否一致"（退出码 0/1）
"""
import argparse
import ast
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SOURCE = os.path.join(ROOT, 'ralsei_pet', 'modules', 'sprite_loader.py')
TARGET = os.path.join(ROOT, 'ralsei_pet', 'assets', 'animations.json')

VAR_NAME = '_builtin_animation_mapping'
KEY_LINE = re.compile(r'^\s*"([^"]+)"\s*:')


def extract_literal(source_path=SOURCE):
    """返回 (mapping: dict, node) —— mapping 是 `_builtin_animation_mapping` 的字面量。"""
    with io.open(source_path, encoding='utf-8') as fh:
        src = fh.read()
    tree = ast.parse(src)
    node = None
    for item in ast.walk(tree):
        if isinstance(item, ast.Assign):
            for tgt in item.targets:
                if isinstance(tgt, ast.Name) and tgt.id == VAR_NAME:
                    node = item.value
    if node is None or not isinstance(node, ast.Dict):
        raise SystemExit('%s 里找不到 %s 的字典字面量' % (source_path, VAR_NAME))
    mapping = ast.literal_eval(node)
    if not isinstance(mapping, dict) or not mapping:
        raise SystemExit('%s 不是非空字典' % VAR_NAME)
    return mapping, node, src.splitlines()


def collect_comments(lines, node):
    """把字典块内的注释行归集到"紧随其后的那个键"上。"""
    out, pending = {}, []
    for lineno in range(node.lineno, node.end_lineno + 1):
        line = lines[lineno - 1]
        stripped = line.strip()
        if stripped.startswith('#'):
            pending.append(stripped.lstrip('#').strip())
            continue
        m = KEY_LINE.match(line)
        if m and pending:
            out.setdefault(m.group(1), []).extend(pending)
            pending = []
    if pending:
        out.setdefault('__tail__', []).extend(pending)
    return out


def resolve_groups(doc):
    """把 {名: {frames, alias_of?, ...}} 归一化成 {名: [帧文件名]}，展开 alias_of。

    规则与 sprite_loader._validate_animation_config 一致：
      - 有 alias_of 的组，帧取自目标组（允许 alias 套 alias，带环检测）；
      - 其余组取自己的 frames（缺失视为空列表）。
    S2/S3 的"深度等价"断言都以此为准 —— 比的是**解析后**的表，而不是文件的原始形状，
    这样"别名从'再写一遍文件名'改成 alias_of"才不会把等价性断言本身搞坏。
    """
    groups = doc['groups']
    cache = {}

    def resolve(name, seen):
        if name in cache:
            return cache[name]
        if name in seen:
            raise ValueError('alias_of 成环：%s' % ' → '.join(list(seen) + [name]))
        entry = groups.get(name)
        if not isinstance(entry, dict):
            raise ValueError('alias_of 指向不存在的组 %r' % name)
        target = entry.get('alias_of')
        if target:
            frames = resolve(target, seen | {name})
        else:
            frames = list(entry.get('frames') or [])
        cache[name] = frames
        return frames

    return {name: resolve(name, set()) for name in groups}


def build_document(mapping, comments):
    """构造 JSON 文档（保持源码顺序）。本函数是导出格式的唯一出口。

    注释只保留在**组内**（`comment` 字段）：源码里的 `# 行走动画（不同情绪）` 这类
    分块标题本来就贴在它所属的第一个键前面，因此组内注释已经无损承载了全部说明，
    再往 meta 里抄一份就是冗余——冗余的配置项迟早会漂移。
    """
    groups = {}
    for name, frames in mapping.items():
        entry = {'frames': list(frames)}
        if name in comments:
            entry['comment'] = comments[name]
        groups[name] = entry
    return {
        'schema_version': 1,
        'meta': {
            'generated_by': 'code-quality-audit/架构改造-H4H5/extract_animations_json.py',
            'source': 'ralsei_pet/modules/sprite_loader.py :: %s' % VAR_NAME,
            'note': ('本文件由上述脚本从代码单向导出，是 H5 S2 的产物。'
                     '改动动画请改这里；加载失败时程序会回落代码里的同名内置表。'
                     '`frames` 的顺序即播放顺序；`alias_of` 表示复用另一组的帧；'
                     '`legacy: true` 表示保留但不建议新增引用的历史键；'
                     '`comment` 是原代码注释，仅作说明。'),
        },
        'groups': groups,
    }


def dumps(doc):
    """确定性 + 可读的序列化：组的 frames / comment 单行，其余两空格缩进。"""
    lines = ['{', '  "schema_version": %d,' % doc['schema_version'], '  "meta": {']
    meta = doc['meta']
    keys = ['generated_by', 'source', 'note']
    for i, key in enumerate(keys):
        tail = ',' if i < len(keys) - 1 else ''
        lines.append('    %s: %s%s' % (json.dumps(key), json.dumps(meta[key], ensure_ascii=False), tail))
    lines.append('  },')
    lines.append('  "groups": {')
    entries = list(doc['groups'].items())
    for idx, (name, entry) in enumerate(entries):
        tail = ',' if idx < len(entries) - 1 else ''
        lines.append('    %s: {' % json.dumps(name, ensure_ascii=False))
        keys = [k for k in ('frames', 'comment', 'loop', 'offset', 'alias_of', 'legacy') if k in entry]
        for j, k in enumerate(keys):
            comma = ',' if j < len(keys) - 1 else ''
            val = entry[k]
            if k == 'frames':
                body = '[%s]' % ', '.join(json.dumps(f) for f in val)
                # 过长的帧列表折行，避免单行上千字符
                if len(body) > 160:
                    inner = ',\n'.join('        %s' % json.dumps(f) for f in val)
                    body = '[\n%s\n      ]' % inner
                lines.append('      "frames": %s%s' % (body, comma))
            else:
                lines.append('      %s: %s%s' % (json.dumps(k), json.dumps(val, ensure_ascii=False), comma))
        lines.append('    }%s' % tail)
    lines.append('  }')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def load_existing(path=TARGET):
    if not os.path.exists(path):
        return None
    with io.open(path, encoding='utf-8') as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stdout', action='store_true', help='只打印不落盘')
    ap.add_argument('--check', action='store_true', help='只校验现有 JSON 与代码是否一致')
    args = ap.parse_args()

    mapping, node, lines = extract_literal()
    comments = collect_comments(lines, node)
    doc = build_document(mapping, comments)
    text = dumps(doc)
    parsed = json.loads(text)

    # 自校验：序列化后再解析，groups 必须与源码字面量逐组相等（防止导出器本身写错）
    back = {name: entry['frames'] for name, entry in parsed['groups'].items()}
    if back != mapping:
        raise SystemExit('导出器自校验失败：JSON 还原的 groups 与源码字面量不一致')

    if args.check:
        existing = load_existing()
        if existing is None:
            print('FAIL 目标文件不存在: %s' % TARGET)
            return 1
        try:
            resolved = resolve_groups(existing)
        except Exception as exc:
            print('FAIL 解析失败: %s' % exc)
            return 1
        # 自校验：导出器幂等（同一输入连续两次导出必须逐字节一致）
        idem = dumps(build_document(mapping, comments)) == dumps(build_document(mapping, comments))
        ok = resolved == mapping and idem
        print('%s 现有 JSON **解析后**与代码字面量%s'
              % ('PASS' if ok else 'FAIL', '一致' if resolved == mapping else '不一致'))
        print('  组数：JSON=%s 代码=%s；导出器幂等=%s' % (
            len(existing.get('groups', {})), len(mapping), idem))
        if resolved != mapping:
            bad = [k for k in mapping if resolved.get(k) != mapping[k]]
            print('  不一致的组：%s' % bad)
        return 0 if ok else 1

    if args.stdout:
        sys.stdout.write(text)
        return 0

    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with io.open(TARGET, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    print('已导出 %d 组 → %s（%d 字节）' % (len(mapping), TARGET, len(text.encode('utf-8'))))
    print('  带注释的组：%d 个' % sum(1 for e in doc['groups'].values() if 'comment' in e))
    return 0


if __name__ == '__main__':
    sys.exit(main())
