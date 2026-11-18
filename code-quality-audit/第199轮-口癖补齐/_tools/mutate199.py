# -*- coding: utf-8 -*-
"""第199轮 · 变异测试（判据能红吗）

规矩（第198轮定下来的，照抄不改）
  · 每次只破坏**一个**性质，红数必须 **>0 且 < 总数**（全红＝判据在互相兜，等于没测）
  · 必带一条**无害变异**，它必须红 **0**
  · 改完**按字节还原**并核 sha1 —— 一个字节都不能差
  · 锚点按**文件自己的行尾**组装（本项目源码是 CRLF）

★ 这一轮的"被测物"有两块：
  ① 76 份人设的**落盘结果**（正例条数 / 尾块 / 英文台词 / 行数）
  ② `apply199.py` 的**施工表**（EDITS / EX_POOL / SKIP_EX）
  两块都要能被判据证伪，否则判据只是"读了一遍文件"。
"""
from __future__ import print_function

import hashlib
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
CHECK = os.path.join(HERE, 'check199.py')
APPLY = os.path.join(HERE, 'apply199.py')
PY = r'C:\Python311\python.exe'

SUM_RE = re.compile(r'(\d+)\s+PASS\s*/\s*(\d+)\s+FAIL')

_p = {'n': 0, 'ok': 0}


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def wr(p, b):
    tmp = p + '.mut.tmp'
    with open(tmp, 'wb') as f:
        f.write(b)
    os.replace(tmp, p)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run_check():
    r = subprocess.run([PY, CHECK], capture_output=True)
    out = (r.stdout or b'').decode('utf-8', 'replace')
    m = SUM_RE.search(out)
    if not m:
        return None, out
    return (int(m.group(1)), int(m.group(2))), out


def eol(b):
    return b'\r\n' if b'\r\n' in b else b'\n'


# ---------------------------------------------------------------- 变异定义
def m_drop_ex():
    """删掉一份人设里的 2 条正例 ⇒ 只剩 63 份是"2 条"，B5 必须红。

    ★ 两版都错过，记在这里：
      ① 第一版按"正例原文"找锚点 ⇒ 锚点没找到（正例是按哈希轮换取 2 条的，
         `ut_sans` 拿到的不是池里头两条）；
      ② 第二版取"全文最后两条 `· ` 行" ⇒ 删到的是【示例反应】，行数 −2 但
         **基线也是改前值**，delta 正好回到 0 ⇒ 一个判据都没红。
         这已经是**无害变异**了，不是"判据抓不到"。
      正解：定位【语言风格】节，删该节**最后两条** `· ` 行 —— 正例就追在节末。
    """
    p = os.path.join(PER, 'ut_sans.txt')
    b = rd(p)
    t = b.decode('utf-8')
    parts = t.split(u'\r\n')
    # 找【语言风格…】标题行 与 下一个【 标题行
    a = next(i for i, ln in enumerate(parts) if ln.strip().startswith(u'【语言风格'))
    z = next(i for i in range(a + 1, len(parts)) if parts[i].strip().startswith(u'【'))
    idx = [i for i in range(a + 1, z) if parts[i].startswith(u'· ')]
    if len(idx) < 3:
        raise RuntimeError('语言风格节里 · 行太少：%d' % len(idx))
    for i in sorted(idx[-2:], reverse=True):
        del parts[i]
    return p, b, u'\r\n'.join(parts).encode('utf-8')


def m_add_ex_to_skipped():
    """给排除名单里的 kris 加 1 条正例 ⇒ B5b 必须红（"0 条的正是排除名单"）。"""
    p = os.path.join(PER, 'kris.txt')
    b = rd(p)
    t = b.decode('utf-8')
    ex = u'\r\n· 平常接话的样子：“嗯，我想想啊。”“哦，对，就是那样。”'
    i = t.find(u'\r\n\r\n' + u'【')
    with open(APPLY, 'rb') as f:
        src = f.read().decode('utf-8')
    pool = re.search(r"EX_POOL = \[\n\s+u'([^']+)'", src)
    if not pool:
        raise RuntimeError('取不到正例句')
    ex = u'\r\n' + pool.group(1)
    j = t.find(u'\r\n' + u'【本项目补充')
    k = t.rfind(u'\r\n\r\n', 0, j) + 2
    return p, b, (t[:k] + ex + t[k:]).encode('utf-8')


