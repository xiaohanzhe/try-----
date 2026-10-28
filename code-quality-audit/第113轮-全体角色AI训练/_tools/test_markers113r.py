# -*- coding: utf-8 -*-
u"""第113轮r · `fix_markers113r.py` 的自测（9 条，全在临时目录里跑，不碰真卡）。

为什么单独测：
  · `voice_markers` 是**评测口径**，改错不会报错，只会让报告里的数字悄悄变样；
  · 手术用 `raw_decode` 而不是"第一个 `]`"—— 因为 `[……]` 这种登记项**自身就含 `]`**，
    写错的话会把数组截断在字符串中间，产出一个**看似合法、实则内容被切**的 JSON；
  · 卡里 CRLF/LF 两种 EOL 都有，写回时若被统一，`git diff` 会整份文件变红（掩盖真改动）。

★ 每条都在**真文件副本**上跑，不是断言"我以为会怎样"。
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fix_markers113r as F

_REAL = F.CARDS
_n = _ok = 0


def check(name, cond, detail=''):
    global _n, _ok
    _n += 1
    if cond:
        _ok += 1
        print('[PASS] %s    %s' % (name, detail))
    else:
        print('[FAIL] %s    %s' % (name, detail))


def main():
    tmp = tempfile.mkdtemp(prefix='markers113r_')
    try:
        # 只复制要动的 10 张卡（真文件，不是造的）
        for cid in F.DROP:
            src = os.path.join(_REAL, cid + '.json')
            assert os.path.exists(src), src
            shutil.copy2(src, os.path.join(tmp, cid + '.json'))
        F.CARDS = tmp

        # ---- A 预览不写盘（默认 --dry 的语义）
        before = {c: io.open(os.path.join(tmp, c + '.json'), 'rb').read() for c in F.DROP}
        for cid in F.DROP:
            F.patch_one(os.path.join(tmp, cid + '.json'), F.DROP[cid], apply=False)
        after = {c: io.open(os.path.join(tmp, c + '.json'), 'rb').read() for c in F.DROP}
        check('A 预览模式一个字节都不改', before == after,
              '变了的：%s' % ([c for c in before if before[c] != after[c]] or '无'))

        # ---- B ★ 数组之外的字节完全不动 + 数组内容恰好是预期
        bad_out, bad_len = [], []
        for cid in F.DROP:
            p = os.path.join(tmp, cid + '.json')
            raw = io.open(p, 'r', encoding='utf-8', newline='').read()
            F.patch_one(p, F.DROP[cid], apply=True)
            out = io.open(p, 'r', encoding='utf-8', newline='').read()
            s0, e0 = F._span_of_markers(raw)
            s1, e1 = F._span_of_markers(out)
            if raw[:s0] != out[:s1] or raw[e0:] != out[e1:]:
                bad_out.append(cid)
            want = [m for m in json.loads(raw)['voice_markers'] if m not in F.DROP[cid]]
            if json.loads(out)['voice_markers'] != want:
                bad_len.append(cid)
        check('B ★ 只换数组那一段，其余字节逐字节相同（10 张全过）', not bad_out,
              '动了别处的：%s' % (bad_out or '无'))
        check('B2 回读的名单恰好等于「原名单减去待删项」', not bad_len,
              '不一致的：%s' % (bad_len or '无'))

        # ---- C EOL 逐文件保留（kris=CRLF / mike=LF 是实测过的两种）
        eol_bad = []
        for cid in F.DROP:
            b = io.open(os.path.join(tmp, cid + '.json'), 'rb').read()
            crlf, lf = b.count(b'\r\n'), b.count(b'\n') - b.count(b'\r\n')
            if (crlf > 0) != (before[cid].count(b'\r\n') > 0) or (lf > 0) != (
                    before[cid].count(b'\n') - before[cid].count(b'\r\n') > 0):
                eol_bad.append(cid)
        check('C 写回后 EOL 种类和写前一致（CRLF 的还 CRLF，LF 的还 LF）', not eol_bad,
              '混了的：%s（kris=%s mike=%s）' % (eol_bad or '无',
                                                'CRLF' if before['kris'].count(b'\r\n') else 'LF',
                                                'CRLF' if before['mike'].count(b'\r\n') else 'LF'))

        # ---- D ★★ 陷阱复现：`[……]` 自身含 `]`，"第一个 ]" 会切在字符串中间
        # ★ 必须用 **B 组改之前** 的原始字节：B 已经把 `[……]` 删掉了，读现盘
        #   会拿到一个不含内嵌 `]` 的数组 ⇒ 陷阱根本不复现（我第一次就这么错了，
        #   报了个假红）。夹具不保真 = 报假问题。
        raw = before['os_rowbot'].decode('utf-8')
        assert '[……]' in raw, '夹具不保真：原始 os_rowbot 里没有 [……]'
        j = raw.index('[', raw.find('"voice_markers"'))
        naive = raw.index(']', j)                    # 天真写法
        s, e = F._span_of_markers(raw)               # 真写法
        check('D ★★ `[……]` 里的 `]` 确实早于数组真结尾（证明这个陷阱真实存在）',
              naive < e - 1, '天真截断位置=%d 真结尾=%d' % (naive, e - 1))
        check('D2 真写法取到的区间能被 json 完整解析（天真写法不能）',
              isinstance(json.loads(raw[s:e]), list) and
              _raises(lambda: json.loads(raw[j:naive + 1])),
              '区间长度=%d' % (e - s))

        # ---- E 负控制：要删的项不在名单里 ⇒ **必须炸**，不许静默跳过
        p = os.path.join(tmp, 'mike.json')
        check('E ★ 负控制：删一个不存在的登记项必须抛断言（不是静默"改完了"）',
              _raises(lambda: F.patch_one(p, ['这个口癖根本不存在'], apply=True)),
              '已抛 AssertionError')

        # ---- F ★ 负控制：重复键必须被读出来（json 默认取最后一个 ⇒ 静默错值）
        p2 = os.path.join(tmp, 'dup.json')
        io.open(p2, 'w', encoding='utf-8', newline='').write(
            '{"voice_markers": ["a"], "voice_markers": ["b"]}')
        check('F ★ 负控制：卡里有重复键时必须报错（否则 json 静默取最后一个）',
              _raises(lambda: F.patch_one(p2, ['a'], apply=True)), '已抛 ValueError')

        # ---- G 幂等性：改完再改一次 ⇒ 待删项已不在 ⇒ 抛断言（说明不会二次破坏）
        check('G 对已修过的卡再跑一次会拒绝（待删项已不存在），不会二次破坏',
              _raises(lambda: F.patch_one(os.path.join(tmp, 'ut_gaster.json'),
                                          F.DROP['ut_gaster'], apply=True)),
              'ut_gaster 已修过')

        # ---- H 真卡没被这场测试碰到（测试用副本，真仓库零改动）
        real_kris = io.open(os.path.join(_REAL, 'kris.json'), 'r', encoding='utf-8',
                           newline='').read()
        check('H 测试全程用的副本 ⇒ 真卡 `kris.json` 原样未动',
              json.loads(real_kris)['voice_markers'] ==
              json.loads(before['kris'].decode('utf-8'))['voice_markers'],
              '真卡名单=%s' % json.dumps(json.loads(real_kris)['voice_markers'],
                                        ensure_ascii=False)[:60])
    finally:
        F.CARDS = _REAL
        shutil.rmtree(tmp, ignore_errors=True)

    print('\n' + '=' * 60)
    print('合计：PASS=%d FAIL=%d' % (_ok, _n - _ok))
    print('=' * 60)
    return 0 if _ok == _n else 1


def _raises(fn):
    try:
        fn()
    except Exception:
        return True
    return False


if __name__ == '__main__':
    sys.exit(main())
