# -*- coding: utf-8 -*-
u"""第113轮r · 清掉会把「口癖命中率」灌水的登记项（**训练结束后才能跑**）。

问题
----
`assets/npc/_training/cards/*.json` 里的 `voice_markers` 是**评测口径**：
每轮回复只要出现任意一个 marker 就算"有他的味道"。
但有些登记项**任何人在任何一句里都可能出现**，于是命中率被灌成 100%：

    `I`      英文代词，任何英文句子都含      ⇒ hy_chujin_ketsukane 31/36 不可信
    `……`     标点，谁说话都可能带            ⇒ mike/kris/ut_frisk 36/36 不可信
    `[……]`   同上（方括号版）                ⇒ os_prototype/os_rowbot/os_silver
    `想`     中文里恒真                      ⇒ kris/ut_frisk
    `时候`   常见名词，不是口头禅            ⇒ os_watcher

⇒ 这些数字不是"他演得好"，是"判据太松"。清掉之后 `marker_hit` 对该角色
   返回 `None`（`eval113.marker_hit` 明确写了"`markers` 空 ⇒ 不参与统计"），
   报告里显示为 N/A，而不是假的 100%。

为什么不许在训练中途跑
----------------------
训练每条记录存的是**跑那一刻**的登记项。中途改，先跑完的角色留着旧值、
后跑的用新值 ⇒ 同一份报告里两套口径，还没法分辨。所以本脚本**自带闸门**：
检测到 `train30.py` 正在跑就拒绝执行（`--force` 可越过，只给人为调试用）。

为什么不 json.dump 整份回写
---------------------------
实测 96 张卡里 **91 张** `json.dumps(ensure_ascii=False, indent=1)` 能字节还原，
**5 张不能**（`kris`/`rouxls`/`susie` 等，含裸 `\\r` 转义差异）—— 而 `kris`
正好在要改的名单里。⇒ 只做**文本手术**：定位 `"voice_markers"` 那个数组的
字节区间（`raw_decode` 拿准确的 `end`，别用"第一个 `]`"—— `[……]` 里就有 `]`），
只换这一段，其余字节一个不动。EOL 逐文件保留（卡里 CRLF/LF 两种都有）。

用法
----
    python fix_markers113r.py --dry     # 只预览（默认）
    python fix_markers113r.py --apply   # 真写盘
"""
import argparse
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')          # ⇒ 仓库根（含 ralsei_pet）
CARDS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_training', 'cards')

# ★ 逐条来自**磁盘实测**（不是抄文档：文档那张表里 `hy_guardener` 的 `_ ; >`
#   和 `noelle` 的 `……` 实际都不存在，而 `ut_frisk` / `ut_gaster` 文档漏了）。
DROP = {
    'hy_chujin_ketsukane': ['I'],
    'hy_guardener':        ['……'],
    'kris':                ['想', '……'],
    'mike':                ['……'],
    'os_prototype':        ['[……]'],
    'os_rowbot':           ['[……]'],
    'os_silver':           ['[……]'],
    'os_watcher':          ['时候'],
    'ut_frisk':            ['想', '……'],
    'ut_gaster':           ['……'],
}


def _training_running():
    u"""`train30.py` 是否在跑（按 **cmdline 子串**筛，不按进程名 —— 见 §11 误判 1）。"""
    try:
        import psutil
    except Exception:
        return False
    for p in psutil.process_iter(['cmdline']):
        try:
            cl = ' '.join(p.info['cmdline'] or [])
        except Exception:
            continue
        if 'train30.py' in cl and 'fix_markers113r' not in cl:
            return True
    return False


def _no_dup_keys(pairs):
    u"""重复键会让 `json` 静默取最后一个 ⇒ 读的时候就得炸。"""
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError('重复键 %r' % (k,))
        seen[k] = v
    return seen


def _span_of_markers(s):
    u"""返回 `voice_markers` 数组的 `(start, end)` 字节区间（`end` 不含）。"""
    i = s.find('"voice_markers"')
    assert i >= 0, '找不到 "voice_markers"'
    j = s.index('[', i)
    obj, end = json.JSONDecoder().raw_decode(s, j)
    assert isinstance(obj, list), 'voice_markers 不是数组'
    return j, end


