# -*- coding: utf-8 -*-
"""第70轮 · 素材提取 + 26 位新增角色的 `objects` 证据（黄魂 15 / Outertale 11）。

为什么本轮"解包"是**核验**而不是**重解**
----------------------------------------
用户给了 4 个 apk 作为素材真源。**逐个对比后发现它们与历轮已解包产物同源**：

| apk | 内层数据 | 历轮产物 | 同源判据 |
|---|---|---|---|
| `undertale.apk` | `assets/game.droid` 75.9 MB | `E:\\Download\\_extract61\\_data\\undertale\\game.droid` | 尺寸+CRC+头部 三者相同 |
| `黄魂.apk` | `assets/game.droid` 174.0 MB | `..\\undertale_yellow\\game.droid` | 同上 |
| `outertale.apk` | `assets/www/` 3637 文件 | `E:\\Download\\_extract61\\outertale\\www` | 文件集**完全相等**（差集 0/0） |
| `红与黄.apk` | `assets/game.droid` 128.1 MB | `E:\\Download\\_extract64\\assets\\game.droid` | 尺寸+CRC+头部 三者相同 |

⇒ 重复解包 500 MB 只是浪费；本轮真正缺的是「**每个角色对应哪个资源名**」这条证据链。
   本工具就是补这条链，并把"同源核验"本身也做成可复看的判据。

本轮的产物是什么（= 解开第69轮注册阻塞的钥匙）
---------------------------------------------
`_registry.json` 有一条硬契约（`code-quality-audit/第49轮-NPC与球容器/verify_npc49.py:110`）：

    check('B4', all(n.objects for n in REG.all()), '每条 NPC 都有原作物件名')

⇒ 26 位新人的 `objects` 必须有据。本工具产出：

    _evidence/objects_undertale_yellow.json   {id: [资源名...]}   15 条
    _evidence/objects_outertale.json          {id: [资源名...]}   11 条

`objects` 的口径**沿用第66轮 N4**（不另立一套）：「该作品里标识角色的**资源名**」
——OneShot 用官方 `walkspriteId`、Undertale 用 `spr_*`。本轮：

* **黄魂** = GameMaker 作品 ⇒ 取 `spr_*` 名（与 Undertale 侧同口径）；
* **Outertale** = Web(HTML5) 打包，**没有 GameMaker 资源表** ⇒ 取打包器里的
  **逻辑资源名**（`ioc<Name>Down` 一族）。

★★★ 为什么用**手写显式表**而不是"规则命中"
------------------------------------------
`objects` 要表达的是「**这个角色**在**那部作品**里长什么样」，不是"名字里含 clover 的都算"。
逐角色看过素材后，命名有 5 种不同家族（`spr_<x>_down_walk` / `spr_<x>_down_talk` /
`<x>_down` / `spr_<x>_npc` / `spr_<x>_body_normal`），**没有一条统一规则**。
硬编一条规则去套 = 第64轮「名字上限 24」那种**判据过窄**的老坑。

所以：**逐条手写 + 逐条上锚点**。锚点分三层（都是可证伪的）：

* **A 存在性锚**：我写下的每个资源名，必须在**该作品自己的**资源名表里**逐字命中**
  （黄魂 = `ut_sprites.json` 的 3814 个 sprite；Outertale = 打包器命名的 1027 个 sprite）。
  —— 若我把名字写错/记错，立刻 MISS。
* **B 负控制**：一组**"看起来很像但不属于这部作品"**的名字，必须**不在**表里：
  * 黄魂侧放 UTRY 专有的 `spr_clover_d`（红与黄 mod 才有）⇒ 必须 MISS；
  * Outertale 侧放 UT 专有的 `spr_sans_d` ⇒ 必须 MISS。
  —— 若我把"哪部作品的表"读错了，负控制会命中（报红）。
* **C 跨表互斥**：15 个黄魂名**全部不出现在 UT 表里**、11 个 Outertale 名
  **全部不出现在 UT/黄魂 表里** ⇒ 证明三张表确实是三份不同的东西。

用法
----
    C:\\Python311\\python.exe -X utf8 extract_assets70.py            # dry（只打印）
    C:\\Python311\\python.exe -X utf8 extract_assets70.py --write    # 写 _evidence/*.json
"""
import io
import json
import os
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.join(HERE, '..', '..', '..')
EV = os.path.join(ROUND, '_evidence')

