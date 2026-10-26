# -*- coding: utf-8 -*-
"""第113轮k-d：活动候选的地名**必须能说出是哪一家**。

问题（端到端实测，非推断）：
    【这会儿能张罗的事】要去吃点东西，你们这儿真有的地方：家乡（第一章 · 黑暗世界）。
用户口径要的是「那要不去 **XXX 家餐厅**」—— 而 `XXX 家餐厅` 没了。
根因：`ch1.hometown.diner` 的 `name` 是 `家乡·diner` 但 `name_derived=True`
⇒ `_scene_place_label` 判它"无名"，只剩区名 `家乡`。

修法（两处）：
  A. `npc_life.py` 新增 `PLACE_GLOSS` / `place_type_name` / `place_label`
     —— **纯拼接**，不查索引；中文类型只做**翻译**（`diner`→餐厅），**不编店名**。
  B. `main.py` 的 `_activity_places` 改调 `_activity_label()`；
     `_scene_place_label` 加 `with_chapter=True` 形参（默认路径**逐字不变**）。

★ 为什么 `with_chapter` 默认 True：第113轮j 的 30 条判据钉的就是带章括注的
  位置块。默认路径不许动 —— 这次只加**活动候选**用的窄口子。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
LIFE = os.path.join(PET, 'modules', 'npc_life.py')
MAIN = os.path.join(PET, 'src', 'main.py')

NL = '\r\n'


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write(p, t):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(t)


def must(hay, needle, tag):
    """★ `.replace()` 没命中必须炸 —— 否则"改完了"是假的。"""
    if needle not in hay:
        print('[FAIL] %s 锚点没命中' % tag)
        sys.exit(1)


# ===================================================================== A · npc_life
LIFE_ANCHOR = "def activity_hint(kind, places, note='', limit=4):"

LIFE_ADD = '''#: 地点类型词 → 中文类型名。
#: ★★ 这是**翻译**，不是给地方起名：`diner` 就是餐厅、`cafe` 就是咖啡店。
#:   原作没给中文名（Deltarune 全是 `room_diner` 这种 id、UT 是 `room_fire_restaurant`），
#:   我们就**照字面翻**；**绝不编**「XX 家餐厅」这种店名 —— 编出来的名字模型会当真，
#:   而那家店在原作里根本不存在。
#: ★ 只收**第113轮k 全量普查里实际出现过**的词：`eat` diner/restaurant/cafe/kitchen/
#:   pizza · `rest` house/couch/bed/bedroom/cabin/inn · `play` carnival/garden/plaza ·
#:   `work` school/hospital/library/lab/shop/store/office/dock/factory/station。
#:   查不到的英文词**原样留着**（宁可给英文，也不给它编个中文名）。
PLACE_GLOSS = {
    # -- 吃
    'diner': '餐厅', 'restaurant': '餐馆', 'cafe': '咖啡店', 'coffee': '咖啡馆',
    'kitchen': '厨房', 'bakery': '面包店', 'pizza': '披萨店', 'burger': '汉堡店',
    'tavern': '酒馆', 'bar': '酒吧', 'food': '餐馆',
    # -- 歇
    'inn': '旅店', 'hotel': '旅馆', 'motel': '汽车旅馆', 'bedroom': '卧室',
    'bed': '床', 'couch': '沙发', 'cabin': '小屋', 'house': '房子', 'home': '家',
    'lodge': '小屋', 'dorm': '宿舍', 'apartment': '公寓',
    # -- 玩
    'park': '公园', 'garden': '花园', 'plaza': '广场', 'yard': '院子',
    'playground': '操场', 'carnival': '游乐场', 'arcade': '游戏厅', 'stage': '舞台',
    'theater': '剧院', 'theatre': '剧院',
    # -- 办事
    'shop': '商店', 'store': '商店', 'market': '市场', 'factory': '工厂',
    'office': '办公室', 'library': '图书馆', 'school': '学校', 'hospital': '医院',
    'clinic': '诊所', 'lab': '实验室', 'mine': '矿', 'station': '车站',
    'dock': '码头', 'bank': '银行',
}


def place_type_name(word):
    """地点类型词 → 中文类型名。中文词原样返回；英文查 `PLACE_GLOSS`；查不到原样返回。

    ★ 中文词原样返回是有意的：`餐` / `咖啡` / `舞台` 本身就是原作给的中文名的一部分，
      再翻一次（`餐`→`餐厅`）反而会把 `理想餐厅` 变成 `理想餐厅（餐厅）`。
    """
    w = str(word or '').strip()
    if not w:
        return ''
    return PLACE_GLOSS.get(w.lower(), w)


def place_label(area, detail, core, hits, sep=PLACE_SEP):
    """拼一个**能说出口**的地点标签：`家乡 · diner（餐厅）`。

    参数
    ----
    area   : 区名。★ 调用方一般已过滤容器名，这里**再过滤一次**（两道都便宜，
             任何一边漏了都不会把「未分区」印给模型）。
    detail : **已经能读的名字**（真名 / 剥过区段名的原作名，如 `希望之园 · 理想餐厅`）。
             非空 ⇒ 直接用它，只补中文类型。
    core   : 原作 id 末段（**剥过区段名**，如 `diner` / `castle cafe`）。
    hits   : `place_matches` 命中的类型词，`hits[0]` 决定括注的中文类型。
    sep    : 层级分隔符。

    ★★ 为什么需要这个函数（而不是直接用 `_scene_place_label`）：
      对 `name_derived=True` 的场景，`_scene_place_label` 只剩区名（`家乡`），
      而 `diner` 在 **id 末段**里 —— 端到端就输出成「你们这儿真有的地方：家乡」，
      用户要的「那要不去 XXX 家餐厅」里那个 **XXX 家餐厅** 没了。第113轮k 实测。
    ★ 纯拼接：不查索引、不猜名字。数据从哪来是调用方的事。
    """
    area = str(area or '').strip()
    if place_container(area):
        area = ''
    detail = ' '.join(str(detail or '').split())
    core = strip_room_index(' '.join(str(core or '').split()))

    cn = ''
    for w in (hits or ()):
        w = str(w or '').strip()
        if w:
            cn = place_type_name(w)
            break

    # ① 已经有像样的名字 ⇒ 原样用（`希望之园 · 理想餐厅` 不许再加 `（餐厅）`）
    if detail:
        if cn and cn not in detail:
            return '%s（%s）' % (detail, cn)
        return detail

    # ② 只剩区名 ⇒ 用原作 id 末段当细节
    body = core
    if body:
        if cn and cn not in body:
            body = '%s（%s）' % (body, cn)
        return (area + sep + body) if area else body
    return area


def strip_room_index(core):
    """去掉**纯数字的房号**：`couch overworld 01` → `couch overworld`。

    ★ 为什么要去：ch3 有 8 间 `dw_couch_overworld_01..05`，留着房号会输出
      「黑暗世界 · couch overworld 01（沙发）」等 4 条几乎一样的东西 ——
      模型只会挑花眼，说不出一个具体的。
    ★ 只去**纯数字**：`tundra inn 2f` 的 `2f` 有意义（二层），不动它。
    """
    toks = [t for t in str(core or '').split() if t]
    while toks and toks[-1].isdigit():
        toks.pop()
    return ' '.join(toks)


'''

# ===================================================================== B · main.py
MAIN_LABEL_SIG = "    def _scene_place_label(self, sid):"
MAIN_LABEL_SIG_NEW = "    def _scene_place_label(self, sid, with_chapter=True):"

MAIN_LABEL_DOC_OLD = '''        ★ 区名 == 场景名时只留一个：`城堡镇 · 城堡镇（第一章 · 黑暗世界）` 读起来像结巴。
        """'''
MAIN_LABEL_DOC_NEW = '''        ★ 区名 == 场景名时只留一个：`城堡镇 · 城堡镇（第一章 · 黑暗世界）` 读起来像结巴。
        ★ `with_chapter=False` ⇒ **不拼章名括注**。给活动候选用的：候选**本来就被
          `_activity_places` 限定在同一章里**，四项各带一遍「（第一章 · 黑暗世界）」
          纯属噪音，还把「那要不去 XXX 家餐厅」里的 XXX 挤没了。
          默认 True ⇒ 位置块（第113轮j）的输出**逐字不变**。
        """'''

MAIN_LABEL_RET_OLD = '''        # ④ 章名与位置同名时不加括注（`桌面（桌面）` 像结巴）
        if ch_name and label and ch_name != label:'''
MAIN_LABEL_RET_NEW = '''        # ④ 章名与位置同名时不加括注（`桌面（桌面）` 像结巴）
        if with_chapter and ch_name and label and ch_name != label:'''

MAIN_ACT_OLD = '''                if not npc_life_mod.place_matches(text, kind):
                    continue
                lbl = self._scene_place_label(sid_s)
                if lbl:'''
MAIN_ACT_NEW = '''                hits = npc_life_mod.place_matches(text, kind)
                if not hits:
                    continue
                lbl = self._activity_label(sid_s, core, hits)
                if lbl:'''

MAIN_METHOD_ANCHOR = '''    def _npc_life_blocks(self, npc_id, heard=None):'''

MAIN_METHOD_ADD = '''    def _activity_label(self, sid, core, hits):
        """活动候选的**可说出口的名字**：`家乡 · diner（餐厅）`（**不带章括注**）。

        ★ 与 `_scene_place_label` 的分工：
          · 它给的是「**你在哪**」——只有区名也算够用（模型知道自己在"家乡"）；
          · 这里要的是「**能去哪一家**」——必须说出是哪一家（餐厅 / 咖啡店 / 图书馆），
            否则模型只能答「那要不去家乡」，答不出用户要的「那要不去 XXX 家餐厅」。
        ★ 细节词优先用真名（`希望之园 · 理想餐厅`），没有再退回**原作 id 末段**
          （`diner` / `castle cafe`）—— 两级都只从已有数据里取，**不编店名**。
        """
        sid = str(sid or '').strip()
        if not sid:
            return ''
        # 真名那一支直接借 `_scene_place_label`（它已经处理好剥区名前缀、剥容器名），
        # 只是不带章括注；处理不了 `name_derived` 的部分由 `place_label` 用 core 补。
        base = self._scene_place_label(sid, with_chapter=False)
        if not base:
            return ''
        info = self._scene_label_map().get(sid) or ('', '', '', False, '')
        area_name = info[1]
        if npc_life_mod.place_container(area_name):
            area_name = ''
        # base 比区名多出信息 ⇒ 它是真名；否则 base 就只是区名，交给 core 补细节。
        detail = '' if (not area_name or base == area_name) else base
        try:
            return npc_life_mod.place_label(area_name, detail, core, hits)
        except Exception as e:
            _log.debug('活动地名拼接失败（退回位置标签）: %s', e)
            return base

'''


def pat(path, pairs, tags):
    t = read(path)
    for (old, new), tag in zip(pairs, tags):
        must(t, old, tag)
        if new in t:
            print('[SKIP] %s 已是新版' % tag)
            continue
        t = t.replace(old, new, 1)
        print('[ OK ] %s' % tag)
    write(path, t)


def main():
    # ---------------- npc_life
    t = read(LIFE)
    if 'def place_label(' in t:
        print('[SKIP] npc_life 已含 place_label')
    else:
        must(t, LIFE_ANCHOR, 'npc_life 锚点')
        add = LIFE_ADD.replace('\n', NL)
        t = t.replace(LIFE_ANCHOR, add + LIFE_ANCHOR, 1)
        write(LIFE, t)
        print('[ OK ] npc_life 插入 PLACE_GLOSS / place_type_name / place_label / strip_room_index')

    # ---------------- main
    t = read(MAIN)
    pairs = [
        (MAIN_LABEL_SIG, MAIN_LABEL_SIG_NEW),
        (MAIN_LABEL_DOC_OLD, MAIN_LABEL_DOC_NEW),
        (MAIN_LABEL_RET_OLD, MAIN_LABEL_RET_NEW),
        (MAIN_ACT_OLD, MAIN_ACT_NEW),
    ]
    tags = ['main _scene_place_label 签名', 'main 文档串', 'main 章括注开关', 'main _activity_places 接线']
    for (old, new), tag in zip(pairs, tags):
        must(t, old, tag)
        t = t.replace(old, new, 1)
        print('[ OK ] %s' % tag)
    if '_activity_label(self, sid, core, hits)' in t:
        print('[SKIP] main 已含 _activity_label')
    else:
        must(t, MAIN_METHOD_ANCHOR, 'main 方法锚点')
        t = t.replace(MAIN_METHOD_ANCHOR,
                      MAIN_METHOD_ADD.replace('\n', NL) + MAIN_METHOD_ANCHOR, 1)
        print('[ OK ] main 插入 _activity_label')
    write(MAIN, t)

    # ---------------- 自检：语法 + 行数 + EOL
    print('--- 自检 ---')
    import ast
    for p in (LIFE, MAIN):
        src = read(p)
        try:
            ast.parse(src)                       # ★ 不产 .pyc（py_compile 会）
            ok = 'PASS'
        except SyntaxError as e:
            ok = 'FAIL %s' % e
        n = src.count('\n')
        crlf = src.count('\r\n')
        print('%-14s 语法=%s 行=%d CRLF=%d gap=%d' % (
            os.path.basename(p), ok, n, crlf, n - crlf))


if __name__ == '__main__':
    main()
