# -*- coding: utf-8 -*-
u"""第116轮 · 变异测试（mutate116）

为什么必须有（本项目铁律）
--------------------------
  **"全绿比报红更危险"**：一条判据如果对**真被破坏的产物**仍然全绿，
  那它不是判据，是装饰。本轮的 E1~E5 是对**用户真机报的缺陷**（门在闪现 /
  黑底没去干净 / 对话框闪现 / 门形式不对）加的回退闸 —— 这类闸最怕
  "加上了、但抓不住回退"。

做法（与 `mutate107/115` 同构）
-------------------------------
  ① 一次把**被判的**几棵子树拷进系统临时目录
     （`ralsei_pet/` 整棵 37 MB + `vault_guard.py` + 两个录制脚本）；
  ② 用 `RALSEI_ROUND116_ROOT` 让 `check116.py` 指过去（本轮新加的覆盖口）；
     ⇒ **产线文件一个字节都不动**，临时树用后即删（系统临时区，不放工作区）；
  ③ 先跑 **M0 正控制**（不破坏 ⇒ 必须 39/0），再逐个**只破坏一处**，
     断言**期望的那条判据名**出现在 `[FAIL]` 里。

★ 只断言"有 FAIL"是不够的：别的判据顺带报红 = 没定位到责任判据。
⇒ 每条变异都带一个**期望判据名前缀**，必须精确命中。

★ 每个变异都先断言 `old` 在目标文件里**恰好出现 1 次**：
  变异打歪了（0 次 / 多次）必须**立刻报 MUTATION NOT APPLIED**，
  而不是拿"没破坏成功"去冒充"判据抓到了"（那是假 CAUGHT，比 MISSED 更坏）。
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
CHECK = os.path.join(HERE, 'check116.py')
PY = sys.executable

PET = os.path.join(ROOT, 'ralsei_pet')
GUARD_REL = os.path.join('code-quality-audit', '_shared', 'vault_guard.py')
DIAG_REL = os.path.join('code-quality-audit', '第96轮-用户视角录制复核',
                        '_tools', 'diag96_exit.py')
REPLAY_REL = os.path.join('code-quality-audit', '第115轮-AI人味训练',
                          '_tools', 'replay115.py')

MAIN_REL = os.path.join('ralsei_pet', 'src', 'main.py')
CV_REL = os.path.join('ralsei_pet', 'modules', 'scene_canvas.py')
DU_REL = os.path.join('ralsei_pet', 'modules', 'dialogue_ui.py')
DJ_REL = os.path.join('ralsei_pet', 'assets', 'scenes', 'desktop.json')

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
    u"""把锚点里的 `\\n` 调成**目标文件真实的** EOL。

    ★★★ 这是第116轮第一次跑变异时踩的坑：`_read()` 用 `newline=''` 是**字节忠实**的
      （铁律），于是 CRLF 文件读出来带 `\\r\\n`；而锚点按 `\\n` 写 ⇒ **多行锚点直接
      0 次命中**，被报成 `MUTATION NOT APPLIED`。单行锚点不受影响 ⇒ 只有 M7/M8 中招
      （本项目"CRLF 锚点必先 `_lf()`"是既有教训，这次换了个方向又踩一遍）。
    """
    if u'\r\n' in src:
        return s.replace(u'\r\n', u'\n').replace(u'\n', u'\r\n')
    return s


def build_tree():
    u"""造一次临时树；返回其根。"""
    base = tempfile.mkdtemp(prefix='mut116_')
    shutil.copytree(PET, os.path.join(base, 'ralsei_pet'))
    for rel in (GUARD_REL, DIAG_REL, REPLAY_REL):
        dst = os.path.join(base, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, rel), dst)
    return base


def run_check(tree):
    env = dict(os.environ)
    env['RALSEI_ROUND116_ROOT'] = tree
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([PY, CHECK], cwd=ROOT, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def fails_of(out):
    return [l.strip() for l in out.splitlines() if l.startswith('[FAIL]')]


#: (tag, 相对路径, old, new, 期望报红的判据名前缀)
MUTS = [
    (u'M1  E1  桌面尺寸改回 geometry()（盖满整屏）',
     MAIN_REL,
     u'a = scr.availableGeometry()',
     u'a = scr.geometry()',
     u'E1 ★★★'),
    (u'M2  E1b 桌面分支不用 _desktop_layer_size()',
     MAIN_REL,
     u'sw, sh = self._desktop_layer_size()',
     u'sw, sh = self._primary_screen_size()',
     u'E1b ★★★'),
    (u'M3  E2a 屏幕门不调 screen_reveal_alpha()',
     MAIN_REL,
     u'door_reveal_mod.screen_reveal_alpha(',
     u'door_reveal_mod.reveal_alpha(',
     u'E2a ★★★'),
    (u'M4  E2b 屏幕层不读 alpha（setOpacity 拿掉）',
     CV_REL,
     u'                else:\n                    try:\n'
     u'                        painter.setOpacity(a)\n',
     u'                else:\n                    try:\n'
     u'                        painter.setCompositionMode('
     u'painter.CompositionMode_SourceOver)\n',
     u'E2b ★★★'),
    (u'M5  E3  门 D 回退成原件 spr_giantdarkdoor_0（带回黑底）',
     DJ_REL,
     u'"objs/desk_door_deltarune.png"',
     u'"objs/spr_giantdarkdoor_0.png"',
     u'E3 ★★★'),
    (u'M6  E4b show_dialogue 加回字面量 setStartValue(0.0)',
     DU_REL,
     u'_start, _need = fade_plan(',
     u'self._fade_anim.setStartValue(0.0)\n            _start, _need = fade_plan(',
     u'E4b ★★★'),
    (u'M7  E4d fade_plan 稳态也判"要淡入"（退化成每次都重淡）',
     DU_REL,
     u'    if cur >= st - ep:',
     u'    if False and cur >= st - ep:',
     u'E4d ★★★'),
    (u'M8  E5  _show_scene_layer 顶层无条件 raise_()',
     MAIN_REL,
     u'    def _show_scene_layer(self):\n',
     u'    def _show_scene_layer(self):\n        self.scene_canvas.raise_()\n',
     u'E5 ★★★'),
    (u'M9  B1  diag96 少设 RALSEI_MEMORY_DIR（只设另两把）',
     DIAG_REL,
     u"    os.environ['RALSEI_MEMORY_DIR'] = _vault      # ★ 设备目录（真源头）\n",
     u'',
     u'B1 '),
    (u'M10 C1  重放器又对外宣称"各 rec*.py 自带沙箱"',
     REPLAY_REL,
     u'def say(m=\'\'):\n    print(m)\n    BUF.write(str(m) + "\\n")\n',
     u'def say(m=\'\'):\n    print(m)\n    BUF.write(str(m) + "\\n")\n\n\n'
     u'say(u\'\u2605 \u6c99\u7bb1\uff1a\u5404 rec*.py \u81ea\u5e26 RALSEI_DATA_DIR\')\n',
     u'C1 '),
    (u'M11 A2  vault_guard.compare 退化成恒"完全一致"',
     GUARD_REL,
     u'    added = sorted(set(cur_files) - set(base_files))',
     u'    return ([], [], [])\n    added = sorted(set(cur_files) - set(base_files))',
     u'A2 '),
]


def main():
    tree = build_tree()
    rc_all = 0
    try:
        # ---------------------------------------------------------- M0 正控制
        say(u'=' * 72)
        say(u'M0 正控制：临时树原样 ⇒ 必须 39 PASS / 0 FAIL（否则下面全是假 CAUGHT）')
        say(u'=' * 72)
        rc0, out0 = run_check(tree)
        ok0 = (rc0 == 0) and (u'PASS=40 FAIL=0' in out0)
        say(u'  rc=%d  尾部=%r' % (rc0, out0.strip().splitlines()[-1:]))
        if not ok0:
            say(u'[FATAL] M0 不绿 ⇒ 变异测试无意义，停。')
            for l in fails_of(out0):
                say(u'    ' + l)
            return 2

        caught = missed = broken = 0
        detail_rows = []
        for tag, rel, old, new, expect in MUTS:
            abs_p = os.path.join(tree, rel)
            src = _read(abs_p)
            old = _adapt_eol(src, old)
            new = _adapt_eol(src, new)
            n = src.count(old)
            if n != 1:
                # ★ 变异打歪 = 这一步什么都没证明，绝不算 CAUGHT
                say(u'\n[%s]  MUTATION NOT APPLIED（old 出现 %d 次，需恰好 1 次）'
                    % (tag, n))
                broken += 1
                detail_rows.append((tag, u'NOT-APPLIED(%d)' % n, u'-'))
                continue
            _write(abs_p, src.replace(old, new, 1))
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
                _write(abs_p, src)          # 立刻恢复，保证下一条变异互不污染

        say(u'')
        say(u'=' * 72)
        say(u'变异合计：%d 条 ｜ CAUGHT=%d ｜ MISSED=%d ｜ NOT-APPLIED=%d'
            % (len(MUTS), caught, missed, broken))
        for tag, st, name in detail_rows:
            say(u'  %-46s %-12s %s' % (tag, st, name))
        say(u'=' * 72)
        if missed or broken:
            rc_all = 1
    finally:
        shutil.rmtree(tree, ignore_errors=True)

    # 落证据（不写工作区的临时物；证据目录是本轮自己的）
    evdir = os.path.join(ROOT, 'code-quality-audit',
                         u'\u7b2c116\u8f6e-\u9000\u51fa\u671f\u5d29\u6e83\u5b9a\u4f4d'
                         u'\u4e0e\u6c99\u7bb1\u8865\u6f0f', '_evidence', 'rec116')
    try:
        os.makedirs(evdir, exist_ok=True)
        with io.open(os.path.join(evdir, 'mutate116.txt'), 'w',
                     encoding='utf-8', newline='\n') as f:
            f.write(u'\n'.join(_BUF) + u'\n')
        with io.open(os.path.join(evdir, 'mutate116.json'), 'w',
                     encoding='utf-8', newline='\n') as f:
            f.write(json.dumps([{'tag': t, 'status': s, 'hit': h}
                                for t, s, h in detail_rows],
                               ensure_ascii=False, indent=2))
    except Exception as e:                                    # noqa: BLE001
        say(u'（证据落盘失败：%r —— 不影响结论）' % (e,))
    return rc_all


if __name__ == '__main__':
    sys.exit(main())