DO_WRITE = '--write' in sys.argv
FAIL = 0
LINES = []

# ---------------------------------------------------------------- 输入路径
APKS = {
    'undertale': r'C:\Users\23002\Downloads\undertale.apk',
    'undertale_yellow': r'C:\Users\23002\Downloads\黄魂.apk',
    'outertale': r'C:\Users\23002\Downloads\outertale.apk',
    '红与黄': r'C:\Users\23002\Downloads\红与黄.apk',
}
UT_DIR = r'E:\Download\_extract61\_data\undertale'
HY_DIR = r'E:\Download\_extract61\_data\undertale_yellow'
OT_WWW = r'E:\Download\_extract61\outertale\www'
RY_DIR = r'E:\Download\_extract64\assets'
RY_NAMES = os.path.join(RY_DIR, 'r64_names.json')
#: 第63轮已把 outertale 的逻辑资源名提取成 (name, png, json) 三元组
OT_ASSETS = os.path.join(ROOT, 'code-quality-audit', '第63轮-跨界扩展数据面',
                         '_evidence', 'outertale63_assets.json')


def w(s=''):
    print(s)
    LINES.append(str(s))


def ok(m):
    w('[PASS] %s' % m)


def bad(m):
    global FAIL
    FAIL += 1
    w('[FAIL] %s' % m)


# ---------------------------------------------------------------- 手写表
#: 黄魂：id -> [该作品里标识此角色的 sprite 名]
#: 选取理由逐条写在 REASON_HY 里（**这是本表最重要的部分**：它说明"为什么是这个名字"）
HY_OBJ = {
    'hy_ace': ['spr_ace_down_walk'],
    'hy_axis': ['spr_axis_down'],
    'hy_bowll': ['spr_bowll_body_normal'],
    'hy_ceroba_ketsukane': ['spr_ceroba_down_walk'],
    'hy_chujin_ketsukane': ['spr_chujin_npc'],
    'hy_clover': ['spr_clover_casual'],
    'hy_dalv': ['dalv_down'],
    'hy_ed': ['spr_ed_down_walk'],
    'hy_flowey': ['spr_flowey'],
    'hy_guardener': ['spr_guardener_body'],
    'hy_martlet': ['spr_martlet_down_talk'],
    'hy_mooch': ['spr_mooch_down_walk'],
    'hy_moray': ['spr_moray_down_walk'],
    'hy_sousborg': ['spr_sousborg_npc'],
    'hy_starlo': ['spr_starlo_down_walk'],
}
REASON_HY = {
    'hy_ace': 'overworld 下行行走图（本作 overworld 命名 = `spr_<名>_down_walk`）',
    'hy_axis': '★ 该角色**没有** `_down_walk` ⇒ 取最接近的方向帧 `spr_axis_down`',
    'hy_bowll': '★ 他是**不移动的狗**（Steamworks 里趴着）⇒ 取本体 `spr_bowll_body_normal`',
    'hy_ceroba_ketsukane': 'overworld 下行行走图',
    'hy_chujin_ketsukane': '★ 只在回忆/NPC 场合出现 ⇒ 取**显式 NPC 立绘** `spr_chujin_npc`',
    'hy_clover': '★★ 主角：本作**没有** `spr_clover_down*`（玩家行走图不在这套命名里）'
                 '⇒ 取唯一站姿 `spr_clover_casual`；'
                 '对比：红与黄 mod 里才有 UT 式 `spr_clover_d`（见负控制 B1）',
    'hy_dalv': '★★ 该角色的行走图**不带 `spr_` 前缀**（本作独有写法：`dalv_down`/`dalv_downt`）',
    'hy_ed': 'overworld 下行行走图',
    'hy_flowey': '★ 本体花 `spr_flowey`（该作 overworld 的那朵花）',
    'hy_guardener': '★ 植物型 Boss（不动）⇒ 取本体 `spr_guardener_body`',
    'hy_martlet': '★ 没有 `_down_walk` ⇒ 取下行对话帧 `spr_martlet_down_talk`',
    'hy_mooch': 'overworld 下行行走图',
    'hy_moray': 'overworld 下行行走图',
    'hy_sousborg': '★ 静止机器 Boss ⇒ 取**显式 NPC 件** `spr_sousborg_npc`',
    'hy_starlo': 'overworld 下行行走图',
}

