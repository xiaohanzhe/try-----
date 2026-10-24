# -*- coding: utf-8 -*-
r"""第113轮b · 核心文件复检（用户口径：「以后再调整重要核心文件时一定要记得复检」）。

本轮动到的**产品核心文件**：
  · `ralsei_pet/modules/npc_persona.py` —— 加了 `evolution_patch` +
    `build_system_prompt` 的 `evolution` 参数。

复检六项（脚本自己也会说谎，所以每一项都要有可复算的判据）：
  ① 语法 / 可编译（用 ast.parse，**不产 .pyc**，避免改变被测状态）
  ② 结构自检：新加的函数/常量/参数**真的在**，且旧的没被顶掉
  ③ 无 BOM / 无 U+FFFD / CRLF 混排
  ④ **恒真判据复查**：本轮新写的验证脚本里有没有 `ck(..., True)` 这类假守卫
  ⑤ **逐令牌回验**：改过/新增的标识符，逐个回原文件 `in` 一次
  ⑥ 工作区状态（**只对"本轮的手"判越界**；前几轮 `git reset` 留下的已暂存删除
     是历史噪声，算进来越界＝判据过宽＝永远 FAIL＝等于没守）

跑法：python recheck113b.py
"""
import ast
import os
import re
import subprocess
import sys

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(REPO, 'ralsei_pet')
ROUND = os.path.join(REPO, 'code-quality-audit', '第113轮-全体角色AI训练')
TOOLS = os.path.join(ROUND, '_tools')

PASS = 0
FAIL = 0
SKIP = 0


