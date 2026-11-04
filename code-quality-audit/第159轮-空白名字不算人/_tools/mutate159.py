# -*- coding: utf-8 -*-
u"""第159轮负控制：逐条破坏产品，断言**恰好**指定的判据变红，再字节级还原。

用法：
    python mutate159.py            # 按 EXPECT 断言
    python mutate159.py --dry      # 只打印每处破坏实际红了哪些（用于写 EXPECT）

★ 纪律（第150~158轮一路踩出来的）：
  · 一处破坏 = 一个**单一**改动；
  · 期望写窄是常态 ⇒ **实得比期望多**不一定是判据坏，先看是不是"同一条闸的多个观测面"；
  · 还原必须**字节级**（sha1 比对）；
  · 收口（Z1）必须再跑一次全绿；Z2 指纹必须与开工前一致；
  · ★ 破坏不许把套件炸掉：每处都保持语法完整、返回值类型不变。
  · ★★ 第160轮：`expect` 写成**空 tuple** 表示**无害变异** —— 断言的语义反过来，
    考的是"语义等价的改写会不会被判据误伤"（假红）。负控制不只问"破坏会不会红"。
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
ERRAND = os.path.join(ROOT, 'ralsei_pet', 'modules', 'npc_errand.py')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CHECK = os.path.join(HERE, 'check159.py')
PY = sys.executable


def _read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _write(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


def _c(s):
    return s.replace('\r\n', '\n').replace('\n', '\r\n')


def _sha(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------- 破坏清单
# (名字, 说明, 目标文件, old, new, 期望变红的判据前缀集合)
MUTATIONS = [
    ('M1', u'宿主层**删掉** `npc_id` 闸（脏参数照进）', MAIN,
     u"""        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1anpc_id \u4e3a\u7a7a\u3001\u5168\u662f\u7a7a\u767d\u3001\u6216\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', npc_id)
            return None""",
     u"""        pass""",
     # 实得：删闸后脏参数一路进到机制层 ⇒ 只有 A5（宿主层不写记忆/不问路）与两道
     #   AST 判据（B4 闸不在、B5 闸不在门控前）必红；A13 走机制层自己的闸，仍然挡得住。
     ('A5', 'B4', 'B5', 'B8')),

    ('M2', u'机制层 `assign` 的 id 判据**只挡全空白**（漏掉首尾空白）', ERRAND,
     u"""        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():
            return None""",
     u"""        if not isinstance(npc_id, str) or not npc_id.strip():
            return None""",
     # 实得：机制层只挡全空白 ⇒ A13（`' ralsei '` 被机制层收下）与 B1（判据里没有
     #   `x != x.strip()` 那一半）红；宿主层的闸还在，A 段绝大多数仍然绿。
     ('A13', 'B1', 'B8')),

    ('M3', u'`Errand.from_dict` 退回"只挡空串"（老档幽灵复活）', ERRAND,
     u"""            if not isinstance(npc_id, str) or not npc_id \\
                    or npc_id != npc_id.strip():
                return None""",
     u"""            if not isinstance(npc_id, str) or not npc_id:
                return None""",
     # 实得：from_dict 放开首尾空白 ⇒ A10（机制层双闸）、B3（from_dict 那道闸的 AST 判据）
     #   直接红；A8（老档幽灵丢不丢）也跟着红 —— 幽灵条目真的被读回来了。
     ('A10', 'A8', 'B3', 'B8')),

    ('M4', u'宿主层判据挪到**门控之后**（脏参数先问路）', MAIN,
     u"""        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1anpc_id \u4e3a\u7a7a\u3001\u5168\u662f\u7a7a\u767d\u3001\u6216\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', npc_id)
            return None""",
     u"""        _ok0, _why0 = self._npc_errand_gate(npc_id, dest_scene)
        if not _ok0:
            return None
        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1anpc_id \u4e3a\u7a7a\u3001\u5168\u662f\u7a7a\u767d\u3001\u6216\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', npc_id)
            return None""",
     # 实得：闸还在（B4 绿），但**顺序**反了 ⇒ 脏参数先被问了路（A5）、
     #   B5 那两条（`len(_gate_calls)==1` 与"判据在门控之前"）同时咬住。
     ('A5', 'B5')),

    ('M5', u'空白事由**不归一**（原样存 `\'   \'`）', ERRAND,
     u"""        elif not what.strip():
            # \u2605 \u7eaf\u7a7a\u767d\u4e8b\u7531 = \u201c\u6ca1\u8bf4\u5e72\u4ec0\u4e48\u201d \u21d2 \u5f52\u4e00\u6210 `''`\uff08\u754c\u9762\u663e\u793a\u201c\u8d70\u4e00\u8d9f\u201d\uff09\u3002
            #   \u539f\u6837\u5b58 `'   '` \u4f1a\u8ba9 prompt / \u8bb0\u5fc6\u91cc\u51fa\u73b0\u201c\u529e\u300c   \u300d\u201d\u8fd9\u79cd\u7a7a\u58f3\u3002
            what = ''""",
     u"""        elif False:
            what = ''""",
     ('A4', 'B7')),

    ('M6', u'改成**静默改写**（`npc_id = npc_id.strip()`）而不是拒', MAIN,
     u"""        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():""",
     u"""        if isinstance(npc_id, str):
            npc_id = npc_id.strip()
        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():""",
     ('A2', 'B6')),

    ('M7', u'**一刀切**：任何非空 str 都拒（把正常路也堵死）', MAIN,
     u"""        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1anpc_id \u4e3a\u7a7a\u3001\u5168\u662f\u7a7a\u767d\u3001\u6216\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', npc_id)
            return None""",
     u"""        if True:
            return None""",
     # 实得：一刀切把宿主层的**正常路**也堵死 ⇒ A11（正常派活）/ A2（`'ralsei'` 也
     #   派不成）/ A4（事由归一那一步走不到）红；A12 直接调机制层，不受影响。
     #   B4（闸被换成 `if True`，AST 里找不到 strip 判据）、B5（只剩一道前置判据）红。
     ('A11', 'A2', 'A4', 'B4', 'B5', 'B8')),

    ('M8', u'宿主层**删掉** `dest_scene` 闸', MAIN,
     u"""        if not isinstance(dest_scene, str) or not dest_scene \\
                or dest_scene != dest_scene.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1a\u76ee\u7684\u5730\u4e3a\u7a7a\u3001\u5168\u662f\u7a7a\u767d\u3001\u6216\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', dest_scene)
            return None""",
     u"""        pass""",
     # 实得：A3 仍然绿 —— 机制层 `assign` 自己也挡 `dest_scene`（宿主删除暴露不了，
     #   说明这道闸是双层的）；只剩两条 AST 判据咬住"宿主层那道闸没了"。
     ('B4', 'B5', 'B8')),

    # ★★★ 第160轮新增：**无害变异**（期望空 = 一条都不许红）。
    #   判据绑写法时，这段**语义完全等价**的改写会被判成破坏（假红，`probe160 --before` 实证）。
    #   ⇒ 负控制不只问"破坏会不会红"，还要问"**没破坏时会不会假红**"。
    ('M9', u'（**无害**）宿主闸拆成两个连续的 `if` —— 语义完全等价，不该红任何一条', MAIN,
     u"""        if not isinstance(npc_id, str) or not npc_id \\
                or npc_id != npc_id.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1anpc_id \u4e3a\u7a7a\u3001\u5168\u662f\u7a7a\u767d\u3001\u6216\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', npc_id)
            return None""",
     u"""        if not isinstance(npc_id, str) or not npc_id:
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1anpc_id \u4e3a\u7a7a\uff08%r\uff09', npc_id)
            return None
        if npc_id != npc_id.strip():
            _log.info('\u6d3e\u6d3b\u88ab\u62d2\uff1a\u9996\u5c3e\u5e26\u7a7a\u767d\uff08%r\uff09', npc_id)
            return None""",
     ()),
]


def run_check():
    p = subprocess.Popen([PY, CHECK], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode('utf-8', 'replace')
    reds = []
    for line in out.splitlines():
        if line.startswith('[FAIL] '):
            reds.append(line[7:].split()[0])
    return p.returncode, sorted(set(reds)), out


def main():
    dry = '--dry' in sys.argv
    base = {'main': _read(MAIN), 'errand': _read(ERRAND)}
    base_sha = dict((k, _sha(v)) for k, v in base.items())
    print(u'基线 sha1: main=%s errand=%s'
          % (base_sha['main'][:12], base_sha['errand'][:12]))
    n_bad = 0
    for name, desc, target, old, new, expect in MUTATIONS:
        key = 'main' if target == MAIN else 'errand'
        o, n = _c(old), _c(new)
        body = base[key]
        if body.count(o) != 1:
            print(u'[FAIL] %s 锚点出现 %d 次：%s' % (name, body.count(o), desc))
            n_bad += 1
            continue
        _write(target, body.replace(o, n))
        try:
            rc, reds, out = run_check()
        finally:
            _write(target, base[key])
            if _sha(_read(target)) != base_sha[key]:
                print(u'[FAIL] %s 还原失败（sha1 不一致）' % (name,))
                return 1
        if dry:
            print(u'%s %s ⇒ 红：%s（rc=%d）'
                  % (name, desc, u' '.join(reds) or u'（无！）', rc))
            continue
        if not expect:
            # ★ 第160轮：**无害变异** —— 期望是"一条都不红"，判据反过来考"会不会假红"。
            ok = (rc == 0) and not reds
            if not ok:
                n_bad += 1
            print(u'%s %s %s ⇒ 红：%s%s'
                  % (u'[PASS]' if ok else u'[FAIL]', name, desc,
                     u' '.join(reds) or u'无',
                     u'' if ok else u'    （无害变异不该红 —— 判据绑写法了）'))
            continue
        ok = (rc != 0) and reds == sorted(expect)
        if not ok:
            n_bad += 1
        print(u'%s %s %s ⇒ 红：%s%s'
              % (u'[PASS]' if ok else u'[FAIL]', name, desc,
                 u' '.join(reds) or u'（无！）',
                 u'' if ok else (u'    期望：%s' % (u' '.join(sorted(expect)),))))
    if dry:
        print(u'')
        print(u'mutate159（dry）：以上为**实得**，用于写 EXPECT。')
        return 0

    # ---- Z1 收口：还原之后必须全绿 ----
    rc, reds, out = run_check()
    z1 = (rc == 0) and not reds
    if not z1:
        n_bad += 1
    print(u'%s Z1 收口：全部还原后 check159 必须**全绿**（红=%s）'
          % (u'[PASS]' if z1 else u'[FAIL]', u' '.join(reds) or u'无'))
    # ---- Z2 指纹 ----
    z2 = (_sha(_read(MAIN)) == base_sha['main']
          and _sha(_read(ERRAND)) == base_sha['errand'])
    if not z2:
        n_bad += 1
    print(u'%s Z2 指纹：收工时两个文件的 sha1 与开工前一致'
          % (u'[PASS]' if z2 else u'[FAIL]'))
    print(u'')
    print(u'mutate159：%s' % (u'%d 处全对' % (len(MUTATIONS),) if not n_bad
                              else u'有 %d 处不对' % (n_bad,)))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
