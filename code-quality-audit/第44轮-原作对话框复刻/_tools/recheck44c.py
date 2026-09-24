# -*- coding: utf-8 -*-
"""第44轮 · 重要核心文件复检（六类判据，逐项 PASS/FAIL 落盘）。

核心文件清单：
  C1 ralsei_pet/modules/dr_textbox.py          本轮新增（被 dialogue_ui 依赖）
  C2 ralsei_pet/modules/dialogue_ui.py         本轮改（8 处接线 + 清导入）
  C3 code-quality-audit/regress/run_all.py     本轮改（登记 box_round44）
  C4 code-quality-audit/regress/baseline.json  本轮改（合并模式 3 套件）
  C5 code-quality-audit/第44轮-.../verify_box_round44.py   本轮新增（回归锁）
  C6 code-quality-audit/第八轮/verify_round8_dialogue.py   本轮改（T4.5 升级）
"""
import io
import json
import os
import re
import subprocess
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PY = r'C:\Python311\python.exe'
R44 = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻')

FILES = {
    'C1 dr_textbox.py': os.path.join(ROOT, 'ralsei_pet', 'modules', 'dr_textbox.py'),
    'C2 dialogue_ui.py': os.path.join(ROOT, 'ralsei_pet', 'modules', 'dialogue_ui.py'),
    'C3 run_all.py': os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py'),
    'C4 baseline.json': os.path.join(ROOT, 'code-quality-audit', 'regress', 'baseline.json'),
    'C5 verify_box_round44.py': os.path.join(R44, 'verify_box_round44.py'),
    'C6 verify_round8_dialogue.py': os.path.join(
        ROOT, 'code-quality-audit', '第八轮', 'verify_round8_dialogue.py'),
    # ---- 后半：路由重建 + 相机（本段新增）----
    'C7 scene_camera.py': os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_camera.py'),
    'C8 scene_routing.py': os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_routing.py'),
    'C9 scene_controller.py': os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_controller.py'),
    'C10 main.py': os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'),
    'C11 _routes.json': os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_routes.json'),
    'C12 verify_camera_round44.py': os.path.join(R44, 'verify_camera_round44.py'),
    'C13 verify_scene_route_original.py': os.path.join(
        ROOT, 'code-quality-audit', '第36轮-按原作路线排场景',
        'verify_scene_route_original.py'),
    # ---- 第44轮续：渲染层落地（本段新增）----
    'C14 scene_render.py': os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_render.py'),
    'C15 scene_canvas.py': os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_canvas.py'),
    'C16 verify_render_round44.py': os.path.join(R44, 'verify_render_round44.py'),
    'C17 verify_canvas_round44.py': os.path.join(R44, 'verify_canvas_round44.py'),
    'C18 verify_routes_order44.py': os.path.join(R44, 'verify_routes_order44.py'),
    'C19 gen_routes44.py': os.path.join(R44, '_tools', 'gen_routes44.py'),
}

OUT = []


def P(s=''):
    OUT.append(s)
    print(s)


