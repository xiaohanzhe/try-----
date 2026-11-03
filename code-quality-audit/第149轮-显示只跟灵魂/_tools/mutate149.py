# -*- coding: utf-8 -*-
u"""第149轮 · 破坏性负控制：逐条拆掉"显示只跟灵魂"，**指定**判据必须报红。

`check149` 全绿本身证明不了什么 —— 全绿也可能因为判据恒真。
这里逐条破坏产品，断言**恰好**是那几条判据变红（多红一条、少红一条都算不合格），
然后**按字节还原**（sha1 校验）。最后再跑一次 `check149`，必须回到全绿。

| # | 破坏 | 期望变红 |
|---|---|---|
| M1 | 闸语义反转（`!=` → `==`） | `C1` `C2` `C3` `C10` `C11` `C12` `C13` |
| M2 | 闸里 `return False` → `return True`（返回值撒谎） | `C3` `C10` `C12` `C15` |
| M3 | `_cur` 改裸属性 `self.current_scene` | `C4` `C14` |
| M4 | 删掉 `init_movement` 里的声明行 | `C6` |
| M4b | 闸**前**提前标记 `fired` | `C11` `C12` |
| M5 | 往 `npc_roam.py` 塞一个 `switch` | `B1` |
| M6 | 往 `main.py` 塞一个新的自动切换点 | `A1` |

## 期望写窄过两次，两次都是判据对、期望错

- **`M1` 漏了 `C2` `C3`**：闸形状一改（`!=` → `==`），`_gate_if` 就定位不到那个对象 ⇒
  `C2`（位置）和 `C3`（body 末句）跟着红。这不是"三条独立信号"，是**同一个对象的三条性质**：
  对象没了，性质当然都不可验（fail-closed）。我第一版按"只有 `C1` 该红"去写，是没想清依赖关系。
- **`M2` 漏了 `C15`**：`return True` 之后"异地"与"在家"**都返回 True** ⇒
  C15 的"结果必须相反"不成立 ⇒ 它红得完全正确 —— 鉴别力判据本来就该在这种时候叫。
  顺带说明 `C15` 不是 N2 的复读：`C10` 只看异地，`C15` 额外要求**两桩除该字段外逐字段相同**。

## 三条说明（写在这里，省得以后重猜）

**① 为什么没有"把闸搬到 `fired` 之后"的变异（`C2` 的直系）。**
`C2` 是**位置**判据，而单点字节替换搬不动整段 5 行（缩进一改就 SyntaxError，
改完语义也该重写）。与其造一个假变异，不如用 `M4b`（**在闸之前**先标记 `fired`）
验证它的**后果**：一旦提前标记，`C11`（"仍为空"）与 `C12`（"重复 tick 仍不标记"）必然红。
—— 承认覆盖缺口，别假装覆盖到了。

**② `M3` 红在 `C14` 而不是 `C10`，是**有价值**的红。**
`self.current_scene` 在**老桩**（没有该字段）上抛 `AttributeError`，
而 `_bedtime_tick` 整段被 `try/except` 包着 ⇒ **静默 return False** ⇒ 桩上"永远不就寝"。
这正是"新增状态位一律走 `getattr`"那条铁律的实证：不走 `getattr` 不是报错，是**悄悄不干活**。

**③ `M5` / `M6` 是"防线外"的两条。**
`B1`（NPC 零处碰显示）和 `A1`（切换点恰好 4 处）都不是行为判据，
所以只能靠**往文件里塞代码**来证明它们不是恒真 —— 塞进去必须红。
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
MAIN = os.path.join(PKG, 'src', 'main.py')
ROAM = os.path.join(PKG, 'modules', 'npc_roam.py')
CHECK149 = os.path.join(HERE, 'check149.py')
PY = u'C:\\Python311\\python.exe'

_n_ok = 0
_n_bad = 0
_failed = []


def check(desc, cond, extra=u''):
    global _n_ok, _n_bad
    cond = bool(cond)
    if cond:
        _n_ok += 1
    else:
        _n_bad += 1
        _failed.append(desc)
    print(u'%s %s%s' % (u'[PASS]' if cond else u'[FAIL]', desc,
                        (u'  ' + extra) if extra else u''))


def _read(p):
    # ★ 字节忠实：`newline=''` 保住 CRLF，否则还原时整份文件的 EOL 都被改写
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def _write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(t)


def _sha1(p):
    with io.open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


#: 开工前的字节指纹。Z2 拿它当对照 —— 第一版写成「`_sha1(p) == sha1(现在再读一遍)`」，
#:  那是**自己跟自己比**，恒真（"判据也是被测物"第 N 次）。
_SHA0 = ((MAIN, _sha1(MAIN)), (ROAM, _sha1(ROAM)))


def _run149():
    u"""跑 `check149`，返回 (变红的判据编号集合, 退出码, 原始输出)。"""
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK149], cwd=ROOT, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    txt = out.decode('utf-8', 'replace')
    toks = set()
    for line in txt.splitlines():
        if not line.startswith(u'[FAIL] '):
            continue
        toks.add(line[len(u'[FAIL] '):].split(u' ')[0])
    return toks, p.returncode, txt


def mutate(tag, path, pairs, expect):
    u"""按 `pairs` 改 → 跑 → 断言恰好 `expect` 变红 → 按字节还原。"""
    src = _read(path)
    bad = [(o, src.count(o)) for o, _n in pairs if src.count(o) != 1]
    if bad:
        check(u'%s 每处锚点都唯一' % tag, False,
              u'；'.join(u'%r 出现 %d 次' % (o[:26], c) for o, c in bad))
        return
    sha0 = _sha1(path)
    try:
        new_src = src
        for o, n in pairs:
            new_src = new_src.replace(o, n, 1)
        if new_src == src:
            check(u'%s 破坏确实改动了源码' % tag, False, u'替换后与原文相同')
            return
        _write(path, new_src)
        got, rc, txt = _run149()
        ok = (got == set(expect)) and rc != 0
        check(u'%s 破坏后**恰好** %s 变红' % (tag, u'+'.join(expect)),
              ok, u'实得 %s' % (u'+'.join(sorted(got)) or u'（无）'))
        if not ok:
            for line in txt.splitlines():
                if line.startswith(u'[FAIL] '):
                    print(u'        %s' % line)
    finally:
        _write(path, src)
        check(u'%s 已按字节还原（sha1 一致）' % tag, _sha1(path) == sha0)


print(u'=' * 78)
print(u'M 破坏性负控制（每处都断言**恰好**指定的判据变红）')
print(u'=' * 78)

# M1 闸语义反转：显示在家时推迟、在异地时照睡 —— 完全反过来
#   ★ C1/C2/C3 会一起红：形状一改，`_gate_if` 定位不到对象 ⇒ 位置与 body 都无从验（见文件头）
mutate(u'M1', MAIN,
       [(u'            if _cur and _cur != _home:\r\n',
         u'            if _cur and _cur == _home:\r\n')],
       [u'C1', u'C2', u'C3', u'C10', u'C11', u'C12', u'C13'])

# M2 返回值撒谎：推迟了却报"已就寝"（两桩都 True ⇒ 鉴别力判据 C15 也该红）
mutate(u'M2', MAIN,
       [(u'                return False\r\n'
         u'            self._bedtime_fired_date = today\r\n'
         u'            _log.info("[就寝] 到点（目标 %s），回房间睡觉"',
         u'                return True\r\n'
         u'            self._bedtime_fired_date = today\r\n'
         u'            _log.info("[就寝] 到点（目标 %s），回房间睡觉"')],
       [u'C3', u'C10', u'C12', u'C15'])

# M3 新增状态位不走 getattr：老桩上静默失败（见文件头说明②）
mutate(u'M3', MAIN,
       [(u"            _cur = getattr(self, 'current_scene', None)\r\n",
         u'            _cur = self.current_scene\r\n')],
       [u'C4', u'C14'])

# M4 声明失踪（只剩 `_bedtime_tick` 里的运行期赋值）—— 行为不受影响，只有 C6 该红
mutate(u'M4', MAIN,
       [(u'        self._bedtime_defer_logged = None\r\n', u'')],
       [u'C6'])

# M4b 闸之前就提前标记 fired ⇒ 今晚再也不试（C2 的**后果**版，见文件头说明①）
mutate(u'M4b', MAIN,
       [(u"            _home = getattr(self, 'BEDTIME_HOME_SCENE', 'desktop')\r\n",
         u'            self._bedtime_fired_date = today\r\n'
         u"            _home = getattr(self, 'BEDTIME_HOME_SCENE', 'desktop')\r\n")],
       [u'C11', u'C12'])

# M5 NPC 模块碰显示（B 段的结构判据只能靠"塞进去必须红"来证伪）
#   ★ 锚点用**整份源码**（出现次数天然为 1），不做"末尾 120 字符"这种脆匹配。
_src_roam = _read(ROAM)
mutate(u'M5', ROAM,
       [(_src_roam,
         _src_roam + u'\ndef _display_leak(self):\n    self.scene.switch("x")\n')],
       [u'B1'])

# M6 新增一个自动切换点（模拟"以后有人又加了一条自动改画面的路径"）
_src_main = _read(MAIN)
mutate(u'M6', MAIN,
       [(_src_main,
         _src_main + u'\ndef _probe_auto(self):\n    self.scene.switch("x")\n')],
       [u'A1'])

print(u'')
print(u'=' * 78)
print(u'收口：全部还原后再跑一遍，必须回到全绿')
_got, _rc, _txt = _run149()
check(u'Z1 收口全绿（FAIL=0）', _rc == 0 and not _got,
      u'变红 %s' % (u'+'.join(sorted(_got)) or u'（无）'))
check(u'Z2 两个被改过的文件都已按字节还原（与**开工前**指纹一致）',
      all(_sha1(p) == s for p, s in _SHA0),
      u'%s' % ([(os.path.basename(p), _sha1(p) == s) for p, s in _SHA0],))

print(u'')
print(u'=' * 78)
print(u'mutate149：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
