# -*- coding: utf-8 -*-
"""mutate106.py —— `check106` 的**变异测试**：把产品源码弄坏，看锁会不会报红。

为什么必须做：一条锁"全绿"有两种可能 ——
  ① 产品真的对；② 判据恒真（写错了、量错了东西、或根本没走到那条分支）。
只看绿是分不出 ①② 的。本脚本对每个"守点"造一次**保真**的破坏，
要求**指定判据由绿变红**；跑完立刻还原并**逐字节核验还原成功**。

本轮两类破坏目标：
  · **非瞬移（A 段）** `ralsei_pet/modules/scene_controller.py`
    —— 把 `travel_to` 的逐跳改回"只走一步"（回到第105轮缺口形态）、
       把 `walk_steps` 的链式校验抠掉、把 `walk_route_home` 改成另算新路。
  · **全屏化（B 段）** `ralsei_pet/modules/scene_controller.py`
    —— 只写 `size` 不写 `scale`（成对契约破坏）、把 `scoped` 基准改错。
  · **清死代码（C 段）** `ralsei_pet/src/main.py`
    —— 把 `camera_follow_or_create()` 调用加回去。

铁律（第85~96轮反复踩过）：
  * 破坏必须**真的破坏**（改产品，不是改判据）；
  * 判据报红之后要**先怀疑判据**（本脚本每条都打印"期望哪条判据红"）；
  * 还原要**逐字节**核对哈希，不是"我改回来了"。
  * ★★ 锚点含 `\\n` 时**必须先 `_lf()`**（源码是 CRLF 读入 ⇒ 锚点匹配不到，
    第98轮栽过）。
"""
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
CTRL = os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_controller.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
BAK = os.path.join(os.environ.get('TEMP') or '/tmp', 'bak106_mutate')
PY = sys.executable
TARGETS = [CTRL, MAIN]


