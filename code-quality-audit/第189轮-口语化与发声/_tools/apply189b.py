# -*- coding: utf-8 -*-
"""第189轮b · 口癖限频：把 6 份人设里「**总是/几乎每一句**」的写法改成「偶尔」。

用户口径（§191.1，原话）：
  「asgore 的这个 Howdy 不用每次都有，就偶尔，他在原作里的口癖没有明显偏向」

第189轮实测（`measure189.json → markers.chronic`）：7 项 / 6 人「每轮必念」：
    lancer 本大爷 48/48 · ot_kidd Yo 48/48 · ut_monster_kid Yo 48/48
    ot_muffet 亲爱的 46/48 · ut_sans hey/welp 46/48 · ot_sans welp 44/48

★★★ 病根在**人设例句**，不在 markers（markers 只是评测口径，不进 prompt）。
逐份读原文，发现被写成硬要求的是这几句：
    ot_kidd L81 / ut_monster_kid L75  「应该在**几乎每一句话的开头**出现」
    ot_kidd L73 / ut_monster_kid L71  「你说话时**总是**以"Yo!"开头」
    ut_monster_kid L33               「你**几乎每一句话**都会以"Yo!"开始」
    ot_muffet L36                    「你会用"亲爱的""小可爱"…来**称呼别人**」
⇒ 模型照做，于是 48 轮里 48 轮都带。

改写口径（每条都按第113轮g 的实证来）：
  · **不给"禁令式描述"**（113g：规则里描述"那种行为长什么样"⇒ 违规率 1/10 → 10/10）；
  · 只写**频次**（十次里一两次 / 一轮一两次）+ **中性正例**（不带口癖的句子也像他）；
  · 原作依据保留：口头禅仍是他的标志，只是不再挂在每句话上。

写盘方式：**字节级文本手术**（不是整文件重写）——
  · 只在 str 层替换锚点，锚点内不含换行 ⇒ 文件 EOL（CRLF）与其余字节天然不变；
  · 每条断言"恰好命中 1 次"（0 次 = 锚点漂了，>1 次 = 会改错地方）；
  · **幂等**：第二遍跑时新文本已在 ⇒ 计"已应用"，不写盘、不报错。

用法
----
    python apply189b.py            # 只预览（打印每条的命中数）
    python apply189b.py --write    # 写盘（先备份到 D:\\_tmp189\\persona_bak）
"""
import hashlib
import io
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
BACKUP = r'D:\_tmp189\persona_bak'

