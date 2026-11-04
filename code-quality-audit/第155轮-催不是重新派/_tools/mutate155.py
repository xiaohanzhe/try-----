# -*- coding: utf-8 -*-
u"""第155轮负控制：逐条破坏产品，断言**恰好**指定的判据变红，再字节级还原。

用法：
    python mutate155.py            # 按 EXPECT 断言
    python mutate155.py --dry      # 只打印每处破坏实际红了哪些（用于写 EXPECT）

★ 纪律（第150~154轮一路踩出来的）：
  · 一处破坏 = 一个**单一**改动，不搞"顺手改三行"（否则红了一片也说不清是哪条守的）；
  · 期望写窄是常态 ⇒ **实得比期望多**不一定是判据坏，先看是不是"同一条闸的多个观测面"；
  · 还原必须**字节级**（sha1 比对），否则下一处破坏就在脏文件上跑；
  · 收口（Z1）必须再跑一次全绿 —— 证明"还原真的还原了"，不是"改坏了不再报"。
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
CHECK = os.path.join(HERE, 'check155.py')
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
    ('M1', u'整段删掉"催"的短路（回到第154轮的行为）',
     u"""        _prev = board.active_of(npc_id)
        if getattr(board, 'enabled', False) and _prev is not None \\
                and _errand_same_job(_prev, dest_scene, what):
            _log.info('催（不重启）：%s 已经在办「%s」（%s，状态=%s）',
                      npc_id, what, dest_scene, getattr(_prev, 'status', u'?'))
            return _prev
""",
     u"""        _prev = board.active_of(npc_id)
