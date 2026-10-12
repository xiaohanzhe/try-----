# -*- coding: utf-8 -*-
"""第112轮变异测试：证明本轮判据**真的有鉴别力**（不是恒真）。

★ 纪律（历轮血泪）：
  · **"夹具不保真 = 报假问题"**，**"夹具不破坏 = 全绿比报红更危险"** ⇒ 每个变异
    必须让**至少一条**判据报红；没报红的变异要么补判据、要么如实登记"判据不覆盖"。
  · 变异一律**改副本**（临时目录），**绝不改工作区真文件**。
  · 变异锚点**禁用 `replace(old,new,1)`**（`str.replace` 的 count=1 会打错位置）；
    一律用**唯一长锚点**并**断言只替换了 1 处**。
  · 跑完**必须还原**（用 `finally` 兜底 + 逐文件 sha256 回验）。

跑法：
    C:\\Python311\\python.exe mutate112.py
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PY = sys.executable if sys.executable else 'C:/Python311/python.exe'

REL = {
    'door_reveal': os.path.join('ralsei_pet', 'modules', 'door_reveal.py'),
    'niko_home': os.path.join('ralsei_pet', 'modules', 'niko_home.py'),
    'item_interact': os.path.join('ralsei_pet', 'modules', 'item_interact.py'),
    'desktop_json': os.path.join('ralsei_pet', 'assets', 'scenes', 'desktop.json'),
    'main': os.path.join('ralsei_pet', 'src', 'main.py'),
}


def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()


def read(p):
    return io.open(p, 'r', encoding='utf-8', newline='').read()


def write(p, s):
    io.open(p, 'w', encoding='utf-8', newline='').write(s)


def sub_once(text, old, new, tag):
    """只替换一次，且**断言恰好命中 1 处**（防 `replace(...,1)` 打错位置）。

    ★★★ CRLF 陷阱（本轮实证）：`main.py` 与 `item_interact.py` 是 **CRLF**；
    锚点里若写了 `\n` 而文件是 `\r\n` ⇒ **必然命中 0 次**。⇒ 这里做**换行无关**
    匹配：把锚点与文本都归一化后再定位，然后**在原文上按归一化位置换算**替换。
    简化实现：先试原样；不中则把锚点的 `\n` 换成 `\r\n` 再试。
    """
    variants = [old]
    if '\n' in old and '\r\n' not in old:
        variants.append(old.replace('\n', '\r\n'))
    for v in variants:
        if text.count(v) == 1:
            return text.replace(v, new.replace('\n', '\r\n') if '\r\n' in v else new, 1)
    n = text.count(old)
    raise AssertionError(u'[%s] 锚点命中 %d 次（应为 1）：%r' % (tag, n, old[:60]))


def run_check(timeout=300):
    """在**临时副本**上跑 check112（临时区 = 系统 temp，不污染工作区）。"""
    r = subprocess.run([PY, 'check112.py'], cwd=TMP_TOOLS,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    out = r.stdout.decode('utf-8', 'replace')
    return r.returncode, out


# ---------------------------------------------------------------------------
# 建临时副本树：把仓库**需要的部分**复制过去（全仓太大，只复制相关目录）
# ---------------------------------------------------------------------------
TMP = os.path.join(tempfile.gettempdir(), 'mutate112_tmp')
TMP_TOOLS = os.path.join(TMP, 'code-quality-audit',
                         u'第112轮-桌面门渐显', '_tools')

_orig_hash = {k: sha(os.path.join(ROOT, v)) for k, v in REL.items()}

if os.path.isdir(TMP):
    shutil.rmtree(TMP, ignore_errors=True)

# 复制 ralsei_pet（模块+src+资源）与本轮工具
shutil.copytree(os.path.join(ROOT, 'ralsei_pet'), os.path.join(TMP, 'ralsei_pet'))
os.makedirs(TMP_TOOLS)
for f in ('check112.py',):
    shutil.copy2(os.path.join(HERE, f), os.path.join(TMP_TOOLS, f))


def tpath(key):
    return os.path.join(TMP, REL[key])


print(u'==== mutate112 ====')
print(u'临时区 = %s' % TMP)

results = []


def mutate(tag, key, old, new, expect_red=True):
    """施加一个变异 ⇒ 跑 check112 ⇒ 记录是否报红 ⇒ **还原**。"""
    p = tpath(key)
    before = read(p)
    h_before = sha(p)
    try:
        after = sub_once(before, old, new, tag)
    except AssertionError as e:
        print(u'[SKIP] %s：%s' % (tag, e))
        results.append((tag, 'SKIP', ''))
        return
    write(p, after)
    try:
        rc, out = run_check()
        red = (rc != 0) or ('[FAIL]' in out)
        n_fail = out.count('[FAIL]')
        if expect_red:
            status = 'CAUGHT' if red else 'MISSED'
        else:
            status = 'OK(no-op)' if not red else 'UNEXPECTED-RED'
        print(u'[%s] %s  (FAIL=%d)' % (status, tag, n_fail))
        if status == 'MISSED':
            # 打印检查尾部，便于定位
            print(u'    ---- 末尾 ----')
            for ln in out.strip().splitlines()[-6:]:
                print(u'    ' + ln)
        results.append((tag, status, u'FAIL=%d' % n_fail))
    finally:
        write(p, before)
        assert sha(p) == h_before, u'还原失败: %s' % key


# ---------------------------------------------------------------------------
# M1: door_reveal 目标门白名单被扩大（把 A/B 也纳入 ⇒ 违背用户"oneshot 和 niko
#     的家不变"）
# ---------------------------------------------------------------------------
mutate(u'M1 白名单扩到 A/B（违背"只 UT/符文"）',
       'door_reveal',
       "REVEAL_DOORS = (('desktop', 'C'), ('desktop', 'D'))",
       "REVEAL_DOORS = (('desktop', 'A'), ('desktop', 'B'),"
       " ('desktop', 'C'), ('desktop', 'D'))")

# ---------------------------------------------------------------------------
# M2: MIN_ALPHA 改成 0（用户要的是"透明到实象"但保留可发现性 ⇒ 0 = 找不到门）
# ---------------------------------------------------------------------------
mutate(u'M2 MIN_ALPHA 改 0（门会彻底看不见）',
       'door_reveal',
       'MIN_ALPHA = 0.14',
       'MIN_ALPHA = 0.0')

# ---------------------------------------------------------------------------
# M3: ease 改成恒等（去掉"从虚到实的**过渡**"，退化成线性/突变手感）
# ---------------------------------------------------------------------------
mutate(u'M3 ease 退化成线性（丢过渡手感）',
       'door_reveal',
       '    t = _clamp01(t)\n    return t * t * (3.0 - 2.0 * t)',
       '    t = _clamp01(t)\n    return t')

# ---------------------------------------------------------------------------
# M4: ★★★ 恢复"派生式"写法 —— 让 item_interact 重新 import niko_home
#     （这正是上一会话我犯的错，会被 G1 硬闸 + L4/L5/N3b 一起抓）
# ---------------------------------------------------------------------------
mutate(u'M4 item_interact 派生台词（改成 import niko_home ⇒ 破坏零依赖、产生初始化环风险）',
       'item_interact',
       "NIKO_HOME_EGG_TEXT = ('你确定吗？',",
       "import niko_home as _nh_derive\nNIKO_HOME_EGG_TEXT = tuple(_nh_derive.EGG_TEXTS) or ('你确定吗？',")

# ---------------------------------------------------------------------------
# M5: 注入式门槛被摘掉（on_interact 里不再调 self.gate）
# ---------------------------------------------------------------------------
mutate(u'M5 摘掉 self.gate 调用（注入式第一道门槛失效）',
       'item_interact',
       '                allowed, _why = self.gate(actor)',
       '                allowed, _why = (True, "no-gate")')

# ---------------------------------------------------------------------------
# M6: niko_home.can_enter 对 None 改成拒绝（最关键的负控制：系统触发也会被挡）
#   ★ 原文里**没有**显式 `if actor is None` 分支（`None` 是经 `is_user_subject`
#     返回 False 才放行的）。⇒ 变异要打在**真正决定 None 放行**的那一句上：
#     在函数体最前插一条显式拒绝。判据 M3/M3b 必须抓得到。
# ---------------------------------------------------------------------------
mutate(u'M6 can_enter(None) 改成拒绝（NPC 自主/系统触发被误挡）',
       'niko_home',
       "    if is_user_subject(actor):\n        return False, 'user'\n    return True, 'other'",
       "    if actor is None:\n        return False, 'user'\n"
       "    if is_user_subject(actor):\n        return False, 'user'\n"
       "    return True, 'other'")

# ---------------------------------------------------------------------------
# M7: 屏蔽语改字（用户逐字要求「内容以屏蔽」）
# ---------------------------------------------------------------------------
mutate(u'M7 屏蔽语改字（违背用户逐字口径）',
       'niko_home',
       "BLOCKED_REPLY = '内容以屏蔽'",
       "BLOCKED_REPLY = '内容已屏蔽'")

# ---------------------------------------------------------------------------
# M8: FOLLOWUP_THRESHOLD 改成 1（第一句就屏蔽 ⇒ 违背"先正常回答"）
# ---------------------------------------------------------------------------
mutate(u'M8 第2次门槛改第1次（第一句就屏蔽）',
       'niko_home',
       'FOLLOWUP_THRESHOLD = 2',
       'FOLLOWUP_THRESHOLD = 1')

# ---------------------------------------------------------------------------
# M9: desktop.json 把 UT 门贴图改回任意门（违背"ut 就用王座那个门"）
# ---------------------------------------------------------------------------
mutate(u'M9 UT 门贴图改回任意门（违背用户点名）',
       'desktop_json',
       '"sprite": "objs/ut_castle_realdoor_0.png"',
       '"sprite": "objs/spr_darkdoor_0.png"')

# ---------------------------------------------------------------------------
# M10: 把 anim 加回 UT 门（重启频闪根因）
# ---------------------------------------------------------------------------
mutate(u'M10 UT 门加回 anim（频闪根因回归）',
       'desktop_json',
       '"sprite": "objs/ut_castle_realdoor_0.png",',
       '"sprite": "objs/ut_castle_realdoor_0.png",\n'
       '      "anim": {"base": "objs/ut_castle_realdoor", "frames": 2,'
       ' "frame_ms": 33.3},')

# ---------------------------------------------------------------------------
# M11: 符文门贴图改错（D 门）
# ---------------------------------------------------------------------------
mutate(u'M11 符文门贴图改错',
       'desktop_json',
       '"sprite": "objs/spr_shortcut_door_0.png"',
       '"sprite": "objs/spr_darkdoor_0.png"')

# ---------------------------------------------------------------------------
# M12: main.py 把 door_reveal 接线摘掉（渐显不再接进渲染路径）
#   ★ 真实调用点是 `_drv.apply_to_objects(...)`（`_drv = door_reveal_mod`），
#     不是 `door_reveal_mod.apply_to_objects(`。
# ---------------------------------------------------------------------------
mutate(u'M12 main.py 摘掉 door_reveal 接线',
       'main',
       '_drv.apply_to_objects(_objs, _sit, _ent, sizer=_door_sizer)',
       '_drv._disabled_apply_to_objects(_objs, _sit, _ent, sizer=_door_sizer)')

# ---------------------------------------------------------------------------
# M13: main.py 摘掉 egg_gate 注入（退化成"没有门槛"）
# ---------------------------------------------------------------------------
mutate(u'M13 摘掉 egg_gate 注入（Niko 家不再有门槛）',
       'main',
       'egg_gate=self._niko_home_gate,',
       'egg_gate=None,')

# ---------------------------------------------------------------------------
# M14: `_niko_home_gate` 改成恒放行（门槛内核失效，但接线还在 ⇒ 必须被抓）
# ---------------------------------------------------------------------------
mutate(u'M14 _niko_home_gate 恒放行（内核失效）',
       'main',
       '            import modules.niko_home as _nh\n            return _nh.can_enter(actor)',
       '            import modules.niko_home as _nh\n            return True, "unknown"')

# ---------------------------------------------------------------------------
# 收尾：确认工作区真文件**一字未改**
# ---------------------------------------------------------------------------
print(u'')
_all_ok = True
for k, v in REL.items():
    now = sha(os.path.join(ROOT, v))
    same = (now == _orig_hash[k])
    if not same:
        _all_ok = False
    print(u'%s 工作区 %s %s' % (u'[OK]  ' if same else u'[BAD] ', k,
                                u'未改动' if same else u'!! 被改了 !!'))

n_caught = sum(1 for r in results if r[1] == 'CAUGHT')
n_missed = sum(1 for r in results if r[1] == 'MISSED')
n_skip = sum(1 for r in results if r[1] == 'SKIP')
print(u'')
print(u'==== mutate112: 变异 %d ｜ CAUGHT=%d ｜ MISSED=%d ｜ SKIP=%d ｜ 工作区%s ===='
      % (len(results), n_caught, n_missed, n_skip,
         u'干净' if _all_ok else u'被污染!!'))

try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass

sys.exit(0 if (n_missed == 0 and _all_ok) else 1)
