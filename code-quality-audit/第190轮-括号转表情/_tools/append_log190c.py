# -*- coding: utf-8 -*-
u"""第190轮（接线收口）· 追加当日日志 §13。

★ 二进制追加（`ab`）：当日日志是 **append-only**，一个字节都不许改前面。
★ 不写 `[PASS]` / `[FAIL]` 字面量 —— `run_all.py` 按出现次数统计，回显会污染计数。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LOG = os.path.join(REPO, '.workbuddy', 'memory', '2026-11-15.md')

BLOCK = u"""
## 13. 产品侧接线落地（用户裁定后）

### 13.1 用户两条补充口径（推翻了我原来的设计）

- `一句话，尽量按贴近原作即可` ⇒ 头像底板 **纯黑 `#000000`**（方案 B，我原默认是 #2A2C33）
  理由：UT/DR 的表情框本来就是这个样子，且黑底同时解决三套底色（§12.3 那 64 帧纯白线）。
- `还有，难匹配也得匹配，后期微调就好` ⇒ 情绪映射**永远返回一个值**，兜底 `neutral`。
  这条**推翻**了 §12.5 末尾写的"匹配不上 ⇒ 只做动作、不换表情"。

### 13.2 整条链四段（全部落地）

```
台词「（苦笑）算了」
  → strip_action_parentheticals(text, sink=acts)   ① 删掉的吐出来
  → acts_to_emotion(acts)                          ② 永远有值
  → _char_face_candidates(emo)                     ③ 展开成该角色真有的名字
  → sprite_loader.get_face_for / any_face_for      ④ 逐级取图
```

### 13.3 四个真坑

1. **`add_npc_line` 才是 NPC 台词主路径**，不是 `add_dialogue`。
   `add_dialogue(<speaker>, ...)` 全项目只有 4 处调用、speaker **全是 `"ralsei"`**
   ⇒ 只改 `add_dialogue` 的 NPC 分支等于没改。判据 `D4b` 钉住。
2. **Ralsei 侧也得补**：`ACT_EMOTION_RULES` 吐短键（`smile`/`laugh`/…），
   而 `_FACE_MAP` 原来只有长键 ⇒ 兜底拼 `face_` 前缀 ⇒ 找 `face_smile.png`（不存在）
   ⇒ 回退 `face_normal` ⇒ **Ralsei 括号里的笑被吃掉**。补 6 条，全指向已有素材。
3. **原作各家"正常脸"名字不统一**：`hy_ace`/`hy_ed` 是 `normal`、
   `hy_ceroba_ketsukane` 是 `default`、**`hy_chujin_ketsukane` 只有 `neutral`**。
   ⇒ `_CHAR_FACE_BASE_NAMES = ('normal','neutral','default','plain')` 四个都试，
   最后还有 `any_face_for()` 拿该角色任意一张。
4. **★★★ 己闸记账不能包闭包**：第一版把 `_ANY_PAREN_RE.sub` 的回调从模块级
   `_rescue_voice` 换成函数内 `_rescue_voice_note` ⇒ `check188`/`check189` 双红。
   三处依赖裸名：`check189 D3`（必须是模块级）、`check188 D3`/`check189 D2`（按回调名判闸序）、
   `probe188.py`（monkeypatch `E._rescue_voice` 关闸）。
   修法＝**先 `finditer` 扫一遍记账，再裸名交 sub**，语义与顺序一字不变。

### 13.4 回归

**187 套件 / PASS=8260 / FAIL=0**（`check99` 判 `IDENTICAL*` 仅空行噪声，未刷基线）。
`check190` 38 条全绿，已固化进基线（`check81 G5` 通过）。
另刷 8 个套件基线：`dialog_turn52` / `check132` / `check133` / `check182` / `check185` /
`check186`（我在 `main.py` 加行 ⇒ 它们回显的行号/导入清单漂了，断言全 PASS）、
`check188` / `check189`（同上，行号 825→866 一类漂移）。

### 13.5 记忆速查本

`E1 净减或持平` 卡了三轮（+78 → +18 → +10 → +5 → −5）。最后靠**合并 5 组老条目**
（169+170 / 171~173 / 178~181）+ 190 条瘦身腾出空间，新增「190 接线」一条。
★ `E2` 第一版报红：我硬凑了个点路径令牌 `PreCreate.doorRoom`，详版里查不到。
**没有**往详版补一句去"自证"（那等于为了让判据变绿去写内容），而是**不造这个令牌**
（改回 `` `PreCreate` 写 `doorRoom` ``，两个词各自都在详版里）。复检 15 条全绿。
"""


def main():
    write = '--write' in sys.argv[1:]
    old = io.open(LOG, 'rb').read()
    add = BLOCK.encode('utf-8')
    print(u'[日志] 现有 %d 字节' % len(old))
    print(u'[追加] %d 字节 ⇒ %d 字节' % (len(add), len(old) + len(add)))
    if not write:
        print(u'[dry] 加 --write 落盘')
        return 0
    with io.open(LOG, 'ab') as fh:
        fh.write(add)
    now = io.open(LOG, 'rb').read()
    print(u'[写回] %d 字节' % len(now))
    print(u'[校验] 前缀逐字节一致 %s'
          % (u'OK' if now[:len(old)] == old else u'报红'))
    print(u'[校验] 增量 == 追加量 %s'
          % (u'OK' if len(now) - len(old) == len(add) else u'报红'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
