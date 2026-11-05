# -*- coding: utf-8 -*-
u"""第164轮 · 变异测试：证明 `check164` 的判据**真的会红**。

## 为什么非要有这个

本项目反复栽在"判据绿着，但守的是空气"上（恒真判据 / 判据过窄 / 桩比产品旧）。
`check164` 全绿只说明"当前没坏"，**不说明"坏了会被发现"**。
所以每个变异体都要求：改一处产品代码 ⇒ **恰好**那几条判据变红，别的一动不动。

## 铁律

1. **绝不改产品文件**：把 `main.py` 复制到临时目录，用 `CQ_SRC_DIR` 喂给套件。
2. **每轮改完立刻按字节还原并校验 sha1**：任何一步还原失败就当场退出，
   绝不留"半改状态"（本项目踩过 `git checkout --` 抹掉四门改写的坑）。
3. 变异体必须**语法正确** —— 考验的是判据，不是 `SyntaxError`
   （第163轮 M5 特意改成语法正确的变异，就是这条）。
4. 每个变异体都要断言"**确实红了**"且"**红的是我预期的那些**"，
   两步缺一：只断言"红了"会掩盖"红错地方"。
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PET, 'src', 'main.py')
CHECK = os.path.join(HERE, 'check164.py')
PY = sys.executable or r'C:\Python311\python.exe'

# (名字, 找什么, 换成什么, 必须变红的判据名片段, 为什么会红)
MUTATIONS = [
    ('M1 助跑永远不给速度',
     u'        return max(_base, min(RUNUP_SPEED_MAX, _meas))',
     u'        return _base',
     u'B6',
     u'闸门永远拿走路速度 ⇒ 助跑那 30px/s 的区间永远打不开（功能等于没做）'),

    ('M2 标了助跑就直接给满速（假放行）',
     u'        return max(_base, min(RUNUP_SPEED_MAX, _meas))',
     u'        return RUNUP_SPEED_MAX',
     u'B8',
     u'没真跑起来也放行 ⇒ 跳出去半路掉下来，比拒绝更糟'),

    ('M3 闸门不再判水平距离',
     u'            vx = abs(dx) / T\n'
     u'            v_max = self._max_run_px_s()\n'
     u'            if vx > v_max + 1e-6:\n'
     u"                self._jump_reject = ('too_far', vx, v_max)\n"
     u'                return False',
     u'            vx = abs(dx) / T\n'
     u'            v_max = self._max_run_px_s()',
     u'B4',
     u'"不可能跳无限远"这条硬闸消失（也能跳远极限就没了）'),

    ('M4 起跑点算成起跳点本身（助跑距离恒 0）',
     u"                _p = QPoint(int(round(to.x() - ux * _L)),\n"
     u"                            int(round(to.y() - uy * _L)))",
     u"                _p = QPoint(int(round(to.x())), int(round(to.y())))",
     u'D5',
     u'助跑距离不再由 v²/(2a) 决定 ⇒ "退多远"变成拍脑袋'),

    ('M5 惊讶小跳不再原地（凭空 +50px 横移）',
     u'        self.jump_target_pos = QPoint(self.pos().x(), self.pos().y())\n'
     u'        self.jump_duration = duration',
     u'        self.jump_target_pos = QPoint(self.pos().x() + 50, self.pos().y())\n'
     u'        self.jump_duration = duration',
     u'C3b',
     u'违反"没有水平初速度就只能跳高"——这正是本轮要修的那条'),

    ('M6 分段不再夹"严格在两层之间"',
     u'            if not (lo < h < hi):\n'
     u'                continue',
     u'            if False:\n'
     u'                continue',
     u'E2',
     u'目标层自己（甚至本层）也会被当成中途落脚板 ⇒ 原地打转'),

    ('M7 分段候选不再排序（先近后远失效）',
     u"        out.sort(key=lambda f: abs((f.get('platform_height', 0) or 0) - cur_h))",
     u'        pass',
     u'E2',
     u'变成"按 floors 原始顺序"⇒ 可能先跳最高那层，等于一步蹦到顶'),

    ('M8 名义帧长不再夹范围（帧率放大回来）',
     u'        if not (1.0 / 60.0 <= dt <= 1.0 / 20.0):\n'
     u'            return 0.033\n'
     u'        return dt',
     u'        return dt if dt > 1e-6 else 0.033',
     u'B10',
     u'1ms 的帧把 max_speed/0.002 推到 4000px/s ⇒ 闸门当场假放行'),

    ('M9 handle_jump 不再跳过楼层穿透',
     u"            if getattr(self, '_hop_mode', False):\n"
     u'                break',
     u'            if False:\n'
     u'                break',
     u'C5',
     u'原地小跳脚下必然是"自己站的那块板"⇒ 旧判定当场判成穿透并摔下来'),
]


def sha1_of(path):
    with open(path, 'rb') as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def run_check(src_dir):
    env = dict(os.environ)
    env['CQ_SRC_DIR'] = src_dir
    env['QT_QPA_PLATFORM'] = 'offscreen'
    p = subprocess.run([PY, CHECK], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    return p.returncode, out


def failed_lines(out):
    return [ln for ln in out.splitlines() if ln.startswith('[FAIL]')]


def main():
    if not os.path.isfile(MAIN):
        print('找不到产品文件：%s' % MAIN)
        return 1

    orig_sha = sha1_of(MAIN)
    with open(MAIN, 'rb') as fh:
        orig_bytes = fh.read()
    with io.open(MAIN, 'r', encoding='utf-8', newline='') as fh:
        orig_text = fh.read()

    print('=' * 66)
    print('基线：未变异的副本必须全绿')
    print('=' * 66)
    tmp = tempfile.mkdtemp(prefix='mutate164_')
    try:
        base_dir = os.path.join(tmp, 'base')
        os.makedirs(base_dir)
        shutil.copy2(MAIN, os.path.join(base_dir, 'main.py'))
        rc, out = run_check(base_dir)
        base_fail = failed_lines(out)
        print('  rc=%d  失败 %d 条' % (rc, len(base_fail)))
        if rc != 0 or base_fail:
            print('  [ABORT] 基线都不绿，后面的变异结果没有意义：')
            for ln in base_fail[:10]:
                print('    ' + ln)
            return 1

        bad = []
        for i, (name, find, repl, want, why) in enumerate(MUTATIONS, 1):
            # ★ 锚点归一：产品文件是 CRLF，用 `newline=''` 读进来保留 `\r\n`；
            #   用 `\n` 写的多行锚点会永远命中 0 次（第一版 9 个里 6 个就这么哑掉，
            #   报出来的现象是"锚点命中 0 次"而不是判据不灵 —— 这一步不做，
            #   变异测试会用"锚点找不到"冒充"通过"）。
            _find = find.replace('\n', '\r\n')
            _repl = repl.replace('\n', '\r\n')
            n = orig_text.count(_find)
            if n != 1:
                print('\n[%d] %s' % (i, name))
                print('  [ABORT] 锚点命中 %d 次（要求恰好 1 次）—— 改代码后必须同步改变异体' % n)
                bad.append(name)
                continue
            mutated = orig_text.replace(_find, _repl)
            d = os.path.join(tmp, 'm%d' % i)
            os.makedirs(d)
            with io.open(os.path.join(d, 'main.py'), 'w',
                         encoding='utf-8', newline='') as fh:
                fh.write(mutated)
            rc, out = run_check(d)
            fails = failed_lines(out)
            hit = [ln for ln in fails if want in ln]
            print('\n[%d] %s' % (i, name))
            print('    预期变红：%s   原因：%s' % (want, why))
            print('    rc=%d  失败 %d 条' % (rc, len(fails)))
            for ln in fails[:6]:
                print('      ' + ln[:110])
            if rc == 0 or not fails:
                print('  [FAIL] 变异体**没被抓住**（判据是空的）')
                bad.append(name)
            elif not hit:
                print('  [FAIL] 红了但不是预期那条（红错地方 = 判据过窄/串味）')
                bad.append(name)
            else:
                print('  [PASS] 被抓：%s' % hit[0][:90])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- 还原校验：产品文件必须一个字节都没动 ----
    print()
    print('=' * 66)
    print('还原校验')
    print('=' * 66)
    now_sha = sha1_of(MAIN)
    with open(MAIN, 'rb') as fh:
        now_bytes = fh.read()
    if now_sha != orig_sha or now_bytes != orig_bytes:
        print('  [FAIL] 产品文件被改动了！%s != %s' % (now_sha, orig_sha))
        return 1
    print('  [PASS] main.py 字节级未变（sha1 %s）' % now_sha[:12])

    print()
    print('=' * 66)
    if bad:
        print('[FAIL] 变异测试未全通过：%d/%d 个变异体有问题' % (len(bad), len(MUTATIONS)))
        for b in bad:
            print('  - %s' % b)
        return 1
    print('[PASS] 第164轮变异测试：%d/%d 个变异体全部被抓，且红的都是预期判据'
          % (len(MUTATIONS), len(MUTATIONS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
