# -*- coding: utf-8 -*-
u"""第158轮负控制：逐条破坏产品，断言**恰好**指定的判据变红，再字节级还原。

用法：
    python mutate158.py            # 按 EXPECT 断言
    python mutate158.py --dry      # 只打印每处破坏实际红了哪些（用于写 EXPECT）

★ 纪律（第150~157轮一路踩出来的）：
  · 一处破坏 = 一个**单一**改动，不搞"顺手改三行"；
  · 期望写窄是常态 ⇒ **实得比期望多**不一定是判据坏，先看是不是"同一条闸的多个观测面"；
  · 还原必须**字节级**（sha1 比对），否则下一处破坏就在脏文件上跑；
  · 收口（Z1）必须再跑一次全绿 —— 证明"还原真的还原了"；
  · ★ 破坏本身**不许把套件炸掉**：异常一路抛出 ⇒ 看到的"红"是崩溃点不是守卫点。
    本清单每处都保持语法完整、返回值类型不变。
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
CHECK = os.path.join(HERE, 'check158.py')
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
    ('M1', u'派活落盘**退回节流**（`force=True` → 默认）',
     u"""        if _new is not None:
            self._npc_errand_save(force=True)
        return _new""",
     u"""        if _new is not None:
            self._npc_errand_save()
        return _new""",
     ('A1', 'A12', 'A2', 'B1')),

    ('M2', u'派活**根本不落盘**（整段拿掉）',
     u"""        if _new is not None:
            self._npc_errand_save(force=True)
        return _new""",
     u"""        return _new""",
     ('A1', 'A12', 'A2', 'A9', 'B1', 'B2', 'B3', 'B8')),

    ('M3', u'守卫被架空（`if _new is not None:` → `if True:`）',
     u"""        if _new is not None:
            self._npc_errand_save(force=True)""",
     u"""        if True:
            self._npc_errand_save(force=True)""",
     ('A5', 'B3')),

    ('M4', u'叫停**退回节流**（`force=True` → 默认）',
     u"""            self._npc_errand_save(force=True)
        except Exception as exc:
            _log.debug('叫停后落盘/重建失败（已忽略）: %s', exc)""",
     u"""            self._npc_errand_save()
        except Exception as exc:
            _log.debug('叫停后落盘/重建失败（已忽略）: %s', exc)""",
     ('A6', 'B4')),

    ('M5', u'tick **一律节流**（结构性变化也不写）',
     u"""                _structural = bool(dropped) or bool(out.get('finished'))
                self._npc_errand_save(force=_structural)""",
     u"""                _structural = bool(dropped) or bool(out.get('finished'))
                self._npc_errand_save()""",
     ('A7', 'B5')),

    ('M6', u'tick **每拍都强写**（力取 `touched`）',
     u"""                _structural = bool(dropped) or bool(out.get('finished'))
                self._npc_errand_save(force=_structural)""",
     u"""                _structural = bool(dropped) or bool(out.get('finished'))
                self._npc_errand_save(force=touched)""",
     ('A8', 'B5')),

    ('M7', u'`_structural` **漏掉"办完"**（只认被拦下）',
     u"""                _structural = bool(dropped) or bool(out.get('finished'))""",
     u"""                _structural = bool(dropped)""",
     ('A7', 'B6')),

    ('M8', u'退出兜底**不写差事档**（只写生活档案）',
     u"""        try:
            self._npc_errand_save(force=True)
        except Exception as e:  # 观测代码绝不能影响退出流程
            _log.debug("main 防御性异常（已忽略）: %s", e)""",
     u"""        pass""",
     ('B7', 'B8')),

    ('M9', u'`_npc_errand_save` **无视 force**（节流永远生效）',
     u"""        last = getattr(self, '_npc_errand_last_save', 0.0) or 0.0
        if not force and (now - last) < RalseiPet.NPC_PLAN_SAVE_EVERY:
            return False""",
     u"""        last = getattr(self, '_npc_errand_last_save', 0.0) or 0.0
        if (now - last) < RalseiPet.NPC_PLAN_SAVE_EVERY:
            return False""",
     ('A1', 'A12', 'A2', 'A6', 'A7')),

    ('M10', u'门控拒**也写盘**（没派成却留痕）',
     u"""            self._npc_errand_note(npc_id,
                                  '我本来要去 %s，但去不了 —— %s' % (dest_scene, why))
            return None""",
     u"""            self._npc_errand_note(npc_id,
                                  '我本来要去 %s，但去不了 —— %s' % (dest_scene, why))
            self._npc_errand_save(force=True)
            return None""",
     ('A4', 'B1', 'B2', 'B3', 'B8')),
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
        print(u'mutate158（dry）：以上为**实得**，用于写 EXPECT。')
        return 0

    # ---- Z1 收口：还原之后必须全绿 ----
    rc, reds, out = run_check()
    z1 = (rc == 0) and not reds
    if not z1:
        n_bad += 1
    print(u'%s Z1 收口：全部还原后 check158 必须**全绿**（红=%s）'
          % (u'[PASS]' if z1 else u'[FAIL]', u' '.join(reds) or u'无'))
    # ---- Z2 指纹：还原后字节必须等于开工前 ----
    z2 = _sha(_read_raw()) == base_sha
    if not z2:
        n_bad += 1
    print(u'%s Z2 指纹：收工时 `main.py` 的 sha1 与开工前一致'
          % (u'[PASS]' if z2 else u'[FAIL]'))
    print(u'')
    print(u'mutate158：%s' % (u'%d 处全对' % (len(MUTATIONS),) if not n_bad
                              else u'有 %d 处不对' % (n_bad,)))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
