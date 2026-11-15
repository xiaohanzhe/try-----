# -*- coding: utf-8 -*-
u"""第190轮 · 详版追加 §196（复检脚本的过期锚点）。

★ 详版是纯 LF（实测行尾无 `^M`）⇒ 追加块必须用 `\\n`，不许带 `\\r\\n`。
★ 二进制追加，前面一个字节不动。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DET = os.path.join(REPO, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')

BLOCK = u"""
## §196 判据绑死字面量 ⇒ 产品一演进就永假（第190轮 · `recheck113b` ②）

### 196.1 事实

`code-quality-audit/第113轮-全体角色AI训练/_tools/recheck113b.py` 的 ② 段有两条顺序判据：

```python
i_rel   = src.find("【你和其他人的关系（照这个，别自己编）】")
i_evo   = src.find("if isinstance(evolution, str) and evolution.strip():")
i_speak = src.find('parts.append(SPEAK_RULES)')       # ← 这里
ck('...', 0 <= i_rel < i_evo)
ck('...', 0 <= i_evo < i_speak)
```

第190轮改完核心文件跑它，结果 **81 / 1**，红的是第二条：实测 `39692 < -1`。

### 196.2 为什么是"早就红了"，不是"这轮弄坏的"

三条都能复算：

1. **这轮没碰那个文件** —— `git log --oneline -- ralsei_pet/modules/npc_persona.py`
   最后一次是 `ea67b36f 第140轮`。
2. **锚点在 `8b70d0f8~1` 存在、之后就没有** ——
   `git show 8b70d0f8~1:ralsei_pet/modules/npc_persona.py | grep -n 'parts.append(SPEAK_RULES)'`
   得第 **877** 行；`8b70d0f8`（第113轮h「角色档位两轴 machine / caps」）
   把它换成了 `parts.append(speak_rules_for(kind, npc_id))`。
3. **提交前那版也是 0 次** —— `git show 12c80e56:...| grep -c` 得 0。

⇒ `src.find()` 恒返 `-1`，`0 <= i_evo < -1` **永假**。从第113轮h 起一直红。

### 196.3 为什么一直没人发现

**它不在 `SUITES` 里**（`grep -c recheck113b code-quality-audit/regress/run_all.py` = 0）。
复检脚本是"某轮收尾时手动跑一次"的工具，红了只在那一次的报告里出现；
之后没人再跑，就再也没人看得见。

⇒ ★ **凡是不进 `SUITES` 的判据，它的红等于不存在。**
要么进回归，要么在脚本顶部写明"本脚本不设定期复查"。

### 196.4 判据该判什么

判**意图**（"speak 那一段必须排在演化卡之后"），不该判**某一行源码长什么样**。
产品写法一演进（常量 → 函数调用、直接赋值 → 辅助函数），绑死字面量的判据就变成永假。

### 196.5 修法与负控制

```python
# 两种写法都认；两种都找不到仍是 -1 ⇒ 照样红（不是恒真）
i_speak = max(src.find('parts.append(SPEAK_RULES)'),
              src.find('parts.append(speak_rules_for('))
```

负控制实测（拿真实源码，把两种写法都抹掉）：

| 输入 | i_evo | i_speak | 判据 |
|---|---|---|---|
| 真实源码 | 39692 | 39789 | 绿 |
| 抹掉两种写法 | 39692 | **-1** | **红** |

⇒ 判据有鉴别力，不是改宽成了恒真。修后复检 **82 / 0**。

### 196.6 与其它轮的同类

| 轮次 | 同型症状 |
|---|---|
| 159 | 判据过宽 ⇒ 误报（D7 全文搜 `background-color: transparent`） |
| 174 | 判据过窄 ⇒ `M11/M12/M13/M15` 锚点写 `\\n` 而盘上是 CRLF ⇒ `old in s` 恒假 |
| 176 | 判据/夹具错位 ⇒ 用四元组查"删掉的内容还在不在"，而那 42 条本来就重合 |
| **190** | **判据锚点绑死一段会演进的字面量 ⇒ 产品改了就永假，且不在回归里 ⇒ 无人发现** |

★ 共同点：**判据也是被测物**。改产品时，绑死实现细节的判据必须同步改口径，
而"同步"的前提是它**跑得起来** —— 不进 `SUITES` 的判据没有这个前提。
"""


def main():
    write = '--write' in sys.argv[1:]
    old = io.open(DET, 'rb').read()
    add = BLOCK.encode('utf-8')
    print(u'[详版] 现有 %d 字节 · 追加 %d' % (len(old), len(add)))
    if b'\r\n' in old[-4096:]:
        print(u'[停手] 详版尾部出现 CRLF，与预设的纯 LF 不符 ⇒ 不写')
        return 3
    if not write:
        print(u'[dry] 加 --write 落盘')
        return 0
    with io.open(DET, 'ab') as fh:
        fh.write(add)
    now = io.open(DET, 'rb').read()
    seg = now[len(old):]
    print(u'[写回] %d 字节' % len(now))
    print(u'[校验] 前缀一致 %s · 增量吻合 %s · 新增段裸LF %d / CRLF %d'
          % (u'OK' if now[:len(old)] == old else u'报红',
             u'OK' if len(seg) == len(add) else u'报红',
             seg.count(b'\n') - seg.count(b'\r\n'), seg.count(b'\r\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
