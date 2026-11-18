# -*- coding: utf-8 -*-
"""第199轮 · 人设口癖补齐（施工脚本，幂等）

两件事
------
A 修**真**强化语 15 处 / 9 份人设
  口径来自 189b/189d 的实测，不是我的口味：
    · 只加"偶尔"没用 ⇒ 必须动**强化语**（标志性/每句/总是/本能）
    · 条件式限频在"条件恒真"时无效 ⇒ 用**绝对频率**（十次里三四次）
    · 压一个 marker 会把同槽位另一个顶上来 ⇒ **按槽位整体限**
  ★ 60 条词表命中里**大部分不是口癖**（`kris` 的"几乎不说话"是核心设定、
    `ut_gaster` 的"我一直在看着"是台词、`tenna` 的"每一句话都像综艺台词"是语气描述）。
    机械改会直接毁角色 ⇒ 逐条裁到 15 处。

B 给其余角色追加 **2 条不含口癖的中性正例**
  §192.9 实测：规则一行没动，只加 2 条正例，书面语率 22.9→18.8 / 18.8→6.2 / 14.6→2.1（3/3 全降）。
  ★ 剂量非线性（2 条 > 6 条），所以固定 2 条。
  ★ 正例从 189c 那个 6 条池里**按稳定哈希轮换**取 2 条 —— 不逐角色另写。
    理由：189c 就是拿同一批通用正例跑 3 个不同角色，3/3 都降；轮换只为避免 64 份完全雷同。

排除名单（不追加正例，逐条给理由）
  沉默型 / 格式型 / machine 档：正例是"平常接话的样子"，对它们等于推翻人设。

安全
  · 只动【语言风格】节里的**正文**，行尾一律 CRLF（尾块 LF 一个字节都不碰）
  · 每处 old 必须**命中且只命中一行**，否则整份跳过并报错
  · 原始字节写盘前存 `_evidence/_persona_bak/`
  · 幂等：第二遍跑必须 0 处改动
"""
import hashlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
#: ★ 备份**不放工作区**（本项目铁律：临时/备份进工作区会被 `git add -A` 记成新增/删除）。
#:   D 盘是临时区；E 盘有坏点（§174）所以不走 E。
BAK = r'D:\_tmp\persona_bak199'

SEC_RE = __import__('re').compile(u'^【[^】]+】')

