# -*- coding: utf-8 -*-
u"""剧情进度标记（PLOT MARK）—— 第85轮 I10。

用户口径（第85轮，逐字）
------------------------
「**别毁，就是已经过完剧情了就好**」
「**只要不是在剧情里死了的npc就可以出现。不用。**」（第85轮后续裁定，逐字）
「**那就别判定死亡，就全部放行就好**」（第86轮收尾裁定，逐字）

⇒ 本模块**只记录**"这件事/这段剧情已经过完了"，**不做任何销毁**：
  · **不**删场景、**不**删 NPC 实例、**不**删道具、**不**清存档；
  · ★★★ **不**把标记当门控；★ **本项目也没有任何出场门控** ——
    「这段剧情过完了」**不等于**「NPC 从此不出现」，NPC **一律可出现**
    （用户第86轮裁定「**那就别判定死亡，就全部放行就好**」）。
    原作的 `instance_destroy()`（`if (global.plot >= 30)`）**本项目不实现**；
    连"剧情里已死亡"这套生死语义**也不建立**（第85轮曾设想它作唯一门控，
    第86轮**作废**）。⇒ `plot_threshold_reached()` 与全部标记**都不得**
    作为"某人不出场"的判据（回归锁 `check85` 以 AST 守这条）。
  · **不**做 UI 显示"剧情已过"（用户口径「**不用**」）。

★★★ 原作依据（第85轮 UTMT 反编译 Deltarune ch1，逐字取证）
----------------------------------------------------------
`gml_Object_obj_npc_susiedark_Create_0`（物证：`code-quality-audit/第85轮-原作用键与移速表取证/_evidence/`）::

    if (global.plot >= 30)
    {
        instance_destroy();
    }
    else
    {
        s = instance_create(450, 950, obj_soliddark);
        s.image_yscale = 8;
    }

**读法（四件事，必须说清）**：
  1. 写在**创建事件**里 ⇒ 房间加载时就决定这个 NPC 出不出场；
  2. `instance_destroy()` 销毁的是**这一个实例**，**不是存档 / 道具 / 玩家进度**；
  3. 语义 = 「剧情走到 30 之后，这个 NPC 不再出现」—— 是**出场门控**，不是"自毁"；
  4. ★★★ **但本项目既不采用第 3 条的语义，也不建立任何出场门控**（用户裁定，逐字）：
     第85轮「**只要不是在剧情里死了的npc就可以出现**」；
     第86轮「**那就别判定死亡，就全部放行就好**」（★ 连"死亡判定"本身也取消）。
     ⇒ 原作拿 `global.plot` 当**出场门控**，本项目**一律不做** ——
       NPC 出场**不受任何条件限制**（"剧情过完"不挡、"生死"也不判）。

`global.plot` 是**单调递增的剧情进度计数器**，本产物里可核到的阈值：
`>= 30`、`>= 245`（正向）/ `< 120`、`< 150`（反向）。
全局表登记：`{"name": "plot", "instance": "Global"}`。

★★ 诚实标注
------------
* **原作没有**给玩家任何"剧情已过"的**文本提示**
  （`dr85_strings.json` 里含 `plot` 的条目 = **0**）；
  ⇒ 本项目**也不做** UI 显示（用户第85轮口径「**不用**」）。
* 原作的"进度"是内存里的 `global.plot`，**每章重来**；
  本项目的标记是**持久化**的（因为桌宠要跨会话记得"你过完了"）—— 是**扩展**。

★★ 与"生死"的关系（**已作废，别复原**）
--------------------------------------
第85轮曾设想：出场门控**只认**「这个 NPC 在剧情里死了没」（生死语义），
与本模块的进度标记**分开算**。
★★★ 第86轮用户裁定**作废**了这套设想 —— 原话「**那就别判定死亡，就全部放行就好**」：
  · **不建立**任何生死语义的真源；
  · **不设**任何出场门控 ⇒ NPC **一律可出现**；
  · 本模块的 `plot` 标记**依旧只记录**（与出场**毫无关系**）。
（回归锁 `check85` F 段以 AST 守"门控绝不接线"，防"同一份规则两处算"。）

三条纪律（与 `possession` / `scene_camera` / `npc_system` 同源）
----------------------------------------------------------------
1. 只允许模块顶部 `import logging`。**禁 import Qt、禁 import 任何项目内模块**。
2. 内部函数**不许**再 import（回归锁 `check84` 用 AST 强制这条）。
3. 不认识的东西**返回 `None` / `False`，不猜、不就近凑**。
"""
import logging

#: 本模块的 schema 版本（与 `item_system` / `possession` 同规）。
SCHEMA_VERSION = 1

#: 标记的 key 前缀（避免与将来的其它"事件标记"混在一格里）。
PLOT_PREFIX = 'plot:'

#: 原作那几个阈值 —— **只登记，不用**（"找不到出处"的变量最容易被后人篡改）。
#: 出处见模块头；单位是"进度点"，不是房间号。
#: ★★★ 用户裁定：「剧情过完 ≠ NPC 消失」（第85轮）＋「**那就别判定死亡，就全部放行**」
#: （第86轮）⇒ 这些阈值**永不**用于任何出场门控（本项目**根本没有**出场门控）。
PLOT_THRESHOLDS = (30, 120, 150, 245)