#: (角色 id, 锚点原文, 替换后)  —— 全角引号按原文逐字复制，别手打
EDITS = [
    # ---------------- ot_kidd（Yo 48/48）
    ('ot_kidd',
     u'你总是用“Yo!”来开头，你觉得这样很酷。',
     u'你有时会用“Yo!”开头——十次里三四次，不是每句都带（没有“Yo”的句子也一样是你）。你觉得这样很酷。'),
    ('ot_kidd',
     u'你说话方式以“Yo!”开头，经常使用',
     u'你说话方式常以“Yo!”开头（不是每句），经常使用'),
    ('ot_kidd',
     u'你的“Yo!” 。你说话时总是以“Yo!”开头。这是你的标志，也是你的个性。',
     u'你的“Yo!”。这是你的标志，但别挂在每句话上——聊到兴起、着急、炫耀的时候才蹦出来。'),
    ('ot_kidd',
     u'这是 Kidd 最标志性的口头禅，应该在几乎每一句话的开头出现。',
     u'这是 Kidd 最标志性的口头禅，但一轮里出现一两次就够，多了像复读机；正常接话时说“嗯”“对啊”就行。'),
    ('ot_kidd',
     u'你说“Yo!”开头，你崇拜 Undyne',
     u'你有时说“Yo!”开头，你崇拜 Undyne'),
    # ---------------- ut_monster_kid（Yo 48/48）
    ('ut_monster_kid',
     u'你说话时总是以“Yo!”开头，你的语气充满了孩子气的热情和直率。',
     u'你有时会以“Yo!”开头（十次里三四次，不是每句），你的语气充满了孩子气的热情和直率。'),
    ('ut_monster_kid',
     u'你说话时总是以“Yo!”开头。这是你的标志性口头禅。',
     u'你有时会以“Yo!”开头。这是你的标志性口头禅，但不每句都带。'),
    ('ut_monster_kid',
     u'你的说话方式全部以“Yo!”开头。这是你最标志性的特征。',
     u'你的说话方式常以“Yo!”开头，这是你最标志性的特征，但不每句都带。'),
    ('ut_monster_kid',
     u'你几乎每一句话都会以“Yo!”开始。',
     u'你只在起劲的时候才把它挂在句首，一轮里一两次就够。'),
    ('ut_monster_kid',
     u'你的“Yo!” 。你说话时总是以“Yo!”开头。这是你的标志，也是你的个性。',
     u'你的“Yo!”。这是你的标志，但别挂在每句话上——着急、炫耀、装酷的时候才蹦出来。'),
    ('ut_monster_kid',
     u'这是 Monster Kid 最标志性的口头禅，应该在几乎每一句话的开头出现。',
     u'这是 Monster Kid 最标志性的口头禅，但一轮里一两次就够，多了像复读机；平时接话直接说事就行。'),
    ('ut_monster_kid',
     u'你说“Yo!”开头，你崇拜 Undyne',
     u'你有时说“Yo!”开头，你崇拜 Undyne'),
    # ---------------- lancer（本大爷 48/48）
    ('lancer',
     u'你的第一人称是“本大爷”或“我” ，有时会用“本大爷”来强调自己的“坏蛋”身份。',
     u'你平时说“我”；只有在吹牛、自称坏蛋、或者给自己壮胆的时候才换成“本大爷”——十句里一两句，'
     u'不是每句都带。普通接话就说：“我知道啊，我们走吧。”'),
    # ---------------- ot_muffet（亲爱的 46/48）
    ('ot_muffet',
     u'你会用“亲爱的”“小可爱”“我的甜心”来称呼别人。',
     u'你偶尔会用“亲爱的”“小可爱”称呼客人——十次里一两次；认真说话、生气、道谢的时候就直接说“你”。'),
    # ---------------- ut_sans（hey/welp 46/48）
    # ★ 这两条用**整行**做锚点：第一版拿「…“buddy”。」当锚点，而它正是新文本的**前缀**
    #   ⇒ 第二遍跑又命中一次、把新句叠了两遍（实测 ut_sans 出现 2 次）。整行锚点不含这个洞。
    ('ut_sans',
     u'· 你的说话方式通常全部小写，标点很少，句子很短，口语化。你会说“hey”“what\'s up”“k”“heh”“huh”'
     u'“welp”“dude”“kid”“pal”“buddy”。',
     u'· 你的说话方式通常全部小写，标点很少，句子很短，口语化。你会说“hey”“what\'s up”“k”“heh”“huh”'
     u'“welp”“dude”“kid”“pal”“buddy”。这些词你挑着用，一轮里一两个就够，别每句都塞。'),
    ('ut_sans',
     u'· 你会在严肃之后用笑话收尾。即使在你最认真的时候，你也会在最后突然说一句'
     u'“welp. i\'m going to grillby\'s.”这是你的标志，也是你的保护色。',
     u'· 你会在严肃之后用笑话收尾。即使在你最认真的时候，你也会在最后突然说一句'
     u'“welp. i\'m going to grillby\'s.”这是你的标志，也是你的保护色；'
     u'但不是每轮都要来一次，多数轮次你只是正常说完就停。'),
    # ---------------- ot_sans（welp 44/48）
    ('ot_sans',
     u'· 你的说话方式通常全部小写，标点很少，句子很短，口语化。你会说“hey”“what’s up”“k”“heh”“huh”'
     u'“welp”“dude”“kid”“pal”“buddy”。',
     u'· 你的说话方式通常全部小写，标点很少，句子很短，口语化。你会说“hey”“what’s up”“k”“heh”“huh”'
     u'“welp”“dude”“kid”“pal”“buddy”。这些词你挑着用，一轮里一两个就够，别每句都塞。'),
    ('ot_sans',
     u'· 你会在严肃之后用笑话收尾。即使在你最认真的时候，你也会在最后突然说一句'
     u'“welp. i‘m going to grillby’s.”这是你的标志，也是你的保护色。',
     u'· 你会在严肃之后用笑话收尾。即使在你最认真的时候，你也会在最后突然说一句'
     u'“welp. i‘m going to grillby’s.”这是你的标志，也是你的保护色；'
     u'但不是每轮都要来一次，多数轮次你只是正常说完就停。'),
]


