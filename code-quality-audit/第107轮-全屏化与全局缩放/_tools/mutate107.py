# -*- coding: utf-8 -*-
"""第107轮 · 定点变异测试：证明 `check107` 的判据**不是恒真**。

做法：把产品代码里每一处"契约点"定点破坏一次 → 跑 `check107.py` →
**必须报红**（且必须报在**预期的那条**判据上）→ 还原 → 全绿。

★ 记忆铁律：**"破坏必报红"** —— 夹具不保真（破坏了却全绿）比报红更危险。
★ 每处破坏都记 `expect`（期望报红的判据前缀），最后核对**命中集合**。

跑法：
    C:\\Python311\\python.exe mutate107.py
"""
import io
import os
import re
import shutil
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
PY = sys.executable or r'C:\Python311\python.exe'
CHECK = os.path.join(HERE, 'check107.py')

F_CAM = os.path.join(PKG, 'modules', 'scene_camera.py')
F_CTRL = os.path.join(PKG, 'modules', 'scene_controller.py')
F_CANVAS = os.path.join(PKG, 'modules', 'scene_canvas.py')
F_MAIN = os.path.join(PKG, 'src', 'main.py')

_OUT = []


def read(p):
    """★★★ 读时归一化 EOL（`\\r\\n` → `\\n`）。

    第107轮实测：`main.py` 是**全 CRLF**（15864 CRLF / 15864 LF）⇒ 多行锚点
    串（用 `\\n` 写的）**必然不命中** = 夹具静默失效。这正是记忆里那条
    「CRLF 锚点必先 `_lf()`」。写回时按原风格还原（见 `write`）。
    """
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read().replace(u'\r\n', u'\n')


def write(p, s):
    """按原风格写回：本函数收到的 `s` 是 LF 归一化过（或未归一化）的文本。

    ★ 统一策略：**先归一化再按 CRLF 写** —— 因为 `main.py` 全 CRLF，
      且 `git` 侧 `autocrlf=true`。写 LF 会造成整文件 EOL 翻转（巨大假 DIFF）。
    """
    with io.open(p, 'rb') as f:
        _orig = f.read()
    _crlf = _orig.count(b'\r\n') > 0
    _txt = s.replace(u'\r\n', u'\n')
    if _crlf:
        _txt = _txt.replace(u'\n', u'\r\n')
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(_txt)


def run_check():
    try:
        r = subprocess.run([PY, CHECK], cwd=HERE, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=300)
        out = r.stdout.decode('utf-8', 'replace')
        return r.returncode, out
    except Exception:
        return -1, traceback.format_exc()