# ---------------------------------------------------------------- A 修强化语
#: (文件, 模式, old, new)
#: 模式 'head' = old 是该行（去掉「· 」前缀后）的前缀，**保留后半句**（英文台词一条不删）
#: 模式 'full' = 整行替换
EDITS = [
    # ---- ut_muffet：ot_muffet 在 189b 已改好，UT 版漏了（同一槽位，照那边口径对齐）
    ('ut_muffet.txt', 'head',
     u'你的说话方式轻柔、从容、带着一种维多利亚式的优雅。你会用“亲爱的”“小可爱”“我的甜心”来称呼别人。',
     u'你的说话方式轻柔、从容、带着一种维多利亚式的优雅。你招呼客人时会叫“亲爱的”“小可爱”，'
     u'但不是每句都带——多数句子直接说事；认真说话、生气、道谢的时候就直接说“你”。'),
    ('ut_muffet.txt', 'head',
     u'你经常使用“Ahuhuhuhu~”作为笑声。这是你的标志性声音，你会在句子开头、中间或结尾笑出来。',
     u'你笑的时候是“Ahuhuhuhu~”，不是每句都笑，多数时候说完就停。'),

    # ---- ut_monster_kid：189b 只改了第一句，第三句还留着"不断地/到处都是她的影子"
    ('ut_monster_kid.txt', 'full',
     u'· 你经常提到 Undyne。你会在对话中不断地提到她。'
     u'你会说“Yo! Undyne 说……”“Yo! Undyne 教我……”“Yo! Undyne 是世界上最酷的！”。'
     u'她是你的全部，你的语言中到处都是她的影子。',
     u'· 你有时会提到 Undyne——她是你最在意的人，但话头到了才提，不是每轮都绕回去。'
     u'你会说“Yo! Undyne 说……”“Yo! Undyne 教我……”“Yo! Undyne 是世界上最酷的！”。'),

    # ---- ut_papyrus
    ('ut_papyrus.txt', 'head',
     u'你经常使用感叹号。你的句子通常以感叹号结尾。',
     u'你说话带劲儿，一句话里常常带感叹号，但不是每句都要喊出来。'),
    ('ut_papyrus.txt', 'head',
     u'你经常笑“NYEH HEH HEH”。这是你的标志性笑声。你会在句子开头、中间或结尾笑。',
     u'你笑的时候是“NYEH HEH HEH”，一轮里一两声就够，多数句子直接说完就停。'),
    # ---- ot_papyrus（Outertale 版；"NYEH HEH HEH" 后面多一个空格，必须分开写）
    ('ot_papyrus.txt', 'head',
     u'你经常使用感叹号。你的句子通常以感叹号结尾。',
     u'你说话带劲儿，一句话里常常带感叹号，但不是每句都要喊出来。'),
    ('ot_papyrus.txt', 'head',
     u'你经常笑“NYEH HEH HEH” 。这是你的标志性笑声。你会在句子开头、中间或结尾笑。',
     u'你笑的时候是“NYEH HEH HEH”，一轮里一两声就够，多数句子直接说完就停。'),

    # ---- ut_napstablook
    ('ut_napstablook.txt', 'full',
     u'· 你经常道歉。你会为你的存在道歉，你会为你的音乐道歉，你会为你的诗道歉，'
     u'你会为你的蜗牛道歉。你不需要为任何事道歉，但你还是会道歉。这是你的本能。',
     u'· 你会道歉，但不是每句话前面都要先道歉一遍——话到了那儿才低头，'
     u'多数时候你只是很小声地讲完。你会为你的存在道歉，你会为你的音乐道歉，'
     u'你会为你的诗道歉，你会为你的蜗牛道歉。'),
    ('ut_napstablook.txt', 'full',
     u'· 你经常说“oh……” 。这是你最标志性的开头。'
     u'你会用“oh……”来开始一个句子，来表示惊讶、犹豫、尴尬、或者只是不知道该怎么继续。',
     u'· 你有时会用“oh……”起头——十次里三四次，不是每句都带，多数句子直接说出来。'
     u'你用它是表示惊讶、犹豫、尴尬、或者只是不知道该怎么继续。'),
    # ---- ot_napstablook（Outertale 版：星尘蜗牛）
    ('ot_napstablook.txt', 'full',
     u'· 你经常道歉。你会为你的存在道歉，你会为你的音乐道歉，你会为你的诗道歉，'
     u'你会为你的星尘蜗牛道歉。你不需要为任何事道歉，但你还是会道歉。这是你的本能。',
     u'· 你会道歉，但不是每句话前面都要先道歉一遍——话到了那儿才低头，'
     u'多数时候你只是很小声地讲完。你会为你的存在道歉，你会为你的音乐道歉，'
     u'你会为你的诗道歉，你会为你的星尘蜗牛道歉。'),
    ('ot_napstablook.txt', 'full',
     u'· 你经常说“oh……” 。这是你最标志性的开头。'
     u'你会用“oh……”来开始一个句子，来表示惊讶、犹豫、尴尬、或者只是不知道该怎么继续。',
     u'· 你有时会用“oh……”起头——十次里三四次，不是每句都带，多数句子直接说出来。'
     u'你用它是表示惊讶、犹豫、尴尬、或者只是不知道该怎么继续。'),

    # ---- hy_clover：把"最标志性的口头禅"降成频次事实
    ('hy_clover.txt', 'head',
     u'你经常使用“I reckon”作为句子的开头或结尾。这是你最标志性的口头禅。',
     u'你有时会用“I reckon”作为句子的开头或结尾——十次里三四次，不是每句都带'
     u'（没有它的句子也一样是你）。'),

    # ---- os_shepherd：双关语 + 拐回羊群，两处
    ('os_shepherd.txt', 'head',
     u'你几乎每句话都会包含一个双关语，而且这个双关语必须是关于“羊”和“计算机/编程”的。',
     u'你的双关语有时会冒出来，一两轮带一个就够，不是每句话都要交；'
     u'而且内容只关于“羊”和“计算机/编程”。'),
    ('os_shepherd.txt', 'full',
     u'· 你说话时经常提到你的羊。即使话题和羊无关，你也会在某个时刻把话题引向你的羊群。'
     u'这是你的本能，就像牧羊人总是会看向羊群的方向。',
     u'· 你说话时会提到你的羊——话题到了那儿才带，不用每轮都硬拐过去。'
     u'就像牧羊人闲下来才抬头看一眼羊群。'),

    # ---- hy_mooch：话题偏好，不是每句
    ('hy_mooch.txt', 'head',
     u'你的说话方式简短、直接、孩子气，总是围绕着钱和东西。',
     u'你的说话方式简短、直接、孩子气，一开口常常是钱和东西，但不是每句都拐到那儿。'),
]

