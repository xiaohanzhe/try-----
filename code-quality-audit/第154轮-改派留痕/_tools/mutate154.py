# -*- coding: utf-8 -*-
u"""第154轮 · 破坏性负控制：逐条拆掉"改派留痕"，**指定**判据必须报红。

`check154` 全绿证明不了什么 —— 全绿也可能因为判据恒真。
这里逐条破坏产品，断言**恰好**是那几条判据变红（多红一条、少红一条都算不合格），
然后**按字节还原**（sha1 校验）。最后再跑一次 `check154`，必须回到全绿。

| # | 破坏 | 期望变红 |
|---|------|----------|
| M1 | 改派**根本不留痕**（把整段删掉） | `A1` `A1b` `A4` `A5` `A8b` `C2` `C3` `C4` |
| M2 | 去掉 `_prev is not None`（手上没东西也说"我本来要去 ?"） | `A1` `A1b` `A2` `A4` `A6` `A7` `A8` `A8b` |
| M3 | 门控拒那条**不再 return**（继续把旧差事换掉） | `A3` `A3b` |
| M4 | 叫停的记忆被写成"又被派去别处"（两件事一句话） | `C4` |
| M5 | 对话层**不把 prev 传给 ack** | `B1` |
| M6 | ack 里**不加**"原来那件被作废了"这句 | `B3a` `B3` |
| M7 | 门控拒也把 prev 传出去（没派成也说"改派了"） | `B4` |
| M8 | `prev` 改成**必填**参数（既有调用点全崩） | `C5` |
| M9 | 去掉 `_new is not None`（**派发失败也写痕** = 假记忆） | `A7` |
| M10 | `assign` 侧去掉 `_errand_same_job`（同一件事重说也留痕） | `A8` |
| M11 | `ack` 侧去掉 `_errand_same_job`（同事实也说"被作废了"） | `B5` |
| M12 | `_errand_same_job` **只比地点**（判据过宽 ⇒ 把真改派一起吃掉） | `A8b` |

## 写期望时先问两句（第150~153轮的教训，这里又用上）

- **"这处改动还有谁在盯？"** —— `M1` 一处删掉，`A1`/`A1b`（有没有记、记全没记全）/
  `A4`（连改两次要两条）/`A5`（空事由文案）/`A8b`（同地换事由也要记）/
  `C2`（note 处数 + 先后）/`C3`（改派那处在门控支之外）一起塌：它们**不是七个独立
  信号**，是同一条"没有留痕"的七个观测面。
- **"改的到底是哪一处？"** —— `main.py` 里 `'我本来要去 %s，但去不了 —— %s'`
  **出现两次**（`assign_errand` 与 `handle_errand_command` 各一处）
  ⇒ M3 的锚点必须带上 `'差事被门控拒绝'` 那行才唯一。**唯一性靠上下文，不靠运气**（§153 同款）。
- **"这条破坏会不会连带打断别的东西？"** —— M2/M9/M10/M12 动的都是
  `if _new is not None and _prev is not None and not _errand_same_job(...)`
  这**同一个三连条件**的不同项，所以四处锚点必须**逐字区分**（见各自的 pairs），
  否则跑起来会"破坏了一处、红的是另一处的账"。
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
CHECK154 = os.path.join(HERE, 'check154.py')
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
    p = subprocess.Popen([PY, CHECK154], cwd=ROOT, env=env,
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

# M1 改派根本不留痕
mutate(u'M1', MAIN,
       [(u"        if _new is not None and _prev is not None \\\r\n"
         u"                and not _errand_same_job(_prev, dest_scene, what):\r\n"
         u"            _p_dest = getattr(_prev, 'dest_scene', u'') or u'?'\r\n"
         u"            _p_what = getattr(_prev, 'what', u'') or u''\r\n"
         u"            _p_txt = (u'\u529e\u300c%s\u300d' % _p_what) if _p_what else u'\u8d70\u4e00\u8d9f'\r\n"
         u"            _n_txt = (u'\u529e\u300c%s\u300d' % what) if what else u'\u8d70\u4e00\u8d9f'\r\n"
         u"            _log.info('\u6539\u6d3e\uff1a%s \u4ece %s\uff08%s\uff09\u6539\u53bb %s\uff08%s\uff09',\r\n"
         u"                      npc_id, _p_dest, _p_txt, dest_scene, _n_txt)\r\n"
         u"            self._npc_errand_note(\r\n"
         u"                npc_id, u'\u6211\u672c\u6765\u8981\u53bb %s %s\uff0c\u8fd8\u6ca1\u529e\u5b8c\uff0c'\r\n"
         u"                        u'\u53c8\u88ab\u6d3e\u53bb %s %s\u4e86'\r\n"
         u"                        % (_p_dest, _p_txt, dest_scene, _n_txt))\r\n",
         u"        pass\r\n")],
       [u'A1', u'A1b', u'A4', u'A5', u'A8b', u'C2', u'C3', u'C4'])

# M2 去掉 `_prev is not None`
#
# ★ 这条会**连坐一大片**：`_prev is not None` 正是"首次派活不许编造"的那道闸，
#   拆掉它 ⇒ **每一个带"首次派活"的夹具都多出一条幽灵痕迹**
#   （A1 变 2 条、A4 变 3 条、A6/A8b 各多一条、A7 在派发失败时也写、A8 同事实也写）。
#   ⇒ 这 8 条不是 8 个独立信号，而是"同一道闸被拆"的 8 个观测面（§153 同款）。
mutate(u'M2', MAIN,
       [(u"        if _new is not None and _prev is not None \\\r\n"
         u"                and not _errand_same_job(_prev, dest_scene, what):\r\n",
         u"        if _new is not None \\\r\n"
         u"                and not _errand_same_job(_prev, dest_scene, what):\r\n")],
       [u'A1', u'A1b', u'A2', u'A4', u'A6', u'A7', u'A8', u'A8b'])

# M3 门控拒那条不再 return（继续把旧差事换掉）
mutate(u'M3', MAIN,
       [(u"        if not ok:\r\n"
         u"            _log.info('\u5dee\u4e8b\u88ab\u95e8\u63a7\u62d2\u7edd\uff1a%s \u2192 %s\uff08%s\uff09', npc_id, dest_scene, why)\r\n"
         u"            self._npc_errand_note(npc_id,\r\n"
         u"                                  '\u6211\u672c\u6765\u8981\u53bb %s\uff0c\u4f46\u53bb\u4e0d\u4e86 \u2014\u2014 %s' % (dest_scene, why))\r\n"
         u"            return None\r\n",
         u"        if not ok:\r\n"
         u"            _log.info('\u5dee\u4e8b\u88ab\u95e8\u63a7\u62d2\u7edd\uff1a%s \u2192 %s\uff08%s\uff09', npc_id, dest_scene, why)\r\n"
         u"            self._npc_errand_note(npc_id,\r\n"
         u"                                  '\u6211\u672c\u6765\u8981\u53bb %s\uff0c\u4f46\u53bb\u4e0d\u4e86 \u2014\u2014 %s' % (dest_scene, why))\r\n")],
       [u'A3', u'A3b'])

# M4 叫停的记忆被写成"又被派去别处"（两件事一句话）
mutate(u'M4', MAIN,
       [(u"            npc_id, u'\u6211\u672c\u6765\u8981\u53bb %s \u529e\u300c%s\u300d\uff0c"
         u"\u8fd8\u6ca1\u529e\u5b8c\u5c31\u88ab\u53eb\u56de\u6765\u4e86%s'\r\n",
         u"            npc_id, u'\u6211\u672c\u6765\u8981\u53bb %s \u529e\u300c%s\u300d\uff0c"
         u"\u8fd8\u6ca1\u529e\u5b8c\uff0c\u53c8\u88ab\u6d3e\u53bb\u522b\u5904\u4e86%s'\r\n")],
       [u'C4'])

# M5 对话层不把 prev 传给 ack
mutate(u'M5', MAIN,
       [(u"                         prev=(_prev if ok else None))\r\n",
         u"                         prev=None)\r\n")],
       [u'B1'])

# M6 ack 里不加"原来那件被作废了"这句
mutate(u'M6', MAIN,
       [(u"            # \u2605 \u7b2c154\u8f6e\uff1a**\u540c\u4e00\u4ef6\u4e8b\u91cd\u8bf4\u4e00\u904d\u4e0d\u7b97\u6539\u6d3e**\uff08`_errand_same_job`\uff09\r\n"
         u"            #   \u2014\u2014 \u4e00\u4ef6\u90fd\u6ca1\u88ab\u4f5c\u5e9f\uff0c\u8fd9\u65f6\u8bf4\"\u539f\u6765\u90a3\u4ef6\u88ab\u4f5c\u5e9f\u4e86\"\u662f\u65e0\u4e2d\u751f\u6709\u3002\r\n"
         u"            if prev is not None and not _errand_same_job(prev, dest_scene, what):\r\n"
         u"                _p_dest = getattr(prev, 'dest_scene', u'') or u'?'\r\n"
         u"                _p_what = getattr(prev, 'what', u'') or u''\r\n"
         u"                brief += ('\uff08\u2605 \u8865\u5145\u4e8b\u5b9e\uff1a\u4ed6\u624b\u4e0a\u539f\u672c\u8fd8\u6709\u4e00\u4ef6\u4e8b \u2014\u2014 "
         u"\u53bb\u300c%s\u300d\u529e\u300c%s\u300d\uff0c'\r\n"
         u"                          '\u5df2\u7ecf\u88ab\u8fd9\u6b21\u6539\u6d3e**\u4f5c\u5e9f**\u4e86\u3002"
         u"\u8981\u4e0d\u8981\u8ddf\u7528\u6237\u63d0\u3001\u600e\u4e48\u63d0\uff0c'\r\n"
         u"                          '\u4f60\u81ea\u5df1\u51b3\u5b9a\uff1b\u522b\u63d0\u8fd9\u6761\u63d0\u793a\u3002\uff09'\r\n"
         u"                          % (self._errand_place_label(_p_dest),\r\n"
         u"                             _p_what or u'\u90a3\u4e00\u8d9f'))\r\n",
         u"            pass\r\n")],
       [u'B3a', u'B3'])

# M7 门控拒也把 prev 传出去
mutate(u'M7', MAIN,
       [(u"                         prev=(_prev if ok else None))\r\n",
         u"                         prev=_prev)\r\n")],
       [u'B4'])

# M8 prev 改成必填参数
mutate(u'M8', MAIN,
       [(u"    def _errand_ack(self, asker_id, target_id, dest_scene, what, ok, why,\r\n"
         u"                    prev=None):\r\n",
         u"    def _errand_ack(self, asker_id, target_id, dest_scene, what, ok, why,\r\n"
         u"                    prev):\r\n")],
       [u'C5'])

# M9 去掉 `_new is not None` ⇒ 派发失败也写痕（假记忆）
mutate(u'M9', MAIN,
       [(u"        if _new is not None and _prev is not None \\\r\n"
         u"                and not _errand_same_job(_prev, dest_scene, what):\r\n",
         u"        if _prev is not None \\\r\n"
         u"                and not _errand_same_job(_prev, dest_scene, what):\r\n")],
       [u'A7'])

# M10 assign 侧去掉 same_job ⇒ 同一件事重说也留痕
mutate(u'M10', MAIN,
       [(u"        if _new is not None and _prev is not None \\\r\n"
         u"                and not _errand_same_job(_prev, dest_scene, what):\r\n",
         u"        if _new is not None and _prev is not None:\r\n")],
       [u'A8'])

# M11 ack 侧去掉 same_job ⇒ 同事实也说"被作废了"
mutate(u'M11', MAIN,
       [(u"            if prev is not None and not _errand_same_job(prev, dest_scene, what):\r\n",
         u"            if prev is not None:\r\n")],
       [u'B5'])

# M12 判据过宽：只比地点 ⇒ 同地换事由也算"同一件"
mutate(u'M12', MAIN,
       [(u"    return (getattr(prev, 'dest_scene', None) == dest_scene\r\n"
         u"            and _p_what == _n_what)\r\n",
         u"    return (getattr(prev, 'dest_scene', None) == dest_scene)\r\n")],
       [u'A8b'])

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
print(u'mutate154：PASS=%d FAIL=%d' % (_n_ok, _n_bad))
if _failed:
    print(u'失败项：')
    for _d in _failed:
        print(u'  - %s' % _d)
sys.exit(0 if _n_bad == 0 else 1)
