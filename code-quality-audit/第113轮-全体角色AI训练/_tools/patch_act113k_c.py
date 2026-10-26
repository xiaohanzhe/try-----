# -*- coding: utf-8 -*-
"""第113轮k · 补丁 9：把「活动 → 去处」接进 prompt（main 侧）。

用户口径
--------
「咱吃饭去吧」→「那要不去 XXX 家餐厅？」。所以信号是**对方刚说的话**。

接线
----
`chat_with_ai(text=…)` 里已经有用户原话 ⇒ 传 `heard=text` 给 `npc_system_prompt`
⇒ 再传给 `_npc_life_blocks` ⇒ 只有检测到活动意图时才追加 ④ 块。

★ 为什么必须**只在有 heard 且检测到活动**时才产块：
  这条 prompt 是**每个** NPC 每次都用的。无条件加几行 = 给所有人改人设 ——
  本项目最贵的坑就是"看起来无害的一行注入把角色演成同一个人"。
  所以默认路径**一字不变**（`heard=None` ⇒ 整块跳过）。

★ 为什么章要从"当前场景 → 归属地"两级取：
  跨作品角色（`_placement.json` 里 `scene=null`）不在任何场景里，但它的
  `home` 有章（`oneshot.mainline.FINALE` ⇒ `oneshot`）。都取不到就**不产块**：
  宁可这次不张罗，也不能推荐另一个世界的餐厅。

守门与 patch4~8 一致。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')


def rd(p):
    return io.open(p, encoding='utf-8', newline='').read()


def wr(p, t):
    io.open(p, 'w', encoding='utf-8', newline='').write(t)
    assert rd(p) == t, '写回与内存不一致：%s' % p


def swap(t, old, new, tag, must=None):
    assert t.count(old) == 1, '%s 锚命中 %d 次（需 1）' % (tag, t.count(old))
    c0 = t.count('\r\n')
    t2 = t.replace(old, new, 1)
    assert t2 != t, '%s 替换无变化' % tag
    if must:
        assert must in t2, '%s 没写进 %r' % (tag, must)
    need = new.count('\r\n') - old.count('\r\n')
    got = t2.count('\r\n') - c0
    assert got == need, '%s CRLF 增量 %d（应 %d）' % (tag, got, need)
    return t2


# ---------------------------------------------------------------- 1) npc_system_prompt 收 heard
A1_OLD = (
    "    def npc_system_prompt(self, npc_id):\r\n"
    "        \"\"\"某个 NPC 的 system prompt —— **唯一出口**。\r\n"
)
A1_NEW = (
    "    def npc_system_prompt(self, npc_id, heard=None):\r\n"
    "        \"\"\"某个 NPC 的 system prompt —— **唯一出口**。\r\n"
    "\r\n"
    "        `heard` = **对方刚说的那句话**（第113轮k）。用来认「他要去干什么」\r\n"
    "        （「咱吃饭去吧」 ⇒ 吃饭），好让这个 NPC 能接一句「那要不去 XXX」。\r\n"
    "        ★ 默认 `None` ⇒ 行为与第113轮j **逐字相同**（不产活动块）。\r\n"
)

# ---------------------------------------------------------------- 2) 传下去
A2_OLD = "            life=self._npc_life_blocks(npc_id),\r\n"
A2_NEW = "            life=self._npc_life_blocks(npc_id, heard=heard),\r\n"

# ---------------------------------------------------------------- 3) 两个新方法（插在 _scene_place_label 之后）
A3_OLD = (
    "        return label or ch_name\r\n"
    "\r\n"
    "    def _npc_life_blocks(self, npc_id):\r\n"
)

A3_NEW = '''        return label or ch_name

    # ---------------------------------------------------------------- 活动与去处（第113轮k）

    def _activity_chapter(self, npc_id):
        """他**现在属于哪一章** —— `ch1.castle_town.x` ⇒ `ch1`；判不出 ⇒ `''`。

        ★ 先看当前场景，再看归属地：跨作品角色（`_placement.json` 里 `scene=null`）
          不在任何场景里，但它登记的 `home` 有章。
        ★ 都判不出 ⇒ `''`，调用方据此**不产块**。宁可这次不张罗，
          也不能推荐另一个世界的餐厅 —— 那是硬错，模型会当真。
        """
        sid = None
        try:
            sid = self._npc_scene_id()
        except Exception as e:
            _log.debug('当前场景解析失败（继续看归属地）: %s', e)
        if not sid:
            try:
                if self.npc_placement is not None:
                    sid = self.npc_placement.home_of(npc_id)
            except Exception as e:
                _log.debug('归属地解析失败（按无章处理）: %s', e)
        if not isinstance(sid, str) or not sid:
            return ''
        return sid.split('.')[0]

    def _activity_places(self, kind, chapter):
        """`chapter` 里「能 kind 这件事」的地点 ⇒ `[(scene_id, 可读名), ...]`。

        ★★ 三条硬约束，每条都是第113轮k 实测踩出来的：
          1. **只在本章里找** —— 跨作品推荐是硬错。
          2. **必须剥掉区段名**再匹配：`ch5` 整个区叫 `garden`、房间 id 全是
             `dw_garden_*`，不剥的话 106 间房会全部判成"公园"。
          3. **只认强信号**（房间名 / 剥过前缀的原作名），**不用区名** ——
             否则「这个区叫希望之园」会被读成「每间房都是公园」。
        ★ 缓存：2166 个场景，每次说话都全扫一遍太贵。
        """
        if not chapter:
            return []
        key = (kind, chapter)
        cache = getattr(self, '_act_places_cache', None)
        if cache is None:
            cache = {}
            self._act_places_cache = cache
        if key in cache:
            return cache[key]

        out = []
        try:
            for sid, info in self._scene_label_map().items():
                sid_s = str(sid)
                if not sid_s.startswith(chapter + '.'):
                    continue
                _ch, _area, _name, _derived, _raw = info
                parts = sid_s.split('.')
                area_id = parts[1] if len(parts) >= 3 else ''
                core = npc_life_mod.room_word(_raw)
                if area_id and core.startswith(area_id + ' '):
                    core = core[len(area_id) + 1:]
                # 强信号文本：剥过前缀/区段名的原作名 +（非推导时）场景名
                text = '%s %s' % (core, '' if _derived else _name)
                if not npc_life_mod.place_matches(text, kind):
                    continue
                lbl = self._scene_place_label(sid_s)
                if lbl:
                    out.append((sid_s, lbl))
        except Exception as e:
            _log.debug('活动候选筛选失败（按无候选处理）: %s', e)
            out = []

        out.sort(key=lambda pair: pair[0])   # 确定性顺序 ⇒ 同一句话每次同样结果
        cache[key] = out
        return out

    def _npc_life_blocks(self, npc_id, heard=None):
'''

# ---------------------------------------------------------------- 4) ④ 块
A4_OLD = (
    "            _log.debug('熟络度分片失败（已忽略）: %s', e)\r\n"
    "        return '\\n\\n'.join(out)\r\n"
)
A4_NEW = (
    "            _log.debug('熟络度分片失败（已忽略）: %s', e)\r\n"
    "        # ---- ④ 活动与去处（★ 第113轮k）----\r\n"
    "        #   ★ 只在**对方刚说了要去干什么**时才产块（`heard`）。这条 prompt 是\r\n"
    "        #     每个 NPC 每次都用 —— 无条件加几行等于给所有人改人设。\r\n"
    "        #   ★ 没有候选就**不产块**（`activity_hint` 返回空串），绝不写\r\n"
    "        #     \"附近没什么地方\"这种废话。\r\n"
    "        if heard:\r\n"
    "            try:\r\n"
    "                _act, _hit = npc_life_mod.detect_activity(heard)\r\n"
    "                if _act:\r\n"
    "                    _places = self._activity_places(\r\n"
    "                        _act, self._activity_chapter(npc_id))\r\n"
    "                    _hint = npc_life_mod.activity_hint(_act, _places)\r\n"
    "                    if _hint:\r\n"
    "                        out.append(_hint)\r\n"
    "            except Exception as e:\r\n"
    "                _log.debug('活动分片失败（已忽略）: %s', e)\r\n"
    "        return '\\n\\n'.join(out)\r\n"
)

# ---------------------------------------------------------------- 5) chat_with_ai 传 heard
A5_OLD = "                system = self.npc_system_prompt(_npc_id)\r\n"
A5_NEW = "                system = self.npc_system_prompt(_npc_id, heard=text)\r\n"


def main():
    t = rd(MAIN)
    gap = len(t.splitlines()) - t.count('\r\n')
    assert gap in (0, 1), 'main.py 不是全 CRLF：gap=%d' % gap

    if '_activity_places' in t:
        print('main.py 已有活动接线，跳过')
        return 0

    t = swap(t, A1_OLD, A1_NEW, 'npc_system_prompt', must='heard=None')
    t = swap(t, A2_OLD, A2_NEW, 'life 传参', must='heard=heard')
    # ★ A3_NEW 是三引号块（真实 LF），文件是 CRLF ⇒ 必须先转，否则 CRLF 增量是负数
    A3_NEW_CRLF = A3_NEW.replace('\n', '\r\n')
    t = swap(t, A3_OLD, A3_NEW_CRLF, '两个新方法', must='def _activity_places')
    t = swap(t, A4_OLD, A4_NEW, '④ 块', must='detect_activity')
    t = swap(t, A5_OLD, A5_NEW, 'chat_with_ai 传 heard', must='heard=text')

    gap2 = len(t.splitlines()) - t.count('\r\n')
    assert gap2 in (0, 1), '写回后不是全 CRLF：gap=%d' % gap2
    wr(MAIN, t)
    print('main.py OK 行数=%d' % len(t.splitlines()))
    print('EXIT=0')
    return 0


if __name__ == '__main__':
    sys.exit(main())