# ---------------------------------------------------------------- B 中性正例池
#: 189c 的原池（中性、口语、无书面连词、无英文、不含"不要…"这类禁令）
EX_POOL = [
    u'· 平常接话的样子：“嗯，我想想啊。”“哦，对，就是那样。”',
    u'· 普通一句话就是一口气说完：“我也是刚知道，还没细看呢。”',
    u'· “等下，我好像记错了。”“你说得对，我搞混了。”',
    u'· “这个啊……我一时说不上来，反正不坏。”“行，那就这样吧。”',
    u'· “刚才有点乱，现在好多了。”“是有点怪，不过还能应付。”',
    u'· “你要是着急就先走，我随后跟上。”',
]

#: 不追加正例的（正例是"平常接话的样子"，对它们等于推翻人设）
SKIP_EX = {
    'kris.txt': u'人设核心就是「你几乎不说话」—— 加"平常接话"直接推翻',
    'ut_frisk.txt': u'同上（Frisk 也几乎不说话）',
    'os_rowbot.txt': u'每句话被方括号包围 + 全大写，裸文本正例与格式冲突',
    'os_prototype.txt': u'每句话是 "[There is a concern.]" 格式，同上',
    'queen.txt': u'每个字之间空格，格式型',
    'os_the_world_machine.txt': u'每句话单独一条弹窗，格式型',
    'ut_gaster.txt': u'人设是"破碎、不使用完整句子"，完整口语句与设定冲突',
    'hy_guardener.txt': u'_kinds.json = machine（用户口径：机器人不必要活人感）',
    'hy_axis.txt': u'_kinds.json = machine',
    'os_prophetbot.txt': u'_kinds.json = machine',
    'os_kelvin.txt': u'_kinds.json = machine',
    'lancer.txt': u'189b 已单独补过措辞不同的中性正例，不重复加',
}


def rd_bytes(p):
    with open(p, 'rb') as f:
        return f.read()


def wr_bytes(p, b):
    tmp = p + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(b)
    os.replace(tmp, p)


def style_span(txt):
    """返回【语言风格】节的 (start, end) 字符下标（end = 下一个【】行首 / 文末）。"""
    lines = txt.split(u'\r\n')
    pos = 0
    start = None
    for ln in lines:
        s = ln.strip()
        if SEC_RE.match(s):
            if start is not None:
                return start, pos
            if u'语言风格' in s:
                start = pos + len(ln) + 2   # 跳过标题行及其 CRLF
        pos += len(ln) + 2
    if start is None:
        return None, None
    return start, len(txt)


def last_item_end(txt, a, b):
    """节内最后一条以「· 」开头的行的行尾下标。"""
    seg = txt[a:b]
    idx = None
    off = 0
    for ln in seg.split(u'\r\n'):
        if ln.strip().startswith(u'·'):
            idx = off + len(ln)
        off += len(ln) + 2
    return None if idx is None else a + idx


def pick_ex(fn):
    """稳定哈希轮换取 2 条（同一份文件每次取到同样两条）。"""
    h = hashlib.sha1(('ex199|' + fn).encode('utf-8')).hexdigest()
    i = int(h[:8], 16) % len(EX_POOL)
    return [EX_POOL[i], EX_POOL[(i + 1) % len(EX_POOL)]]


