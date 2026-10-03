# -*- coding: utf-8 -*-
u"""第81轮 · 层4 接线探针（**不启真机**，只做 AST + 行为级等价验证）。

守的是什么
----------
`_npc_roam_decide` / `_npc_roam_sleep` / `_npc_plan_save` / `_npc_plan_file`
这几个方法在 `main.py` 里 —— main 有 13000+ 行且要 Qt，**不能 import**。
所以：
  · 结构面 → AST 抽出来看（判据名/调用是否存在、`last=None` 是否真被换掉）；
  · 行为面 → 用 `ast` 抽出**真函数体**（不是重写一份）exec 到假宿主上跑。
★ 「能从源码拿的别 import／能 import 的别重写／不得不重写必须锁等价」。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

PASS = 0
FAIL = 0


def ok(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s' % msg)
    else:
        FAIL += 1
        print('[FAIL] %s' % msg)


def read_src():
    with io.open(MAIN, 'r', encoding='utf-8') as fh:
        return fh.read()


def find_method(tree, name):
    """在 main.py 的 AST 里找 `def name(...)` 的 FunctionDef 节点。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            out.append(node)
    return out


def call_names(fn):
    """函数体里所有被调用的名字（属性访问取末段）。"""
    names = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                names.append(f.id)
            elif isinstance(f, ast.Attribute):
                names.append(f.attr)
    return names


def kw_present(fn, kw):
    """函数体里是否存在名为 kw 的关键字参数（任何调用）。"""
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            for k in node.keywords:
                if k.arg == kw:
                    return True
    return False


def kw_value_is_none(fn, kw):
    """名为 kw 的关键字参数，其值是否恒为字面量 None。"""
    seen = False
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            for k in node.keywords:
                if k.arg == kw:
                    seen = True
                    if not (isinstance(k.value, ast.Constant)
                            and k.value.value is None):
                        return False
    return seen


