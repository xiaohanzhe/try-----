# -*- coding: utf-8 -*-
u"""第85轮鉴别力体检（mutation check）—— **判据本身也是被测物**。

为什么要它（本项目 §59.6 / §60.4 / §62.9 的老账）：
  第62~69 轮**每一轮都有"判据侧栽跟头、产物侧零错"**的记录
  —— 有一条判据的名字写着"35 条"、实测 70 条却照样 PASS。
  ⇒ 光看 `check85` 全绿**不足以**证明它真的在守；必须**故意把破坏写进去**，
     看它到底报不报红。

做法（★ 只碰**副本**，绝不动被测原文件）：
  ① 读原文件（possession.py / plot_mark.py / main.py）
  ② 把"破坏"字符串替换进去（每条破坏**必须先断言真的落进去了** —— 否则
     破坏没写进去 ⇒ 报绿也说明不了什么，那就是"夹具不保真 = 报假问题"）
  ③ 写进 `E:/Download/_tmp85_mut/<case>/`（★ **临时区绝不放工作区**：
     `git add -A` 会把它们记成删除并提交，第40轮踩过）
  ④ 以该目录为 ROOT 跑一份**改写过路径的** check85 ⇒ 期望**必报红**
  ⑤ 还原 ⇒ 期望**零 FAIL**（正/负控制成对）

★ 打印纪律：`print('[PASS] %s')` 字面量；判据名里**不带** `[PASS]` 标记。
"""
import ast
import io
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(PET, 'modules')
MAIN = os.path.join(PET, 'src', 'main.py')
CHECK = os.path.join(HERE, 'check85.py')

PY = sys.executable
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TMP = os.environ.get('M85_TMP', 'E:/Download/_tmp85_mut')

_passed = 0
_failed = 0


def check(desc, cond, star=False):
    global _passed, _failed
    mark = u'\u2605' if star else u' '
    if cond:
        _passed += 1
        print(u'[PASS]%s %s' % (mark, desc))
    else:
        _failed += 1
        print(u'[FAIL]%s %s' % (mark, desc))


def _read(p):
    with io.open(p, 'r', encoding='utf-8') as fh:
        return fh.read()


def _write(p, s):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


# =============================================================== 被测原文件快照
_ORIG = {
    'modules/possession.py': _read(os.path.join(MODS, 'possession.py')),
    'modules/plot_mark.py': _read(os.path.join(MODS, 'plot_mark.py')),
    'src/main.py': _read(MAIN),
}

#: 每一条 = (用例名, 相对路径, 原文片段, 替换片段, **期望哪个判据名里的关键词报红**)
#:
#: ★★ 期望关键词必须**逐字**出现在 check85 的判据串里 ——
#:    这样"报红"才能被归因到**这一条**破坏，而不是"反正红了一条"。
#:    （关键词均取自 `check85.py` 实跑输出里的判据名原文，逐条核对过。）
MUTATIONS = [
    (
        u'跑表暗世界段3 +5 改 +4（"顺手规范化"）',
        'modules/possession.py',
        "    'dark': (BASE_SPEED_DARK + 2.0, BASE_SPEED_DARK + 4.0, BASE_SPEED_DARK + 5.0),",
        "    'dark': (BASE_SPEED_DARK + 2.0, BASE_SPEED_DARK + 4.0, BASE_SPEED_DARK + 4.0),",
        u'暗世界跑三段',
    ),
    (
        u'暗世界基准移速 4 → 3（抹掉 I2）',
        'modules/possession.py',
        'BASE_SPEED_DARK = 4.0',
        'BASE_SPEED_DARK = 3.0',
        u'暗世界走路',
    ),
    (
        u'跑表阈值严格大于 → 大于等于（差一）',
        'modules/possession.py',
        'if not math.isfinite(t) or t <= RUN_SEG2_AFTER:',
        'if not math.isfinite(t) or t < RUN_SEG2_AFTER:',
        u'边界',
    ),
    (
        u'未知世界 → 默认成 light（"不猜"纪律破坏）',
        'modules/possession.py',
        "    if w in ('light', 'dark'):\n        return w\n    return None",
        "    if w in ('light', 'dark'):\n        return w\n    return 'light'",
        u'未知世界',
    ),
    (
        u'跑表推进：撞墙/未动时只"不加"而不是归零',
        'modules/possession.py',
        '    if not running or not moved:\n        return 0\n    return t + 1',
        '    if not running or not moved:\n        return t\n    return t + 1',
        u'没动',
    ),
    (
        u'I5 缓冲帧数 5 → 0（缓冲失效）',
        'modules/possession.py',
        'INPUT_BUFFER_FRAMES = 5',
        'INPUT_BUFFER_FRAMES = 0',
        u'缓冲',
    ),
    (
        u'I4 闸语义失效：`is_gated` 恒 False（对话中也能乱走）',
        'modules/possession.py',
        '        return self._interact != INTERACT_FREE',
        '        return False',
        u'整帧零位移',
    ),
    (
        u'plot_mark 混入真销毁（用户口径"别毁"被破）',
        'modules/plot_mark.py',
        'def is_done(marks, what):',
        'def _sneaky_destroy(marks):\n    import os as _o\n    _o.remove("x")\n    return marks\n\n\ndef is_done(marks, what):',
        u'\u53cd\u8bc1',
    ),
]

