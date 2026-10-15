# -*- coding: utf-8 -*-
"""
第115轮后续 · 生成「所有轮改动 × 录屏测试」清点表

用户口径（逐字）：「把咱目前所有轮，记住，所有轮的改动都**逐项录屏测试**，
测试完没问题再推进」

★ 这张表要回答三件事（**不许含糊**）：
  1. **有多少项**：99 个轮次目录 + 106 个回归套件 ⇒ 逐条列出，不漏项；
  2. **哪些能录屏、哪些不能**：桌面宠物/场景/门/缩放/气泡/道具/球/灵魂/坐姿/电梯/幽灵
     这些**屏上看得见**；而数据面/哈希/解析/拓扑（如 7804 物件件、栅格外推、原作转储）
     **屏上没有像素**，只能 headless 断言 —— 硬说"录屏测过"就是编。
  3. **每一项的录屏动作是什么**（可视项才有），以及**状态**（待测/已过/不可视）。

数据来源（全部机器可复核，不手抄）：
  · `code-quality-audit/regress/run_all.py` 的 `SUITES` ⇒ id / offscreen / desc
  · `code-quality-audit/第*轮-*/` 目录名 ⇒ 轮次清单
产物：`_evidence/RECORD_MATRIX.md`
"""
import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
CQA = os.path.join(ROOT, 'code-quality-audit')
RUN_ALL = os.path.join(CQA, 'regress', 'run_all.py')
EV = os.path.join(ROUND, '_evidence')

# ---------------------------------------------------------------- 可视性判据
# ★ 判定"屏上是否看得见"的关键词（按主题分组，命中即**可视**）。
#   依据：这些主题在真机上会产生**像素变化**（窗口几何/贴图/气泡/位移）。
VISUAL_KEYS = (
    '场景', '房间', '门', '相机', '全屏', '缩放', '画布', '贴图', '素材', '精灵',
    'sprite', 'anim', '动画', '渲染', 'render', '气泡', '对话', 'dialog', '对话框',
    '道具', '背包', 'item', '球', 'bubble', '灵魂', 'soul', '坐姿', '电梯', '幽灵',
    'ghost', '移动', 'movement', 'move', '甩飞', 'fling', '建楼', '楼层', 'floor',
    '攀爬', 'climb', '窗口', '桌面', '桌宠', 'pet', '伙伴', 'companion', 'NPC',
    'npc', '站位', 'place', '游荡', 'roam', '差事', 'errand', '附身', '带路',
    '视角', '彩蛋', '过渡', '渐显', '点亮', 'light', '光照', '物件栅格',
)
# ★ 明确**屏上没有像素**的主题（数据/解析/协议面）—— 这些只做 headless，如实登记。
NONVISUAL_KEYS = (
    '哈希', 'sha', '索引', '解析', '转储', '反编译', '拓扑', '数据面', '登记',
    '注册', 'schema', '版本', '上限', '压缩', 'token', '回归', '基线', '落盘',
    '存档', 'store', 'config', '配置', 'privacy', '隐私', '并发', '常驻', '预热',
    'keep_alive', '门控', 'world_gate', '别名', 'alias', '人设索引', '勾稽',
)


def load_suites():
    """从 run_all.py 的 AST 里取 SUITES（**不 exec 它**，避免副作用）。"""
    tree = ast.parse(io.open(RUN_ALL, encoding='utf-8').read())
    out = []
    for nd in ast.walk(tree):
        if isinstance(nd, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'SUITES' for t in nd.targets):
            for el in nd.value.elts:
                if not isinstance(el, ast.Dict):
                    continue
                d = {}
                for k, v in zip(el.keys, el.values):
                    kk = getattr(k, 'value', None)
                    try:
                        if kk in ('id', 'desc', 'offscreen'):
                            d[kk] = ast.literal_eval(v)
                    except Exception:  # noqa: BLE001
                        pass
                if d.get('id'):
                    out.append(d)
    return out


