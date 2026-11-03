# -*- coding: utf-8 -*-
u"""第152轮 · 破坏性负控制：逐条拆掉"差事叫停"，**指定**判据必须报红。

`check152` 全绿证明不了什么 —— 全绿也可能因为判据恒真。
这里逐条破坏产品，断言**恰好**是那几条判据变红（多红一条、少红一条都算不合格），
然后**按字节还原**（sha1 校验）。最后再跑一次 `check152`，必须回到全绿。

| # | 破坏 | 期望变红 |
|---|------|----------|
| M1 | 叫停时**不撤位置覆盖**（"人回来了"却还站在目的地） | `A1` `A2` `A8` |
| M2 | 把作废当办完（`_npc_errand_note` → `_npc_errand_commit`） | `A3b` `A9` `A9b` |
| M3 | 撤完**不 `return True`**（继续往下走去派活） | `C2` `C5` |
| M4 | 拆掉"否定句不派"闸 | `C3` |
| M5 | 未点名时**不看条数**（有两条也随手挑一条） | `B4` |
| M6 | 点名的人没在办时**退化成唯一在办** | `B5` |
| M7 | 把「算了」收进取消词（口语会被当叫停） | `B6` |
| M8 | 去掉**动作层**的 `board.enabled` 检查（关闸了还照撤） | `A6` |
| M8b | 去掉**解析层**的 `board.enabled` 检查（关闸之后还继续认这句话） | `B8` |
| M9 | 在取消块**之前**多解析一次派活（顺序/唯一性） | `C1` |

## 写期望时先问两句（第150/151轮的教训，这里又用上）

- **"这件事还有谁在盯？"** —— `M1` 一处改动同时踩 `A1`（路上）/`A2`（到了）/
  `A8`（连叫两次）三条：它们各看一个阶段，**不是三条独立信号**，是同一条
  "覆盖没撤"的三个观测面。
- **"谁在它下游？"** —— `M3` 一拆，`C2`（真跑那句"别让…去了"）与 `C5`（AST）
  一起红：前者看行为、后者看形状，**fail-closed 时下游一起塌**。
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CHECK152 = os.path.join(HERE, 'check152.py')
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


#: 开工前的字节指纹。Z2 拿它当对照 —— 不许写成"再读一遍跟自己比"（恒真）。
_SHA0 = ((MAIN, _sha1(MAIN)),)


def _run152():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK152], cwd=ROOT, env=env,
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
    src = _read(path)
    bad = [(o, src.count(o)) for o, _n in pairs if src.count(o) != 1]
    if bad:
        check(u'%s 每处锚点都唯一' % tag, False,
              u'；'.join(u'%r 出现 %d 次' % (o[:30], c) for o, c in bad))
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
        got, rc, txt = _run152()
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

# M1 叫停时**不撤位置覆盖** ⇒ 人"回来了"却还站在目的地
mutate(u'M1', MAIN,
       [(u'                roam.drop(npc_id)      # \u2605 \u56de\u843d\u9759\u6001\u5f52\u5c5e = \u56de\u5bb6\r\n',
         u'                pass  # \u4e0d\u64a4\u8986\u76d6\r\n')],
       [u'A1', u'A2', u'A8'])

# M2 把"作废"当"办完"：走 commit（结果写记忆）而不是 note（写"被叫回来"）
mutate(u'M2', MAIN,
       [(u'        self._npc_errand_note(\r\n'
         u'            npc_id, u\'\u6211\u672c\u6765\u8981\u53bb %s \u529e\u300c%s\u300d\uff0c\u8fd8\u6ca1\u529e\u5b8c\u5c31\u88ab\u53eb\u56de\u6765\u4e86%s\'\r\n'
         u'                    % (dest, what, (u\'\uff08%s\uff09\' % reason) if reason else u\'\'))\r\n',
         u'        self._npc_errand_commit(npc_id, e)\r\n')],
       [u'A3b', u'A9', u'A9b'])

# M3 撤完不 `return True` ⇒ 继续往下走去派活
mutate(u'M3', MAIN,
       [(u'                                    getattr(_err, \'what\', u\'\'))\r\n'
         u'            return True\r\n',
         u'                                    getattr(_err, \'what\', u\'\'))\r\n'
         u'            pass\r\n')],
       [u'C2', u'C5'])

# M4 拆掉"否定句不派"闸
mutate(u'M4', MAIN,
       [(u'        if RalseiPet._errand_is_negative(low):\r\n'
         u'            return None\r\n',
         u'        if False:  # \u5426\u5b9a\u95f8\u88ab\u62c6\r\n'
         u'            return None\r\n')],
       [u'C3'])

# M5 未点名时**不看条数**（有两条也随手挑一条）
mutate(u'M5', MAIN,
       [(u'            if len(act) != 1:\r\n'
         u'                return None               # 0 \u6761 = \u6ca1\u5728\u529e\uff1b\u22652 \u6761 = \u4e0d\u731c\u662f\u8c01\r\n',
         u'            if len(act) < 1:\r\n'
         u'                return None\r\n')],
       [u'B4'])

# M6 点名的人没在办时**退化成唯一在办**（替用户"取消"不存在的事）
mutate(u'M6', MAIN,
       [(u'        e = board.active_of(target)\r\n'
         u'        if e is None:\r\n'
         u'            return None\r\n'
         u'        return target, e\r\n',
         u'        e = board.active_of(target)\r\n'
         u'        if e is None:\r\n'
         u'            _act = board.by_npc()\r\n'
         u'            if len(_act) == 1:\r\n'
         u'                target = next(iter(_act))\r\n'
         u'                e = board.active_of(target)\r\n'
         u'        if e is None:\r\n'
         u'            return None\r\n'
         u'        return target, e\r\n')],
       [u'B5'])

# M7 把「算了」收进取消词（最常见口语会被当叫停）
mutate(u'M7', MAIN,
       [(u"                          '\u56de\u6765\u5427')\r\n",
         u"                          '\u56de\u6765\u5427', '\u7b97\u4e86')\r\n")],
       [u'B6'])

# M8 去掉 `cancel_errand` 里的 `board.enabled` 检查（关闸了还照撤）
#   ★ 期望只写 `A6`：`_errand_parse_cancel` 里**另有一处**同样的检查（解析层），
#     它由 `B8` 单独守 —— 两处是**两个责任**（解析层不许吞聊天 / 动作层不许动手），
#     不是"同一件事两处算"。拆一处只该红一条，M8b 拆另一处。
mutate(u'M8', MAIN,
       [(u"        board = getattr(self, 'npc_errand', None)\r\n"
         u'        if board is None or not board.enabled:\r\n'
         u'            return None\r\n'
         u'        e = board.active_of(npc_id)\r\n',
         u"        board = getattr(self, 'npc_errand', None)\r\n"
         u'        if board is None:\r\n'
         u'            return None\r\n'
         u'        e = board.active_of(npc_id)\r\n')],
       [u'A6'])

# M8b 去掉**解析层**的 `board.enabled` 检查（关闸之后还继续认这句话）
mutate(u'M8b', MAIN,
       [(u"        board = getattr(self, 'npc_errand', None)\r\n"
         u'        if board is None or not board.enabled:\r\n'
         u'            return None\r\n'
         u'        low = text.lower()\r\n',
         u"        board = getattr(self, 'npc_errand', None)\r\n"
         u'        if board is None:\r\n'
         u'            return None\r\n'
         u'        low = text.lower()\r\n')],
       [u'B8'])

# M9 在取消块**之前**多解析一次派活（顺序/唯一性）
mutate(u'M9', MAIN,
       [(u'        _cancel = self._errand_parse_cancel(text)\r\n',
         u'        intent = self._errand_parse_intent(text)\r\n'
         u'        _cancel = self._errand_parse_cancel(text)\r\n')],
       [u'C1'])

# M10 不看 `cancel_errand` 的返回值 ⇒ 竞态时冒认"他回来了"
mutate(u'M10', MAIN,
       [(u'            if self.cancel_errand(_nid, reason=u\'\u7528\u6237\u53eb\u505c\') is None:\r\n'
         u'                return False\r\n',
         u'            self.cancel_errand(_nid, reason=u\'\u7528\u6237\u53eb\u505c\')\r\n')],
       [u'C6'])

print(u'')
print(u'=' * 78)
print(u'收口：全部还原后再跑一遍，必须回到全绿')
_got, _rc, _txt = _run152()
check(u'Z1 收口全绿（FAIL=0）', _rc == 0 and not _got,
      u'变红 %s' % (u'+'.join(sorted(_got)) or u'（无）'))
check(u'Z2 被改过的文件已按字节还原（与**开工前**指纹一致）',
      all(_sha1(p) == s for p, s in _SHA0),
      u'%s' % ([(os.path.basename(p), _sha1(p) == s) for p, s in _SHA0],))

print(u'')
print(u'=' * 78)
print(u'mutate152：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
