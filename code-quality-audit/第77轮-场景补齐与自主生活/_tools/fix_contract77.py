
import io, json
p = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\assets\npc\_crossworld.json'
d = json.load(io.open(p, encoding='utf-8'))
d['scene_traits']['wired_how'] = (
    '已接线：traits 来源定为**场景 id / 内部名 / 资源名的文本语义**'
    '（零依赖、可复算、可解释 —— `trait_hits()` 会返回凭什么这么判）。'
    '\n\n★★★ **第77轮重大更新：UT / 黄魂 场景迁入 `_index.json` 后，'
    '`ruined`（破败）从零命中转为真命中**：'
    '实测命中 **35 处**（`ut.rooms.room_ruins1` ~ `room_ruinsA` 等 UT「废墟」区域为主），'
    '⇒ 用户点名的「破败这类的词也需要有能力识别」**现已兑现一部分**（UT 侧）。'
    '\n\n★ 现网覆盖（第77轮复算，全部键 1,739 = 真场景 1,659 + 章/区域名 80）：'
    '命中 **dark 181 / ruined 35 / crowded 287 / quiet 404** 四个特质，'
    '**1,081 个键零特质**（如实）。'
    '`bright`（明亮）/ `cosmic`（宇宙）**仍是零命中** —— '
    '因为这两个特质的令牌只在 **OneShot / Outertale** 的场景名里，'
    '而那两部还没进 `_index.json`（第77轮只补了 UT / 黄魂）。'
    '（数字由 `_tools/probe73_traits.py` 与第77轮复算真跑产出，'
    '落 `_evidence/probe73_traits.json`。）'
)
d['scene_traits']['round77_update'] = {
    'why': '第77轮把 UT/黄魂 场景迁入产品索引，破了 ruined 的零命中',
    'ruined_now_hits': 35,
    'ruined_samples': ['ut.rooms.room_ruins1', 'ut.rooms.room_ruins7A'],
    'still_reserved_traits': ['bright', 'cosmic'],
    'still_zero_tokens': ['broken', 'wreck', 'abandon', 'desolate'],
    'why_still_zero': '这些令牌只在 OneShot / Outertale 场景名里，那两部尚未迁入',
    'recount': {'all_keys': 1739, 'traits': {'dark': 181, 'ruined': 35,
                                            'crowded': 287, 'quiet': 404},
                'no_trait': 1081},
}
d['round'] = 77
d.setdefault('round77', {})['scene_import'] = {
    'works': ['ut', 'uty'], 'scenes': 645,
    'why': '跨作品大图 bigmap66.json 的房间迁入产品场景索引，见 第77轮报告',
}
io.open(p, 'w', encoding='utf-8', newline='\n').write(
    json.dumps(d, ensure_ascii=False, indent=1))
print('OK wired_how len =', len(d['scene_traits']['wired_how']))
print('  trait_hits preserved =', 'trait_hits()' in d['scene_traits']['wired_how'])