def sha(p):
    with open(p, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_raw(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_raw(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _lf(s):
    """把 CRLF 归一成 LF（锚点一律按 LF 写，否则 CRLF 源码匹配不到）。"""
    return s.replace('\r\n', '\n').replace('\r', '\n')


def patch(path, old, new, cnt=1):
    """在**原始 CRLF 文本**上做替换：锚点与替换串都先按 LF 想，落盘保持原 EOL。

    ★ 做法：把文件按 CRLF 读入 → 归一成 LF 做替换 → 结果按 LF→CRLF 写回。
      （源码 EOL 全为 CRLF —— 本项目 `autocrlf=true`，工作区实测 CRLF。）
    """
    orig = read_raw(path)
    lf = _lf(orig)
    if old not in lf:
        raise RuntimeError('锚点未命中：\n%s' % old[:200])
    n = lf.count(old)
    if n < cnt:
        raise RuntimeError('锚点命中 %d 次 < 期望 %d 次' % (n, cnt))
    lf2 = lf.replace(old, new, cnt)
    write_raw(path, lf2.replace('\n', '\r\n'))


def run_check():
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    pr = subprocess.run([PY, os.path.join(HERE, 'check106.py')], env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = pr.stdout.decode('utf-8', 'replace')
    # ★★ 第106轮修正：`check106.check()` 的 PASS/FAIL 行在**星标判据**下形如
    #   `[FAIL] ★ A2 …` ⇒ 旧正则 `^\[FAIL\] (\S+)` 抓到的**首 token 是 `★`**
    #   （`★` 与后面的描述之间有空格）⇒ `f.startswith('A2')` **恒假** ⇒
    #   7 个变异体会**全部被误判成 MISS**（"夹具不保真"的镜像：**判据名匹配写错**
    #   让变异测试自己说谎）。改法：剥掉 `★ ` 前缀再取首 token。
    fails = []
    for m in re.finditer(r'^\[FAIL\]\s*(.+)$', out, re.M):
        body = m.group(1)
        if body.startswith('\u2605 '):
            body = body[2:]
        tok = body.split(' ')[0]
        fails.append(tok)
    return pr.returncode, fails


def restore():
    bad = []
    for p in TARGETS:
        shutil.copy2(os.path.join(BAK, os.path.basename(p)), p)
        if sha(p) != _orig[p]:
            bad.append(p)
    return bad


os.makedirs(BAK, exist_ok=True)
_orig = {}
for _p in TARGETS:
    shutil.copy2(_p, os.path.join(BAK, os.path.basename(_p)))
    _orig[_p] = sha(_p)
print('备份 %d 个文件 -> %s' % (len(TARGETS), BAK))


# ------------------------------------------------- M1 逐跳改回"只走一步"
def m1():
    """回到第105轮缺口形态：拿到 steps 也只 switch 终点一次。"""
    patch(CTRL,
          "            walked = self.walk_steps(plan.get('steps') or [])",
          "            walked = {'ok': True, 'visited': [], 'aborted_at': None}\n"
          "            if not self.switch(sid):\n"
          "                return result")
    return 'A2', '把 travel_to 的逐跳改回"只 switch 一次"（回到第105轮缺口）'


# ------------------------------------------- M2 walk_steps 的链式校验抠掉
def m2():
    patch(CTRL,
          "                if want_from and cur and want_from != cur:",
          "                if False and want_from and cur and want_from != cur:")
    return 'A5', '抠掉 walk_steps 的链式校验（脱节的跳必须被拒）'


# ------------------------------------------- M3 walk_steps 的 switch 抠掉
def m3():
    patch(CTRL,
          "                if not self.switch(nxt):",
          "                if False:")
    return 'A6', '把 walk_steps 里的 switch 短路（逐跳必须真走门）'


# --------------------------------- M4 walk_route_home 改成"另算新路"
def m4():
    patch(CTRL,
          "        plan = self.plan_route_to(home_scene)",
          "        plan = {'ok': True, 'steps': [{'from': None, 'to': home_scene}],\n"
          "                'hops': 1, 'route': 'direct'}")
    return 'A9', '把 walk_route_home 改成"另算直达路"（必须复用原路线）'


# --------------------------------- M5 全屏化只写 size 不写 scale（成对破坏）
def m5():
    patch(CTRL,
          "        cam.set_scale(out_w / scoped_w)",
          "        pass  # 变异测试：故意不写 scale（size/scale 不再成对）")
    return 'B3', 'fit_camera_to_screen 只写 size 不写 scale（成对契约破坏）'


# --------------------------------- M6 scoped 基准被改错（逻辑窗口不再 320×240）
def m6():
    patch(CTRL,
          "        scoped_w = base_w / 2.0          # 320",
          "        scoped_w = base_w / 4.0          # 变异测试：基准改错")
    return 'B4', '把 fit_camera_to_screen 的逻辑窗口基准改错（scoped 不再 320）'


# --------------------------------- M7 死代码调用加回去（**保真**：加在 `try:` 内）
def m7():
    """★ 第106轮踩坑记录（**夹具不保真**，别重犯）：
    初版拿 `'    if cam is None or state is None:'` 当锚点、把死代码加在它**上面**
    ⇒ 那一行的**缩进是 8 空格**（函数体顶层，`if not SCENE_LAYER_ENABLED` 那一段），
      而 `cam = self.__dict__.get('_scene_camera')` 在 `try:` **里面（12 空格）**
    ⇒ 插进去之后 `try:` 块被拆断、`except` 变孤儿 ⇒ **`SyntaxError`**
    ⇒ 判据 C1/C2 走 `ast.parse` 拿不到树，如实返回"没找到" ⇒ 变异测试报 MISS。
    **这不是判据的错**：`ast` 判据**看不到语法错误的文件**是设计如此。
    ⇒ 保真的 M7 必须把死代码**插回它原来的位置**（`try:` 内、`cam` 赋值之前），
      也就是注释里写的那一行 —— 用 `cam` 赋值行当锚点、加在它**前面**。
    """
    patch(MAIN,
          "            cam = self.__dict__.get('_scene_camera')",
          "            cam = scene.camera_follow_or_create()\n"
          "            cam = self.__dict__.get('_scene_camera')")
    return 'C1', '把 camera_follow_or_create() 调用加回 _update_scene_layer（死代码复活）'


MUTS = [m1, m2, m3, m4, m5, m6, m7]

rc0, f0 = run_check()
print('基线（未变异）：rc=%d FAIL=%s' % (rc0, f0 or '无'))
if rc0 != 0 or f0:
    print('!! 基线本身不是全绿 —— 先修产品/锁，再谈变异测试')
    restore()
    raise SystemExit(2)

bad = 0
for fn in MUTS:
    want, desc = fn()
    rc, fails = run_check()
    hit = any(f.startswith(want) for f in fails)
    ok = (rc != 0) and hit
    print('[%s] %s → 期望判据 %s 报红；实得 rc=%d FAIL=%s'
          % ('OK' if ok else 'MISS', desc, want, rc, fails or '无'))
    bad += 0 if ok else 1
    back = restore()
    if back:
        print('!! 还原失败：%s' % back)
        raise SystemExit(3)

print()
print('变异测试：%d/%d 命中' % (len(MUTS) - bad, len(MUTS)))
print('全部文件已还原并逐字节核验：%s'
      % ('OK' if all(sha(p) == _orig[p] for p in TARGETS) else 'FAIL'))
raise SystemExit(1 if bad else 0)
