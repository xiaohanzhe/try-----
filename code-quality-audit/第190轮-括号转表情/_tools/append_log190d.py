# -*- coding: utf-8 -*-
u"""第190轮 · 追加当日日志 §13.6（复检脚本的过期锚点）。

★ 二进制追加，前面一个字节不动。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LOG = os.path.join(REPO, '.workbuddy', 'memory', '2026-11-15.md')

BLOCK = u"""
### 13.6 核心文件复检：抓到一条**从第113轮h 起就一直红着**的老锚点

改过 4 个产品文件 + 两份记忆 ⇒ 跑 `recheck113b.py`，结果 81/1。
红的是 ②「演化卡插在 SPEAK_RULES 之前」，实测 `39692 < -1`。

**不是我这轮弄坏的**，三步查证：
① 我**没动** `npc_persona.py`（`git log` 最后改动是 `ea67b36f 第140轮`）；
② `git show 8b70d0f8~1:...npc_persona.py` 有 `parts.append(SPEAK_RULES)`（第 877 行），
   而第113轮h **之后**变成了 `parts.append(speak_rules_for(kind, npc_id))`
   （角色档位两轴 machine/caps）⇒ `src.find()` 恒返 -1 ⇒ `0 <= i_evo < -1` **永假**；
③ 我提交前那版（`12c80e56`）的这个文件里该字面量**本来就是 0 次** ⇒ 早就红了。

**教训**：判据该判**意图**（"speak 那一段必须排在演化卡之后"），不该判**某一行源码长什么样**。
产品写法一演进（这轮是"常量 → 函数调用"），绑死字面量的判据就变成永假，
而它**又不在 `SUITES` 里**（`run_all.py` grep 计数 0）⇒ 红了也没人发现。

修法：`i_speak = max(find('parts.append(SPEAK_RULES)'), find('parts.append(speak_rules_for('))`
—— 两种写法都认，**两种都找不到仍是 -1、照样红**。
负控制实测：把两种写法都抹掉 ⇒ `i_speak=-1`、判据 RED（不是恒真）。复检 82/0。

★ 顺带记一条缺口：`recheck113b.py` 这类**复检脚本不进 `SUITES`**，
所以它的红只有在有人手动跑时才看得见 —— 今天就是靠"改完核心文件必须复检"这条规矩才撞出来的。
"""


def main():
    write = '--write' in sys.argv[1:]
    old = io.open(LOG, 'rb').read()
    add = BLOCK.encode('utf-8')
    print(u'[日志] 现有 %d 字节 · 追加 %d' % (len(old), len(add)))
    if not write:
        print(u'[dry] 加 --write 落盘')
        return 0
    with io.open(LOG, 'ab') as fh:
        fh.write(add)
    now = io.open(LOG, 'rb').read()
    print(u'[写回] %d 字节 · 前缀一致 %s · 增量吻合 %s'
          % (len(now), u'OK' if now[:len(old)] == old else u'报红',
             u'OK' if len(now) - len(old) == len(add) else u'报红'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