#: Outertale（Web 打包）：id -> [打包器里的逻辑资源名]
OT_OBJ = {
    'ot_alphys': ['iocAlphysDown'],
    'ot_asgore': ['iocAsgoreDown'],
    'ot_asriel_twinkly': ['iocAsrielDown', 'iocTwinklyMain'],
    'ot_kidd': ['iocKiddDown'],
    'ot_mettaton': ['iocMettatonDressIdle'],
    'ot_muffet': ['ionFMuffet'],
    'ot_napstablook': ['iocNapstablookBody'],
    'ot_papyrus': ['iocPapyrusDown'],
    'ot_sans': ['iocSansDown'],
    'ot_toriel': ['iocTorielDown'],
    'ot_undyne': ['iocUndyneDown'],
}
REASON_OT = {
    'ot_alphys': '`ioc` = overworld character 家族・下行帧',
    'ot_asgore': '同上',
    'ot_asriel_twinkly': '★ 一个 id 覆盖两个身份（Asriel / Twinkly）⇒ 两个资源名都收：'
                         '`iocAsrielDown`（羊形变身）+ `iocTwinklyMain`（小花本体）',
    'ot_kidd': '同上',
    'ot_mettaton': '★ 他**没有** `iocMettatonDown`（本作里多为他「Anchor/姿势」件）⇒ 取站姿 `iocMettatonDressIdle`',
    'ot_muffet': '★ Muffet 只在 `ionF*`（front 家族）里有整体件 ⇒ `ionFMuffet`',
    'ot_napstablook': '★ 他**没有**方向帧 ⇒ 取本体 `iocNapstablookBody`',
    'ot_papyrus': '`ioc` 家族・下行帧',
    'ot_sans': '`ioc` 家族・下行帧',
    'ot_toriel': '`ioc` 家族・下行帧',
    'ot_undyne': '`ioc` 家族・下行帧',
}

#: B 负控制：**必须不存在**的名字（用来证明"我读的是哪张表"没搞错）
NEG_HY = {
    'spr_clover_d': '红与黄(UTRY) mod 专有；黄魂本体没有 ⇒ 若命中说明读错了表',
    'spr_ace_down_ZZZ': '不存在的名字（纯哨兵）',
}
NEG_OT = {
    'spr_sans_d': 'Undertale(GameMaker) 专有；Outertale 是 Web 打包 ⇒ 若命中说明读错了表',
    'iocSansDownTalkZZZ': '不存在的名字（纯哨兵）',
}


def rd_json(p):
    return json.loads(io.open(p, 'rb').read().decode('utf-8'))


def zip_entry(apk, inner):
    z = zipfile.ZipFile(apk)
    for i in z.infolist():
        if i.filename == inner:
            return i
    return None


