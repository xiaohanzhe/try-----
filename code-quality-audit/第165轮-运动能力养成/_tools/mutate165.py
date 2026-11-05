# -*- coding: utf-8 -*-
u"""第165轮 · 变异测试：证明 `check165` 的判据**真的会红**。

## 为什么非要有这个

`check165` 全绿只说明"当前没坏"，**不说明"坏了会被发现"**。
本项目反复栽在"判据绿着，但守的是空气"上（恒真 / 判据过窄 / 桩比产品旧），
本轮第一版 `check165` 就有两条恒真（E4 恒绿、E5 恒假），正好互相掩护。

## 铁律（与 `mutate164.py` 同源）

1. **绝不改产品文件**：把 `src/main.py` 与整个 `modules/` 复制到临时目录，
   用 `CQ_SRC_DIR` / `CQ_MOD_DIR` 喂给套件，改的永远是副本。
2. **每个变异体只改一处**，且锚点必须**恰好命中 1 次**（禁止 `replace(...,1)`
   掩盖"锚点已经不存在了"——那样变异测试会用"锚点找不到"冒充"通过"）。
3. 变异体必须**语法正确** —— 考验的是判据，不是 `SyntaxError`。
4. 每个变异体都要断言"**确实红了**"且"**红的是我预期的那些**"。
5. 跑完全部变异体后，产品文件必须**字节级未变**（sha1 校验）。
6. ⚠️ 副本里 `PYTHONDONTWRITEBYTECODE=1` 且删掉 `__pycache__`：
   否则同一秒内写入且大小相同的变异体会命中旧 `.pyc`，
   报出来的现象是"变异没生效 ⇒ 判据全绿 ⇒ 误判判据失灵"。
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
MOD = os.path.join(PET, 'modules', 'motion_profile.py')
PROFILE = os.path.join(PET, 'assets', 'npc', '_motion_profile.json')
CHECK = os.path.join(HERE, 'check165.py')
PY = sys.executable or r'C:\Python311\python.exe'

# (名字, 改哪个文件, 找什么, 换成什么, 必须变红的判据名片段, 为什么会红)
MUTATIONS = [
    # ---------------- 纯函数层：成长曲线与零回归的根 ----------------
    (u'M1 默认档 jump 抬到 1.05（零回归的根被打破）', 'module',
     u"DEFAULT_PROFILE = {\n    'jump': 1.0,",
     u"DEFAULT_PROFILE = {\n    'jump': 1.05,",
     u'A1',
     u'"没有档案 = 1.0"一破，所有没档案的人物立刻跳矮/跳高，旧行为不再逐值相同'),

    (u'M2 负数经验也给减（"不练会退步"）', 'module',
     u'    if a <= 0:\n        return e',
     u'    if a == 0:\n        return e',
     u'A5',
     u'用户没要求遗忘；一旦能减分，任何一次读坏档都会让人物变弱'),

    (u'M3 去掉经验封顶（会练成超人）', 'module',
     u'    return MAX_EXP if e > MAX_EXP else e',
     u'    return e',
     u'A6',
     u'不封顶 ⇒ 跑速迟早突破屏幕，且"满级"这件事失去定义'),

    (u'M4 成长率不参与成长（growth 变成摆设）', 'module',
     u"    mult = 1.0 + GAIN_PER_LEVEL * p['growth'] * lv",
     u'    mult = 1.0 + GAIN_PER_LEVEL * lv',
     u'A8',
     u'用户点名的"进步速度不同"直接失效 —— 全员涨得一样快'),

    (u'M5 越界不钳（手写档案写错就把产品带飞）', 'module',
     u'def _clamp(v, lo, hi):\n    return lo if v < lo else (hi if v > hi else v)',
     u'def _clamp(v, lo, hi):\n    return v',
     u'A3',
     u'档案是手写的，`jump: 99` 这种笔误必须被钳回来而不是直接乘进物理量'),

    (u'M6 等级阈值翻倍（练 240 点还不升级）', 'module',
     u'    lv = int(e // LEVEL_STEP)',
     u'    lv = int(e // (LEVEL_STEP * 2))',
     u'A4',
     u'升级点漂移 ⇒ "满级 100 次起跳"这个可解释的设计作废'),

    (u'M7 校验器不查 why（"有值"就算合格）', 'module',
     u'    if not isinstance(why, str) or not why.strip():',
     u'    if False:',
     u'A11',
     u'用户选的是"每人落值 + 标依据等级"⇒ 没有依据的数值就是编的'),

    (u'M8 校验器不查 evidence 三档', 'module',
     u'    if ev not in EVIDENCE_LEVELS:',
     u'    if False:',
     u'A12',
     u'依据等级随便填 ⇒ 三档形同虚设，也就没法审"谁是无据的"'),

    # ---------------- 接线层：倍率到底有没有接上去 ----------------
    (u'M9 起跳闸门不乘 jump 倍率（练了也够不着）', 'main',
     u"            _limit *= self._motion_eff()['jump']",
     u'            _limit *= 1.0',
     u'C4',
     u'整个模块就白装了：练满级还是被同一条 700 的线拒掉'),

    (u'M10 冲刺上限不乘 run 倍率', 'main',
     u"        _cap = RUNUP_SPEED_MAX * self._motion_eff()['run']",
     u'        _cap = RUNUP_SPEED_MAX',
     u'C5b',
     u'跑得快也跳不远 ⇒ 只有一半能力接上了'),

    (u'M11 走路速度也乘 run 倍率（手感随练习变）', 'main',
     u"        _base = float(getattr(self, 'max_speed', 15.0) or 15.0) / dt",
     u"        _base = float(getattr(self, 'max_speed', 15.0) or 15.0) / dt * self._motion_eff()['run']",
     u'D4b',
     u'用户只要"练得能跳"，没要"走得越来越快"；且 max_speed 被 19 个套件引用'),

    (u'M12 成功起跳按失败权重记账（撞墙更划算那条回来了）', 'main',
     u"                'jump_ok': motion_profile_mod.EXP_JUMP_OK,",
     u"                'jump_ok': motion_profile_mod.EXP_JUMP_FAIL,",
     u'C6',
     u'12:3 的比值是"成功才值得"的全部依据，掉了就变成鼓励撞墙'),

    (u'M13 练完不失效倍率缓存（练了白练）', 'main',
     u'                    self._motion_eff_cache = None      # ★ 练了就重算，否则涨了不生效',
     u'                    pass',
     u'C6d',
     u'经验涨了倍率照旧 —— 界面上一切正常，就是练不动（哑巴 bug 的典型形态）'),

    (u'M14 落盘不写 NPC 表（NPC 练完就忘）', 'main',
     u"                'npcs': {k: round(float(v), 3)",
     u"                'npcs': {k: 0.0 for k in ()",
     u'C7',
     u'NPC 的运动能力只在内存里活着，重启归零 ⇒ "两边都接"只接了一半'),

    (u'M15 读档不读 NPC 表', 'main',
     u"            table = raw.get('npcs')",
     u"            table = raw.get('npcs_v2')",
     u'C7',
     u'写得进读不出（同样是"只接一半"，但故障点落在读侧）'),
]


def sha1_of(path):
    with open(path, 'rb') as fh:
        return hashlib.sha1(fh.read()).hexdigest()


def read_text(path):
    """按字节忠实读（`newline=''`），并报告它用的是不是 CRLF。"""
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        txt = fh.read()
    return txt, ('\r\n' in txt)


def write_text(path, txt):
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(txt)


def run_check(src_dir, mod_root):
    env = dict(os.environ)
    env['CQ_SRC_DIR'] = src_dir
    env['CQ_MOD_DIR'] = mod_root
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONDONTWRITEBYTECODE'] = '1'      # ★ 见文件头第 6 条
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
    for need in (MAIN, MOD, PROFILE, CHECK):
        if not os.path.isfile(need):
            print(u'缺文件：%s' % need)
            return 1

    prod = {p: sha1_of(p) for p in (MAIN, MOD, PROFILE)}
    orig = {}
    is_crlf = {}
    for p in (MAIN, MOD):
        orig[p], is_crlf[p] = read_text(p)

    tmp = tempfile.mkdtemp(prefix='mutate165_')
    src_dir = os.path.join(tmp, 'src')
    mod_root = os.path.join(tmp, 'mod')
    try:
        # ---- 搭一个最小可信的"项目根"：src/main.py + modules/ + 只那份档案 ----
        os.makedirs(src_dir)
        os.makedirs(mod_root)
        shutil.copy2(MAIN, os.path.join(src_dir, 'main.py'))
        shutil.copytree(os.path.join(PET, 'modules'), os.path.join(mod_root, 'modules'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        os.makedirs(os.path.join(tmp, 'assets', 'npc'))
        shutil.copy2(PROFILE, os.path.join(tmp, 'assets', 'npc', '_motion_profile.json'))
        #   ★ `project_root` = `dirname(dirname(main.py))` ⇒ 必须在 tmp 下放
        #     `assets/npc/_motion_profile.json`，否则产品的档案读取器取到空表，
        #     C3b 在**基线**就红（那是夹具问题，不是产品问题）。
        copy_main = os.path.join(src_dir, 'main.py')
        copy_mod = os.path.join(mod_root, 'modules', 'motion_profile.py')

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
        for i, (name, target, find, repl, want, why) in enumerate(MUTATIONS, 1):
            path = copy_main if target == 'main' else copy_mod
            src_path = MAIN if target == 'main' else MOD
            text = orig[src_path]
            # ★ 锚点归一：main.py 是 CRLF、motion_profile.py 是 LF，
            #   多行锚点用 `\n` 写；这里按目标文件的实际行尾换算，
            #   否则"命中 0 次"会被误读成判据不灵。
            _find = find.replace('\n', '\r\n') if is_crlf[src_path] else find
            _repl = repl.replace('\n', '\r\n') if is_crlf[src_path] else repl
            n = text.count(_find)
            if n != 1:
                print('')
                print(u'[%d] %s' % (i, name))
                print(u'  [ABORT] 锚点命中 %d 次（要求恰好 1 次）—— 改代码后必须同步改变异体' % n)
                bad.append(name)
                continue
            write_text(path, text.replace(_find, _repl))
            _drop_pycache(mod_root)
            rc, out = run_check(src_dir, mod_root)
            # 立刻还原副本（下一个变异体要从干净副本出发）
            write_text(path, text)
            _drop_pycache(mod_root)

            fails = failed_lines(out)
            hit = [ln for ln in fails if want in ln]
            print('')
            print(u'[%d] %s' % (i, name))
            print(u'    预期变红：%s   原因：%s' % (want, why))
            print(u'    rc=%d  失败 %d 条' % (rc, len(fails)))
            for ln in fails[:6]:
                print('      ' + ln[:110])
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

    # ---- 还原校验：产品文件必须一个字节都没动 ----
    print('')
    print('=' * 66)
    print(u'还原校验（产品文件必须在整个过程中字节级未变）')
    print('=' * 66)
    for p in (MAIN, MOD, PROFILE):
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
    print(u'[PASS] 第165轮变异测试：%d/%d 个变异体全部被抓，且红的都是预期判据'
          % (len(MUTATIONS), len(MUTATIONS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