def classify(suite):
    text = (suite.get('id', '') + ' ' + str(suite.get('desc', '')))
    low = text.lower()
    vis = [k for k in VISUAL_KEYS if k.lower() in low]
    nonvis = [k for k in NONVISUAL_KEYS if k.lower() in low]
    if vis and not nonvis:
        return '可视', vis[:4]
    if nonvis and not vis:
        return '不可视', nonvis[:4]
    if vis and nonvis:
        return '混合', (vis[:3], nonvis[:3])
    return '待定', []


#: 可视项 → 真机录屏动作（人工锚定的关键动作，别的可视项落到最近的一条）
ACTION_MAP = [
    ('scene', '起真机 → 切场景（桌面/城堡镇/黑暗世界）→ 抓帧：背景铺满/黑边/相机跟随'),
    ('route', '起真机 → 逐门寻路（撞门 → 换房）→ 抓帧：门在位、真实可达、不瞬移'),
    ('door', '起真机 → 走到 4 扇桌面门前 → 抓帧：门贴屏边、渐显、外观 spr_darkdoor'),
    ('camera', '起真机 → 让宠物横穿屏幕 → 抓帧：背景随相机平移（不是视差）'),
    ('fit', '起真机 → 切非桌面场景 → 抓帧：按比例铺满+黑边；改窗口大小 → 重算'),
    ('ui', '起真机 → 打开对话框 → 抓帧：字号随场景缩放、位置不溢出'),
    ('render', '起真机 → 抓帧：物件/贴图/图层顺序正确'),
    ('canvas', '起真机 → 抓帧：画布尺寸与场景对齐'),
    ('box', '起真机 → 打开道具/背包 → 抓帧：原作风对话框样式'),
    ('bubble', '起真机 → 让 NPC 头顶冒气泡 → 抓帧：气泡在头顶、不遮脸'),
    ('item', '起真机 → 走到可交互道具前 → 抓帧：高亮/菜单'),
    ('soul', '起真机 → 附身/带路（R5/R6）→ 抓帧：灵魂可见、跟随位移'),
    ('ghost', '起真机 → 与 Kris 同场停留 → 抓帧：幽灵淡入'),
    ('sit', '起真机 → 电梯坐姿 → 抓帧：坐姿帧、不晃'),
    ('npc', '起真机 → 同场 NPC → 抓帧：站位/游荡/不叠人'),
    ('anim', '起真机 → 逐动画名播放 → 抓帧：命中率、帧序正确'),
    ('companion', '起真机 → 伙伴交互 → 抓帧：对话框/菜单'),
    ('pathfind', '起真机 → 点远处 → 抓帧：连续位移（非瞬移）'),
    ('errand', '起真机 → 对话里派差事 → 抓帧：看板变化、画面不变'),
]


def action_for(sid, kind, keys):
    for k, a in ACTION_MAP:
        if k in sid.lower():
            return a
    if keys:
        for k, a in ACTION_MAP:
            if k in ' '.join(map(str, keys)).lower():
                return a
    return '起真机 → 按该轮功能操作 → 抓帧对比' if kind == '可视' else '—'