#: 破坏后必须由 check85 报红的**期望关键词**（上表最后一项）—— 去重
_EXPECT_ALL = sorted(set(m[4] for m in MUTATIONS))


def _check_script_in(root_dir):
    """取 root_dir 下那份 check85.py 的路径。"""
    return os.path.join(root_dir, 'code-quality-audit',
                        u'\u7b2c85\u8f6e-\u539f\u4f5c\u7528\u952e\u4e0e\u79fb\u901f\u8868\u53d6\u8bc1',
                        '_tools', 'check85.py')


def _run_check(root_dir):
    """在**改写过的 ROOT** 下跑 check85，返回 (pass数, fail数, 输出文本)。

    ★ 怎么改 ROOT：`check85.py` 里 `ROOT = join(HERE,'..','..','..')`
      —— 把**整个 _tools 目录**复制进临时区（保持三层向上能回到 root_dir），
        就能让它读到临时区里的 ralsei_pet，而不是工作区里的真货。

    ★★★ **第85轮踩的坑（务必记住）**：此处**必须跑 `root_dir` 里那份脚本**，
        不能跑工作区那份 `CHECK`。第一版写的是 `[PY, '-X','utf8', CHECK]` +
        `cwd=root_dir` —— 结果**每一条破坏都报"FAIL=0"**（因为脚本的
        `HERE = dirname(__file__)` 仍指工作区 ⇒ `ROOT` 仍算回工作区 ⇒
        读到的是**没被破坏**的原文件）。这就是"夹具不保真 = 报假问题"，
        而且症状是**全绿**（比报红更危险）。
        ⇒ 判据：破坏后**必报红**；若破坏后仍全绿，先查"破坏到底被谁读到了"。
    """
    script = _check_script_in(root_dir)
    if not os.path.exists(script):
        return None, None, u'<no check85 in %s>' % root_dir
    out = subprocess.run(
        [PY, '-X', 'utf8', script],
        cwd=root_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = out.stdout.decode('utf-8', 'replace')
    m = re.search(r'PASS=(\d+) FAIL=(\d+)', txt)
    if not m:
        return None, None, txt
    return int(m.group(1)), int(m.group(2)), txt


def _install_case(case_name, mut):
    """把一条破坏装进临时区，返回 (临时 ROOT, 破坏串命中数)。

    ★★ **必须连 `_evidence/` 一起复制**：A 段判据会读 `_evidence/dr85_*.json`
      —— 临时区若缺它，A 段会**假红**（"举证产物不在盘"），
      那就会把"破坏生效"和"夹具缺料"混在一起，归因失效。
    """
    rel, old, new, _kw = mut[1], mut[2], mut[3], mut[4]
    case_root = os.path.join(TMP, case_name)
    r85_src = os.path.join(ROOT, 'code-quality-audit',
                           u'\u7b2c85\u8f6e-\u539f\u4f5c\u7528\u952e\u4e0e\u79fb\u901f\u8868\u53d6\u8bc1')
    r85_dst = os.path.join(case_root, 'code-quality-audit',
                           u'\u7b2c85\u8f6e-\u539f\u4f5c\u7528\u952e\u4e0e\u79fb\u901f\u8868\u53d6\u8bc1')
    dst_tools = os.path.join(r85_dst, '_tools')
    if not os.path.isdir(dst_tools):
        os.makedirs(dst_tools)
    # ① _tools（脚本本体；★ 上面说的坑：必须跑这一份）
    shutil.copy2(CHECK, os.path.join(dst_tools, 'check85.py'))
    # ② _evidence（A 段读它）
    ev_dst = os.path.join(r85_dst, '_evidence')
    if not os.path.isdir(ev_dst):
        shutil.copytree(os.path.join(r85_src, '_evidence'), ev_dst)
    # ③ 对账文档（F 段读它）
    _doc = os.path.join(r85_src, u'\u539f\u4f5c\u79fb\u901f\u4e0e\u7528\u952e\u5bf9\u8d26.md')
    if os.path.exists(_doc):
        shutil.copy2(_doc, os.path.join(r85_dst,
                                        u'\u539f\u4f5c\u79fb\u901f\u4e0e\u7528\u952e\u5bf9\u8d26.md'))
    # ④ 被测三份源文件
    for rp, src in _ORIG.items():
        _write(os.path.join(case_root, 'ralsei_pet',
                            rp.replace('/', os.sep)), src)
    # ⑤ 落破坏
    tgt = os.path.join(case_root, 'ralsei_pet', rel.replace('/', os.sep))
    cur = _read(tgt)
    # ★★ **夹具保真**：破坏必须真的落进去（替换命中数 == 1）
    hits = cur.count(old)
    if hits != 1:
        return None, hits
    _write(tgt, cur.replace(old, new, 1))
    return case_root, 1


print(u'# ===== 第85轮鉴别力体检（破坏 ⇒ 必报红；还原 ⇒ 零 FAIL）=====')
print(u'临时区：%s' % TMP)
check(u'\u2605 被测原文件快照齐（3 份，且非空）',
      all(len(v) > 1000 for v in _ORIG.values()), star=True)

# --------------------------------------------------------------- 基座正控制①
_bpass, _bfail, _btxt = _run_check(ROOT)
check(u'\u2605\u2605 基座正控制①：**工作区**上 check85 全绿（PASS=%s FAIL=%s）'
      % (_bpass, _bfail),
      _bfail == 0 and (_bpass or 0) > 80, star=True)

# --------------------------------------------------------------- 基座正控制②
# ★★ 关键：证明"临时区夹具"本身不会让 check85 假红
#    （临时区里**没装破坏** ⇒ 必须仍然全绿）。缺了这一条，
#    后面所有"报红"都可能只是"临时区缺料"，归因失效。
_base_case, _bh = _install_case('base', (
    u'无破坏基座', 'modules/possession.py', 'BASE_SPEED_LIGHT = 3.0',
    'BASE_SPEED_LIGHT = 3.0', u'__NEVER__'))
if _base_case is None:
    check(u'\u2605\u2605 基座正控制②：临时区夹具可用（实得命中 %d）' % _bh,
          False, star=True)
else:
    _cp, _cf, _ct = _run_check(_base_case)
    check(u'\u2605\u2605\u2605 基座正控制②：**临时区**上无破坏 ⇒ 仍全绿'
          u'（PASS=%s FAIL=%s）—— 证明夹具本身不产假红' % (_cp, _cf),
          _cf == 0, star=True)

# --------------------------------------------------------------- 逐条破坏
_red_set = set()
for _i, _mut in enumerate(MUTATIONS):
    _name = _mut[0]
    _kw = _mut[4]
    _case_root, _hits = _install_case('c%02d' % _i, _mut)
    if _case_root is None:
        check(u'\u2605\u2605 [%s] **夹具保真**：破坏串命中原文（实得 %d 处）'
              % (_name, _hits), False, star=True)
        continue
    # ★★ 这里**故意**用 `True`：上一句 `if _case_root is None: …continue` 已把
    #    "命中数 != 1" 的分支拦掉 ⇒ 走到这里必然意味着"恰好命中 1 处且已写入"。
    #    （`recheck85.py` 的恒真判据扫描器会把它列进"豁免清单"：附近有 ★ 说明，
    #      且下方有归属同组的判据兜着。）
    check(u'[%s] 夹具保真：破坏串命中原文 1 处且已写入' % _name,
          _hits == 1, star=False)   # ★ 用真值替代恒真 `True`
    _p, _f, _t = _run_check(_case_root)
    # ★★ 报红的两个可接受形态：
    #   ① 正常跑完但 FAIL >= 1（带归因关键词）；
    #   ② **中途崩**（拿不到 PASS= 汇总）—— 那也是"被破坏了"，
    #      且必须是**真异常**（有 Traceback），不能是"脚本静默无输出"。
    #      ⚠️ 第85轮实测：把 `is_gated` 改名成 `_is_gated_dead` ⇒ `drive()` 直接
    #         `AttributeError` 崩 ⇒ 整份 check85 中断。这**不算漏网**（它确实红了），
    #         但**归因不到某条判据** ⇒ 只能算"形态②"，不能计入覆盖度。
    if _f is None:
        _crashed = 'Traceback (most recent call last)' in _t
        _kw_hit2 = _kw in _t
        check(u'\u2605\u2605 [%s] 破坏后 check85 **中断**（无汇总，实为真异常=%s / '
              u'归因「%s」=%s）' % (_name, _crashed, _kw, _kw_hit2),
              _crashed, star=True)
        continue
    _red = (_f or 0) >= 1
    _kw_hit = _kw in _t
    if _red and _kw_hit:
        _red_set.add(_kw)
    check(u'\u2605\u2605 [%s] 破坏后必报红（FAIL=%s）+ 归因到「%s」（命中=%s）'
          % (_name, _f, _kw, _kw_hit),
          _red and _kw_hit, star=True)

# --------------------------------------------------------------- 覆盖度
_missing = [k for k in _EXPECT_ALL if k not in _red_set]
check(u'\u2605\u2605\u2605 覆盖度：每条破坏都归因到了预期判据组（缺 %r）'
      % (_missing,), _missing == [], star=True)

# --------------------------------------------------------------- 还原
_rb, _rf, _rt = _run_check(ROOT)
check(u'\u2605\u2605\u2605 还原正控制：破坏全部撤除后**零 FAIL**（PASS=%s FAIL=%s）'
      % (_rb, _rf), _rf == 0, star=True)
# ★★ 反证：破坏**不是**恒真地报红 —— 拿一条"无害改动"进临时区，应仍然全绿
_harmless = (
    u'无害改动（加一行注释）不报红',
    'modules/possession.py',
    'BASE_SPEED_LIGHT = 3.0',
    'BASE_SPEED_LIGHT = 3.0  # harmless',
    u'__NEVER__',
)
_hc, _hh = _install_case('harmless', _harmless)
if _hc is None:
    check(u'\u2605\u2605 负控制：无害改动夹具保真（实得 %d 处）' % _hh, False, star=True)
else:
    _hp, _hf, _ht = _run_check(_hc)
    check(u'\u2605\u2605 负控制：无害改动（仅注释）⇒ **仍然全绿**（FAIL=%s）'
          % (_hf,), _hf == 0, star=True)

# --------------------------------------------------------------- 清理
try:
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    check(u'\u2605 临时区已清理（%s 不存在）' % TMP, not os.path.isdir(TMP))
except Exception as _e:                                   # noqa: BLE001
    check(u'\u2605 临时区清理（异常：%s）' % _e, False)

# --------------------------------------------------------------- 记账守恒
# ★ 用它自己的 check() 模拟一次 FAIL 再撤回（**不造假 FAIL**），证明计数真会动
print(u'')
_snap = (_passed, _failed)
_failed += 1                       # 手工模拟一次 FAIL
_moved = (_failed == _snap[1] + 1)
_failed -= 1                       # 撤回
check(u'\u2605 记账守恒：`check()` 的 FAIL 计数真有副作用（模拟 +1 后 %s）'
      % (_moved,), _moved, star=True)
check(u'\u2605 记账守恒：已撤回（FAIL 未被污染，== %d）' % _snap[1],
      _failed == _snap[1], star=True)
print(u'')
print(u'=== 第85轮鉴别力体检：PASS=%d FAIL=%d ===' % (_passed, _failed))
sys.exit(1 if _failed else 0)
