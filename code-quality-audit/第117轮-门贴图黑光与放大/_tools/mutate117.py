# -*- coding: utf-8 -*-
u"""第117轮 · 变异测试（mutate117）

为什么必须有（本项目铁律）
--------------------------
  **"全绿比报红更危险"**。本轮 `check117` 的 33 条判据全部对着用户 10-18 那四个
  分句（黑光 / Niko 家不动 / UT 不动 / 大一点），这类"口径闸"最怕
  "加上了、但抓不住回退"。⇒ 逐条破坏，看责任判据**是否精确报红**。

做法（与 `mutate107/116` 同构）
-------------------------------
  ① 把 `ralsei_pet/` 整棵拷进系统临时目录；
  ② 用 `RALSEI_ROUND117_ROOT` 让 `check117.py` 指过去
     ⇒ **产线文件一个字节都不动**，临时树用后即删（系统临时区，不放工作区）；
  ③ 先跑 **M0 正控制**（不破坏 ⇒ 必须 33/0），再逐个**只破坏一处**，
     断言**期望的那条判据名**出现在 `[FAIL]` 里。

★ 只断言"有 FAIL"是不够的：别的判据顺带报红 = 没定位到责任判据
  ⇒ 每条变异都带一个**期望判据名前缀**，必须精确命中。
★ 每个变异都先断言 `old` 在目标文件里**恰好出现 1 次**：打歪了（0 次 / 多次）
  必须**立刻报 MUTATION NOT APPLIED**，而不是拿"没破坏成功"去冒充"判据抓到了"。

★★ 本轮的**两类**变异
---------------------
  · `text`  —— 改源码 / JSON 字面量（同 107/116）；
  · `png`   —— 直接改**贴图像素**（本轮的核心产物就是一张 PNG ⇒ 必须能变异它）：
      `png_copy` 用原件整张覆盖变体（= "号称黑光，其实是原色"）；
      `png_flat` 全部可见像素涂成一个色（= "糊成一块黑"，第116轮用户报过的形态）；
      `png_alpha` 把 alpha 全置 255（= "形状被改"，最容易被忽视的一类回退）。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CHECK = os.path.join(HERE, 'check117.py')
PY = sys.executable

PET = os.path.join(ROOT, 'ralsei_pet')
DJ_REL = os.path.join('ralsei_pet', 'assets', 'scenes', 'desktop.json')
DD_REL = os.path.join('ralsei_pet', 'modules', 'desk_doors.py')
PNG_A_REL = os.path.join('ralsei_pet', 'assets', 'scenes', 'objs',
                         'desk_door_oneshot_black.png')
PNG_B_REL = os.path.join('ralsei_pet', 'assets', 'scenes', 'objs',
                         'niko_door_portal.png')
# ★ 第117轮补：F 组（对话框避让「正下」那扇门）要能变异 ⇒ 需要这两个文件
DLG_REL = os.path.join('ralsei_pet', 'modules', 'dialogue_ui.py')
MAIN_REL = os.path.join('ralsei_pet', 'src', 'main.py')

_BUF = []


def say(m=''):
    print(m)
    _BUF.append(str(m))


def _read(p):
    u"""**字节忠实**读（`newline=''` ⇒ 不把 CRLF 归一掉，写回才是原样）。"""
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _adapt_eol(src, s):
    u"""把锚点里的 `\\n` 调成**目标文件真实的** EOL（CRLF 文件 + `newline=''` 的坑）。"""
    if u'\r\n' in src:
        return s.replace(u'\r\n', u'\n').replace(u'\n', u'\r\n')
    return s


def build_tree():
    base = tempfile.mkdtemp(prefix='mut117_')
    shutil.copytree(PET, os.path.join(base, 'ralsei_pet'))
    return base


def run_check(tree):
    env = dict(os.environ)
    env['RALSEI_ROUND117_ROOT'] = tree
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([PY, CHECK], cwd=ROOT, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def fails_of(out):
    return [l.strip() for l in out.splitlines() if l.startswith('[FAIL]')]


#: (tag, kind, 相对路径, old/None, new/None, 期望报红的判据名前缀)
MUTS = [
    (u'M1  A1   门 A 贴图回退成旧暗门 spr_darkdoor_0', 'text', DJ_REL,
     u'"sprite": "objs/desk_door_oneshot_black.png"',
     u'"sprite": "objs/spr_darkdoor_0.png"',
     u'A1 \u2605\u2605\u2605'),
    (u'M2  A4   变体整张换成原件（号称黑光，其实没变暗）', 'png_copy', PNG_A_REL,
     None, PNG_B_REL, u'A4 \u2605\u2605\u2605'),
    (u'M3  A3   变体 alpha 全置 255（形状被改）', 'png_alpha', PNG_A_REL,
     None, None, u'A3 \u2605\u2605\u2605'),
    (u'M4  A4b  变体涂成单一色（糊成一块，第116轮用户报过的形态）', 'png_flat', PNG_A_REL,
     None, None, u'A4b \u2605\u2605\u2605'),
    (u'M5  B1   门 B 也被换成黑光变体（"niko 的加"没保住原色）', 'text', DJ_REL,
     u'"sprite": "objs/niko_door_portal.png"',
     u'"sprite": "objs/desk_door_oneshot_black.png"',
     u'B1 \u2605\u2605\u2605'),
    (u'M6  C1   门 C（UT）被换掉', 'text', DJ_REL,
     u'"sprite": "objs/desk_door_ut.png"',
     u'"sprite": "objs/desk_door_deltarune.png"',
     u'C1 \u2605\u2605\u2605'),
    (u'M7  D1   DOOR_FIT_CAP 回退成 1.2（"大一点"失效）', 'text', DD_REL,
     u'DOOR_FIT_CAP = 1.6', u'DOOR_FIT_CAP = 1.2', u'D1 \u2605\u2605\u2605'),
    (u'M8  D3   cap 改成 3.0（放大过头，越过"按原作"区间）', 'text', DD_REL,
     u'DOOR_FIT_CAP = 1.6', u'DOOR_FIT_CAP = 3.0', u'D3 \u2605\u2605\u2605'),
    (u'M9  D6   EDGE_MARGIN 0 -> 24（门被顶离屏幕边框）', 'text', DD_REL,
     u'EDGE_MARGIN = 0', u'EDGE_MARGIN = 24', u'D6 \u2605\u2605\u2605'),
    (u'M10 D7   统一倍率退回"逆门算"（按 A 门定尺 ⇒ 四门不再同一把尺）', 'text', DD_REL,
     u'        _s_uniform = fit_doors_uniform_scale(sizes, pet_box)',
     u"        _s_uniform = fit_door_scale(sizes.get('A', (1, 1)), pet_box)",
     u'D7 \u2605\u2605\u2605'),
    # ★ `"enabled": false` 在 desktop.json 里出现 **4 次**（每扇门一次）——
    #   首版拿它当锚点 ⇒ 直接 `MUTATION NOT APPLIED`（"变异锚点禁 replace(...,1)+
    #   禁'全文唯一'假设"的又一次实证）。改用**带门 D 上下文**的多行锚点。
    (u'M11 E3   把一扇门 enabled 改回 true（房间层又画一遍）', 'text', DJ_REL,
     u'      "sprite": "objs/desk_door_deltarune.png",\n'
     u'      "pos": [\n        140,\n        42\n      ],\n'
     u'      "depth": 0,\n      "enabled": false',
     u'      "sprite": "objs/desk_door_deltarune.png",\n'
     u'      "pos": [\n        140,\n        42\n      ],\n'
     u'      "depth": 0,\n      "enabled": true',
     u'E3 \u2605\u2605'),
    # ---- F 组：对话框避让（第117轮录屏发现的"门 B 被整块盖住"）----
    (u'M12 F7   main 摘掉桌面分支的登记调用（门 B 又被对话框盖住）', 'text', MAIN_REL,
     u'                    self._register_door_avoid(_doors)\n',
     u'',
     u'F7 \u2605\u2605\u2605'),
    (u'M13 F3   避让计算恒不抬（形同虚设）', 'text', DLG_REL,
     u'                cand = ry - self.AVOID_GAP - h          # 底边移到门上方',
     u'                cand = bottom_y                          # 变异：永不抬',
     u'F3 \u2605\u2605\u2605'),
    (u'M14 F2   AVOID_GAP 改成 0（框与门贴死）', 'text', DLG_REL,
     u'    AVOID_GAP = 8',
     u'    AVOID_GAP = 0',
     u'F2 \u2605\u2605'),
]


def _mutate_png(kind, abs_p, newrel, tree):
    u"""改贴图像素。拿不到 PIL ⇒ 返 False（调用方报 NOT-APPLIED）。"""
    try:
        from PIL import Image
    except Exception:                                            # noqa: BLE001
        return False
    if kind == 'png_copy':
        src = os.path.join(tree, newrel)
        if not os.path.isfile(src):
            return False
        shutil.copy2(src, abs_p)
        return True
    if not os.path.isfile(abs_p):
        return False
    im = Image.open(abs_p).convert('RGBA')
    px = list(im.getdata())
    if kind == 'png_alpha':
        px = [(t[0], t[1], t[2], 255) for t in px]
    elif kind == 'png_flat':
        px = [(10, 4, 12, t[3]) for t in px]
    else:
        return False
    out = Image.new('RGBA', im.size)
    out.putdata(px)
    out.save(abs_p)
    return True


def _restore_png(abs_p, backup):
    shutil.copy2(backup, abs_p)


def main():
    tree = build_tree()
    rc_all = 0
    detail_rows = []
    try:
        # ---------------------------------------------------------- M0 正控制
        say(u'=' * 72)
        say(u'M0 正控制：临时树原样 ⇒ 必须**全 PASS / 0 FAIL**（否则下面全是假 CAUGHT）')
        say(u'=' * 72)
        rc0, out0 = run_check(tree)
        ok0 = (rc0 == 0) and (u'PASS / 0 FAIL' in out0)
        say(u'  rc=%d  尾部=%r' % (rc0, out0.strip().splitlines()[-1:]))
        if not ok0:
            say(u'[FATAL] M0 不绿 ⇒ 变异测试无意义，停。')
            for l in fails_of(out0):
                say(u'    ' + l)
            return 2

        caught = missed = broken = 0
        for tag, kind, rel, old, new, expect in MUTS:
            abs_p = os.path.join(tree, rel)
            if kind == 'text':
                src = _read(abs_p)
                _old = _adapt_eol(src, old)
                _new = _adapt_eol(src, new)
                n = src.count(_old)
                if n != 1:
                    say(u'\n[%s]  MUTATION NOT APPLIED（old 出现 %d 次，需恰好 1 次）'
                        % (tag, n))
                    broken += 1
                    detail_rows.append((tag, u'NOT-APPLIED(%d)' % n, u'-'))
                    continue
                _write(abs_p, src.replace(_old, _new, 1))
                undo = lambda: _write(abs_p, src)                    # noqa: E731
            else:
                if not os.path.isfile(abs_p):
                    say(u'\n[%s]  MUTATION NOT APPLIED（目标贴图不在）' % tag)
                    broken += 1
                    detail_rows.append((tag, u'NOT-APPLIED(no-png)', u'-'))
                    continue
                backup = abs_p + '.bak'
                shutil.copy2(abs_p, backup)
                if not _mutate_png(kind, abs_p, new, tree):
                    _restore_png(abs_p, backup)
                    os.remove(backup)
                    say(u'\n[%s]  MUTATION NOT APPLIED（PNG 变异失败，PIL 不可用？）'
                        % tag)
                    broken += 1
                    detail_rows.append((tag, u'NOT-APPLIED(png)', u'-'))
                    continue
                undo = lambda: (_restore_png(abs_p, backup), os.remove(backup))  # noqa: E731
            try:
                rc, out = run_check(tree)
                fs = fails_of(out)
                hit = [l for l in fs if l.startswith(u'[FAIL] ' + expect)]
                good = bool(hit)
                if good:
                    caught += 1
                else:
                    missed += 1
                say(u'\n[%s]  rc=%d  FAIL=%d  ⇒ %s'
                    % (tag, rc, len(fs), u'CAUGHT' if good else u'*** MISSED ***'))
                if not good:
                    for l in fs:
                        say(u'    ' + l)
                else:
                    say(u'    ' + hit[0])
                detail_rows.append((tag, u'CAUGHT' if good else u'MISSED',
                                    hit[0] if hit else (fs[0] if fs else u'-')))
            finally:
                undo()                          # 立刻恢复，保证下一条变异互不污染

        say(u'')
        say(u'=' * 72)
        say(u'变异合计：%d 条 ｜ CAUGHT=%d ｜ MISSED=%d ｜ NOT-APPLIED=%d'
            % (len(MUTS), caught, missed, broken))
        for tag, st, name in detail_rows:
            say(u'  %-52s %-12s %s' % (tag, st, name))
        say(u'=' * 72)
        if missed or broken:
            rc_all = 1
    finally:
        shutil.rmtree(tree, ignore_errors=True)

    evdir = os.path.join(ROOT, 'code-quality-audit',
                         u'\u7b2c117\u8f6e-\u95e8\u8d34\u56fe\u9ed1\u5149\u4e0e'
                         u'\u653e\u5927', '_evidence', 'mut117')
    try:
        os.makedirs(evdir, exist_ok=True)
        with io.open(os.path.join(evdir, 'mutate117.txt'), 'w',
                     encoding='utf-8', newline='\n') as f:
            f.write(u'\n'.join(_BUF) + u'\n')
        with io.open(os.path.join(evdir, 'mutate117.json'), 'w',
                     encoding='utf-8', newline='\n') as f:
            f.write(json.dumps([{'tag': t, 'status': s, 'hit': h}
                                for t, s, h in detail_rows],
                               ensure_ascii=False, indent=2))
    except Exception as e:                                       # noqa: BLE001
        say(u'（证据落盘失败：%r —— 不影响结论）' % (e,))
    return rc_all


if __name__ == '__main__':
    sys.exit(main())