def _pet_logger_name(_name):
    """把模块 `__name__` 映射到 `ralsei_pet.` 命名空间下的名字（零依赖，同兄弟模块）。"""
    if not _name or _name == '__main__':
        return 'ralsei_pet.main'
    if _name.startswith('ralsei_pet.'):
        return _name
    if _name.startswith('modules.'):
        return 'ralsei_pet.' + _name
    return 'ralsei_pet.' + _name


_log = logging.getLogger(_pet_logger_name(__name__))


def mark_key(what):
    """把"一件已过完的事"归一成**存储 key**；认不出（空 / 非字符串）⇒ `None`。

    ★ 为什么统一加前缀：标记桶将来还会放别的（成就、见面对话…），
      不加前缀迟早撞名 —— "一个 key 两个意思"是本项目反复踩过的坑
      （如 `PossessionState.release` 与 `release_key` 那次）。
    """
    if not isinstance(what, str):
        return None
    s = what.strip()
    if not s:
        return None
    if s.startswith(PLOT_PREFIX):
        return s
    return PLOT_PREFIX + s


def mark_done(marks, what, note=None):
    """★ **只记录**"`what` 已经过完"。（纯函数：返回**新**字典，不改输入。）

    ★★★ 这是本模块的**全部副作用** —— 就是"写一个 True"。
      没有 `instance_destroy` 的等价物、不删任何东西（用户口径「**别毁**」）。

    :param marks: 现有标记表（`dict` 或 `None`）
    :param what: 事/剧情的标识（字符串）
    :param note: 可选备注（存进 `'note'`，供报告/调试读）
    :return: 新的标记表（`what` 认不出 ⇒ 原样返回一个**等价副本**）
    """
    out = dict(marks) if isinstance(marks, dict) else {}
    key = mark_key(what)
    if key is None:
        return out
    rec = {'done': True, 'schema_version': SCHEMA_VERSION}
    if note:
        rec['note'] = str(note)
    out[key] = rec
    return out


def is_done(marks, what):
    """`what` 是否被标记为"已过完"。**认不出的一律 `False`**（不猜）。"""
    key = mark_key(what)
    if key is None or not isinstance(marks, dict):
        return False
    rec = marks.get(key)
    if isinstance(rec, dict):
        return bool(rec.get('done'))
    if isinstance(rec, bool):
        return rec      # 容忍"历史上存成裸布尔"的旧格（不报错、不迁移）
    return False


def done_keys(marks):
    """所有"已过完"的 key，**去前缀、排序**（供报告 / UI 显示）。"""
    if not isinstance(marks, dict):
        return ()
    out = []
    for k, v in marks.items():
        if not isinstance(k, str) or not k.startswith(PLOT_PREFIX):
            continue
        done = v.get('done') if isinstance(v, dict) else v
        if done:
            out.append(k[len(PLOT_PREFIX):])
    return tuple(sorted(out))


def plot_threshold_reached(plot_value, threshold=30):
    """照抄原作 `if (global.plot >= 30)` 的比较（**只用于判"到没到"**）。

    ⚠️ **本函数在本项目当前不接线，且已裁定永远不用于出场判定**：
      · 本项目没有 `global.plot` 这个运行时计数器
        （第85轮取证只找到它的阈值用法，没找到"谁在给它加"）；
      · ★★★ 用户第85轮裁定「**只要不是在剧情里死了的npc就可以出现**」，
        第86轮进一步裁定「**那就别判定死亡，就全部放行就好**」
        ⇒ **本项目不设任何出场门控**（既不按进度、也不按生死），
        所以这里的 `>= 30` **不许**被拿去挡任何 NPC 出场。
        留在这里是**为了将来接原作进度时有个唯一出处**。
      现在调用它不会有任何后果 —— 它是个纯比较，**不触发任何销毁**
      （原作的 `instance_destroy()` **不在这里**，在本项目里也**不存在**）。
    """
    try:
        p = int(plot_value)
    except (TypeError, ValueError):
        return False
    return p >= int(threshold)


def as_dict(marks):
    """导出快照（形状恒定的 dict；非 dict 输入 ⇒ 空表）。"""
    return {'schema_version': SCHEMA_VERSION,
            'marks': dict(marks) if isinstance(marks, dict) else {}}


def load_dict(data):
    """从快照恢复。**只认显式列出的格**；非法输入 ⇒ 空表 + `False`（同 `ConsentState`）。"""
    if not isinstance(data, dict):
        return ({}, False)
    marks = data.get('marks')
    if not isinstance(marks, dict):
        return ({}, False)
    clean = {}
    for k, v in marks.items():
        if not isinstance(k, str) or not k.startswith(PLOT_PREFIX):
            continue
        if isinstance(v, dict):
            clean[k] = {'done': bool(v.get('done')),
                        'schema_version': SCHEMA_VERSION}
            if v.get('note'):
                clean[k]['note'] = str(v['note'])
        elif isinstance(v, bool):
            clean[k] = {'done': v, 'schema_version': SCHEMA_VERSION}
    return (clean, True)