def main():
    src = read_src()
    tree = ast.parse(src)

    print('== A 结构面（AST 断言）==')
    # A1 三处 import
    ok(('npc_plan_store_mod' in src) and
       ('from modules import npc_plan_store as npc_plan_store_mod' in src),
       'A1 `npc_plan_store` 真被 import（别名 npc_plan_store_mod）')

    dec = find_method(tree, '_npc_roam_decide')
    ok(len(dec) == 1, 'A2 `_npc_roam_decide` 恰好定义 1 次（实际 %d）' % len(dec))
    dec = dec[0]
    cn = call_names(dec)
    ok('plan_of' in cn, 'A3 `_npc_roam_decide` 真调 `plan_of()`（档案真被用）')
    ok('note' in cn, 'A4 `_npc_roam_decide` 真调 `plan.note()`（结果真记回）')
    ok(kw_present(dec, 'last'), 'A5 `decide()` 调用带 `last=` 关键字')
    ok(not kw_value_is_none(dec, 'last'),
       'A6 ★★ `last=` **不再恒为 None**（层4 之前是硬编码 None）')
    ok('decide' in cn, 'A7 仍真调 `npc_intent_mod.decide()`')

    slp = find_method(tree, '_npc_roam_sleep')
    ok(len(slp) == 1, 'A8 `_npc_roam_sleep` 恰好定义 1 次')
    slp = slp[0]
    scn = call_names(slp)
    ok('last_sleep_of' in scn, 'A9 `_npc_roam_sleep` 真调 `book.last_sleep_of()`')
    ok('note_sleep' in scn, 'A10 `_npc_roam_sleep` 真调 `book.note_sleep()`')
    ok('choose_sleep_scene' in scn, 'A11 仍真调 `npc_intent_mod.choose_sleep_scene()`')
    ok('last_sleep' in [a.arg for a in slp.args.args] or
       kw_present(slp, 'last_sleep'),
       'A12 `last_sleep` 仍作为入参被透传')

    pf = find_method(tree, '_npc_plan_file')
    ok(len(pf) == 1, 'A13 `_npc_plan_file` 恰好定义 1 次（路径注入点）')
    ok('app_file' in call_names(pf[0]),
       'A14 `_npc_plan_file` 真走 `data_store.app_file()`（唯一入口）')

    ps = find_method(tree, '_npc_plan_save')
    ok(len(ps) == 1, 'A15 `_npc_plan_save` 恰好定义 1 次')
    psn = call_names(ps[0])
    ok('save' in psn, 'A16 `_npc_plan_save` 真调 `npc_plan_store_mod.save()`')
    # ★ 查**形参**（def 的参数表），不是调用侧的关键字 —— 第一版写成 `kw_present`
    #   （查 Call 的 keywords）⇒ 对着 `def _npc_plan_save(self, force=False)` 恒假。
    #   判据侧 bug，已修（"报红先怀疑判据"）。
    _ps_args = [a.arg for a in ps[0].args.args]
    ok('force' in _ps_args,
       'A17 `_npc_plan_save` 有 `force` 形参（退出兜底要用） 实有=%s' % _ps_args)

    tk = find_method(tree, '_npc_roam_tick')
    ok(len(tk) == 1, 'A18 `_npc_roam_tick` 恰好定义 1 次')
    ok('_npc_plan_save' in call_names(tk[0]),
       'A19 ★★ `_npc_roam_tick` 真调 `_npc_plan_save()`（世界变了就落盘）')

    # 退出收尾：强制落盘
    ok(src.count('_npc_plan_save(force=True)') >= 1,
       'A20 退出收尾有 `_npc_plan_save(force=True)` 兜底')

    # init_npc_systems 里真建书
    ini = find_method(tree, 'init_npc_systems')
    ok(len(ini) == 1, 'A21 `init_npc_systems` 恰好定义 1 次')
    ini_src = ast.get_source_segment(src, ini[0]) or ''
    ok('npc_plan_store_mod.load' in ini_src,
       'A22 ★ `init_npc_systems` 真调 `npc_plan_store_mod.load()`（读回存档）')
    ok('npc_plan_store_mod.Book()' in ini_src,
       'A23 ★ 属性预声明成 `Book()`（不是 None —— plan_of 才能随手用）')
    ok('_npc_plan_file()' in ini_src,
       'A24 路径由 `_npc_plan_file()` 注入')

    # 驻留表灌回（书里的才是重启前的世界）
    ok('_roam_from_book' in ini_src,
       'A25 ★★ 书里的 roam 真被灌回 `self.npc_roam`（否则存档白读）')

    print('')
    print('== B 行为面（真 exec 抽出的真函数体，跑在假宿主上）==')
    # 抽出真源码来 exec —— 不重写一份（否则"锁等价"变成"锁我的重写"）
    # ★ 两个方法编译成**同一份** globals（`ns`）—— 它们共享 `npc_intent_mod`
    #   / `_log` / `time` 这些全局名；各编译一份会让 B 段换模块时只换到一半。
    #   第一版就是栽在这：A 段（结构）过、B 段 NameError。
    #   ★ 与 `main.py` 的真实语义一致（那里这些名字本来就在**同一个模块命名空间**）。
    mod = ast.Module(body=[dec, slp], type_ignores=[])
    code = compile(ast.fix_missing_locations(mod), '<probe81>', 'exec')

    ns = {}
    ns['time'] = __import__('time')
    exec(code, ns)
    RealDecide = ns['_npc_roam_decide']
    RealSleep = ns['_npc_roam_sleep']

    # ---- 假 npc_intent_mod：记下每次调用收到的 last / last_sleep ----
    class FakeIntent(object):
        def __init__(self):
            self.decide_last = []
            self.sleep_last = []

        def decide(self, npc_id, now, **kw):
            self.decide_last.append(kw.get('last'))
            return ('go_scene', 'somewhere')

        def choose_sleep_scene(self, npc_id, now, **kw):
            self.sleep_last.append(kw.get('last_sleep'))
            return ('home_scene', 'own_home')

    fake = FakeIntent()
    # ★★ 把假模块塞进**同一份** globals（真函数体的 `npc_intent_mod` 从这里取）
    ns['npc_intent_mod'] = fake

    class FakePlan(object):
        def __init__(self):
            self.intent = 'PREV_INTENT'
            self.last_sleep_scene = 'PREV_SLEEP'
            self.notes = []

        def note(self, it):
            self.notes.append(it)

    class FakeBook(object):
        def __init__(self):
            self.p = FakePlan()
            self.slept = []

        def plan_of(self, nid):
            return self.p

        def last_sleep_of(self, nid):
            return self.p.last_sleep_scene

        def note_sleep(self, nid, scene):
            self.slept.append((nid, scene))
            self.p.last_sleep_scene = scene
            return True

    class FakeLog(object):
        def debug(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

    host = type('Host', (), {})()
    host.npc_plan_book = FakeBook()
    host._log = FakeLog()

    # B1 decide 真把档案里的上一次意图喂进 last
    host._npc_roam_decide = lambda *a, **k: RealDecide(host, *a, **k)
    it = RealDecide(host, 'kris', 1000.0, traits=None, familiar=0.0,
                    home=None, reachable=None, friends=None)
    ok(fake.decide_last and fake.decide_last[-1] == 'PREV_INTENT',
       'B1 ★★ `decide` 真收到档案里的上一次意图（实收 %r）' % (fake.decide_last[-1:],))
    ok(host.npc_plan_book.p.notes and
       host.npc_plan_book.p.notes[-1] == ('go_scene', 'somewhere'),
       'B2 ★★ 本次结果真被 `note()` 记回档案')

    # B3 sleep 真把档案里的 last_sleep 喂进去
    sc, why = RealSleep(host, 'kris', 1000.0, home=None, friends=None,
                        reachable=None, last_sleep=None)
    ok(fake.sleep_last and fake.sleep_last[-1] == 'PREV_SLEEP',
       'B3 ★★ `choose_sleep_scene` 真收到档案里的 last_sleep（实收 %r）'
       % (fake.sleep_last[-1:],))

    # B4 决策出地点后真记回
    ok(host.npc_plan_book.slept and host.npc_plan_book.slept[-1] ==
       ('kris', 'home_scene'),
       'B4 ★★ 睡哪真被 `note_sleep()` 记回档案')

    # B5 负控制：调用方**给了** last_sleep 时不许被档案覆盖（显式优先）
    fake.sleep_last = []
    RealSleep(host, 'kris', 2000.0, home=None, friends=None,
              reachable=None, last_sleep='EXPLICIT')
    ok(fake.sleep_last and fake.sleep_last[-1] == 'EXPLICIT',
       'B5 ★ 负控制：调用方显式给的 last_sleep **优先于**档案（实收 %r）'
       % (fake.sleep_last[-1:],))

    # B6 负控制：哪儿也去不了（nowhere）不许记进档案
    class FakeNowhere(FakeIntent):
        def choose_sleep_scene(self, npc_id, now, **kw):
            return None, 'nowhere'

    host.npc_plan_book.slept = []
    old = ns['npc_intent_mod']
    ns['npc_intent_mod'] = FakeNowhere()
    host.npc_plan_book.p.last_sleep_scene = 'PREV_SLEEP'
    RealSleep(host, 'kris', 3000.0, home=None, friends=None,
              reachable=None, last_sleep=None)
    ok(not host.npc_plan_book.slept,
       'B6 ★ 负控制：`nowhere`（哪儿也去不了）**不许**记进档案')
    ns['npc_intent_mod'] = old

    # B7 档案拿不到（book=None）时不许抛 —— 退化成"无记忆决策"
    host2 = type('Host2', (), {})()
    host2.npc_plan_book = None
    host2._log = FakeLog()
    ns['npc_intent_mod'] = fake
    try:
        RealDecide(host2, 'kris', 1.0, traits=None, familiar=0.0,
                   home=None, reachable=None, friends=None)
        RealSleep(host2, 'kris', 1.0, home=None, friends=None,
                  reachable=None, last_sleep=None)
        ok(True, 'B7 ★ 档案缺失（None）时两处都不抛（退化为无记忆决策）')
    except Exception as e:
        ok(False, 'B7 ★ 档案缺失时抛了异常: %r' % (e,))

    # B8 判据自身体检：假宿主真被调到（记账口不是 no-op）
    ok(len(fake.decide_last) > 0 and len(fake.sleep_last) > 0,
       'B8 判据自身体检：假桩真被调用（记账口非 no-op）')

    print('')
    print('PASS=%d FAIL=%d' % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
