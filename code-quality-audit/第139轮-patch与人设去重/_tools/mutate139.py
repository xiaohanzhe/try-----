# -*- coding: utf-8 -*-
"""第139轮 · `check139` 的**破坏性负控制**：改坏了必须报红。

## 为什么非要有这个

第85/129/136 轮的教训是同一条：**判据自己也会恒真**。
"删掉了一句重复"这种改动，最容易写成"看起来在守、其实什么都没守"——
比如判 `u'两三句' not in patch`，但 `patch` 取成了空串，那条判据就永远绿。

所以这里逐个把 `check139` 要守的东西**弄坏**，要求它**至少报一条 FAIL**，
再恢复回去要求**重新全绿**。两半都要成立：
  - 只有"弄坏会红" ⇒ 可能是"任何改动都红"的暴脾气；
  - 只有"恢复会绿" ⇒ 证明不了它抓得到。

## 三条纪律（第113/125 轮踩过的坑）

1. **备份在内存里**，一字节不落盘 —— 这个脚本不碰临时盘、不碰 `D:`；
   中途崩了由 `finally` 还原，还原后再独立跑一次 `check139` 复核。
2. **负控制的输入必须真落进被测分支**：每个用例都断言 `old` 在文件里
   （替换失败 ⇒ 用例本身无效，直接判这个脚本自己失败）。
3. **不做"整文件重写"**：只替换那一处子串，其余字节原样 —— 否则"红了"
   可能来自格式破坏而不是判据命中。
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TRAIN = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', '_training')
EV = os.path.join(ROUND, '_evidence')
CHECK = os.path.join(HERE, 'check139.py')
PY = sys.executable

LEAD_LINE = u'一次最多两三句，短一点，像随口说出来的。 '

# (名字, 文件, 原串, 换成, 期望红的判据名里的关键字)
CASES = [
    (u'M1 把 ① 塞回 `patches["ralsei"]`',
     os.path.join(TRAIN, '_index.json'),
     u'"ralsei": "只认得原作里真有的名字',
     u'"ralsei": "%s只认得原作里真有的名字' % LEAD_LINE,
     u'A1', False),
    # ★ M2 要改 `_index.json` 里的**两处**（cards 段 + patches 段），否则只会撞 A2/A3
    #   （"两份副本不一致"），而不是 A6（"实测例没了"）。这条是第一次跑出来的：
    #   原先只改卡片文件，撞的是 A3，A6 一点没动 —— 期望的判据名写错了，不是判据漏了。
    (u'M2 从 patch 里抹掉实测例「凯斯恩」（两处副本一起改）',
     os.path.join(TRAIN, '_index.json'),
     u'「凯斯恩」',
     u'「某某」',
     u'A6', True),
    (u'M2b 只改卡片文件、不动 `_index.json`（两份副本漂移）',
     os.path.join(TRAIN, 'cards', 'ralsei.json'),
     u'「凯斯恩」',
     u'「某某」',
     u'A3', False),
    (u'M3 动一下别人的 patch（berdly）',
     os.path.join(TRAIN, '_index.json'),
     u'"berdly": "别提作品名',
     u'"berdly": "（测）别提作品名',
     u'D2', False),
    (u'M4 从 A/B 证据里删掉一条',
     os.path.join(EV, 'ab139.jsonl'),
     None,
     None,
     u'F0', False),
    (u'M5 只改汇总、不改数据（over3 14 → 15）',
     os.path.join(EV, 'ab139_summary.json'),
     u'"over3": 14',
     u'"over3": 15',
     u'F2', False),
]


def run_check():
    """跑一次 check139，返回 (returncode, [FAIL 行])。"""
    p = subprocess.run([PY, CHECK], cwd=ROOT, capture_output=True)
    out = p.stdout.decode('utf-8', 'replace')
    fails = [ln.strip() for ln in out.splitlines() if u'[FAIL]' in ln]
    return p.returncode, fails


def read(p):
    return io.open(p, 'rb').read()


def write(p, b):
    with io.open(p, 'wb') as f:
        f.write(b)


def main():
    bad = 0
    rc, fails = run_check()
    ok0 = (rc == 0 and not fails)
    print(u'[基线] check139 全绿 = %s（rc=%d，FAIL=%d）' % (ok0, rc, len(fails)))
    if not ok0:
        print(u'[ABORT] 基线都不是绿的，负控制没有意义')
        return 2

    for name, path, old, new, key, all_ in CASES:
        raw = read(path)                      # ① 备份在内存
        txt = raw.decode('utf-8')
        try:
            if old is None:                   # M4：删掉最后一行
                lines = [l for l in txt.split('\n') if l.strip()]
                if len(lines) < 2:
                    raise AssertionError(u'证据文件行数不足，用例无效')
                mut = '\n'.join(lines[:-1]) + '\n'
                hit = True
            else:
                hit = old in txt
                if not hit:
                    raise AssertionError(u'原串不在文件里，用例无效：%r' % old)
                mut = txt.replace(old, new) if all_ else txt.replace(old, new, 1)
            if mut == txt:
                raise AssertionError(u'替换后没有变化，用例无效')
            write(path, mut.encode('utf-8'))
            rc2, fails2 = run_check()
            caught = [f for f in fails2 if key in f]
            good = (rc2 != 0 and bool(caught))
            print(u'%s %s  ⇒ rc=%d FAIL=%d 命中 %s：%s'
                  % (u'[PASS]' if good else u'[FAIL]', name, rc2, len(fails2),
                     key, (caught[0][:60] if caught else u'<没抓到>')))
            if not good:
                bad += 1
        finally:
            write(path, raw)                  # ② 无论如何先还原
        rc3, fails3 = run_check()
        restored = (rc3 == 0 and not fails3)
        print(u'%s %s —— 还原后重新全绿 = %s'
              % (u'[PASS]' if restored else u'[FAIL]', name, restored))
        if not restored:
            bad += 1

    print(u'')
    print(u'=' * 78)
    print(u'mutate139：%d 个用例，%d 处不合格' % (len(CASES), bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