def _dump_array(lst, eol):
    u"""按卡里实际的排版还原：`[` 换行、每项 2 空格、收尾 `]` 前 1 空格。"""
    txt = json.dumps(lst, ensure_ascii=False, indent=1)
    return txt.replace('\n', eol) if eol != '\n' else txt


def patch_one(path, drop, apply=False):
    u"""返回 `(ok, msg)`。`ok=False` 表示该卡没动（不需要动或有问题）。"""
    raw = io.open(path, 'r', encoding='utf-8', newline='').read()
    eol = '\r\n' if '\r\n' in raw else '\n'
    data = json.loads(raw, object_pairs_hook=_no_dup_keys)
    cur = data.get('voice_markers')
    assert isinstance(cur, list), '%s 没有 voice_markers 数组' % os.path.basename(path)

    # ★ 要删的每一条都必须在场 —— 静默跳过等于"以为修了其实没修"
    missing = [m for m in drop if m not in cur]
    assert not missing, '%s 里没有这些登记项：%r（实际=%r）' % (
        os.path.basename(path), missing, cur)

    new = [m for m in cur if m not in drop]
    start, end = _span_of_markers(raw)
    out = raw[:start] + _dump_array(new, eol) + raw[end:]

    # 三重自证：① 能解析 ② 内容恰好是预期的 ③ 除这一段外字节完全没动
    back = json.loads(out, object_pairs_hook=_no_dup_keys)
    assert back.get('voice_markers') == new, '回读不一致'
    assert out[:start] == raw[:start] and out[start + len(_dump_array(new, eol)):] == raw[end:], \
        '数组之外的字节被动了'
    s2, e2 = _span_of_markers(out)
    assert s2 == start and out[:s2] == raw[:start], '重定位失败'

    if apply:
        with io.open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        disk = io.open(path, 'r', encoding='utf-8', newline='').read()
        assert disk == out, '写盘后回读不一致'

    return True, '%s  %s → %s' % (json.dumps(cur, ensure_ascii=False),
                                  json.dumps(new, ensure_ascii=False),
                                  '已写盘' if apply else '未写')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help=u'真写盘（默认只预览）')
    ap.add_argument('--dry', action='store_true', help=u'只预览（默认行为）')
    ap.add_argument('--force', action='store_true',
                    help=u'训练在跑也强改（不建议：同一份报告会混两套口径）')
    a = ap.parse_args()
    apply = a.apply and not a.dry

    if not os.path.isdir(CARDS):
        print('找不到卡片目录：%s' % CARDS)
        return 2
    if _training_running() and not a.force:
        print('⛔ train30.py 正在跑 ⇒ 拒绝执行（中途改会让同一份报告混两套口径）。')
        print('   训练结束后再跑；确要越过加 --force。')
        return 3

    files = {}
    for p in sorted(glob.glob(os.path.join(CARDS, '*.json'))):
        files[os.path.splitext(os.path.basename(p))[0]] = p

    absent = [k for k in DROP if k not in files]
    assert not absent, '这些 id 没有卡文件：%r' % (absent,)

    n_ok = n_marker = 0
    emptied = []
    for cid in sorted(DROP):
        ok, msg = patch_one(files[cid], DROP[cid], apply=apply)
        print(('[改] ' if apply else '[预览] ') + msg)
        n_ok += 1
        n_marker += len(DROP[cid])
        if apply:
            left = json.loads(io.open(files[cid], encoding='utf-8').read()).get('voice_markers')
            if not left:
                emptied.append(cid)

    print('\n合计：%d 张卡 / %d 条登记项  %s' % (n_ok, n_marker, '已写盘' if apply else '（未写盘）'))
    if apply and emptied:
        print('★ 清完变空名单（该角色的"口癖命中率"从此记 N/A，不是记 0）：%s'
              % '、'.join(emptied))
    if not apply:
        print('加 --apply 才真写。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