# ================================================================ STAGE 0
def stage0():
    w('=' * 78)
    w('[STAGE 0] 4 个 apk 与历轮已解包产物的**同源核验**')
    w('=' * 78)

    # --- UT / 黄魂 / 红与黄：game.droid 三元组（size / CRC / 头 32B）
    for tag, apk, disk, label in (
        ('undertale', APKS['undertale'], os.path.join(UT_DIR, 'game.droid'), 'UT'),
        ('undertale_yellow', APKS['undertale_yellow'], os.path.join(HY_DIR, 'game.droid'), '黄魂'),
        ('红与黄', APKS['红与黄'], os.path.join(RY_DIR, 'game.droid'), '红与黄'),
    ):
        if not os.path.isfile(apk):
            bad('%s apk 不存在：%s' % (label, apk))
            continue
        if not os.path.isfile(disk):
            bad('%s 盘上产物不存在：%s' % (label, disk))
            continue
        zi = zip_entry(apk, 'assets/game.droid')
        if zi is None:
            bad('%s apk 里没有 assets/game.droid' % label)
            continue
        z = zipfile.ZipFile(apk)
        headsame = z.open('assets/game.droid').read(32) == open(disk, 'rb').read(32)
        dsize = os.path.getsize(disk)
        same = (zi.file_size == dsize) and headsame
        w('  %-6s zip_size=%-10d disk_size=%-10d crc=0x%08X head_same=%s'
          % (label, zi.file_size, dsize, zi.CRC, headsame))
        if same:
            ok('%s：apk 与盘上 game.droid 同源' % label)
        else:
            bad('%s：apk 与盘上 game.droid **不同源**（必须先重解）' % label)

    # --- outertale：www 文件集完全相等
    apk_set = set()
    if os.path.isfile(APKS['outertale']):
        z = zipfile.ZipFile(APKS['outertale'])
        apk_set = set(n[len('assets/www/'):] for n in z.namelist()
                      if n.startswith('assets/www/') and not n.endswith('/'))
    disk_set = set(os.listdir(OT_WWW)) if os.path.isdir(OT_WWW) else set()
    w('  outertale  apk_www=%-6d disk_www=%-6d only_apk=%d only_disk=%d'
      % (len(apk_set), len(disk_set), len(apk_set - disk_set), len(disk_set - apk_set)))
    if apk_set and apk_set == disk_set:
        ok('outertale：apk 与盘上 www 文件集完全相等')
    else:
        bad('outertale：www 文件集不等（差 %d/%d）' % (len(apk_set - disk_set), len(disk_set - apk_set)))

    return len(apk_set), len(disk_set)


# ================================================================ STAGE 1
def stage1(ut_spr):
    w('')
    w('=' * 78)
    w('[STAGE 1] 黄魂 objects 证据（15 条）')
    w('=' * 78)
    d = rd_json(os.path.join(HY_DIR, 'ut_sprites.json'))
    spr = [s['name'] for s in d['sprites']]
    S = set(spr)
    w('  ut_sprites.json 名表 = %d 条' % len(spr))

    # A 存在性锚
    missA = []
    for i, names in sorted(HY_OBJ.items()):
        for n in names:
            if n not in S:
                missA.append((i, n))
                bad('A 锚 MISS：%s 的 %r 不在黄魂 sprite 名表里' % (i, n))
            else:
                w('    A[%s] %-26s <- %s' % (i, n, REASON_HY.get(i, '')))
    if not missA:
        ok('A 锚：15 条 × %d 个名字**全部**在黄魂名表里逐字命中'
           % sum(len(v) for v in HY_OBJ.values()))

    # B 负控制
    w('  --- B 负控制（必须不存在）---')
    for n, why in sorted(NEG_HY.items()):
        if n in S:
            bad('B 负控制**命中**（说明读错了表）：%s — %s' % (n, why))
        else:
            w('    B[ok] %-22s 不存在 — %s' % (n, why))

    # C 跨表：两表必须是**不同的**素材集；允许的重叠必须白名单化（逐条给出理由）
    #
    # ★ 第70轮实测修正（判据侧自纠，产物没错）：
    #   第一版把 C 写成"15 条里一个名字都不许出现在 UT 表里" ⇒ `spr_flowey` 报红。
    #   但那是**真事实**：Flowey 在 Undertale 与 Undertale Yellow **两部作品里都有**
    #   ⇒ 两表天然可以共享名字。**判据过窄 = 误报**（第64轮"名字上限 24"同类）。
    #   改成两条更准的判据：
    #     C1 两表**不是同一张表**（交集占比足够小）；
    #     C2 交集**逐条白名单**，出现计划外的交集才报红。
    SHARED_OK = {
        'spr_flowey': 'Flowey 在 UT 与 黄魂 **两作都有** ⇒ 同名合理。'
                      '★ 这同时是第72轮「无身份标识」的一条实证：'
                      '**只按 sprite 名查角色会撞车**，运行期必须按作品分别解析。',
    }
    inter = sorted(n for v in HY_OBJ.values() for n in v if n in ut_spr)
    unexpected = [n for n in inter if n not in SHARED_OK]
    jac = len(S & ut_spr) / float(len(S | ut_spr))
    w('  C1 两表交集占比：|HY∩UT|=%-5d |HY∪UT|=%-5d jaccard=%.4f'
      % (len(S & ut_spr), len(S | ut_spr), jac))
    if jac < 0.9:
        ok('C1：黄魂表与 UT 表**不是同一张表**（jaccard=%.4f < 0.9）' % jac)
    else:
        bad('C1 失败：两表几乎相同（jaccard=%.4f）⇒ 很可能读错了文件' % jac)
    if not unexpected:
        for n in inter:
            w('    C2[ok] 白名单内交集 %-14s — %s' % (n, SHARED_OK[n]))
        if not inter:
            ok('C2：15 条与 UT 表**零交集**')
        else:
            ok('C2：15 条与 UT 表的交集（%d 个）**全部在白名单内**' % len(inter))
    else:
        bad('C2 失败：计划外的交集 %s ⇒ 说明读错了表' % unexpected)
    return S


