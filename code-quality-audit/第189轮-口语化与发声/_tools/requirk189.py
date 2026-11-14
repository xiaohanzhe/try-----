# -*- coding: utf-8 -*-
"""第189轮d · 口癖复测：6 人改完人设后，48 轮里还"每轮必念"吗？

背景
----
第189轮b 把 6 个角色的「总是 / 几乎每一句话都」改成「偶尔 / 一轮一两次」并加了中性正例
（共 17 处，commit `fe7edd1f`），但**只做到"改完 + G2 全绿"，没重训验证**
（详见 §192.8「未复测」）。

这个脚本补那一刀：
  · 基线 = `_evidence/raw30` 里现有的 48 轮（187 那批，一个字节不动）
  · 复测 = 用**当前人设**重训 24 轮（见 TURNS 的说明），输出到 `_evidence/requirk189/`
  · 对照 = 逐个 marker 的命中轮数 / 总轮数

★ 与 ab189 的关键差别：**本脚本不改人设**（改的是已经提交进仓库的现行人设），
  所以没有还原风险，也不需要 `try/finally` 字节回滚。

★ 判据陷阱：`marker_rate` 是"**任一** marker 命中"，6 人里有好几个角色有 2 个以上 marker
  （如 sans 的 hey/welp），只看合计会把"welp 没了但 hey 还在"读成"没改善"
  ⇒ **必须逐 marker 出数**，合计只作参考。

用法
----
    python requirk189.py --check      # 只出基线（逐 marker），不训练
    python requirk189.py              # 重训 6 人 × 24 轮（约 2 小时）
"""
import io
import json
import os
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
TOOLS113 = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练', '_tools')
EVID = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EVID, 'requirk189')
OLLAMA = r'C:\Users\23002\AppData\Local\Programs\Ollama\ollama.exe'

sys.path.insert(0, TOOLS113)
import common113 as C      # noqa: E402
import train30 as T        # noqa: E402

#: 第189轮b 改过口癖频次的 6 人（顺序无关）
TARGETS = ['lancer', 'ot_kidd', 'ot_muffet', 'ot_sans', 'ut_monster_kid', 'ut_sans']

#: ★ 复测轮数取 **24** 而不是 48：本机实测 ~40~75s/轮，48 轮 × 6 人 ≈ 4.5 小时，
#: 会顶到夜里那个 10 小时预算的上限。判据是**比率**，基线（48 轮）与复测（24 轮）
#: 同为比率、可直接比；24 轮足以把"每轮必念(100%)"与"偶尔(~25%)"分开
#: （二项 95% 区间约 ±18%）。同理 `rate_of` 里按这个数过记录。
TURNS = 24


def ensure_ollama():
    try:
        urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=3).read()
        return True
    except Exception:  # noqa: BLE001
        pass
    if not os.path.isfile(OLLAMA):
        print('[失败] 找不到 ollama.exe')
        return False
    os.makedirs(OUT, exist_ok=True)
    import subprocess
    fh = open(os.path.join(OUT, 'ollama_serve.log'), 'ab')
    flags = (0x00000008 | 0x00000200) if os.name == 'nt' else 0
    subprocess.Popen([OLLAMA, 'serve'], stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
                     creationflags=flags, close_fds=True)
    for _ in range(60):
        time.sleep(2)
        try:
            urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=3).read()
            print('ollama 已就绪')
            return True
        except Exception:  # noqa: BLE001
            continue
    print('[失败] ollama 120s 内没起来')
    return False


def markers_of(fid):
    card = C.load_json(os.path.join(C.TRAIN_DIR, 'cards', fid + '.json'), {}) or {}
    return card.get('voice_markers') or []


def rate_of(rawdir, fid, markers, turns_n=48):
    """返回 (n_turns, {marker: 命中轮数}, 任一中标轮数, 平均条数/轮)。"""
    p = os.path.join(rawdir, fid + '.jsonl')
    if not os.path.isfile(p):
        return None
    rec = None
    for line in io.open(p, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(r, dict) and r.get('turns_n') == turns_n:
            rec = r
    if not rec:
        return None
    turns = [t.get('final') or '' for t in (rec.get('turns') or [])]
    turns = [x for x in turns if x.strip()]
    if not turns:
        return None
    per = {}
    for m in markers:
        per[m] = sum(1 for x in turns if m in x)
    any_hit = sum(1 for x in turns if any(m in x for m in markers))
    total = sum(per.values())
    return {'turns': len(turns), 'per_marker': per, 'any_hits': any_hit,
            'any_rate': round(any_hit * 100.0 / len(turns), 1),
            'avg_per_turn': round(float(total) / len(turns), 2)}


def fmt(d):
    if not d:
        return '（缺）'
    inner = ' '.join('%s=%d' % (k, v) for k, v in d['per_marker'].items())
    return '任一 %d/%d=%s%% · 均 %s 次/轮 · %s' % (
        d['any_hits'], d['turns'], d['any_rate'], d['avg_per_turn'], inner)


def main():
    argv = sys.argv[1:]
    check_only = '--check' in argv
    print('=' * 78)
    print('口癖复测：第189轮b 改过的 6 人')
    base = {}
    for fid in TARGETS:
        m = markers_of(fid)
        b = rate_of(C.RAW30, fid, m)
        base[fid] = b
        print('  %-15s %s' % (fid, fmt(b)))
    if any(v is None for v in base.values()):
        print('[停手] 有角色缺 48 轮基线语料')
        return 2
    if check_only:
        print('（--check：只看基线，不训练）')
        return 0

    os.makedirs(OUT, exist_ok=True)
    rawdir = os.path.join(OUT, 'raw')
    os.makedirs(rawdir, exist_ok=True)
    T.RAW30 = rawdir
    T.TR30 = os.path.join(OUT, 'tr')
    if not ensure_ollama():
        return 3

    print('\n---------- 重训 %d 人 × %d 轮 ----------' % (len(TARGETS), TURNS))
    T.main(['--only', ','.join(TARGETS), '--turns', str(TURNS), '--force',
            '--sleep', '3', '--pause-every', '3', '--pause-sec', '20',
            '--log', os.path.join(OUT, 'train.log')])

    summary = {'baseline': base, 'after': {}}
    print('\n---------- 对照 ----------')
    for fid in TARGETS:
        m = markers_of(fid)
        a = rate_of(rawdir, fid, m, TURNS)
        summary['after'][fid] = a
        print('  %-15s 改前 %s' % (fid, fmt(base[fid])))
        print('  %-15s 改后 %s' % ('', fmt(a)))
    with io.open(os.path.join(OUT, 'summary.json'), 'w', encoding='utf-8',
                 newline='\n') as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    print('\n汇总 → %s' % os.path.join(OUT, 'summary.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
