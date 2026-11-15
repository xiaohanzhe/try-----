# -*- coding: utf-8 -*-
u"""第190轮（下半·接线）· 往记忆**详版**追加 §195（append-only）。

★ 追加前查撞号：§194 已存在，本节应为 195。
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

P = os.path.abspath(os.path.join(u'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本',
                                 '.workbuddy', 'memory', u'参考-契约与历轮（详版）.md'))

BODY = u"""
---

## 195. 第190轮（接线）· 括号动作 → 表情，全角色一视同仁（2026-11-15）

> 用户三条补充口径：
> ① 底板 `一句话，尽量按贴近原作即可` ⇒ **纯黑**
> ② `还有，难匹配也得匹配，后期微调就好` ⇒ **永远给一个表情，不许空着**
> ③ 上一轮已定 `一视同仁，不再是主体为 ralsei 的项目了`

### 195.1 整条链（四段，每段单独可验）

```
台词「（苦笑）算了」
  └─① strip_action_parentheticals(text, sink=acts)
       acts = ['苦笑']              ← 删掉的必须吐出来；返回值语义不变
  └─② acts_to_emotion(acts) = 'sad' ← **永远有值**（兜底 neutral）
       main._clean_ai_reply 存 self._pending_face_emotion
  └─③ pop_pending_face_emotion()   ← 取出即清，一句一个表情
       dialogue_ui._char_face_candidates('sad')
         = ['sad','big_sad','downer','sorrowful','disappointed','mourning',
            'normal','neutral','default','plain']
  └─④ sprite_loader.get_face_for(cid, name) 逐级试 → any_face_for(cid) 兜底
       贴到 face_label（#000000 底 + 2px 白边，84×84，KeepAspectRatio）
```

### 195.2 ★★★ 三个坑（都是本轮实测撞出来的）

**坑 1：兜底名不能只认 `normal`。** 原作各家"正常脸"名字不统一：

| 角色 | 正常脸 | 情绪数 |
|---|---|---|
| `hy_ace` / `hy_ed` | `normal` | 6 / 4 |
| `hy_ceroba_ketsukane` | `default` | 28 |
| **`hy_chujin_ketsukane`** | **只有 `neutral`** | 8 |

⇒ `_CHAR_FACE_BASE_NAMES = ('normal','neutral','default','plain')`，四个都试。
只写 `normal` 会让 chujin **永远贴不出图**（而它在 8 个角色里，占比 12.5%）。

**坑 2：`get_face_for` 的缓存键必须带角色 id。**
不同角色的 `normal.png` 是不同图片，只用文件名当键会**串图** ——
表现是"某个角色一直显示别人的脸"，而且看起来像素材错了。

**坑 3：最后一道保险 = `any_face_for(char_id)`。**
候选链一路没命中时拿该角色任意一张。宁可这张表情不够准（用户说会后期微调），
也不能让头像**停在上一个角色脸上** —— 后者是明显的错，前者只是不准。

### 195.3 ★★★ 差点只改一半：NPC 台词不走 `add_dialogue`

第一版只改了 `add_dialogue` 的 NPC 分支（`_is_npc_speaker(speaker)` 为真才走）。
查调用点才发现：

* `add_dialogue(<speaker>, ...)` 全项目只有 4 处调用，**speaker 全是 `"ralsei"`**
* NPC 台词的真正主路径是 **`add_npc_line(label, text)`**（`npc_speak` 回调走它）

⇒ 只改 `add_dialogue` 等于没改，NPC 头像永远不变。
补 `add_npc_line(label, text, char_id=None)`，在 `npc_speak` 回调里传 `npc_id`。

★ 判据 **D4b** 钉住这件事（AST 查签名 + 查调用处真的传了 `npc_id`），
否则以后有人改回去不会报错 —— 这是"改了但没接上"的典型暗雷。

### 195.4 ★★ Ralsei 自己那条链也得补，否则只接了一半

`ACT_EMOTION_RULES` 吐的是**短键**（`smile`/`laugh`/`cry`/`love`/`smug`/`hurt`），
而 Ralsei 的 `_FACE_MAP` 原来只有长键（`happy_very`/`sad_force_smile` …）。

`_resolve_face_name` 对未知键的兜底是**拼 `face_` 前缀** ⇒ 会去找 `face_smile.png`
这种不存在的文件 ⇒ `set_face` 查出缺失 ⇒ 回退 `face_normal`
⇒ **Ralsei 括号里的笑被吃掉**（NPC 那条链接得再好，主宠身上是白接的）。