def m_double_period():
    """塞一个「。。」⇒ B4 必须红。"""
    p = os.path.join(PER, 'noelle.txt')
    b = rd(p)
    t = b.decode('utf-8')
    old = u'· 你经常道歉。'
    if t.count(old) != 1:
        raise RuntimeError('锚点 %d 次' % t.count(old))
    return p, b, t.replace(old, u'· 你经常道歉。。', 1).encode('utf-8')


def m_touch_tail():
    """动尾块一个字 ⇒ B1/B2 必须红（这正是 check115 C2c 的命门）。"""
    p = os.path.join(PER, 'toriel.txt')
    b = rd(p)
    key = u'桌面上'.encode('utf-8')
    i = b.rfind(key)
    if i < 0:
        raise RuntimeError('尾块锚点没找到')
    nb = b[:i] + u'桌面上。'.encode('utf-8') + b[i + len(key):]
    return p, b, nb


def m_drop_english():
    """删掉一行英文台词 ⇒ C1 必须红。"""
    p = os.path.join(PER, 'ut_papyrus.txt')
    b = rd(p)
    t = b.decode('utf-8')
    old = u'“THAT\'S AMAZING！”'
    if old not in t:
        raise RuntimeError('英文锚点没找到')
    return p, b, t.replace(old, u'', 1).encode('utf-8')


def m_one_line():
    """只加 1 行而不是 2 行 ⇒ B3（行数变化）与 B5 必须红。"""
    p = os.path.join(PER, 'lancer.txt')
    b = rd(p)
    t = b.decode('utf-8')
    j = t.find(u'\r\n' + u'【本项目补充')
    k = t.rfind(u'\r\n\r\n', 0, j) + 2
    return p, b, (t[:k] + u'\r\n· 这是一行只加了一半的样例。' + t[k:]).encode('utf-8')


def _mut_source(path, old, new):
    """改源码。★ 锚点**不要求唯一**：这套正文里 ut/ot 两版 Papyrus 的新措辞一模一样
    （两处同文），第一版写"必须命中 1 次"⇒ 直接构造失败。改 1 处就够破坏了。"""
    b = rd(path)
    t = b.decode('utf-8')
    if t.count(old) < 1:
        raise RuntimeError('源码锚点没找到：%s' % (old[:40],))
    return path, b, t.replace(old, new, 1).encode('utf-8')


def m_boost_in_new():
    """把一处新措辞换成带强化语的说法 ⇒ A3 必须红。"""
    return _mut_source(
        APPLY,
        u'u\'你说话带劲儿，一句话里常常带感叹号，但不是每句都要喊出来。\'',
        u'u\'你的句子总是以感叹号结尾，每句都要喊出来。\'')


def m_ex_pool_quirk():
    """正例池塞一条带口癖的句子 ⇒ A4 必须红（等于换个口癖加进去）。"""
    return _mut_source(
        APPLY,
        u"    u'· 平常接话的样子：“嗯，我想想啊。”“哦，对，就是那样。”',",
        u"    u'· 平常接话的样子：“嗯，我想想啊。”“哦，对，就是那样。”',\n"
        u"    u'· “Yo!”',")