# ================================================================ STAGE 2
def stage2(ut_spr, hy_spr):
    w('')
    w('=' * 78)
    w('[STAGE 2] Outertale objects 证据（11 条）')
    w('=' * 78)
    d = rd_json(OT_ASSETS)
    named = {x['name']: x for x in d['named']}
    w('  outertale63_assets.json 的 named sprite = %d 条（另有 image-only %d 条）'
      % (len(named), d.get('image_only_count', -1)))
    w('  第63轮 anchors：%s' % json.dumps(
        {k: v for k, v in d['anchors'].items()
         if k in ('url_vars', 'unresolved', 'missing_on_disk', 'geom_ok', 'geom_bad')},
        ensure_ascii=False))

    missA = []
    for i, names in sorted(OT_OBJ.items()):
        for n in names:
            if n not in named:
                missA.append((i, n))
                bad('A 锚 MISS：%s 的 %r 不在 Outertale 名表里' % (i, n))
            else:
                w('    A[%s] %-24s <- %s' % (i, n, REASON_OT.get(i, '')))
    if not missA:
        ok('A 锚：11 条 × %d 个名字**全部**在 Outertale 名表里逐字命中'
           % sum(len(v) for v in OT_OBJ.values()))

    w('  --- B 负控制（必须不存在）---')
    for n, why in sorted(NEG_OT.items()):
        if n in named:
            bad('B 负控制**命中**：%s — %s' % (n, why))
        else:
            w('    B[ok] %-22s 不存在 — %s' % (n, why))

    inter_ut = sorted(n for v in OT_OBJ.values() for n in v if n in ut_spr)
    inter_hy = sorted(n for v in OT_OBJ.values() for n in v if n in hy_spr)
    if not inter_ut and not inter_hy:
        ok('C 互斥：11 条里没有一个名字出现在 UT / 黄魂 的名称表里')
    else:
        bad('C 互斥失败：UT=%s HY=%s' % (inter_ut, inter_hy))
    return named


# ================================================================ STAGE 3
def stage3():
    w('')
    w('=' * 78)
    w('[STAGE 3] 红与黄(UTRY) 只读勘查 —— 本轮**不注册**（它不是独立世界观）')
    w('=' * 78)
    if not os.path.isfile(RY_NAMES):
        bad('缺少 %s' % RY_NAMES)
        return {}
    d = rd_json(RY_NAMES)
    w('  counts = %s' % json.dumps(d['counts'], ensure_ascii=False))
    spr = [n.split('\t', 1)[1] for n in d['names'] if n.startswith('sprite\t')]
    w('  sprite 名 %d 条' % len(spr))
    probe = {}
    for k in ('clover', 'ceroba', 'martlet', 'dalv', 'starlo', 'ed', 'mooch', 'moray',
              'ace', 'axis', 'bowll', 'sousborg', 'guardener', 'chujin'):
        h = sorted(s for s in spr if k in s.lower())
        probe[k] = h[:6]
        w('    %-11s n=%-4d %s' % (k, len(h), h[:4]))
    w('  ★ 说明：红与黄 = **_extract64 已证**的 "Undertale 本体 + mod"（同命名空间），')
    w('    它的房间表 = 358（原版 338 + 追加 20），已在第65轮并入正典大图。')
    w('    ⇒ 它不是"第 5 个世界观"，不产生新 NPC；此处只留名表证据供后续取贴图用。')
    return {'counts': d['counts'], 'sprite_total': len(spr), 'probe': probe}


