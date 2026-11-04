# -*- coding: utf-8 -*-
u"""第157轮负控制：逐条破坏产品，断言**恰好**指定的判据变红，再字节级还原。

用法：
    python mutate157.py            # 按 EXPECT 断言
    python mutate157.py --dry      # 只打印每处破坏实际红了哪些（用于写 EXPECT）

★ 纪律（第150~156轮一路踩出来的）：
  · 一处破坏 = 一个**单一**改动，不搞"顺手改三行"（否则红了一片也说不清是哪条守的）；
  · 期望写窄是常态 ⇒ **实得比期望多**不一定是判据坏，先看是不是"同一条闸的多个观测面"；
  · 还原必须**字节级**（sha1 比对），否则下一处破坏就在脏文件上跑；
  · 收口（Z1）必须再跑一次全绿 —— 证明"还原真的还原了"，不是"改坏了不再报"；
  · ★ 破坏本身**不许把套件炸掉**：异常一路抛出 ⇒ 后面的判据根本没跑，看到的"红"是崩溃点
    不是守卫点。所以每处破坏都保持语法完整、返回值类型不变（`A10` 那处是**故意**让它抛，
    因为产品自己的契约就是"绝不抛"，抛了就说明守卫被拆掉了）。
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
CHECK = os.path.join(HERE, 'check157.py')
PY = sys.executable


def _read_raw():
    with io.open(MAIN, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _write_raw(s):
    with io.open(MAIN, 'w', encoding='utf-8', newline='') as fh:
        fh.write(s)


def _c(s):
    return s.replace('\r\n', '\n').replace('\n', '\r\n')


def _sha(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------- 破坏清单
# (名字, 说明, old, new, 期望变红的判据前缀集合)
MUTATIONS = [
    ('M1', u'`_npc_errand_save` 退回**传裸 board**（欠账又没地方写）',
     u"""            ok = bool(npc_plan_store_mod.save(
                path, _ErrandDoc(board, _errand_given_up_dump(self, now=now))))""",
     u"""            ok = bool(npc_plan_store_mod.save(path, board))""",
     ('A1', 'A11', 'A12', 'A2', 'A3', 'A5', 'B1', 'C6')),

    ('M2', u'★ restore **不转回 tuple**（盘上是 list ⇒ `_errand_given_up_of` 静默全丢）',
     u"""            rows.append((ts, dest, what))      # ★★ 转回 **tuple**（关键）""",
     u"""            rows.append([ts, dest, what])      # ★★ 转回 **tuple**（关键）""",
     ('A1', 'A11', 'A12', 'A2', 'A3', 'A9', 'B3', 'C5')),

    ('M3', u'dump **不过 TTL**（陈年旧账也写进档）',
     u"""            if now - ts > ERRAND_GIVEN_UP_TTL:
                continue
            if not (isinstance(dest, str) and dest):""",
     u"""            if not (isinstance(dest, str) and dest):""",
     ('A6',)),

    ('M4', u'dump **不截断**（档里能攒到 12 件）',
     u"""        if keep:
            out[nid] = keep[-ERRAND_GIVEN_UP_MAX:]""",
     u"""        if keep:
            out[nid] = keep""",
     ('A7',)),

    ('M5', u'restore **坏一条就整表放弃**（不是"坏一条丢一条"）',
     u"""            try:
                ts = float(it[0])
            except (TypeError, ValueError):
                continue
            if now - ts > ERRAND_GIVEN_UP_TTL:
                continue
            dest = it[1]""",
     u"""            try:
                ts = float(it[0])
            except (TypeError, ValueError):
                return 0
            if now - ts > ERRAND_GIVEN_UP_TTL:
                continue
            dest = it[1]""",
     ('A9',)),

    ('M6', u'restore **不校验 `given_up` 是不是 dict**（旧档被手改坏就抛）',
     u"""    if not isinstance(raw, dict):
        return 0""",
     u"""    if raw is None:
        return 0""",
     ('A10',)),

    ('M7', u'`_npc_errand_load` **不调 restore**（写了也不读）',
     u"""        if isinstance(raw, dict):
            try:
                _n_back = _errand_given_up_restore(self, raw.get('given_up'))
                if _n_back:
                    _log.info('欠账读回：%d 件', _n_back)
            except Exception as e:
                _log.debug('欠账读回失败（已忽略）: %s', e)""",
     u"""        # （读回被拿掉 —— 负控制）""",
     ('A1', 'A11', 'A12', 'A2', 'A3', 'B3')),

    ('M8', u'restore **不过 TTL**（档被手改就能把陈年账塞回内存表）',
     u"""            if now - ts > ERRAND_GIVEN_UP_TTL:
                continue
            dest = it[1]""",
     u"""            dest = it[1]""",
     ('A6b',)),

    ('M9', u'restore **不截断**（手改档能塞进 12 条）',
     u"""        if rows:
            tbl[nid] = rows[-ERRAND_GIVEN_UP_MAX:]""",
     u"""        if rows:
            tbl[nid] = rows""",
     ('A7b',)),

    ('M10', u'`_ErrandDoc.to_dict()` **丢掉 board 的形状**（只写 given_up）',
     u"""        d = self._board.to_dict() if self._board is not None else {}
        if not isinstance(d, dict):
            d = {}
        d['given_up'] = self._given_up
        return d""",
     u"""        return {'given_up': self._given_up}""",
     ('A4', 'B1')),
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
    base = _read_raw()
    base_sha = _sha(base)
    print(u'基线 sha1=%s bytes=%d' % (base_sha[:12], len(base)))
    n_bad = 0
    for name, desc, old, new, expect in MUTATIONS:
        _o, _n = _c(old), _c(new)
        if base.count(_o) != 1:
            print(u'[FAIL] %s 锚点出现 %d 次：%s' % (name, base.count(_o), desc))
            n_bad += 1
            continue
        _write_raw(base.replace(_o, _n))
        try:
            rc, reds, out = run_check()
        finally:
            _write_raw(base)
            if _sha(_read_raw()) != base_sha:
                print(u'[FAIL] %s 还原失败（sha1 不一致）' % (name,))
                return 1
        if dry:
            print(u'%s %s ⇒ 红：%s（rc=%d）'
                  % (name, desc, u' '.join(reds) or u'（无！）', rc))
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
        print(u'mutate157（dry）：以上为**实得**，用于写 EXPECT。')
        return 0

    # ---- Z1 收口：还原之后必须全绿 ----
    rc, reds, out = run_check()
    z1 = (rc == 0) and not reds
    if not z1:
        n_bad += 1
    print(u'%s Z1 收口：全部还原后 check157 必须**全绿**（红=%s）'
          % (u'[PASS]' if z1 else u'[FAIL]', u' '.join(reds) or u'无'))
    # ---- Z2 指纹：还原后字节必须等于开工前 ----
    z2 = _sha(_read_raw()) == base_sha
    if not z2:
        n_bad += 1
    print(u'%s Z2 指纹：收工时 `main.py` 的 sha1 与开工前一致'
          % (u'[PASS]' if z2 else u'[FAIL]'))
    print(u'')
    print(u'mutate157：%s' % (u'%d 处全对' % (len(MUTATIONS),) if not n_bad
                              else u'有 %d 处不对' % (n_bad,)))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