""",
     ('A1', 'A11', 'A13', 'A2', 'A3',
      'A4', 'A5', 'A6', 'A9', 'B1',
      'C0', 'C1', 'C2', 'C3', 'C4')),

    ('M2', u'短路还在，但条件恒假（`_errand_same_job` 换成 `False`）',
     u"""        if getattr(board, 'enabled', False) and _prev is not None \\
                and _errand_same_job(_prev, dest_scene, what):""",
     u"""        if getattr(board, 'enabled', False) and _prev is not None \\
                and False:""",
     ('A1', 'A11', 'A13', 'A2', 'A3',
      'A4', 'A5', 'A6', 'A9', 'B1',
      'C4')),

    ('M3', u'只删 `return _prev`（日志还在）⇒ 催也继续走到门控与 `assign`',
     u"""            _log.info('催（不重启）：%s 已经在办「%s」（%s，状态=%s）',
                      npc_id, what, dest_scene, getattr(_prev, 'status', u'?'))
            return _prev
        # ★★★ 第114轮""",
     u"""            _log.info('催（不重启）：%s 已经在办「%s」（%s，状态=%s）',
                      npc_id, what, dest_scene, getattr(_prev, 'status', u'?'))
        # ★★★ 第114轮""",
     ('A1', 'A11', 'A13', 'A2', 'A3',
      'A4', 'A5', 'A6', 'A9', 'B1',
      'C0', 'C1', 'C2', 'C3')),

    ('M4', u'去掉 `board.enabled` 闸（关闸时也返旧条）',
     u"""        if getattr(board, 'enabled', False) and _prev is not None \\
                and _errand_same_job(_prev, dest_scene, what):""",
     u"""        if _prev is not None \\
                and _errand_same_job(_prev, dest_scene, what):""",
     ('A10', 'C3')),

    ('M5', u'把"催"的短路挪到**门控之后**（催也问路）',
     u"""        _prev = board.active_of(npc_id)
        if getattr(board, 'enabled', False) and _prev is not None \\
                and _errand_same_job(_prev, dest_scene, what):
            _log.info('催（不重启）：%s 已经在办「%s」（%s，状态=%s）',
                      npc_id, what, dest_scene, getattr(_prev, 'status', u'?'))
            return _prev
        # ★★★ 第114轮：**派发的当场**就过世界门控。""",
     u"""        _prev = board.active_of(npc_id)
        # ★★★ 第114轮：**派发的当场**就过世界门控。""",
     ('A1', 'A11', 'A13', 'A2', 'A3',
      'A4', 'A5', 'A6', 'A9', 'B1',
      'C0', 'C1', 'C2', 'C3', 'C4')),

    ('M6', u'ack 里 `_same` 恒假（催与首次说同一句）',
     u"""            _same = (prev is not None
                     and _errand_same_job(prev, dest_scene, what))""",
     u"""            _same = False""",
     ('B3', 'B4', 'B6', 'B8', 'C4')),

    ('M7', u'ack 里 `_same` 恒真（首次派活也被当成催）',
     u"""            _same = (prev is not None
                     and _errand_same_job(prev, dest_scene, what))""",
     u"""            _same = True""",
     ('B5', 'B7', 'C4')),

    ('M8', u'ack 不看状态（永远说"还在去的路上"）',
     u"""                if _st == npc_errand_mod.WORKING:
                    _doing = u'他已经到了那里、正在办'
                elif _st == npc_errand_mod.DONE:""",
     u"""                if _st == npc_errand_mod.TRAVELING:
                    _doing = u'他还在去的路上'
                elif _st == npc_errand_mod.DONE:""",
     ('B6',)),

    ('M9', u'`_errand_same_job` 只比地点（同地换事由被当成催）',
     u"""    return (getattr(prev, 'dest_scene', None) == dest_scene
            and _p_what == _n_what)""",
     u"""    return (getattr(prev, 'dest_scene', None) == dest_scene)""",
     ('A7',)),

    ('M10', u'催的 brief 删掉"没有重新计时"',
     u"""                         '这次**没有**重新出发、也没有重新计时。'""",
     u"""                         '这次**没有**重新出发。'""",
     ('B3', 'C7')),

    ('M11', u'短路里 `return _prev` 改成 `return None`（不派也不认）',
     u"""                      npc_id, what, dest_scene, getattr(_prev, 'status', u'?'))
            return _prev""",
     u"""                      npc_id, what, dest_scene, getattr(_prev, 'status', u'?'))
            return None""",
     ('A1', 'A11', 'A13', 'A2', 'A3',
      'A9', 'B1', 'C0', 'C1', 'C2',
      'C3')),

    ('M12', u'催时把旧那条的 `finish_at` 往后推 1 秒（对象没换，时间被改）',
     u"""            _log.info('催（不重启）：%s 已经在办「%s」（%s，状态=%s）',
                      npc_id, what, dest_scene, getattr(_prev, 'status', u'?'))
            return _prev""",
     u"""            _log.info('催（不重启）：%s 已经在办「%s」（%s，状态=%s）',
                      npc_id, what, dest_scene, getattr(_prev, 'status', u'?'))
            _prev.finish_at = _prev.finish_at + 1.0
            return _prev""",
     ('A3',)),
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
        print(u'mutate155（dry）：以上为**实得**，用于写 EXPECT。')
        return 0

    # ---- Z1 收口：还原之后必须全绿 ----
    rc, reds, out = run_check()
    z1 = (rc == 0) and not reds
    if not z1:
        n_bad += 1
    print(u'%s Z1 收口：全部还原后 check155 必须**全绿**（红=%s）'
          % (u'[PASS]' if z1 else u'[FAIL]', u' '.join(reds) or u'无'))
    # ---- Z2 指纹：还原后字节必须等于开工前 ----
    z2 = _sha(_read_raw()) == base_sha
    if not z2:
        n_bad += 1
    print(u'%s Z2 指纹：收工时 `main.py` 的 sha1 与开工前一致'
          % (u'[PASS]' if z2 else u'[FAIL]'))
    print(u'')
    print(u'mutate155：%s' % (u'%d 处全对' % (len(MUTATIONS),) if not n_bad
                              else u'有 %d 处不对' % (n_bad,)))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
