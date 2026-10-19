# -*- coding: utf-8 -*-
u"""mutate118.py —— 证明 `check118` 的判据**真有鉴别力**（不是恒真）。

纪律（本项目铁律）
------------------
  · **"夹具不破坏 = 全绿比报红更危险"**：每个变异都必须让**至少一条**判据报红；
  · 变异一律**改副本**（系统临时区），**绝不碰工作区**；
  · 锚点必须**恰好出现 1 次**（0 次/多次 ⇒ 立刻报 NOT APPLIED，不许冒充 CAUGHT）；
  · 断言的是**责任判据名**（只写"有 FAIL"不够，别的判据顺带报红 = 没定位到）。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\mutate118.py
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
CHECK = os.path.join(HERE, 'check118.py')
PY = sys.executable

MAIN_REL = os.path.join('ralsei_pet', 'src', 'main.py')
DRC_REL = os.path.join('ralsei_pet', 'modules', 'dr_choice.py')

MUTS = [
    (u'M1  A5   摘掉桌面门选取的调用（退回房间坐标射线）', MAIN_REL,
     u'            dpick = self._desktop_door_pick(props)\n',
     u'            dpick = None\n',
     u'A5'),
    (u'M2  A2   桌面门选取改用房间坐标的实体（同一坑复发）', MAIN_REL,
     u'            pet = self._pet_screen_rect()',
     u'            pet = self._npc_interact_actor_room_xy()',
     u'A2'),
    (u'M3  B2   帧钩子不再驱动 update（全局锁永久占着）', MAIN_REL,
     u'                p.update(dt)',
     u'                pass',
     u'B2'),
    (u'M4  C1   先清空列表再释放（顺序反了 = 僵尸锁照旧）', MAIN_REL,
     u'                        _bus.release(_old)',
     u'                        pass',
     u'C1'),
    (u'M5  D1   桌面上又把主体判回 soul（彩蛋永远弹不出）', MAIN_REL,
     u"            if self._scene_is_desktop_scene():\n                _actor = 'pet'",
     u"            if False:\n                _actor = 'pet'",
     u'D1'),
    (u'M6  G5   选择框退回系统弹窗 QMessageBox', MAIN_REL,
     u'            idx = dr_choice.choose(self, [yes_label, \'我再考虑考虑\'],',
     u'            QtWidgets.QMessageBox.question(self, \'x\', \'y\')\n'
     u'            idx = dr_choice.choose(self, [yes_label, \'我再考虑考虑\'],',
     u'G5'),
    (u'M7  G3   红心素材名改错（光标没了）', DRC_REL,
     u"        p = os.path.join(_assets_dir(), 'soul', 'spr_heart_0.png')",
     u"        p = os.path.join(_assets_dir(), 'soul', 'spr_heart_missing.png')",
     u'G3'),
]


def rd(p):
    # ★ 统一成 LF 再比锚点（main.py 是 CRLF；带 \n 的锚点在 CRLF 里命中 0 次）
    return io.open(p, 'r', encoding='utf-8', newline='').read().replace('\r\n', '\n')


def wr(p, s):
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)


def run_check(tree):
    env = dict(os.environ)
    env['RALSEI_ROUND118_ROOT'] = tree
    env.setdefault('QT_QPA_PLATFORM', 'offscreen')
    r = subprocess.run([PY, CHECK], cwd=ROOT, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = r.stdout.decode('utf-8', 'replace')
    return r.returncode, out


def fails(out):
    return [l for l in out.splitlines() if l.startswith('[FAIL]')]


def main():
    tree = tempfile.mkdtemp(prefix='mut118_')
    dst = os.path.join(tree, 'ralsei_pet')
    shutil.copytree(os.path.join(ROOT, 'ralsei_pet'), dst,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    say = print
    rows = []
    try:
        say('=' * 64)
        rc0, out0 = run_check(tree)
        ok0 = (rc0 == 0) and ('0 FAIL' in out0)
        say('M0 正控制：rc=%d 尾部=%r' % (rc0, out0.strip().splitlines()[-1:]))
        if not ok0:
            say('[FATAL] M0 不绿 ⇒ 变异无意义，停。')
            for l in fails(out0)[:8]:
                say('    ' + l)
            return 2

        caught = missed = bad = 0
        for tag, rel, old, new, expect in MUTS:
            p = os.path.join(tree, rel)
            src = rd(p)
            n = src.count(old)
            if n != 1:
                say(u'\n[%s]  MUTATION NOT APPLIED（锚点命中 %d 次，需恰好 1）' % (tag, n))
                bad += 1
                rows.append({'tag': tag, 'status': 'NOT-APPLIED(%d)' % n})
                continue
            wr(p, src.replace(old, new, 1))
            try:
                rc, out = run_check(tree)
            finally:
                wr(p, src)                     # 还原
            fl = fails(out)
            hit = [l for l in fl if expect in l]
            if rc != 0 and hit:
                caught += 1
                say(u'\n[%s]  rc=%d FAIL=%d ⇒ CAUGHT' % (tag, rc, len(fl)))
                rows.append({'tag': tag, 'status': 'CAUGHT', 'hit': hit[0]})
            elif not fl:
                missed += 1
                say(u'\n[%s]  rc=%d 但**零 FAIL** ⇒ MISSED（判据抓不到）  尾部=%r'
                    % (tag, rc, out.strip().splitlines()[-3:]))
                rows.append({'tag': tag, 'status': 'MISSED'})
            else:
                bad += 1
                say(u'\n[%s]  报红但不是责任判据 ⇒ 判据定位不准' % tag)
                for l in fl[:4]:
                    say('      ' + l)
                rows.append({'tag': tag, 'status': 'WRONG-HIT', 'fails': fl[:4]})
        say('\n' + '=' * 64)
        say(u'变异合计：%d 条 ｜ CAUGHT=%d ｜ MISSED=%d ｜ 问题=%d'
            % (len(MUTS), caught, missed, bad))

        ev = os.path.join(ROOT, 'code-quality-audit', u'\u7b2c118\u8f6e-\u684c\u9762\u95e8'
                          u'\u53ef\u8fbe\u6027', '_evidence')
        os.makedirs(ev, exist_ok=True)
        with io.open(os.path.join(ev, 'mutate118.json'), 'w', encoding='utf-8',
                     newline='\n') as f:
            f.write(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0 if (missed == 0 and bad == 0) else 1
    finally:
        shutil.rmtree(tree, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
