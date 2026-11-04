# -*- coding: utf-8 -*-
u"""第156轮负控制：逐条破坏产品，断言**恰好**指定的判据变红，再字节级还原。

用法：
    python mutate156.py            # 按 EXPECT 断言
    python mutate156.py --dry      # 只打印每处破坏实际红了哪些（用于写 EXPECT）

★ 纪律（第150~155轮一路踩出来的）：
  · 一处破坏 = 一个**单一**改动，不搞"顺手改三行"（否则红了一片也说不清是哪条守的）；
  · 期望写窄是常态 ⇒ **实得比期望多**不一定是判据坏，先看是不是"同一条闸的多个观测面"；
  · 还原必须**字节级**（sha1 比对），否则下一处破坏就在脏文件上跑；
  · 收口（Z1）必须再跑一次全绿 —— 证明"还原真的还原了"，不是"改坏了不再报"；
  · ★ 破坏本身**不许把套件炸掉**：`AttributeError` 一路抛出 ⇒ 后面的判据根本没跑，
    看到的"红"是崩溃点不是守卫点。所以每处破坏都保持语法完整、返回值类型不变。
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
CHECK = os.path.join(HERE, 'check156.py')
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
    ('M1', u'去掉**去重**（同一件事被挤掉两次就记两笔）',
     u"""    items = [it for it in items
             if not (isinstance(it, tuple) and len(it) >= 3
                     and it[1] == dest and it[2] == what)]
""",
     u"""""",
     ('A7',)),

    ('M2', u'把上限从 8 调到 20（截断还在，但已经不算"人话"）',
     u"""ERRAND_GIVEN_UP_MAX = 8""",
     u"""ERRAND_GIVEN_UP_MAX = 20""",
     ('A8',)),

    ('M3', u'整段删掉**截断**（欠账能长到 10 件）',
     u"""    if len(items) > ERRAND_GIVEN_UP_MAX:
        items = items[-ERRAND_GIVEN_UP_MAX:]
""",
     u"""    # （截断被拿掉 —— 负控制）
""",
     ('A8',)),

    ('M4', u'删掉 **TTL** 过滤（陈年旧账也挂嘴边）',
     u"""        try:
            if now - float(ts) > ERRAND_GIVEN_UP_TTL:
                continue
        except (TypeError, ValueError):
            pass""",
     u"""        try:
            pass
        except (TypeError, ValueError):
            pass""",
     ('A9',)),

    ('M5', u'**空账也返回一句**（不再是 `""` ⇒ 没被派过的人 prompt 也变了）',
     u"""    items = _errand_given_up_of(owner, npc_id, now=now)
    if not items:
        return u''""",
     u"""    items = _errand_given_up_of(owner, npc_id, now=now)
    if not items:
        return u'（你手上没有欠着没办完的事。）'""",
     ('B2', 'B5')),

    ('M6', u'brief 里**不写件数**（只列出事由）',
     u"""    return (u'（你手上还有 %d 件没办完就被叫走的事：%s。'
            u'要不要提、怎么提由你自己决定；别提这条提示。）'
            % (len(items), _txt))""",
     u"""    return (u'（你手上有没办完就被叫走的事：%s。'
            u'要不要提、怎么提由你自己决定；别提这条提示。）'
            % (_txt,))""",
     ('B1',)),

    ('M7', u'`_errand_item_txt` 去掉"走一趟"兜底（空事由变「办「」」）',
     u"""    return (u'去 %s 办「%s」' % (dest, _w)) if _w else (u'去 %s 走一趟' % (dest,))""",
     u"""    return (u'去 %s 办「%s」' % (dest, _w))""",
     ('A12',)),

    ('M8', u'NPC 上下文**不挂**欠账（只靠记忆，等它出窗）',
     u"""        if _backlog:
            _txt = (_txt + '\\n' + _backlog) if _txt else _backlog
        return _txt""",
     u"""        return _txt""",
     ('B4', 'B4a')),

    ('M9', u'Ralsei 主链**不挂**欠账',
     u"""            _backlog = _errand_backlog_brief(self, 'ralsei')
            if _backlog:
                system = system + "\\n\\n" + _backlog""",
     u"""            pass""",
     ('B6', 'C5')),

    ('M10', u'把欠账登记**挪到 `board.assign` 之前**（派发失败也记一笔"被挤掉"）',
     u"""        try:
            _new = board.assign(now, npc_id, dest_scene, what, **kw)""",
     u"""        if _prev is not None:
            _errand_given_up_add(self, npc_id,
                                 getattr(_prev, 'dest_scene', u'') or u'?',
                                 getattr(_prev, 'what', u'') or u'', now=now)
        try:
            _new = board.assign(now, npc_id, dest_scene, what, **kw)""",
     ('C1',)),

    ('M11', u'门控拒那一支也记一笔欠账（"去不了"当成"被改派"）',
     u"""            _log.info('差事被门控拒绝：%s → %s（%s）', npc_id, dest_scene, why)
            self._npc_errand_note(npc_id,""",
     u"""            _log.info('差事被门控拒绝：%s → %s（%s）', npc_id, dest_scene, why)
            _errand_given_up_add(self, npc_id, dest_scene, what,
                                 now=kw.get('now'))
            self._npc_errand_note(npc_id,""",
     ('A10', 'C1', 'C2')),

    ('M12', u'痕迹退回第154轮的行为：**只写"上一件"**',
     u"""            _all_txt = u'、'.join(_errand_item_txt(d, w) for d, w in _items)""",
     u"""            _all_txt = _p_txt""",
     ('A1',)),

    ('M13', u'NPC 线写死成 `\'ralsei\'`（串味：别人的欠账串到他头上）',
     u"""        _backlog = _errand_backlog_brief(self, npc_id)""",
     u"""        _backlog = _errand_backlog_brief(self, 'ralsei')""",
     ('C4', 'C5')),

    ('M14', u'Ralsei 线写成别人（主链读不到自己的欠账）',
     u"""            _backlog = _errand_backlog_brief(self, 'ralsei')""",
     u"""            _backlog = _errand_backlog_brief(self, 'susie')""",
     ('C5',)),

    ('M15', u'brief 把"提不提由你定"删掉（变成写死的一句台词）',
     u"""            u'要不要提、怎么提由你自己决定；别提这条提示。）'""",
     u"""            u'别提这条提示。）'""",
     ('B3',)),
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
        print(u'mutate156（dry）：以上为**实得**，用于写 EXPECT。')
        return 0

    # ---- Z1 收口：还原之后必须全绿 ----
    rc, reds, out = run_check()
    z1 = (rc == 0) and not reds
    if not z1:
        n_bad += 1
    print(u'%s Z1 收口：全部还原后 check156 必须**全绿**（红=%s）'
          % (u'[PASS]' if z1 else u'[FAIL]', u' '.join(reds) or u'无'))
    # ---- Z2 指纹：还原后字节必须等于开工前 ----
    z2 = _sha(_read_raw()) == base_sha
    if not z2:
        n_bad += 1
    print(u'%s Z2 指纹：收工时 `main.py` 的 sha1 与开工前一致'
          % (u'[PASS]' if z2 else u'[FAIL]'))
    print(u'')
    print(u'mutate156：%s' % (u'%d 处全对' % (len(MUTATIONS),) if not n_bad
                              else u'有 %d 处不对' % (n_bad,)))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