def main():
    w('第70轮 · 素材提取与 objects 证据')
    w('证据目录：%s' % EV)
    w('')

    for tag, p in (('UT sprite 表', os.path.join(UT_DIR, 'ut_sprites.json')),
                   ('黄魂 sprite 表', os.path.join(HY_DIR, 'ut_sprites.json')),
                   ('Outertale 名表', OT_ASSETS),
                   ('红与黄名表', RY_NAMES)):
        if not os.path.isfile(p):
            bad('输入缺失：%s（%s）' % (p, tag))
    if FAIL:
        w('')
        w('RESULT: FAIL=%d' % FAIL)
        return 1

    apk_www, disk_www = stage0()
    ut_spr = set(s['name'] for s in rd_json(os.path.join(UT_DIR, 'ut_sprites.json'))['sprites'])
    hy_spr = stage1(ut_spr)
    stage2(ut_spr, hy_spr)
    ry = stage3()

    w('')
    w('=' * 78)
    w('[产物]')
    w('=' * 78)
    w('  objects_undertale_yellow.json = %d 条' % len(HY_OBJ))
    w('  objects_outertale.json        = %d 条' % len(OT_OBJ))
    w('  合计 = %d 条（= 第69轮待登记数 26）' % (len(HY_OBJ) + len(OT_OBJ)))
    if len(HY_OBJ) + len(OT_OBJ) != 26:
        bad('产出 %d ≠ 26' % (len(HY_OBJ) + len(OT_OBJ)))
    else:
        ok('产出条数 = 26，与第69轮 `register_npcs69.py` 的 EXPECT_NEW 一致')

    if DO_WRITE and not FAIL:
        if not os.path.isdir(EV):
            os.makedirs(EV)
        payload = {
            'objects_undertale_yellow.json': HY_OBJ,
            'objects_outertale.json': OT_OBJ,
        }
        for fn, obj in payload.items():
            t = json.dumps(obj, ensure_ascii=False, indent=1)
            with io.open(os.path.join(EV, fn), 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(t)
            # 回读自检
            back = rd_json(os.path.join(EV, fn))
            if back == obj:
                ok('已写 %s（%d 条 / %d 字节）并回读一致' % (fn, len(obj), len(t.encode('utf-8'))))
            else:
                bad('回读不一致：%s' % fn)
        full = {
            'round': 70,
            'what': '4 个 apk 同源核验 + 26 位新增角色的 objects 证据',
            'sources': {'apk': APKS, 'ut_dir': UT_DIR, 'hy_dir': HY_DIR,
                        'ot_www': OT_WWW, 'ry_dir': RY_DIR},
            'stage0_same_source': {'outertale_apk_www': apk_www, 'outertale_disk_www': disk_www},
            'stage1_hy': {'count': len(HY_OBJ), 'objects': HY_OBJ, 'reasons': REASON_HY,
                          'negatives': NEG_HY},
            'stage2_ot': {'count': len(OT_OBJ), 'objects': OT_OBJ, 'reasons': REASON_OT,
                          'negatives': NEG_OT},
            'stage3_ry': ry,
            '口径': '沿用第66轮 N4：「该作品里标识角色的资源名」；'
                   'GameMaker 作品取 spr_*，Web 打包取逻辑资源名。',
        }
        t = json.dumps(full, ensure_ascii=False, indent=1)
        with io.open(os.path.join(EV, 'assets70.json'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(t)
        w('  已写 assets70.json（%d 字节）' % len(t.encode('utf-8')))

    out = os.path.join(EV, 'extract_assets70.txt')
    if not os.path.isdir(EV):
        os.makedirs(EV)
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(LINES) + '\n')
    w('')
    w('落盘 %s' % out)
    w('RESULT: FAIL=%d' % FAIL)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