⇒ 补 6 条（**全指向已存在素材**，不新建文件）：
`smile→face_normal_smile_little`、`laugh→face_happy_very`、
`cry→face_sad with a little hopeless`、`love→face_shy with touched and happy`、
`smug→face_happy and playful`、`hurt→face_a little sad`。

判据 **C6** 拿 `ralsei_face/` 实际文件清单验 18 个通用键**全部**能落到真实 png。

### 195.5 纯黑底板 = 一行 CSS

```
QLabel { background-color: #000000; border: 2px solid #ffffff; }   /* 原 transparent */
```

这是 §194.5 那 64 帧"纯白线看不见"的**全部解法**，素材一个像素没动：
79 帧黑底白线的黑矩形融进底板、64 帧白线清晰、21 帧剪影正常。
`preview_box190.py` 离线复现渲染规则，产物 `face_boxes.png` 8 个角色全部清晰。

### 195.6 已知缺口（本轮**不做**，如实登记）

`（想了想）` / `（尴尬地笑了笑）` 这类**不被护栏删掉**的括号**不触发表情**，
而且括号会原样显示在台词里。

原因：第188轮锁 `A22g` 明确"裸「笑」故意留在 `_ACTION_VERBS` 之外"
（否则 `（笑不出来）` 会被误伤成"在笑"），戊闸也只认"整段是标签"。
动它要改已锁定的护栏，需要单独拍口径 —— 不在本轮顺手扩大改动面。

★ 演示图 `chain_demo.png` 里把这一行**标红写出**，不藏。

### 195.7 本轮套件 `check190.py`（38 条，全绿）

| 段 | 条数 | 守住什么 |
|---|---|---|
| A sink 通道 | 6 | 删掉的能吐出来、返回值不变、空括号不记 |
| B 情绪映射 | 10 | 具体规则压过笼统规则（苦打压过笑）、兜底不空 |
| C 别名链 | 6 | 末尾四个底图名、未知键不吞、**Ralsei 侧 18 键全覆盖** |
| D 接线 | 8 | AST 找 `sink=`；**NPC 主路径 `add_npc_line`**；底色 #000 |
| E 素材可达 | 5 | 8 id × 18 键笛卡尔积全落真实图 + 端到端台词→png |
| F 自检 | 3 | 条数 / 只读 / `[PASS]` 字面量 |

★ E 段才是"难匹配也得匹配"的硬证据：不测"函数返回了值"，
而是拿**真实 manifest + 真实磁盘文件**验"一定贴得出图"。

### 195.8 三条写判据的教训（本轮自己踩的）

1. **判据范围要收窄**：D7 第一版全文搜 `background-color: transparent`，
   而别的控件（输入框/按钮）本来就有 ⇒ 恒红。改成**只取
   `self.face_label.setStyleSheet(...)` 那一块**。（"判据过宽=误报"，第159轮）
2. **夹具要按产品的真实分支选**：B8 第一版用 `['叹气','笑']` 验"取第一个"，
   而"叹气"本轮已归到 `tired`（具体情绪）⇒ 返回 tired 是**正确行为**，
   判据却期望 smile。正解是拿一个**落兜底**的动作打头（`轻轻敲了敲键盘`）。
3. **AST 取不到就怀疑自己**：D4b 一开始把 `_du_tree` 用在定义之前，
   `NameError` 直接崩 —— 自检类的判据要先跑通再谈严格。
"""


def main():
    if not os.path.isfile(P):
        print(u'[停手] 详版不存在：%s' % P)
        return 2
    s = io.open(P, encoding='utf-8').read()
    if re.search(u'^## 195\\.', s, re.M):
        print(u'[空转] §195 已存在，不重复追加')
        return 0
    before = len(s.encode('utf-8'))
    with io.open(P, 'a', encoding='utf-8', newline='\n') as fh:
        fh.write(BODY)
    back = io.open(P, encoding='utf-8').read()
    print(u'[写前] %d → [写后] %d（增量 %d）'
          % (before, len(back.encode('utf-8')),
             len(back.encode('utf-8')) - before))
    print(u'[自证] 旧内容逐字未变：%s' % (u'OK' if back.startswith(s) else u'报红'))
    print(u'[自证] §195 存在：%s' % (u'OK' if re.search(u'^## 195\\.', back, re.M) else u'报红'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