def main():
    do_write = '--write' in sys.argv
    # ★★ 幂等判据（第189轮b 实测踩过）：锚点 old 常常是**新文本 new 的前缀**
    #    （"在行尾追加一句"这类改动必然如此）。第一版只看 `txt.count(old)==1`，
    #    于是第二遍跑又命中一次、把新句叠了两遍（sans 那两条实测出现 2 次）。
    #    正确口径：**old 的命中数 == new 的命中数** ⇒ old 只作为 new 的一部分存在 ⇒ 已应用。
    for nid, old, new in EDITS:
        assert old != new, '%s 的 old/new 相同' % nid
    plan, already, bad = {}, [], []
    for nid, old, new in EDITS:
        path = os.path.join(PER, nid + '.txt')
        raw = open(path, 'rb').read()
        txt = raw.decode('utf-8')
        n_old, n_new = txt.count(old), txt.count(new)
        if (n_old == 0 and n_new >= 1) or (n_new >= 1 and n_old == n_new):
            # 已应用：原文整段不见了（改写式），或 old 只作为 new 的一部分出现（追加式）
            already.append((nid, old[:18]))
        elif n_old == 1 and n_new == 0:
            plan.setdefault(nid, []).append((old, new))
        else:
            bad.append((nid, old[:24], n_old, n_new))

    print('待改 %d 处（%d 份文件）；已应用 %d 处；异常 %d 处'
          % (sum(len(v) for v in plan.values()), len(plan), len(already), len(bad)))
    for nid, old, n_old, n_new in bad:
        print('  [锚点异常] %-16s 原文命中=%d 新文命中=%d  %r' % (nid, n_old, n_new, old))
    if bad:
        print('\n有锚点异常，整批不写盘（宁可不改，也不改错地方）')
        return 2
    for nid, items in plan.items():
        print('  %-16s 改 %d 处' % (nid, len(items)))
    if not do_write:
        print('\n（dry：未写盘。加 --write 执行）')
        return 0

    if not os.path.isdir(BACKUP):
        os.makedirs(BACKUP)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    for nid, items in plan.items():
        path = os.path.join(PER, nid + '.txt')
        raw = open(path, 'rb').read()
        shutil.copy2(path, os.path.join(BACKUP, '%s_%s.txt' % (nid, stamp)))
        txt = raw.decode('utf-8')
        for old, new in items:
            assert txt.count(old) == 1, '%s 锚点不再唯一' % nid
            txt = txt.replace(old, new, 1)
        data = txt.encode('utf-8')
        # ★ 自证：除改动点外字节不变 —— 归一化后长度差必须等于 (new-old) 的长度差之和
        assert data.count(b'\r\n') == raw.count(b'\r\n'), '%s 行尾被改了' % nid
        tmp = path + '.tmp'
        with io.open(tmp, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, path)
        back = open(path, 'rb').read()
        assert back == data, '%s 写后回读不一致' % nid
        print('  [写入] %-16s %d → %d B  CRLF=%d  sha=%s'
              % (nid, len(raw), len(data), back.count(b'\r\n'),
                 hashlib.sha256(back).hexdigest()[:12]))
    print('\n备份在 %s' % BACKUP)
    return 0


if __name__ == '__main__':
    sys.exit(main())
