# -*- coding: utf-8 -*-
"""第37轮补丁：把 verify_scene_route_original.py 里恒真的 E3 判据换成真判据 + 负控制。"""
import io, sys

P = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第36轮-按原作路线排场景\verify_scene_route_original.py'

src = io.open(P, 'r', encoding='utf-8', newline='').read()
nl = '\r\n' if '\r\n' in src else '\n'
print('EOL =', 'CRLF' if nl == '\r\n' else 'LF')

OLD_HDR = '#  E. 素材占位口径（用户选 B：自导出）不许伪装成"没素材"'
NEW_HDR = ('#  E. 背景素材口径 —— 第37轮已由反编译补齐，故升级为真判据\n'
           '#     （原 E3 是 check(..., True) 的恒真占位：当时素材确实还没到位。\n'
           '#       恒真判据比不写还危险 —— 它看着像在守，其实什么都没守。）')

OLD_BLOCK = """# bg 文件确实还不存在（用户尚未导出）—— 这是**预期状态**，不是缺陷
_bg_base = os.path.join(_SCENES)
_existing_bg = 0
for sid in sorted(_story_scenes.keys()):
    scene = ss.load_scene(sid, _SCENES)
    if scene and scene.bg:
        if os.path.isfile(os.path.join(_bg_base, scene.bg)):
            _existing_bg += 1
check('E3 bg 占位文件当前尚不存在（等待用户导出，属预期）',
      True, '已存在的 bg 文件数 = %d（导出后会 > 0）' % _existing_bg)"""

NEW_BLOCK = """# bg 文件在第37轮已由反编译补齐 —— 此处升级为真判据
_bg_base = os.path.join(_SCENES)


def _bg_health_pairs(pairs):
    \"\"\"pairs=[(sid, abs_path)] -> (missing, not_png)。判据内核，正负控制共用。\"\"\"
    miss, bad = [], []
    for sid, fp in pairs:
        if not os.path.isfile(fp):
            miss.append(sid)
            continue
        with open(fp, 'rb') as fh:
            if fh.read(8) != b'\\x89PNG\\r\\n\\x1a\\n':
                bad.append(sid)
    return miss, bad


_scan = []
for sid in sorted(_story_scenes.keys()):
    scene = ss.load_scene(sid, _SCENES)
    if scene and scene.bg:
        _scan.append((sid, os.path.join(_bg_base, scene.bg)))
_miss, _notpng = _bg_health_pairs(_scan)
check('E3 每个场景声明的 bg 都指向真实存在的 PNG（第37轮素材已反编译就位）',
      (not _miss) and (not _notpng) and len(_scan) > 0,
      '扫描 %d 个；缺失 %d %s；非PNG %d %s'
      % (len(_scan), len(_miss), _miss[:4], len(_notpng), _notpng[:4]))

_neg1, _ = _bg_health_pairs([('bogus', os.path.join(_bg_base, 'bg', '__no_such__.png'))])
check('E3b 负控制：判据抓得住"bg 文件不存在"（有鉴别力）',
      _neg1 == ['bogus'], 'got=%r' % _neg1)

_, _neg2 = _bg_health_pairs([('json', os.path.join(_SCENES, '_index.json'))])
check('E3c 负控制：判据抓得住"文件存在但不是 PNG"',
      _neg2 == ['json'], 'got=%r' % _neg2)"""

OLD_E1 = "check('E1 每个作品内场景都声明了 bg 占位路径',"
NEW_E1 = "check('E1 每个作品内场景都声明了 bg 路径',"
OLD_T = "print('=== E. 背景素材占位口径 ===')"
NEW_T = "print('=== E. 背景素材口径 ===')"

hits = 0
for old, new in [(OLD_HDR, NEW_HDR), (OLD_BLOCK, NEW_BLOCK), (OLD_E1, NEW_E1), (OLD_T, NEW_T)]:
    o = old.replace('\n', nl)
    n = new.replace('\n', nl)
    if o in src:
        src = src.replace(o, n, 1)
        hits += 1
        print('patched:', old.splitlines()[0][:60])
    else:
        print('NOT FOUND:', old.splitlines()[0][:60])

print('patches applied =', hits)
io.open(P, 'w', encoding='utf-8', newline='').write(src)
print('written', P)

# 自检
chk = io.open(P, 'r', encoding='utf-8').read()
for k in ['E3b', 'E3c', '_bg_health_pairs', '素材已反编译就位']:
    print('  contains %-24s %s' % (k, k in chk))
print('  no longer has 尚不存在 :', '尚不存在' not in chk)
