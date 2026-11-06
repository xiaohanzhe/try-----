# -*- coding: utf-8 -*-
u"""第166轮 · 变异测试：证明 `check166` 的判据**真的会红**。

## 为什么非要有这个

`check166` 全绿只说明"当前没坏"，**不说明"坏了会被发现"**。
本轮判据自己就栽了三次（`_funcdef` 抓到别的类的 `__init__`、D3 只扫 `ast.Name`
漏了 `getattr` 的**字符串字面量**、C3 写成一坨 lambda），
前两条正是"一恒真配一恒假、互相掩护"那一族。

## 铁律（与 `mutate164/165` 同源）

1. **绝不改产品文件**：`src/main.py` + 整个 `modules/` 复制到临时目录，
   用 `CQ_SRC_DIR` / `CQ_MOD_DIR` 喂给套件，改的永远是副本。
2. **每个变异体只改一处**，锚点必须**恰好命中 1 次**
   （禁止 `replace(...,1)` 掩盖"锚点已经不存在了"）。
3. 变异体必须**语法正确** —— 考验的是判据，不是 `SyntaxError`。
4. 每个变异体都断言"**确实红了**"且"**红的是预期那些**"；
   **M15 是无害变异**（只动注释）⇒ 期望**一条都不红**，专门验"没破坏时会不会假红"。
5. 跑完后产品文件必须**字节级未变**（sha1 校验）。
6. ⚠️ 副本里 `PYTHONDONTWRITEBYTECODE=1` 且删 `__pycache__`：否则同秒同大小的
   变异体会命中旧 `.pyc`，现象是"变异没生效 ⇒ 判据全绿 ⇒ 误判判据失灵"。
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
MOD_DIR = os.path.join(PET, 'modules')
CHECK = os.path.join(HERE, 'check166.py')
PY = sys.executable or r'C:\Python311\python.exe'

# (名字, 找什么, 换成什么, 必须变红的判据名片段（None=一条都不许红）, 为什么会红)
MUTATIONS = [
    (u'M1 助跑时把速度削回"所需"（距离又变回输入）',
     u'_v_lock = min(_meas, _cap0)',
     u'_v_lock = _v_need',
     u'B4 助跑',
     u'这正是 D1 的病根：只要把实测削回所需，"跑多快跳多远"就再次变成"目标决定速度"'),

    (u'M2 助跑时恒给满速（不看实测）',
     u'_v_lock = min(_meas, _cap0)',
     u'_v_lock = _cap0',
     u'B4 助跑',
     u'实测 300 却给 320 ⇒ 落点差 20px，是第164轮"假放行"的同型：给了一个他跑不出来的速度'),

    (u'M3 上限不生效（实测多少就多少）',
     u'_v_lock = min(_meas, _cap0)',
     u'_v_lock = _meas',
     u'B5 助跑上限',
     u'疲惫/短帧时实测可能被算到几千 px/s，必须封到冲刺上限'),

    (u'M4 上限不乘 run 倍率（练了也白练）',
     u"_cap0 = float(RUNUP_SPEED_MAX) * float(self._motion_eff()['run'])",
     u'_cap0 = float(RUNUP_SPEED_MAX)',
     u'B5b',
     u'第165轮的能力养成有一半就白装了：练出来的冲刺速度抬不动上限'),

    (u'M5 原地起跳也横移（推论1 被破）',
     u'_vx0 = ((1.0 if _dx0 >= 0 else -1.0) * _v_lock) if abs(_dx0) > 0 else 0.0',
     u'_vx0 = ((1.0 if _dx0 >= 0 else -1.0) * _v_lock) if abs(_dx0) > 0 else 1.0',
     u'B3 原地起跳',
     u'用户第164轮原话："没有水平初速度就只能跳高" —— 原地跳凭空横移 1px 就是回归'),

    (u'M6 丢掉方向符号',
     u'(1.0 if _dx0 >= 0 else -1.0) * _v_lock',
     u'1.0 * _v_lock',
     u'B2 方向',
     u'往左跳变成往右飞 —— 屏幕 X 的正负号丢了'),

    (u'M7 近跳也吃 run 倍率（豁免区间被污染）',
     u'_v_lock = _v_need                     # 近跳豁免：与改动前逐值相同',
     u"_v_lock = _v_need * float(self._motion_eff()['run'])",
     u'B5c',
     u'用户裁定"近跳豁免助跑"就是为了这一段逐值不变；乘上倍率等于偷偷改了近跳手感'),

    (u'M8 吸附半径归零（浮点差一律算落空）',
     u'JUMP_SNAP_PX = 12.0',
     u'JUMP_SNAP_PX = 0.0',
     u'C1',
     u'实测与规划的末帧差是连续量，归零 ⇒ 几乎每一跳都判"冲过头"'),

    (u'M9 吸附半径放到 100（冲过头也被吞掉）',
     u'JUMP_SNAP_PX = 12.0',
     u'JUMP_SNAP_PX = 100.0',
     u'C2 ',
     u'"如实掉"被吞掉 ⇒ 落点永远等于目标，等于把这次修复又抹回去了'),

    (u'M10 落空不坠落（跳偏了站着不动）',
     u'                    # `start_falling` 自带"正在跳就跳过"的守卫 ⇒ 必须先撤起跳标记\r\n'
     u'                    self.start_falling()\r\n',
     u'',
     u'C2 ',
     u'2.5D 口径："走出平台边缘就是掉"；不坠就是悬空站在空气里'),

    (u'M11 掉之前不撤 `is_jumping`（产品里会被静默跳过）',
     u'                if not _inside:\n                    self.is_jumping = False',
     u'                if not _inside:\n                    pass',
     u'C6 ',
     u'`start_falling` 第一段就有 `if is_jumping: return` ⇒ 不撤标记就永不坠落（哑巴 bug）'),

    (u'M12 正常落地不清锁存位（下一跳拿上次的 vx 飞）',
     u'            # ★ 第166轮：这次跳跃的弹道锁存到此失效 —— 不清的话，下一次**不走\n'
     u'            #   `start_jump`** 的跳（如惊讶小跳）会拿着上次的 `_jump_vx0` 横移出去。\n'
     u'            self._jump_vx0 = None\n'
     u'            self._jump_vy0 = None\n'
     u'            self._jump_dur0 = None',
     u'            # ★ 第166轮：这次跳跃的弹道锁存到此失效（变异体：故意不清）',
     u'C7 ',
     u'惊讶小跳不走 `start_jump` ⇒ 残留的 `_jump_vx0` 会让"被吓一跳"变成横向平移'),

    (u'M13 落空时把位置拉回目标',
     u'x = self.jump_target_pos.x() if abs(_miss_px) <= JUMP_SNAP_PX else _x_calc',
     u'x = self.jump_target_pos.x()',
     u'C2b',
     u'"落点由物理算"又被悄悄抹平：位置被拉回目标 ⇒ 用户看到的是"跳得准"，实际是作弊'),

    (u'M14 落地时不读锁存值（退回"按目标落"的旧口径）',
     u"_vx_land = getattr(self, '_jump_vx0', None)",
     u'_vx_land = None',
     u'C2 ',
     u'等于把本轮修复整个回滚 —— 落点重新"永远等于目标"，冲过头这条路彻底消失；'
     u'（★ 第一版改的是飞行插值用的 `_vx0`，落地分支压根不读它 ⇒ 变异对断言不可见，'
     u'  报出来像"判据不灵"，其实是变异体没打到点上）'),

    (u'M15 无害变异：只在一行注释里加字（一条都不许红）',
     u'        # 计算水平速度',
     u'        # 计算水平速度（第166轮：锁存值）',
     None,
     u'没有破坏行为 ⇒ 判据必须全绿，否则就是"改个注释也报红"的假红'),
]


def sha1_of(path):
    with open(path, 'rb') as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def read_text(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write_text(path, txt):
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(txt)


def run_check(src_dir, mod_root):
    env = dict(os.environ)
    env['CQ_SRC_DIR'] = src_dir
    env['CQ_MOD_DIR'] = mod_root
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    p = subprocess.run([PY, CHECK], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def failed_lines(out):
    return [ln for ln in out.splitlines() if ln.startswith('[FAIL]')]


def _drop_pycache(root):
    for cur, dirs, _files in os.walk(root):
        for d in list(dirs):
            if d == '__pycache__':
                shutil.rmtree(os.path.join(cur, d), ignore_errors=True)
                dirs.remove(d)


def main():
    for need in (MAIN, CHECK):
        if not os.path.isfile(need):
            print(u'缺文件：%s' % need)
            return 1

    prod = {p: sha1_of(p) for p in (MAIN,)}
    text = read_text(MAIN)
    crlf = '\r\n' in text

    tmp = tempfile.mkdtemp(prefix='mutate166_')
    src_dir = os.path.join(tmp, 'src')
    mod_root = os.path.join(tmp, 'mod')
    try:
        os.makedirs(src_dir)
        os.makedirs(mod_root)
        shutil.copy2(MAIN, os.path.join(src_dir, 'main.py'))
        shutil.copytree(MOD_DIR, os.path.join(mod_root, 'modules'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        #   ★ `project_root` = `dirname(dirname(main.py))` ⇒ 副本里也要有 assets 骨架，
        #     否则产品的档案读取器取到空表（第165轮踩过：基线就红，与产品无关）
        os.makedirs(os.path.join(tmp, 'assets', 'npc'))
        _prof = os.path.join(PET, 'assets', 'npc', '_motion_profile.json')
        if os.path.isfile(_prof):
            shutil.copy2(_prof, os.path.join(tmp, 'assets', 'npc', '_motion_profile.json'))
        copy_main = os.path.join(src_dir, 'main.py')

        print('=' * 66)
        print(u'基线：未变异的副本必须全绿')
        print('=' * 66)
        rc, out = run_check(src_dir, mod_root)
        base_fail = failed_lines(out)
        print(u'  rc=%d  失败 %d 条' % (rc, len(base_fail)))
        if rc != 0 or base_fail:
            print(u'  [ABORT] 基线都不绿，后面的变异结果没有意义：')
            for ln in base_fail[:10]:
                print('    ' + ln)
            return 1

        bad = []
        for i, (name, find, repl, want, why) in enumerate(MUTATIONS, 1):
            # ★ 锚点归一：main.py 是 CRLF，多行锚点统一按实际行尾换算，
            #   否则"命中 0 次"会被误读成判据不灵（第164轮同型坑）
            _find = find.replace('\n', '\r\n').replace('\r\r\n', '\r\n') if crlf else find
            _repl = repl.replace('\n', '\r\n').replace('\r\r\n', '\r\n') if crlf else repl
            n = text.count(_find)
            print('')
            print(u'[%d] %s' % (i, name))
            if n != 1:
                print(u'  [ABORT] 锚点命中 %d 次（要求恰好 1 次）—— 改代码后必须同步改变异体' % n)
                bad.append(name)
                continue
            write_text(copy_main, text.replace(_find, _repl))
            _drop_pycache(mod_root)
            rc, out = run_check(src_dir, mod_root)
            write_text(copy_main, text)           # 立刻还原副本
            _drop_pycache(mod_root)

            fails = failed_lines(out)
            print(u'    原因：%s' % why)
            print(u'    rc=%d  失败 %d 条' % (rc, len(fails)))
            for ln in fails[:6]:
                print('      ' + ln[:110])
            if want is None:
                if fails:
                    print(u'  [FAIL] 无害变异也报红 ⇒ 判据假红（改注释就报警）')
                    bad.append(name)
                else:
                    print(u'  [PASS] 无害变异不报红（判据没在扫注释）')
                continue
            hit = [ln for ln in fails if want in ln]
            if rc == 0 or not fails:
                print(u'  [FAIL] 变异体**没被抓住**（判据是空的）')
                bad.append(name)
            elif not hit:
                print(u'  [FAIL] 红了但不是预期那条（红错地方 = 判据过窄/串味）')
                bad.append(name)
            else:
                print(u'  [PASS] 被抓：%s' % hit[0][:90])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print('')
    print('=' * 66)
    print(u'还原校验（产品文件必须在整个过程中字节级未变）')
    print('=' * 66)
    for p in (MAIN,):
        now = sha1_of(p)
        if now != prod[p]:
            print(u'  [FAIL] %s 被改动了！%s != %s' % (os.path.basename(p), now, prod[p]))
            return 1
        print(u'  [PASS] %-22s sha1 %s' % (os.path.basename(p), now[:12]))

    print('')
    print('=' * 66)
    if bad:
        print(u'[FAIL] 变异测试未全通过：%d/%d 个变异体有问题' % (len(bad), len(MUTATIONS)))
        for b in bad:
            print(u'  - %s' % b)
        return 1
    print(u'[PASS] 第166轮变异测试：%d/%d 个变异体全部被抓，且红的都是预期判据'
          % (len(MUTATIONS), len(MUTATIONS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