# 每处变异：(名字, 文件, old, new, 期望报红的判据前缀)
_MUTS = [
    ('M1 fit_fullscreen 的 `<=` 改成 `>=`（min/max 方向反 ⇒ 溢出屏幕）',
     F_CAM, u'if w_by_h <= vw:', u'if w_by_h >= vw:', u'A10'),

    ('M2 SCENE_ASPECT 改 16/9（比例错 ⇒ 画面变形）',
     F_CAM, u'SCENE_ASPECT = 4.0 / 3.0', u'SCENE_ASPECT = 16.0 / 9.0', u'A3'),

    ('M3 fit_fullscreen 返回 3 元组（消费面拿不到偏移）',
     F_CAM, u'return (w, h, ox, oy)', u'return (w, h, ox)', u'A5'),

    ('M4 fit_fullscreen 非法输入不返 None（改成返 (1,1,0,0)）',
     F_CAM, u'return None', u'return (1, 1, 0, 0)', u'A6'),

    ('M5 fit_camera_to_screen 加回 `frac` 形参（旧口径复活）',
     F_CTRL, u'def fit_camera_to_screen(self, screen_size, pet_scale=None):',
     u'def fit_camera_to_screen(self, screen_size, pet_scale=None, frac=0.85):',
     u'B3'),

    ('M6 scoped 基数改 base_w/4.0（可见范围翻倍 = 镜头拉远）',
     F_CTRL, u'base_w / 2.0', u'base_w / 4.0', u'B6'),

    ('M7 不再调 fit_fullscreen（自己乱算）',
     F_CTRL, u'scene_camera.fit_fullscreen(', u'__nope__(', u'B4'),

    ('M8 paintEvent 不消费 _opaque_bg（房间漏成透明）',
     F_CANVAS, u'if self._opaque_bg:', u'if False and self._opaque_bg:', u'C3'),

    ('M9 _place_scene_layer 改回四向钳制（半新半旧）',
     F_MAIN, u'canvas.move(int(g.x()), int(g.y()))',
     u'canvas.move(max(0, min(int(g.x()), 100)), max(0, min(int(g.y()), 100)))',
     u'C6'),

    ('M10 摆位不 repaint（透明窗口 move 后上屏空内容）',
     F_MAIN, u'canvas.repaint()', u'pass', u'C9'),

    ('M11 _scene_is_transparent 的 except 块返 False 改成 True（房间漏成透明）',
     F_MAIN, u'        except Exception as e:\n            _log.debug("main 防御性异常（已忽略）: %s", e)\n            return False\n\n    def _place_scene_layer',
     u'        except Exception as e:\n            _log.debug("main 防御性异常（已忽略）: %s", e)\n            return True\n\n    def _place_scene_layer',
     u'D3'),

    ('M12 PET_SCALE_DEFAULT 改 3.0（默认档不再贴原作）',
     F_MAIN, u'PET_SCALE_DEFAULT = 1.0', u'PET_SCALE_DEFAULT = 3.0', u'E1b'),

    ('M13 渲染倍率不再乘 cam.scale（宠物与场景不同尺）',
     F_MAIN, u'v = sc * rel', u'v = rel', u'E3'),

    ('M14 ui_scale 平方根改线性（UI 暴涨）',
     F_MAIN, u'r = (cur / base) ** 0.5', u'r = (cur / base)', u'E5b'),

    ('M15 set_pet_scale 不再钳位（可设成 100 倍）',
     F_MAIN, u'if target < self.PET_SCALE_MIN:', u'if False:',
     u'E4c', 'set_pet_scale'),

    # ★ 组合变异：产品有**两段**钳位（防浮点归整后越界）⇒ 必须**同拆**
    #   才复现"不钳位"（记忆铁律「负控制必须拆干净」）。单独拆一段 ⇒
    #   另一段仍真守卫 ⇒ **预期不报红**（若报红反说明判据过宽）。
    ('M15b 两段钳位**同拆**（必须报红 —— 证明 E4c 有鉴别力）',
     F_MAIN, u'if target < self.PET_SCALE_MIN:', u'if False:',
     u'E4c', 'set_pet_scale', [
         (u'elif target > self.PET_SCALE_MAX:', u'elif False:'),
     ]),
]


def _scope_replace(src, old, new, scope=None):
    """在 `scope`（函数名）的作用域内替换**全部** `old`。

    ★★★ 为什么必须限定作用域 + 全替换（变异测试 M11/M15 逼出来的）：
      · 不限定作用域：`return False` 全文 **201 处** ⇒ `.replace(..., 1)` 改的是
        别处 ⇒ 夹具没破坏到目标 ⇒ 判据"看起来恒真"（**夹具不保真**）。
      · 只替换第一处：`if target < self.PET_SCALE_MIN:` 在产品里出现 **2 次**
        （两段钳位）⇒ 只拆一段、另一段仍真守卫 ⇒ 同样"拆不干净"。
      两者都是记忆铁律「**负控制必须拆干净**」的实例。
    """
    if scope:
        m = re.search(r'^(\s*)def %s\(' % re.escape(scope), src, re.M)
        if not m:
            return None
        indent = m.group(1)
        start = m.start()
        # 找下一个同/更低缩进的 `def`/类成员作为结束
        nxt = None
        for mm in re.finditer(r'^(?P<ind>[ \t]*)def ', src[m.end():], re.M):
            if len(mm.group('ind')) <= len(indent):
                nxt = m.end() + mm.start()
                break
        body = src[start:nxt if nxt else len(src)]
        if old not in body:
            return None
        return src[:start] + body.replace(old, new) + (src[nxt:] if nxt else u'')
    if old not in src:
        return None
    return src.replace(old, new)


