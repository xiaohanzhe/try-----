# -*- coding: utf-8 -*-
"""把 `check113k` 注册进 G2 的 `SUITES`（第 108 个套件）。

★ 为什么进 G2：这一层决定 NPC **会不会把人推荐到别的地方去**。
  它一坏，用户看到的不是报错，而是角色很自信地说「那要不去 XX」——
  而 XX 可能是另一个世界的餐厅，或者一个调试房。**静默错比崩溃难发现得多**。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
RUN = os.path.join(ROOT, 'code-quality-audit', 'regress', 'run_all.py')
NL = '\r\n'

ANCHOR = "         '也算成三段 ⇒ 谎报 320 条。'," + NL + "    }," + NL + "]"

ENTRY = """    },
    # ★ 第113轮k：**特定事件 → 去哪儿**。
    #   为什么进 G2：这一层坏掉**不会报错**，而是角色很自信地推荐一个
    #   不存在 / 别的世界 / 调试房的地方 —— 静默错比崩溃难发现得多。
    {
        'id': 'check113k',
        'script': os.path.join(ROOT, 'code-quality-audit',
                               '第113轮-全体角色AI训练', '_tools', 'check113k.py'),
        'offscreen': False,
        'desc': '第一百一十三轮k：**特定事件 → 去哪儿**（NPC 听懂「咱吃饭去吧」'
                '并给出「那要不去 XXX 家餐厅」）。'
                '用户口径「吃饭/活动/休息/做任务等，他能识别出来要去哪，并给出建议」。'
                '★ 两件事必须分开：`detect_activity` 只认**意图词**、`place_matches` 只认'
                '**地点词** —— 混成一张表会因果倒置（"因为人在餐厅所以他在吃饭"）。'
                'A 抽取 + 策略层零依赖 · B 听懂四种 + 多活动取**语序最先** · '
                'C `place_matches` 正负成对（`town_school` 要命中 `school`；`sparks` 不许命中 '
                '`park`）· D 候选必须**说得出是哪一家**（`家乡 · diner（餐厅）`；'
                '第一版输出「真有的地方：家乡」，用户要的那个「XXX 家餐厅」没了 —— 实测抓到的真错误）+ '
                '去重不变量（同区同类只留一条，但**不许过度**）· E 负控制（无关话/判不出章/'
                '**调试区**都不产块）· F 翻译表**不越权**（`Research Station` 不是火车站）· '
                'G 名字整形三条正负成对（房号/行首单字母/截到类型词为止）· H 全量普查 · '
                'I AST 接线（`heard` 必须从 `chat_with_ai` 一路传下来，且**有闸** —— '
                '没闸就是给所有 NPC 无条件加行、等于改人设）· J 方法级端到端。'
                '★ 判据用**不变量**（"同区不许有两家同类型店"），不冻结数据（"ch1 必须 3 条"）'
                '—— 否则以后加素材就假红。',
    },
]"""


def main():
    t = io.open(RUN, 'r', encoding='utf-8', newline='').read()
    if "'check113k'" in t:
        print('[SKIP] 已注册')
        return 0
    if ANCHOR not in t:
        print('[FAIL] 锚点没命中')
        return 1
    t = t.replace(ANCHOR, ENTRY.replace('\n', NL), 1)
    io.open(RUN, 'w', encoding='utf-8', newline='').write(t)
    print('[ OK ] SUITES 追加 check113k')

    src = io.open(RUN, 'r', encoding='utf-8', newline='').read()
    try:
        ast.parse(src)
        print('[ OK ] 语法 PASS')
    except SyntaxError as e:
        print('[FAIL] 语法 %s' % e)
        return 1
    n = src.count('\n')
    print('行=%d CRLF=%d gap=%d' % (n, src.count('\r\n'), n - src.count('\r\n')))

    # 套件数与 id 唯一性（重复 id 会让基线静默覆盖）
    tree = ast.parse(src)
    ids = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys
                    if isinstance(k, ast.Constant) and k.value == 'id']
            if keys:
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value == 'id' \
                            and isinstance(v, ast.Constant):
                        ids.append(v.value)
    print('SUITES 条数=%d  重复 id=%r' % (len(ids),
                                          [x for x in set(ids) if ids.count(x) > 1]))
    print('末三条=%r' % (ids[-3:],))
    return 0


if __name__ == '__main__':
    sys.exit(main())
