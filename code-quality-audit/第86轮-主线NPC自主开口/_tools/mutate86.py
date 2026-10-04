# -*- coding: utf-8 -*-
u"""第86轮鉴别力体检（mutation check）—— **判据本身也是被测物**。

为什么要它（本项目 §59.6 / §60.4 / §62.9 / §65 的老账）：
  第62~70 轮**每一轮都有"判据侧栽跟头、产物侧零错"**的记录
  —— 有一条判据的名字写着"35 条"、实测 70 条却照样 PASS。
  ⇒ 光看 `check86` 全绿**不足以**证明它真的在守；必须**故意把破坏写进去**，
     看它到底报不报红。

做法（★ 只碰**副本**，绝不动被测原文件）：
  ① 读原文件（npc_life.py / main.py）
  ② 把"破坏"字符串替换进去（每条破坏**必须先断言真的落进去了** —— 否则
     破坏没写进去 ⇒ 报绿也说明不了什么，那就是"夹具不保真 = 报假问题"）
  ③ 写进 `E:/Download/_tmp86_mut/<case>/`（★ **临时区绝不放工作区**：
     `git add -A` 会把它们记成删除并提交，第40轮踩过）
  ④ 以该目录为 ROOT 跑一份**改写过路径的** check86 ⇒ 期望**必报红**
  ⑤ 还原 ⇒ 期望**零 FAIL**（正/负控制成对）

★★★ 本轮特别记的坑（第85轮踩的，别再踩）：
  `_run_check` **必须跑 `case_root` 里那份脚本**，不能跑工作区那份 ——
  否则脚本的 `HERE = dirname(__file__)` 仍指工作区 ⇒ `ROOT` 算回工作区 ⇒
  读到的是**没被破坏**的原文件 ⇒ 每条破坏都"FAIL=0"（症状是**全绿**，最危险）。

★ 打印纪律：`print('[PASS] %s')` 字面量；判据名里**不带** `[PASS]` 标记。
"""
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
CHECK = os.path.join(HERE, 'check86.py')

PY = sys.executable
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TMP = os.environ.get('M86_TMP', 'E:/Download/_tmp86_mut')

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
    'modules/npc_life.py': _read(os.path.join(MODS, 'npc_life.py')),
    'src/main.py': _read(MAIN),
}

#: 每一条 = (用例名, 相对路径, 原文片段, 替换片段, **期望哪个判据名里的关键词报红**)
#:
#: ★★ 期望关键词必须**逐字**出现在 check86 的判据串里 ——
#:    这样"报红"才能被归因到**这一条**破坏，而不是"反正红了一条"。
MUTATIONS = [
    (
        u'纯竖直位移又编左右（把 where_of 的 None 分支删掉）',
        'modules/npc_life.py',
        "    if ax < (ay * HORIZ_RATIO):\n        return None\n"
        "    return 'left' if dx < 0 else 'right'",
        "    return 'left' if dx < 0 else 'right'",
        u'纯竖直',
    ),
    (
        u'说话者自己没被剔除（presence_hint 漏剔）',
        'modules/npc_life.py',
        '        if not o or o == sid or o in seen:',
        '        if not o or o in seen:',
        u'说话者',
    ),
    (
        u'空名单也硬产一行（presence_hint 不再返回 ""）',
        'modules/npc_life.py',
        '    if not seen:\n        return \'\'',
        '    if not seen:\n        return u\'【此刻这里还有谁】\'',
        u'无别人',
    ),
    (
        u'归属泄露：提示尾巴里把"是哪个版本不知道"删掉（模型开始瞎猜归属）',
        'modules/npc_life.py',
        u"            + '。（只知道他叫什么、大概在哪个方位 —— 他是哪里来的、是哪个版本，'\n"
        u"              '你并不知道，也别去猜。）')",
        u"            + '。')",
        u'\u7248\u672c',
    ),
    (
        u'主线不再走 npc_speak（另起一条裸路径）',
        'src/main.py',
        '            sent = self.npc_speak(speaker, \'\', _on_reply)',
        '            sent = False  # 假装调了',
        u'npc_speak',
    ),
    (
        u'失败不 abort（主线一报错就永久 busy，生活线卡死）',
        'src/main.py',
        '        if not sent:\n'
        '            # 明确拒绝（模型不可用 / 人设缺失…）⇒ **必须解锁**，否则节拍器卡死。\n'
        '            loop.abort(now)',
        '        if not sent:\n'
        '            # 明确拒绝（模型不可用 / 人设缺失…）⇒ **必须解锁**，否则节拍器卡死。\n'
        '            pass',
        u'abort',
    ),
    (
        u'_npc_main_ids 不再要求人设（没设定的人也开口）',
        'src/main.py',
        '                if not self.npc_persona_of(nid):\n'
        '                    continue\n'
        '                out.append(nid)',
        '                out.append(nid)',
        u'\u4eba\u8bbe',
    ),
    (
        u'_npc_main_ids 不再查模型可用（没模型也选，一路 abort）',
        'src/main.py',
        '            if not self._npc_ai_available():\n'
        '                return []\n'
        '        except Exception:\n'
        '            return []\n'
        '        out = []',
        '            pass\n'
        '        except Exception:\n'
        '            return []\n'
        '        out = []',
        u'\u6a21\u578b\u53ef\u7528',
    ),
    (
        u'让路闸被摘掉（NPC 跟用户抢那唯一的模型实例）',
        'src/main.py',
        '                gate=self._npc_life_gate)',
        '                gate=None)',
        u'\u6ce8\u5165\u5230 loop',
    ),
    (
        u'接线断掉：`life=` 不再进 build_system_prompt（写了没人用）',
        'src/main.py',
        'life=self._npc_life_blocks(npc_id)',
        'life=\'\'',
        u'build_system_prompt',
    ),
]