def m_edits_count():
    """施工表少一条 ⇒ A1 必须红（证明"15 处"这个数是判据在看，不是注释）。

    ★ 第一版只把**首行**注释掉 ⇒ 那条 EDITS 是**跨三行**的元组，注释首行后
      剩下的两个字符串实参悬空，`apply199` 直接 SyntaxError，判据"跑不起来"
      不等于"抓到"。必须整条替换掉。
    """
    return _mut_source(
        APPLY,
        u"    ('hy_mooch.txt', 'head',\n"
        u"     u'\u4f60\u7684\u8bf4\u8bdd\u65b9\u5f0f\u7b80\u77ed\u3001\u76f4\u63a5\u3001\u5b69\u5b50\u6c14\uff0c"
        u"\u603b\u662f\u56f4\u7ed5\u7740\u94b1\u548c\u4e1c\u897f\u3002',\n"
        u"     u'\u4f60\u7684\u8bf4\u8bdd\u65b9\u5f0f\u7b80\u77ed\u3001\u76f4\u63a5\u3001\u5b69\u5b50\u6c14\uff0c"
        u"\u4e00\u5f00\u53e3\u5e38\u5e38\u662f\u94b1\u548c\u4e1c\u897f\uff0c\u4f46\u4e0d\u662f\u6bcf\u53e5\u90fd\u62d0\u5230\u90a3\u513f\u3002'),",
        u"    # m9: 整条剪掉")


def m_harmless():
    """无害变异：把一处「你」改成「您」，不触碰任何判据 ⇒ 必须红 0。"""
    p = os.path.join(PER, 'susie.txt')
    b = rd(p)
    t = b.decode('utf-8')
    old = u'· 你说话'
    cand = [i for i in range(len(t)) if t.startswith(old, i)]
    if not cand:
        raise RuntimeError('无害变异锚点没找到')
    i = cand[0]
    return p, b, (t[:i + 2] + u'您' + t[i + 3:]).encode('utf-8')


MUTANTS = [
    ('M1 删掉一份人设的 2 条正例', m_drop_ex),
    ('M2 给排除名单里的人设加正例', m_add_ex_to_skipped),
    ('M3 塞一个「。。」', m_double_period),
    ('M4 动尾块一个字节', m_touch_tail),
    ('M5 删掉一行英文台词', m_drop_english),
    ('M6 只加 1 行而不是 2 行', m_one_line),
    ('M7 新措辞里塞回强化语', m_boost_in_new),
    ('M8 正例池塞一条口癖', m_ex_pool_quirk),
    ('M9 施工表少一条', m_edits_count),
    ('M10 无害变异（你→您）', m_harmless),
]


def main():
    base, out = run_check()
    if base is None:
        print('[失败] 基线跑不起来：\n%s' % out[-800:])
        return 2
    tot = base[0] + base[1]
    print('基线：PASS=%d FAIL=%d（总数 %d）' % (base[0], base[1], tot))
    if base[1] != 0:
        print('[失败] 基线不是全绿，先修基线')
        return 2

    bad = []
    for name, fn in MUTANTS:
        try:
            p, orig, mut = fn()
        except Exception as e:      # noqa: BLE001
            print('[失败] %-28s 变异构造失败：%s' % (name, e))
            bad.append(name)
            continue
        h0 = sha(orig)
        wr(p, mut)
        try:
            got, _o = run_check()
        finally:
            wr(p, orig)
        if got is None:
            print('[失败] %-28s 变异后判据跑不起来' % name)
            bad.append(name)
            continue
        if sha(rd(p)) != h0:
            print('[严重] %-28s 还原后 sha 不一致！' % name)
            bad.append(name)
            continue
        nf = got[1]
        good = (nf == 0) if '无害' in name else (0 < nf < tot)
        _p['n'] += 1
        _p['ok'] += 1 if good else 0
        if not good:
            bad.append(name)
        print('%s %-28s FAIL %d→%d  红数=%d  %s' % (
            '[ok]' if good else '[NG]', name, base[1], nf, nf,
            '（无害变异应红 0）' if '无害' in name else ''))

    print('\n=== 结论 ===')
    print('变异 %d/%d 达到预期' % (_p['ok'], _p['n']))
    if bad:
        print('未达标：%s' % bad)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