def main():
    print(u'=' * 72)
    print(u'第107轮 · 定点变异测试（证明 check107 判据有鉴别力）')
    print(u'=' * 72)

    _rc0, _out0 = run_check()
    if _rc0 != 0:
        print(u'[ABORT] 变异前 check107 未全绿（rc=%d）—— 先修产品/判据' % _rc0)
        print(_out0[-3000:])
        return 2
    print(u'基线：check107 全绿（rc=0）\n')

    _hit = 0
    _miss = []
    _wrong = []
    for _mut in _MUTS:
        _name, _f, _old, _new, _expect = _mut[:5]
        _scope = _mut[5] if len(_mut) > 5 else None
        _extra = _mut[6] if len(_mut) > 6 else ()
        _orig = read(_f)
        _new_src = _scope_replace(_orig, _old, _new, _scope)
        if _new_src is None:
            _miss.append((_name, u'锚点未命中: %r' % _old[:60]))
            print(u'[SKIP] %s —— 锚点未命中' % _name)
            continue
        # ★ 组合变异：逐个追加（同一作用域内）
        _comb_ok = True
        for _o2, _n2 in _extra:
            _tmp = _scope_replace(_new_src, _o2, _n2, _scope)
            if _tmp is None:
                _comb_ok = False
                break
            _new_src = _tmp
        if not _comb_ok:
            _miss.append((_name, u'组合锚点未命中'))
            print(u'[SKIP] %s —— 组合锚点未命中' % _name)
            continue
        try:
            write(_f, _new_src)
            _rc, _out = run_check()
        except Exception:
            _rc, _out = -1, u''
        finally:
            write(_f, _orig)

        _fails = [l for l in _out.splitlines() if l.strip().startswith(u'[FAIL]')]
        _hit_expected = any(_expect in l for l in _fails)
        if _rc != 0 and _hit_expected:
            _hit += 1
            print(u'[OK]   %s  ⇒ 报红 %d 条，含期望 `%s`'
                  % (_name, len(_fails), _expect))
        elif _rc != 0 and _fails:
            _wrong.append((_name, _expect,
                           u'报红了但非期望：%s' % (_fails[0][:90],)))
            print(u'[MISS] %s  ⇒ 报红但**不是**期望的 `%s`：%s'
                  % (_name, _expect, _fails[0][:100]))
        else:
            _miss.append((_name, u'破坏后 check107 **仍全绿**（判据恒真）'))
            print(u'[BAD]  %s  ⇒ ★★★ 破坏后仍全绿！判据恒真' % _name)

    print(u'\n' + u'=' * 72)
    print(u'变异命中 %d/%d' % (_hit, len(_MUTS)))
    if _wrong:
        print(u'报红错位 %d 处：' % len(_wrong))
        for _n, _e, _d in _wrong:
            print(u'  · %s（期望 %s）%s' % (_n, _e, _d))
    if _miss:
        print(u'未命中/恒真 %d 处：' % len(_miss))
        for _n, _d in _miss:
            print(u'  · %s —— %s' % (_n, _d))
    print(u'=' * 72)

    # 终局复核：还原后必须全绿
    _rc2, _out2 = run_check()
    _ok_final = (_rc2 == 0)
    print(u'终局复核：还原后 check107 %s' % (u'全绿 ✓' if _ok_final else u'仍未全绿 ✗'))
    if not _ok_final:
        print(_out2[-2000:])

    # 落盘
    _ev = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'mutate107.txt'))
    try:
        _lines = [u'变异命中 %d/%d' % (_hit, len(_MUTS))]
        for _n, _e, _d in _wrong:
            _lines.append(u'报红错位: %s (%s) %s' % (_n, _e, _d))
        for _n, _d in _miss:
            _lines.append(u'未命中: %s —— %s' % (_n, _d))
        _lines.append(u'终局还原全绿: %r' % _ok_final)
        with io.open(_ev, 'w', encoding='utf-8') as _f:
            _f.write(u'\n'.join(_lines) + u'\n')
    except Exception:
        pass

    return 0 if (_hit == len(_MUTS) and _ok_final) else 1


if __name__ == '__main__':
    sys.exit(main())