#: 破坏后必须由 check86 报红的**期望关键词**（上表最后一项）—— 去重
_EXPECT_ALL = sorted(set(m[4] for m in MUTATIONS))


def _check_script_in(root_dir):
    """取 root_dir 下那份 check86.py 的路径。"""
    return os.path.join(root_dir, 'code-quality-audit',
                        u'\u7b2c86\u8f6e-\u4e3b\u7ebfNPC\u81ea\u4e3b\u5f00\u53e3',
                        '_tools', 'check86.py')


def _run_check(root_dir):
    """在**改写过的 ROOT** 下跑 check86，返回 (pass数, fail数, 输出文本)。

    ★★★ **必须跑 `root_dir` 里那份脚本**（第85轮踩的坑）：
        跑工作区那份 ⇒ `HERE` 指工作区 ⇒ `ROOT` 算回工作区 ⇒ 读到的是
        **没被破坏**的原文件 ⇒ 每条破坏都"FAIL=0"（症状是**全绿**）。
    """
    script = _check_script_in(root_dir)
    if not os.path.exists(script):
        return None, None, u'<no check86 in %s>' % root_dir
    out = subprocess.run(
        [PY, '-X', 'utf8', script],
        cwd=root_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = out.stdout.decode('utf-8', 'replace')
    m = re.search(r'PASS=(\d+) FAIL=(\d+)', txt)
    if not m:
        return None, None, txt
    return int(m.group(1)), int(m.group(2)), txt


def _install_case(case_name, mut):
    """把一条破坏装进临时区，返回 (临时 ROOT, 破坏串命中数)。"""
    rel, old, new = mut[1], mut[2], mut[3]
    case_root = os.path.join(TMP, case_name)
    r86_src = os.path.join(ROOT, 'code-quality-audit',
                           u'\u7b2c86\u8f6e-\u4e3b\u7ebfNPC\u81ea\u4e3b\u5f00\u53e3')
    r86_dst = os.path.join(case_root, 'code-quality-audit',
                           u'\u7b2c86\u8f6e-\u4e3b\u7ebfNPC\u81ea\u4e3b\u5f00\u53e3')
    dst_tools = os.path.join(r86_dst, '_tools')
    if not os.path.isdir(dst_tools):
        os.makedirs(dst_tools)
    # ① _tools（脚本本体；★ 必须跑这一份）
    shutil.copy2(CHECK, os.path.join(dst_tools, 'check86.py'))
    # ② 被测两份源文件
    for rp, src in _ORIG.items():
        _write(os.path.join(case_root, 'ralsei_pet',
                            rp.replace('/', os.sep)), src)
    # ③ 落破坏
    tgt = os.path.join(case_root, 'ralsei_pet', rel.replace('/', os.sep))
    cur = _read(tgt)
    hits = cur.count(old)
    if hits != 1:
        return None, hits
    _write(tgt, cur.replace(old, new, 1))
    return case_root, 1


print(u'# ===== 第86轮鉴别力体检（破坏 ⇒ 必报红；还原 ⇒ 零 FAIL）=====')
print(u'临时区：%s' % TMP)
check(u'\u2605 被测原文件快照齐（2 份，且非空）',
      all(len(v) > 1000 for v in _ORIG.values()), star=True)

# --------------------------------------------------------------- 基座正控制①
_bpass, _bfail, _btxt = _run_check(ROOT)
check(u'\u2605\u2605 基座正控制①：**工作区**上 check86 全绿（PASS=%s FAIL=%s）'
      % (_bpass, _bfail),
      _bfail == 0 and (_bpass or 0) > 55, star=True)

# --------------------------------------------------------------- 基座正控制②
# ★★ 关键：证明"临时区夹具"本身不会让 check86 假红
_base_case, _bh = _install_case('base', (
    u'无破坏基座', 'modules/npc_life.py', 'MIN_TALKERS = 2',
    'MIN_TALKERS = 2', u'__NEVER__'))
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
    check(u'[%s] 夹具保真：破坏串命中原文 1 处且已写入' % _name,
          _hits == 1, star=False)
    _p, _f, _t = _run_check(_case_root)
    if _f is None:
        _crashed = 'Traceback (most recent call last)' in _t
        _kw_hit2 = _kw in _t
        check(u'\u2605\u2605 [%s] 破坏后 check86 **中断**（无汇总，实为真异常=%s / '
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
    'modules/npc_life.py',
    'MIN_TALKERS = 2',
    'MIN_TALKERS = 2  # harmless',
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
print()
print(u'=== 第86轮鉴别力体检：PASS=%d FAIL=%d ===' % (_passed, _failed))
sys.exit(0 if _failed == 0 else 1)