def rd(p):
    with io.open(p, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def rb(p):
    with open(p, 'rb') as fh:
        return fh.read()


P('=' * 78)
P('第 44 轮 · 重要核心文件复检')
P('=' * 78)

# ---------------------------------------------------------------- ① 可编译
P()
P('① 语法 / 可编译')
for tag, p in FILES.items():
    if not p.endswith('.py'):
        P('  [SKIP] %-28s （非 .py）' % tag)
        continue
    r = subprocess.run([PY, '-m', 'py_compile', p],
                       capture_output=True, text=True)
    P('  [%s] %-28s rc=%d %s'
      % ('PASS' if r.returncode == 0 else 'FAIL', tag, r.returncode,
         (r.stderr or '').strip()[:120]))

# JSON 可解析
for tag, p in FILES.items():
    if not p.endswith('.json'):
        continue
    try:
        d = json.loads(rd(p))
        n = len(d.get('suites', d)) if isinstance(d, dict) else len(d)
        P('  [PASS] %-28s JSON 可解析，顶层条目=%s' % (tag, n))
    except Exception as e:
        P('  [FAIL] %-28s JSON 解析失败：%s' % (tag, e))

# ---------------------------------------------------------------- ② 结构
P()
P('② 结构自检（关键符号在位、无粘连）')
NEED = {
    'C1 dr_textbox.py': ['BAND = 32', 'STRETCH_GAP = 63', 'CORNER_SIZE = 32',
                         'BLACK_INSET = 14', 'CORNER_FRAMES = 8',
                         'JEWEL_TICKS_PER_FRAME = 10', 'TYPE_INTERVAL_MS =',
                         'def jewel_frame', 'def textbox_metrics',
                         'def darkbox_blits', 'def paint_dark_box',
                         'class TextboxSprites', 'class DrTextboxFrame',
                         'def set_animation_enabled', 'def hideEvent',
                         'def showEvent'],
    'C2 dialogue_ui.py': ['_drbox.DrTextboxFrame(', 'BOX_INSET = _drbox.CONTENT_INSET',
                          '_should_play_text_sound', '_TEXT_SOUND_SKIP',
                          'QGraphicsDropShadowEffect', 'BASE_WIDTH = 620',
                          'MIN_BOX_HEIGHT = 220', 'def _ralsei_font'],
    'C3 run_all.py': ["'id': 'box_round44'", 'box_round44', "'id': 'camera_round44'",
                      'camera_round44'],
    'C5 verify_box_round44.py': ["print('[PASS] %s", 'GML_DIR', 'TB_DIR',
                                  'def check', 'sys.exit'],
    'C6 verify_round8_dialogue.py': ['def visible_inset_of', 'BLACK_INSET',
                                     'T4.5'],
    'C7 scene_camera.py': ['DEFAULT_CAMERA_SIZE = (640, 480)', 'DEFAULT_BORDER = 0',
                           'def clamp', 'def camera_rect', 'def world_to_view',
                           'def view_rect_in_world', 'def scale_rect',
                           'class Camera', 'def follow', 'def to_view',
                           'def scoped_size', 'camera_set_view_target',
                           'prev_cam'],
    'C8 scene_routing.py': ['when_door', 'def _match_one', 'def match',
                            'def load_routes', 'have_door'],
    'C9 scene_controller.py': ['import scene_camera', 'def init_camera',
                               'def camera_follow', 'def switch',
                               'def load_routes'],
    'C10 main.py': ['self._scene_camera = None', 'self.scene_scale = 2.0',
                    'self.camera_rect = None', 'self.scene.init_camera()',
                    "'scene'"],
    'C11 _routes.json': ['when_door', 'room_delta', 'obj_doorA',
                         'critical_warning_priority_beats_score', 'coverage_policy'],
    'C13 verify_scene_route_original.py': ['_DOOR_DELTA', 'when_door',
                                           'ch1.home.krishallway',
                                           'C4b2'],
    'C14 scene_render.py': ['def room_geometry', 'def room_world_rect',
                            'def viewport_size', 'def to_output',
                            'def visible_in_view', 'def plan_frame',
                            'def plan_viewport', 'K_BG', 'K_OBJ',
                            'K_PLACEHOLDER', 'K_ROOM_BORDER',
                            'PLACEHOLDER_STRIPE'],
    'C15 scene_canvas.py': ['class SceneAssetCache', 'def paint_on',
                            'def _paint_bg', 'def _paint_obj',
                            'def _paint_placeholder', 'def _paint_room_border',
                            'class SceneCanvas', 'def set_plan',
                            'def sprite_size', 'def paintEvent'],
    'C16 verify_render_round44.py': ["print('[PASS] %s", 'def ok'],
    'C17 verify_canvas_round44.py': ["print('[PASS] %s", 'def ok'],
    'C18 verify_routes_order44.py': ["print('[PASS] %s", 'def ok', 'B2'],
    'C19 gen_routes44.py': ['scene_ord', 'BAND', 'DOOR_DELTA', 'marker_letter'],
}
for tag, keys in NEED.items():
    t = rd(FILES[tag])
    miss = [k for k in keys if k not in t]
    P('  [%s] %-28s 缺=%s' % ('PASS' if not miss else 'FAIL', tag, miss or '无'))

# 粘连检测：关键行不许出现两个语句挤在一行（>200 字符的行）
for tag, p in FILES.items():
    t = rd(p)
    longl = [(i + 1, len(l)) for i, l in enumerate(t.split('\n')) if len(l) > 200]
    P('  [%s] %-28s 超长行(>200)=%d %s'
      % ('PASS' if not longl else 'WARN', tag, len(longl), longl[:3]))

# ---------------------------------------------------------------- ③ 编码
P()
P('③ 编码（无 BOM / 无 U+FFFD / EOL 一致）')
for tag, p in FILES.items():
    b = rb(p)
    bom = b[:3] == b'\xef\xbb\xbf'
    crlf = b.count(b'\r\n')
    lf = b.count(b'\n') - crlf
    fffd = b.count(b'\xef\xbf\xbd')
    ok = (not bom) and fffd == 0 and (crlf == 0 or lf == 0)
    P('  [%s] %-28s bytes=%-8d BOM=%s CRLF=%-5d LF=%-5d FFFD=%d'
      % ('PASS' if ok else 'FAIL', tag, len(b), bom, crlf, lf, fffd))

# ---------------------------------------------------------------- ④ 恒真判据
P()
P('④ 恒真 / 占位判据复查')
for tag, p in FILES.items():
    if not p.endswith('.py'):
        continue
    t = rd(p)
    sus = re.findall(r'check\(\s*[\'"][^\'"]*[\'"]\s*,\s*(?:True|1)\s*[,)]', t)
    assert0 = re.findall(r'\bassert\s+True\b', t)
    P('  [%s] %-28s check(…,True)=%d assert True=%d'
      % ('PASS' if not sus and not assert0 else 'FAIL', tag, len(sus),
         len(assert0)))

# ---------------------------------------------------------------- ⑤ 逐令牌回验
P()
P('⑤ 逐令牌回验（改/删过的关键令牌，逐个回原文 in 一次）')
TOKENS = {
    'C1 dr_textbox.py': ['BAND = 32', 'STRETCH_GAP = 63', 'CORNER_SIZE = 32',
                         'BLACK_INSET = 14', 'CORNER_FRAMES = 8',
                         'JEWEL_TICKS_PER_FRAME = 10', 'ENGINE_FPS = 30',
                         'CONTENT_INSET = BAND + 2',
                         'spr_textbox_topleft_%d.png', 'global.flag[8]',
                         'cur_jewel'],
    'C2 dialogue_ui.py': ['" &^!?.,:/\|*"', '_PIXEL_NOAA = True',
                          '普通字体.ttf', 'QFont.NoAntialias',
                          'from PyQt5.QtGui import QFont, QColor, QFontDatabase',
                          'margin_r = self.BOX_INSET - 18',
                          'margin_b = self.BOX_INSET - 18'],
    'C3 run_all.py': ["'id': 'box_round44'", "'offscreen': True"],
    'C4 baseline.json': ['box_round44', 'round8_dialogue', 'round5_smoke'],
    'C5 verify_box_round44.py': ["print('[PASS] %s", "print('[FAIL] %s",
                                 '[0, 0, 1, 1, 2, 7, 0, 2]', 'spr_textbox_top'],
    'C6 verify_round8_dialogue.py': ['def visible_inset_of',
                                     'dr_textbox.BLACK_INSET',
                                     '4 角都在黑底可见区内', 'import os\nimport sys'],
    'C7 scene_camera.py': ['DEFAULT_CAMERA_SIZE = (640, 480)', 'DEFAULT_BORDER = 0',
                           'camera_set_view_target', 'camera_set_view_border',
                           'parallax', '视差', 'prev_cam', 'scale_rect',
                           'GMS2FPS', '640×480'],
    'C8 scene_routing.py': ['when_door', '反向语义', 'have_door',
                            'want_door'],
    'C9 scene_controller.py': ['import scene_camera', 'def init_camera',
                               'def camera_follow', 'scene_camera.Camera(',
                               'pet.camera_rect = rect'],
    'C10 main.py': ['self._scene_camera = None', 'self.scene_scale = 2.0',
                    'self.camera_rect = None', 'self.scene.init_camera()',
                    '第44轮'],
    'C11 _routes.json': ['when_door', 'room_delta', 'coverage_policy',
                         'mechanism', 'obj_doorA'],
    'C12 verify_camera_round44.py': ['def check', 'DEFAULT_CAMERA_SIZE',
                                     'prev_cam', 'self.scene.init_camera(',
                                     'scene_scale'],
    'C13 verify_scene_route_original.py': ['_DOOR_DELTA', 'when_door',
                                           'ch1.home.krishallway',
                                           'krishallway'],
    'C14 scene_render.py': ['def room_geometry', 'def room_world_rect',
                            'def viewport_size', 'def plan_frame',
                            'def plan_viewport', 'K_BG', 'K_PLACEHOLDER',
                            'native', 'sprite_size', '无视差'],
    'C15 scene_canvas.py': ['class SceneAssetCache', 'def paint_on',
                            'def _paint_bg', 'def _paint_obj',
                            'class SceneCanvas', 'def set_plan',
                            'def sprite_size', 'drawn', 'MISSING_OBJ_PEN'],
    'C16 verify_render_round44.py': ['D7', 'D8', 'D9', 'native'],
    'C17 verify_canvas_round44.py': ['SceneAssetCache', 'paint_on', '伪'],
    'C18 verify_routes_order44.py': ['order % ', 'scene_ord', 'when_door'],
    'C19 gen_routes44.py': ['scene_ord[sa] * BAND + k', 'priority 回绕',
                            '独立验证', '不猜'],
}
tot = mis = 0
for tag, toks in TOKENS.items():
    t = rd(FILES[tag])
    m = [k for k in toks if k not in t]
    tot += len(toks)
    mis += len(m)
    P('  [%s] %-28s 令牌=%d 缺=%s'
      % ('PASS' if not m else 'FAIL', tag, len(toks), m or '无'))
P('  ---- 令牌合计 = %d ；missing = %d' % (tot, mis))

# 负控制：这些"已被删掉的东西"不许回来
NEG = {
    'C2 dialogue_ui.py': ['border-radius', '#drFrame'],
    'C6 verify_round8_dialogue.py': ['import re'],
    'C7 scene_camera.py': ['QTimer', 'lerp', 'interpolat'],
    'C9 scene_controller.py': ['QTimer'],
}
P()
P('  负控制（被删的不许回来）:')
for tag, toks in NEG.items():
    t = rd(FILES[tag])
    back = [k for k in toks if k in t]
    P('  [%s] %-28s 回来了=%s'
      % ('PASS' if not back else 'FAIL', tag, back or '无'))

# ---------------------------------------------------------------- ⑥ 工作区
P()
P('⑥ 工作区干净（git status --porcelain）')
r = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT,
                   capture_output=True, text=True)
P('  ' + (r.stdout.strip().replace('\n', '\n  ') or '(empty)'))
P('  → 本轮是"待提交"状态，清单即为本轮改动；提交后应为空。')

# ---------------------------------------------------------------- 汇总
P()
P('=' * 78)
n_fail = sum(1 for l in OUT if l.strip().startswith('[FAIL]'))
P('复检结论：FAIL 行 = %d' % n_fail)
P('=' * 78)

outp = os.path.join(R44, '_evidence', '核心文件复检.txt')
with io.open(outp, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(OUT) + '\n')
print()
print('[done] -> %s' % outp)