def main():
    suites = load_suites()
    rounds = sorted(d for d in os.listdir(CQA)
                    if os.path.isdir(os.path.join(CQA, d))
                    and (d.startswith('第') and '轮' in d or d in (
                        '人味改造-2026-09-18', '人味诊断-2026-09-18', '场景系统-P0',
                        '基础代码严查-2026-09-22', '复审_2026-09-12', '架构改造-H4H5',
                        '模型选型-4B-2026-09-18', '模型选型-7B-2026-09-18')))

    L = []
    L.append('# 录屏测试清点表（所有轮改动 × 逐项）\n')
    L.append('> 生成：`_tools/rec115_matrix.py`（机器生成，数据源 = `regress/run_all.py` 的 `SUITES` 与人读目录名）\n')
    L.append('## §0 总量核对（先看这一节：不许漏项）\n')
    L.append('| 项 | 数 |')
    L.append('|---|---|')
    L.append('| 轮次目录 | **%d** |' % len(rounds))
    L.append('| 回归套件（G2 SUITES） | **%d** |' % len(suites))
    L.append('| 其中 `offscreen=True`（要起 App 才能跑） | **%d** |'
             % sum(1 for s in suites if s.get('offscreen')))
    L.append('')
    L.append('★ **关键诚实声明**：**不是每一项都能录屏。** 数据面/哈希/解析/拓扑'
             '（如 7804 物件件、栅格外推、原作转储、索引勾稽）在屏幕上**没有像素**，'
             '只能用 headless 判据守 —— 把它们说成"录屏测过"是编。本表把两类**分开列**。\n')

    kinds = {}
    for s in suites:
        k, keys = classify(s)
        s['_kind'], s['_keys'] = k, keys
        kinds[k] = kinds.get(k, 0) + 1
    L.append('## §1 套件可视性分类\n')
    L.append('| 类别 | 数 | 含义 |')
    L.append('|---|---|---|')
    L.append('| 可视 | %d | 真机上有像素变化 ⇒ **要录屏** |' % kinds.get('可视', 0))
    L.append('| 混合 | %d | 既有可视面也有数据面 ⇒ 录屏 + headless 都做 |' % kinds.get('混合', 0))
    L.append('| 不可视 | %d | 屏上无像素 ⇒ **只能 headless**，如实登记 |' % kinds.get('不可视', 0))
    L.append('| 待定 | %d | 需人工判 |' % kinds.get('待定', 0))
    L.append('')

    L.append('## §2 逐套件明细（%d 条）\n' % len(suites))
    L.append('| # | 套件 | 可视性 | 录屏动作 | 状态 |')
    L.append('|---|---|---|---|---|')
    for i, s in enumerate(suites, 1):
        act = action_for(s['id'], s['_kind'], s['_keys'])
        st = '待测' if s['_kind'] in ('可视', '混合') else '不适用（无像素）'
        L.append('| %d | `%s` | %s | %s | %s |'
                 % (i, s['id'], s['_kind'], act, st))
    L.append('')

    L.append('## §3 轮次目录（%d 个）\n' % len(rounds))
    for r in rounds:
        L.append('- %s' % r)
    L.append('')
    L.append('## §4 AI 线（用户点名：**每个都测**）\n')
    L.append('| 项 | 验证方式 | 脚本 |')
    L.append('|---|---|---|')
    L.append('| Ralsei 本线对话 | 真机真链：persona+【此刻】+关系+记忆+世界观+历史 → 模型 → 护栏 | `ai115_sweep.py` A9 |')
    L.append('| **每一位 NPC**（注册表全量） | 逐位 `npc_system_prompt` → 真 `api_client.chat` → 护栏 | `ai115_sweep.py` B |')
    L.append('| 装配面 9 项 | 人设/此刻/关系/紧张/记忆召回/世界观召回/流式/护栏 | `ai115_sweep.py` A1~A8 |')
    L.append('| 事件台词（lean 路径） | 另测 | 待补 |')
    L.append('| 差事派发（114轮） | 真机：对话里派活 → 看板/位置真源/记忆 | `rec114.py` |')
    L.append('| 附身 R5 / 带路 R6（82/83轮） | 真机：换方向键消费方 | 待补 |')
    L.append('| 输出护栏 | 产品真源码跑正负控制 | `guard115.py` 21/0 |')
    L.append('')
    L.append('★ 说明：**"每个"= 注册表里的每一位角色都真发一次请求**（不是抽样）。'
             '纯 CPU 上每位约 80s（实测 asgore 71s / berdly 88s）⇒ 全量约 1.5~2 小时，'
             '结果**增量**写 `_evidence/ai115_sweep.jsonl`（跑一半中断也不丢）。\n')

    txt = '\n'.join(L) + '\n'
    with io.open(os.path.join(EV, 'RECORD_MATRIX.md'), 'w',
                 encoding='utf-8', newline='') as f:
        f.write(txt)
    print('轮次目录 = %d ｜ 套件 = %d ｜ 可视 %d / 混合 %d / 不可视 %d / 待定 %d'
          % (len(rounds), len(suites), kinds.get('可视', 0), kinds.get('混合', 0),
             kinds.get('不可视', 0), kinds.get('待定', 0)))
    print('已写 %s' % os.path.join(EV, 'RECORD_MATRIX.md'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
