# -*- coding: utf-8 -*-
u"""第153轮 · 破坏性负控制：逐条拆掉"办完交差"，**指定**判据必须报红。

`check153` 全绿证明不了什么 —— 全绿也可能因为判据恒真。
这里逐条破坏产品，断言**恰好**是那几条判据变红（多红一条、少红一条都算不合格），
然后**按字节还原**（sha1 校验）。最后再跑一次 `check153`，必须回到全绿。

| # | 破坏 | 期望变红 |
|---|------|----------|
| M1 | tick 里**根本不交差**（删掉调用） | `A1` `A1b` `A5` `C1` `C4` |
| M2 | 先开口、后记住（`report` 提到 `commit` 之前） | `A5` `C1` |
| M3 | 办完**不回家**（删掉 `roam.drop`） | `A1c` `A5` `C1` |
| M4 | 空结果也开口 | `B4` |
| M5 | 没装设定的 NPC 也开口（回落成 Ralsei 的口气） | `B3` |
| M6 | 去掉模型闸（模型不可用也发请求） | `B5` |
| M7 | `remember=True`（结果被记两条） | `B1b` `C3b` |
| M8 | `speaker` 恒 `None`（不管谁办的事，都当主链路） | `B2` `B3` |
| M9 | brief 里**不给结果** | `A1b` `B8` |
| M10 | brief 里**不给"用户此刻在哪"** | `B6` `B6b` |
| M11 | 交差时**再写一遍记忆** | `C3` |
| M12 | 改用 `npc_speak()` 而不是 `chat_with_ai` | `A1` `A1b` `C2` `C3b` |
| M13 | 对 `done` 全体交差（每拍重复交代） | `A2` |

## 写期望时先问两句（第150/151/152轮的教训，这里又用上）

- **"一处改动还有谁在盯？"** —— `M1` 一处删掉，`A1`（有没有说）/`A1b`（话里带不带结果）/
  `A5`（顺序）/`C1`（AST 行序）/`C4`（调用点计数）**五条一起塌**：
  它们**不是五个独立信号**，是同一条"没交差"的五个观测面（行为 2 条 + 顺序 2 条 + 形状 1 条）。
- **"fail-closed 会带到哪？"** —— `M12` 换成 `npc_speak`：桩宿主没有这个方法 ⇒
  抛异常 ⇒ `try/except` 吞掉 ⇒ **一句都说不出** ⇒ 行为面的 `A1`/`A1b` 跟形状面的
  `C2`/`C3b` 一起红。这是**下游一起塌**，不是判据互相污染。
- **"期望里有没有判据本来就该红？"** —— `A2` 第一版写的是"总数 == 1"，
  那 `M1` 会把 `A2` 也带着红（0 ≠ 1）⇒ 改成"**没有新增**"，
  `A2` 才只考"不重复"这一件事（`M13` 单独验它）。
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
CHECK153 = os.path.join(HERE, 'check153.py')
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


def _run():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    p = subprocess.Popen([PY, CHECK153], cwd=ROOT, env=env,
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
        got, rc, txt = _run()
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

# M1 tick 里根本不交差（把那次调用整块删掉）
mutate(u'M1', MAIN,
       [(u"                self._errand_report_ack(nid, getattr(err, 'dest_scene', u''),\r\n"
         u"                                        getattr(err, 'what', u''),\r\n"
         u"                                        getattr(err, 'result', u''))\r\n",
         u'                pass\r\n')],
       [u'A1', u'A1b', u'A5', u'C1', u'C4'])

# M2 先开口、后记住（report 提到 commit 之前）
mutate(u'M2', MAIN,
       [(u"                self._npc_errand_commit(nid, err)\r\n"
         u"                self._errand_report_ack(nid, getattr(err, 'dest_scene', u''),\r\n"
         u"                                        getattr(err, 'what', u''),\r\n"
         u"                                        getattr(err, 'result', u''))\r\n",
         u"                self._errand_report_ack(nid, getattr(err, 'dest_scene', u''),\r\n"
         u"                                        getattr(err, 'what', u''),\r\n"
         u"                                        getattr(err, 'result', u''))\r\n"
         u"                self._npc_errand_commit(nid, err)\r\n")],
       [u'A5', u'C1'])

# M3 办完不回家（删掉 roam.drop）
mutate(u'M3', MAIN,
       [(u"                roam.drop(nid)\r\n"
         u"                touched = True\r\n"
         u"                self._npc_errand_commit(nid, err)\r\n",
         u"                pass  # \u4e0d\u64a4\u8986\u76d6\r\n"
         u"                touched = True\r\n"
         u"                self._npc_errand_commit(nid, err)\r\n")],
       [u'A1c', u'A5', u'C1'])

# M4 空结果也开口
mutate(u'M4', MAIN,
       [(u"        txt = (result or u'').strip()\r\n"
         u"        if not txt:\r\n",
         u"        txt = (result or u'').strip()\r\n"
         u"        if False:\r\n")],
       [u'B4'])

# M5 没装设定的 NPC 也开口
mutate(u'M5', MAIN,
       [(u"        if speaker is not None and not self.npc_persona_of(speaker):\r\n",
         u"        if False and not self.npc_persona_of(speaker):\r\n")],
       [u'B3'])

# M6 去掉模型闸
mutate(u'M6', MAIN,
       [(u"        if not self._npc_ai_available():\r\n"
         u"            _log.info('\u4ea4\u5dee\uff1a\u6a21\u578b\u4e0d\u53ef\u7528 \u21d2 \u8fd9\u53e5\u4e0d\u8bf4\u4e86\uff08\u7ed3\u679c\u5df2\u8fdb\u4ed6\u8bb0\u5fc6\uff09')\r\n",
         u"        if False and not self._npc_ai_available():\r\n"
         u"            _log.info('\u4ea4\u5dee\uff1a\u6a21\u578b\u4e0d\u53ef\u7528 \u21d2 \u8fd9\u53e5\u4e0d\u8bf4\u4e86\uff08\u7ed3\u679c\u5df2\u8fdb\u4ed6\u8bb0\u5fc6\uff09')\r\n")],
       [u'B5'])

# M7 remember=True（结果被记两条）
#   ★ 锚点必须带上 `model=` 那行 —— 只写 `None, speaker=speaker, remember=False,`
#     会同时命中 `_errand_ack` 与 `_errand_cancel_ack`（三处同形，MT 第一条就报"出现 3 次"）。
mutate(u'M7', MAIN,
       [(u"                              None, speaker=speaker, remember=False,\r\n"
         u"                              model=(self._npc_model(npc_id) if speaker else None))\r\n",
         u"                              None, speaker=speaker, remember=True,\r\n"
         u"                              model=(self._npc_model(npc_id) if speaker else None))\r\n")],
       [u'B1b', u'C3b'])

# M8 speaker 恒 None（不管谁办的事，都当主链路）
mutate(u'M8', MAIN,
       [(u"        speaker = None if npc_id == 'ralsei' else npc_id\r\n",
         u"        speaker = None\r\n")],
       [u'B2', u'B3'])

# M9 brief 里不给结果
#   ★ 锚点跟着产品改过一次：brief 里 `%s` 后面**不再补句号**
#     （结果自带句号 ⇒ 原来会出现「……受伤。。」，两个句号）。
mutate(u'M9', MAIN,
       [(u"                 '**\u5df2\u7ecf\u529e\u5b8c\u4e86**\uff0c\u7ed3\u679c\u662f\uff1a%s\\n'\r\n",
         u"                 '**\u5df2\u7ecf\u529e\u5b8c\u4e86**\uff0c\u5904\u7406\u597d\u4e86\u3002\\n'\r\n"),
        (u"                 % (where, what, txt, here))\r\n",
         u"                 % (where, what, here))\r\n")],
       [u'A1b', u'B8'])

# M10 brief 里不给"用户此刻在哪"
mutate(u'M10', MAIN,
       [(u"                 '\u4f60\u73b0\u5728\u5df2\u7ecf\u56de\u6765\u4e86\uff1b\u7528\u6237\u6b64\u523b\u5728\u300c%s\u300d\u3002\\n'\r\n",
         u"                 '\u4f60\u73b0\u5728\u5df2\u7ecf\u56de\u6765\u4e86\u3002\\n'\r\n"),
        (u"                 % (where, what, txt, here))\r\n",
         u"                 % (where, what, txt))\r\n")],
       [u'B6', u'B6b'])

# M11 交差时再写一遍记忆
mutate(u'M11', MAIN,
       [(u"        except Exception as e:\r\n"
         u"            _log.debug('\u4ea4\u5dee\u8bed\u53d1\u8d77\u5931\u8d25\uff08\u5df2\u5ffd\u7565\uff09: %s', e)\r\n",
         u"        except Exception as e:\r\n"
         u"            _log.debug('\u4ea4\u5dee\u8bed\u53d1\u8d77\u5931\u8d25\uff08\u5df2\u5ffd\u7565\uff09: %s', e)\r\n"
         u"        self.npc_memory.remember(npc_id, txt)\r\n")],
       [u'C3'])

# M12 改用 npc_speak（它没有"系统提示"通道，还会把 brief 当玩家发言记下来）
#   ★ 期望写得长：桩宿主**没有** `npc_speak` ⇒ 抛异常 ⇒ `try/except` 吞掉 ⇒
#     一句都说不出 ⇒ 凡是以 `chats` 为观测量的 B 段**全部**跟着红。
#     这不是判据互相污染，是 fail-closed 的**下游一起塌**（同第152轮 M3）。
mutate(u'M12', MAIN,
       [(u"            self.chat_with_ai(brief,\r\n"
         u"                              lambda r: self._errand_show_reply(npc_id, r),\r\n"
         u"                              None, speaker=speaker, remember=False,\r\n"
         u"                              model=(self._npc_model(npc_id) if speaker else None))\r\n",
         u"            self.npc_speak(npc_id, brief,\r\n"
         u"                           lambda r: self._errand_show_reply(npc_id, r))\r\n")],
       [u'A1', u'A1b', u'A5', u'B0', u'B1', u'B1b', u'B2', u'B6b', u'B7', u'B8',
        u'B9', u'C2', u'C3b'])

# M13 对 done 全体交差（每拍重复交代）
#   ★ 第一版写成 `list(board.done.values())` ⇒ **拆包失败**
#     （`done.values()` 里是 `Errand`，而 `finished` 里是 `(nid, Errand)`）⇒
#     异常被 tick 的 `except` 吞掉 ⇒ 表现出来是"整段没执行"，一眼看去像"这个破坏没生效"。
#     ⇒ 必须换成 `(nid, Errand)` 的形状，破坏才真的落在"重复交代"这件事上。
mutate(u'M13', MAIN,
       [(u"            for nid, err in (out.get('finished') or ()):\r\n",
         u"            for nid, err in ([(k, v) for k, v in board.done.items()] or ()):\r\n")],
       [u'A2'])

# M14 去掉"场景取不到"的人话兜底 ⇒ brief 里出现「None」
mutate(u'M14', MAIN,
       [(u"        here = self._errand_place_label(self._npc_scene_id()) or u'\u684c\u9762'\r\n",
         u"        here = self._errand_place_label(self._npc_scene_id())\r\n")],
       [u'B9'])

print(u'')
print(u'=' * 78)
print(u'收口：全部还原后再跑一遍，必须回到全绿')
_got, _rc, _txt = _run()
check(u'Z1 收口全绿（FAIL=0）', _rc == 0 and not _got,
      u'变红 %s' % (u'+'.join(sorted(_got)) or u'（无）'))
check(u'Z2 被改过的文件已按字节还原（与**开工前**指纹一致）',
      all(_sha1(p) == s for p, s in _SHA0),
      u'%s' % ([(os.path.basename(p), _sha1(p) == s) for p, s in _SHA0],))

print(u'')
print(u'=' * 78)
print(u'mutate153：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