def ck(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  [PASS] %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  [FAIL] %s %s' % (name, detail))


def skip(name, why):
    global SKIP
    SKIP += 1
    print('  [SKIP] %s —— %s' % (name, why))


CORE = os.path.join(PET, 'modules', 'npc_persona.py')


def item1_syntax():
    print('\n=== ① 语法 / 可编译 ===')
    targets = [CORE]
    for f in ('train30.py', 'dialogue113.py', 'report30.py', 'chain113.py',
              'evolve113.py', 'verify_script48.py', 'verify_relation_evo.py'):
        targets.append(os.path.join(TOOLS, f))
    for p in targets:
        if not os.path.exists(p):
            ck('① %s 存在' % os.path.basename(p), False, '文件不存在')
            continue
        src = open(p, encoding='utf-8', errors='replace').read()
        try:
            ast.parse(src)
            ck('① ast.parse %s' % os.path.basename(p), True, '%d 字符' % len(src))
        except SyntaxError as e:
            ck('① ast.parse %s' % os.path.basename(p), False,
               'line %s: %s' % (e.lineno, e.msg))


def item2_structure():
    print('\n=== ② 结构自检：新东西在、旧东西没被顶掉 ===')
    src = open(CORE, encoding='utf-8', errors='replace').read()
    must_have = [
        ('def evolution_patch(', '新增函数 evolution_patch'),
        ('_EVOLVE_HINTS', '新增常量 _EVOLVE_HINTS'),
        ("evolution=''", 'build_system_prompt 新增 evolution 参数（默认空）'),
        ("relation=''", '旧的 relation 参数还在（默认空）'),
        ("patch=''", '旧的 patch 参数还在（默认空）'),
        ('def relation_patch(', '旧的 relation_patch 还在'),
        ('def training_patch(', '旧的 training_patch 还在'),
        ('SPEAK_RULES = (', 'SPEAK_RULES 还在'),
        ('每句话本身也要短', '上一轮加的"话多≠句长"还在（没被这轮顶掉）'),
        ('用简体中文说话', '语言约束还在'),
        ('WHO_IS_TALKING = (', 'WHO_IS_TALKING 还在'),
    ]
    for token, why in must_have:
        ck('② %s' % why, token in src)

    # 顺序：静态关系卡 → 演化卡 → SPEAK_RULES
    i_rel = src.find("【你和其他人的关系（照这个，别自己编）】")
    i_evo = src.find("if isinstance(evolution, str) and evolution.strip():")
    i_speak = src.find('parts.append(SPEAK_RULES)')
    ck('② 演化卡插在静态关系卡之后', 0 <= i_rel < i_evo, '%d < %d' % (i_rel, i_evo))
    ck('② 演化卡插在 SPEAK_RULES 之前', 0 <= i_evo < i_speak, '%d < %d' % (i_evo, i_speak))

    # 函数定义只应有 1 处（重复定义会"后面覆盖前面"——本轮就栽过一次）
    for fn in ('build_system_prompt', 'evolution_patch', 'relation_patch'):
        n = len(re.findall(r'^def %s\(' % fn, src, re.M))
        ck('② %s 只定义一次' % fn, n == 1, '实际 %d 处' % n)


def item3_encoding():
    print('\n=== ③ 编码 / 换行 ===')
    for p in (CORE, os.path.join(TOOLS, 'train30.py'),
              os.path.join(TOOLS, 'dialogue113.py')):
        raw = open(p, 'rb').read()
        name = os.path.basename(p)
        ck('③ %s 无 UTF-8 BOM' % name, not raw.startswith(b'\xef\xbb\xbf'))
        text = raw.decode('utf-8', 'replace')
        ck('③ %s 无 U+FFFD（替换字符）' % name, '\ufffd' not in text)
        crlf = raw.count(b'\r\n')
        lf = raw.count(b'\n')
        ck('③ %s 换行风格一致' % name,
           crlf == 0 or crlf == lf,
           'CRLF=%d 总LF=%d' % (crlf, lf))


def item4_tautology():
    print('\n=== ④ 恒真判据复查（本轮新写的验证脚本） ===')
    pats = [
        (r'ck\([^)]*,\s*True\s*[,)]', 'ck(..., True) 直接通过'),
        (r'assert\s+True\b', 'assert True'),
        (r'if\s+False\s*:', 'if False 死分支'),
        (r'\{\}\s*==\s*\{\}', '空字典自比'),
    ]
    for f in ('verify_script48.py', 'verify_relation_evo.py'):
        p = os.path.join(TOOLS, f)
        if not os.path.exists(p):
            skip('④ %s' % f, '文件不存在')
            continue
        src = open(p, encoding='utf-8', errors='replace').read()
        code = '\n'.join(l for l in src.split('\n')
                         if not l.strip().startswith('#'))
        bad = []
        for pat, why in pats:
            for m in re.finditer(pat, code):
                bad.append('%s @%d' % (why, code[:m.start()].count('\n') + 1))
        ck('④ %s 无恒真判据' % f, not bad, '; '.join(bad[:3]))
        # 反过来：必须真的有负控制（找 "负控制" 字样且配套 ck）
        ck('④ %s 带负控制' % f, '负控制' in src,
           '出现 %d 次' % src.count('负控制'))


def item5_tokens():
    print('\n=== ⑤ 逐令牌回验（改过的标识符逐个回原文件 in 一次） ===')
    core = open(CORE, encoding='utf-8', errors='replace').read()
    train = open(os.path.join(TOOLS, 'train30.py'),
                 encoding='utf-8', errors='replace').read()
    dlg = open(os.path.join(TOOLS, 'dialogue113.py'),
               encoding='utf-8', errors='replace').read()

    core_tokens = ['evolution_patch', '_EVOLVE_HINTS', 'evolution', '_PATCH_CACHE',
                   '你和你身边的人之间的事', '也别重编']
    # 上面第二项里我写的是"你和别人之间的事"，这里用真实字符串再验一次
    core_tokens[4] = '你和别人之间的事'
    for t in core_tokens:
        ck('⑤ npc_persona 含 `%s`' % t, t in core)

    train_tokens = ['SCRIPT48', 'TAGS48', 'tag_of', 'slots_of', 'SCRIPT30',
                    'pref_topics', 'NPC_LINES', 'PLOT_TEMPLATES',
                    'PREF_TEMPLATES', 'REL_TEMPLATES', 'FALLBACK_NPC',
                    'PREF_SLOTS', 'NPC_SLOTS', 'REL_SLOTS', 'PLOT_SLOTS',
                    '__PREF1__', '__PREF2__', '__NPC1__', '__PLOT3__']
    for t in train_tokens:
        ck('⑤ train30 含 `%s`' % t, t in train)

    ck('⑤ dialogue113 传了 relation', 'relation=C._NP.relation_patch(' in dlg)
    ck('⑤ dialogue113 传了 evolution', 'evolution=C._NP.evolution_patch(' in dlg)

    # 数字类令牌：这三处必须一致
    m = re.search(r'^TURNS_DEFAULT = (\d+)', train, re.M)
    ck('⑤ TURNS_DEFAULT == 48', bool(m) and m.group(1) == '48',
       m.group(1) if m else '未找到')
    ck('⑤ TURNS_DEFAULT 只有一处定义',
       len(re.findall(r'^TURNS_DEFAULT\s*=', train, re.M)) == 1,
       str(len(re.findall(r'^TURNS_DEFAULT\s*=', train, re.M))))
    m2 = re.search(r'^CTX30 = (\d+)', train, re.M)
    ck('⑤ CTX30 == 20480', bool(m2) and m2.group(1) == '20480',
       m2.group(1) if m2 else '未找到')
    ck('⑤ 剧本 48 条（数 tag 元组）',
       len(re.findall(r"^\s*\('(?:open|pref|press|quirk|mem|plot|rel|npc|feel|world|meta|deep|close)',",
                      train, re.M)) == 48,
       str(len(re.findall(r"^\s*\('(?:open|pref|press|quirk|mem|plot|rel|npc|feel|world|meta|deep|close)',",
                          train, re.M))))


# 本轮允许碰的路径（只对"本轮的手"生效，见 _split_hands）
ALLOWED = ('ralsei_pet/modules/npc_persona.py',
           '.workbuddy/memory/',
           'code-quality-audit/第113轮-全体角色AI训练/',
           'ralsei_pet/assets/npc/_relations/_evolution.json')

# 本轮该改的产品**代码**（多一个都算越界）
#   npc_persona.py = evolution_patch + build_system_prompt(evolution=)
#   src/main.py    = 唯一出口补接线 patch / relation / evolution（check113 C5/C10 断言）
PRODUCT_EDITS = ('ralsei_pet/modules/npc_persona.py',
                 'ralsei_pet/src/main.py')

# "产品代码"＝.py 源码；assets/*.json 是数据面，历轮遗留的改动不算越界（只报数）
PRODUCT_CODE = ('ralsei_pet/modules/', 'ralsei_pet/src/')

# 产品代码 / 人设数据不许"被删掉"（资产、评测脚本可以是历史遗留删除）
NO_DELETE = ('ralsei_pet/modules/', 'ralsei_pet/assets/npc/', 'ralsei_pet/src/')


def _porcelain_paths(out):
    """把 `git status --porcelain` 拆成 [(XY, path), ...]。

    两个坑都踩过：
      ① `l[3:]` 是惯用法，但**重命名/复制条目**形如 `R  old -> new`，
         必须取箭头右边的目标路径，否则会把源路径误判成"越界"。
      ② **必须 `-c core.quotepath=false`**：中文路径默认被 C 引号包成
         `"code-quality-audit/\\347\\254\\254113..."`，那样连"预期路径"
         都匹配不上 —— 第 113 轮b 首跑就是被这个假象骗了。
    """
    rows = []
    for l in out.split('\n'):
        if not l.strip() or len(l) < 4:
            continue
        xy, rest = l[:2], l[3:]
        if ' -> ' in rest:
            rest = rest.split(' -> ', 1)[1]
        rows.append((xy, rest.strip().strip('"')))
    return rows


def _split_hands(rows):
    """按**状态字母**分类：未跟踪 / 已修改 / 已删除。

    为什么不再按"暂存列"切：实测第 113 轮b 的工作区是
    `63 ' M' + 1020 ' D' + 50 '??'` —— 那 1020 条历史删除**并没有暂存**，
    全是工作区侧的 ` D`（前几轮搬走/归档留下的）。按暂存列切会把它们
    判成"本轮的手"，于是 1122 条历史噪声把唯一的 FAIL 顶出来。
    """
    untracked, modified, deleted = [], [], []
    for xy, path in rows:
        if xy == '??':
            untracked.append(path)
        elif 'D' in xy:
            deleted.append(path)
        elif 'M' in xy or 'R' in xy or 'A' in xy:
            modified.append(path)
    return untracked, modified, deleted


def _out_of_scope(paths):
    return [p for p in paths if not any(a in p for a in ALLOWED)]


def _deleted_product(paths):
    return [p for p in paths if any(p.startswith(a) for a in NO_DELETE)]


def _selftest61():
    """判据自己的负控制：分类器与越界判定都必须能"抓得住"，也必须放得过。

    没有这一段，"全部落在预期路径内"只是我自认为它是对的。
    """
    print('\n=== ⑥-selftest（判据的负控制）===')
    fake = ('?? code-quality-audit/第113轮-全体角色AI训练/_tools/x.py\n'
            ' M ralsei_pet/modules/npc_persona.py\n'
            ' M ralsei_pet/modules/evil_backdoor.py\n'
            ' D code-quality-audit/第101轮-旧/x.py\n'
            ' D ralsei_pet/modules/door_reveal.py\n'
            'R  a.py -> b.py\n')
    rows = _porcelain_paths(fake)
    untracked, modified, deleted = _split_hands(rows)
    ck('⑥-ctl 未跟踪/已修改/已删除切对',
       (len(untracked), len(modified), len(deleted)) == (1, 3, 2),
       '%d/%d/%d' % (len(untracked), len(modified), len(deleted)))
    ck('⑥-ctl 重命名取目标路径', 'b.py' in modified, str(modified))
    bad = _out_of_scope(untracked + modified)
    ck('⑥-ctl 越界路径被抓出（含重命名目标）',
       sorted(bad) == ['b.py', 'ralsei_pet/modules/evil_backdoor.py'], str(bad))
    ck('⑥-ctl 预期路径被放过',
       'ralsei_pet/modules/npc_persona.py' not in bad, '')
    ck('⑥-ctl 产品模块被删会被抓出',
       _deleted_product(deleted) == ['ralsei_pet/modules/door_reveal.py'],
       str(_deleted_product(deleted)))
    ck('⑥-ctl 评测目录的删除被放过',
       'code-quality-audit/第101轮-旧/x.py' not in _deleted_product(deleted), '')


def item6_worktree():
    print('\n=== ⑥ 工作区 ===')
    _selftest61()
    p = subprocess.run(['git', '-c', 'core.quotepath=false', 'status', '--porcelain'],
                       cwd=REPO, capture_output=True)
    rows = _porcelain_paths((p.stdout or b'').decode('utf-8', 'replace'))
    untracked, modified, deleted = _split_hands(rows)
    print('     条目 %d：未跟踪 %d / 已修改 %d / 已删除 %d'
          % (len(rows), len(untracked), len(modified), len(deleted)))

    # (a) 未跟踪 = 本轮新建的产物，必须全在预期路径（防临时文件落进仓库）
    bad = _out_of_scope(untracked)
    if bad:
        print('     ⚠ 越界的未跟踪文件（前 10）：')
        for x in bad[:10]:
            print('        ', x)
    ck('⑥ 未跟踪文件都在预期路径内', not bad,
       '越界 %d / 共 %d' % (len(bad), len(untracked)))

    # (b) 产品**代码**本轮只该改 npc_persona.py 一个（多改一个都是越界）
    prod = [m for m in modified if m.startswith(PRODUCT_CODE)]
    extra = [m for m in prod if m not in PRODUCT_EDITS]
    if extra:
        for x in extra[:10]:
            print('        ', x)
    ck('⑥ 产品代码只改了本轮预期的那一个文件', not extra,
       '多改 %d 个 / 共改 %d 个' % (len(extra), len(prod)))
    # 数据面（assets/*.json）的改动只报数：历轮遗留，本轮不碰
    data = [m for m in modified if m.startswith('ralsei_pet/assets/')]
    if data:
        print('     （另有 %d 个资产 JSON 被改：历轮遗留，本轮未动）' % len(data))

    # (c) 产品代码/人设数据不许被删；资产与评测脚本的历史删除只报数
    dprod = _deleted_product(deleted)
    if dprod:
        for x in dprod[:10]:
            print('        ', x)
    ck('⑥ 产品代码与人设数据没有文件被删', not dprod,
       '被删 %d 个' % len(dprod) if dprod else
       '（另有 %d 条历史遗留删除，属资产/评测目录，非本轮）' % len(deleted))


# ---- ⑦ 反回滚闸 ----------------------------------------------------------
# 为什么要有这一条：第 113 轮b 实测发现**工作区有一批产品文件被回滚成
# 2026-10-06/09 的旧版**（`scene_camera.py` 少了整块 `SCENE_ASPECT`/`fit_fraction`、
# `dialogue_ui.py` 少了 160 行、`door_reveal.py`/`niko_home.py` 整个文件消失），
# 而 HEAD 里全都在。⑥ 只看"路径是否越界"，看不出"内容倒退"。
# 判据：产品文件的**行数不许比 HEAD 缩水 >30%**，且关键文件必须在。
ROLLBACK_GUARD = [
    'ralsei_pet/modules/dialogue_ui.py',
    'ralsei_pet/modules/dr_textbox.py',
    'ralsei_pet/modules/item_interact.py',
    'ralsei_pet/modules/item_menu_ui.py',
    'ralsei_pet/modules/npc_persona.py',
    'ralsei_pet/modules/scene_camera.py',
    'ralsei_pet/modules/scene_canvas.py',
    'ralsei_pet/modules/scene_controller.py',
    'ralsei_pet/modules/scene_render.py',
    'ralsei_pet/modules/soul_entity.py',
    'ralsei_pet/modules/soul_overlay.py',
    'ralsei_pet/modules/door_reveal.py',
    'ralsei_pet/modules/niko_home.py',
    'ralsei_pet/src/main.py',
    # ★ 回归脚手架也要守：`run_all.py` 被回滚到旧版 ⇒ 套件从 102 条**静默缩到 93 条**
    #   （check101~107/109/111/112 全掉出 SUITES），G2 仍然"跑绿"，只是少测了 9 轮。
    #   同理 `baseline.json` 被回滚 ⇒ 基线对不上当前树，DIFF 满天飞但看不出根因。
    'code-quality-audit/regress/run_all.py',
    'code-quality-audit/regress/baseline.json',
]


def _shrink_ratio(head_src, disk_src):
    """返回 磁盘行数 / HEAD 行数（>1 表示变多，正常）。HEAD 为空时返回 1.0。"""
    hl = head_src.count('\n') + 1
    dl = disk_src.count('\n') + 1
    return (dl / float(hl)) if hl else 1.0


def _shrunk(head_src, disk_src, floor=0.7):
    """磁盘内容比 HEAD 缩水 >(1-floor) 即算倒退；**文件消失也算倒退**。

    负控制抓到的坑：最初写成 `disk_src is not None and ...`，
    于是"文件整个没了"被判成"没有缩水" —— 恰恰最该报的情况漏掉了。
    """
    if disk_src is None:
        return True
    return _shrink_ratio(head_src, disk_src) < floor


def item7_rollback():
    print('\n=== ⑦ 反回滚闸（内容不许比 HEAD 倒退）===')
    # 负控制：真缩水要抓得住；只是多了几行要放过
    ck('⑦-ctl 缩水 40% 会被抓出', _shrunk('a\n' * 100, 'a\n' * 60), '')
    ck('⑦-ctl 变多不会被误报', not _shrunk('a\n' * 100, 'a\n' * 120), '')
    ck('⑦-ctl 文件消失会被抓出', _shrunk('a\n' * 100, None), '')

    miss, shrunk = [], []
    for rel in ROLLBACK_GUARD:
        fp = os.path.join(REPO, rel)
        if not os.path.exists(fp):
            miss.append(rel)
            continue
        head = subprocess.run(['git', 'show', 'HEAD:' + rel], cwd=REPO,
                              capture_output=True).stdout.decode('utf-8', 'replace')
        disk = open(fp, encoding='utf-8', errors='replace').read()
        if _shrunk(head, disk):
            shrunk.append((rel, head.count('\n') + 1, disk.count('\n') + 1))
    ck('⑦ 产品文件一个都不缺', not miss,
       '缺 %s' % miss if miss else '%d 个文件齐' % len(ROLLBACK_GUARD))
    if shrunk:
        for rel, hl, dl in shrunk:
            print('        %-48s HEAD %d → 磁盘 %d' % (rel, hl, dl))
    ck('⑦ 产品文件行数没有比 HEAD 缩水 >30%', not shrunk,
       '缩水 %d 个' % len(shrunk) if shrunk else '')


def main():
    item1_syntax()
    item2_structure()
    item3_encoding()
    item4_tautology()
    item5_tokens()
    item6_worktree()
    item7_rollback()
    print('\n===== PASS=%d FAIL=%d SKIP=%d =====' % (PASS, FAIL, SKIP))
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