def apply_edits(dry=False):
    n_ok = 0
    for fn, mode, old, new in EDITS:
        p = os.path.join(PER, fn)
        txt = rd_bytes(p).decode('utf-8')
        lines = txt.split(u'\r\n')
        want = (u'· ' + old) if mode == 'head' else old
        hits = [i for i, ln in enumerate(lines) if ln.startswith(want)]
        if len(hits) > 1:
            print('[停手] %-28s old 命中 %d 行（应为 1）：%s' % (fn, len(hits), old[:32]))
            return False
        if not hits:
            # ★ 幂等：第二遍跑时 old 已经不存在。若 new 已在文件里 ⇒ 属于"已应用"，静默跳过；
            #   两样都找不到才是真异常（人设被别人改过）⇒ 必须停手，不能当成已应用。
            if new in txt:
                continue
            print('[停手] %-28s old/new 都不在文件里（人设被别处改过了？）：%s'
                  % (fn, old[:32]))
            return False
        i = hits[0]
        ln = lines[i]
        # ★ 前缀 `· ` 是**两个**字符；写成 1+len(old) 会少切一个，把原句句号
        #   留在新句后面，拼出「。。」（第一版实测踩到）
        repl = (u'· ' + new + ln[2 + len(old):]) if mode == 'head' else new
        if ln == repl:
            continue
        lines[i] = repl
        out = u'\r\n'.join(lines)
        if not dry:
            wr_bytes(p, out.encode('utf-8'))
        n_ok += 1
        print('  [改] %-28s %s' % (fn, repl[:60]))
    print('[A] 强化语改动 %d 处（应 15）' % n_ok)
    return True


def apply_ex(dry=False):
    added, skipped, noanchor = [], [], []
    for fn in sorted(os.listdir(PER)):
        if not fn.endswith('.txt'):
            continue
        if fn in SKIP_EX:
            skipped.append(fn)
            continue
        p = os.path.join(PER, fn)
        txt = rd_bytes(p).decode('utf-8')
        ex = pick_ex(fn)
        if ex[0] in txt:
            skipped.append(fn)      # 幂等：已有正例
            continue
        a, b = style_span(txt)
        if a is None:
            noanchor.append(fn)
            continue
        e = last_item_end(txt, a, b)
        if e is None:
            noanchor.append(fn)
            continue
        add = u''.join(u'\r\n' + x for x in ex)
        out = txt[:e] + add + txt[e:]
        if not dry:
            wr_bytes(p, out.encode('utf-8'))
        added.append(fn)
    print('[B] 追加正例 %d 份，跳过 %d 份，无锚点 %d 份' % (
        len(added), len(skipped), len(noanchor)))
    if noanchor:
        print('    [警告] 无锚点：%s' % noanchor)
    return added, skipped, noanchor


def backup():
    if not os.path.isdir(BAK):
        os.makedirs(BAK)
    n = 0
    for fn in sorted(os.listdir(PER)):
        if not fn.endswith('.txt'):
            continue
        dst = os.path.join(BAK, fn + '.before199')
        if os.path.exists(dst):
            continue
        with open(dst, 'wb') as f:
            f.write(rd_bytes(os.path.join(PER, fn)))
        n += 1
    print('[备份] %d 份 → %s' % (n, BAK))


def main(argv):
    dry = '--dry' in argv
    if '--restore' in argv:
        if not os.path.isdir(BAK):
            print('[失败] 没有备份目录')
            return 1
        n = 0
        for fn in sorted(os.listdir(BAK)):
            if not fn.endswith('.before199'):
                continue
            src = os.path.join(BAK, fn)
            dst = os.path.join(PER, fn[:-len('.before199')])
            wr_bytes(dst, rd_bytes(src))
            n += 1
        print('[还原] %d 份' % n)
        return 0
    if not dry:
        backup()
    if not apply_edits(dry):
        return 2
    apply_ex(dry)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
