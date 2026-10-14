# -*- coding: utf-8 -*-
"""第114轮 · 真机自检：**差事的世界门控 + 派发入口 + 落盘**。

用户铁律：「**一定要看录像而不是只读后台输出**」「**记得录屏自检**」。

★★★ 沙箱（第114轮第二版新增，**必须**）
----------------------------------------
本脚本会**真写盘**（差事档 / 角色记忆 / 驻留表）。默认这些落 `E:\\RalseiMemory\\`
—— 那是**用户真实的角色记忆**（用户口径：「记忆不要随便修改，三思而后行」）。
所以本脚本在 `import main` **之前**做两件事，把整棵数据根挪进临时目录：
  ① `os.environ['RALSEI_DATA_DIR'] = <临时目录>`；
  ② `data_store.vault_root = lambda **k: None` ⇒ `data_root()` 只能返回 staging。
⇒ 之后 `data_store.app_file(...)` 一律落在沙箱里，**一个字节都不碰用户档**。

要证明的五件事（每件都必须在**真机起过的实例**上断言）
----------------------------------------------------
  B. **门控的拒绝面**（用户点名的例子）：让「苏西」派 **Ralsei 无球**去三角符文
     （光世界）⇒ ① 这句话**被识别为派活**；② 但看板里**没有**这条差事；
     ③ 他的位置真源**没被改写**；④ 他记忆里多了一条"去不了"。
     ★ 这是本轮的**核心口径**：「被派不可进入原本不可进入的世界」。
  C. **派发入口的放行面**（用户主用例，逐字：「我让 ralsei 去 oneshot 里干什么
     事情，**他能去，干，然后产生结果**」）：用户在对话框说「让 ralsei 去 oneshot
     帮我拿个东西」⇒ 看板里真多一条、目的地是 oneshot 那一侧、**当前显示一字不变**。
     ★ 与 B 段**成对**：**同一个人**（ralsei）在 B 被拒、在 C 被放行 ⇒ 证明门控
       不是"一刀切拦住"，而是**按世界判**（光世界要球 / 别的暗世界自由）。
  C'. **跨作品回家**（第114轮新修的别名缺口）：让 Ralsei 派 **Papyrus 去 ut**
     ⇒ 必须**放行**（`home_production:ut`）。配上两条负控制：
       · 清空 `CHAPTER_ALIASES` ⇒ 同一句**必须翻成拒绝**（隔离别名的作用）；
       · 派 Papyrus 去 **oneshot**（另一部作品的暗世界）⇒ 必须拒绝 + 留痕。
     ★ 修前 `'ut' in ['undertale']` 恒假 ⇒ UT / UTY 共 29 位角色**连自己家都进不去**。
  D. **落地与"中途进去能看到"**：推进到 `working` ⇒ 位置真源变成目标场景 ⇒
     按驻留表在目标场景重建身体时**他在里面**。
  E. **落盘**：`_npc_errand_save(force=True)` 后盘上真有这份差事，
     且 `_npc_errand_load()` 能读回同样条数。

★★ 本脚本**只验机制，不验模型**：`_errand_ack`（"让模型说一句"）被**显式短路**
   并**打印**出来 —— 因为真机不一定有 Ollama，而"台词由模型生成"这件事已由
   `check114 H8`（AST：真调 `chat_with_ai`）与代码审查覆盖。
   短路是 **no-op 必须显式打印** 那条纪律的落地。

跑法（真机）：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe rec114.py
（不设 QPA 时退化为离屏：状态断言照跑，PNG 为 0 属预期。）
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

# ---- ★★★ 沙箱：**必须在 import main 之前**（见模块 docstring）----
# ⚠️ 用 `tempfile.mkdtemp()`（**绝不 rmtree** —— 本机清理守卫累积删除会拦 import）。
_SANDBOX = tempfile.mkdtemp(prefix='rec114_')
os.environ['RALSEI_DATA_DIR'] = _SANDBOX
import data_store  # noqa: E402

_VAULT_PATCHED = False
try:
    data_store.vault_root = lambda create=True: None
    _VAULT_PATCHED = True
except Exception:
    pass

_EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
_FR = os.path.join(_EV, 'frames114')
for _d in (_EV, _FR):
    if not os.path.isdir(_d):
        os.makedirs(_d)

_OUT = []
_N = {'p': 0, 'f': 0}
_SNAPS = []


def ok(name, cond, detail=u''):
    _N['p' if cond else 'f'] += 1
    line = u'%s %s' % (u'[PASS]' if cond else u'[FAIL]', name)
    if detail:
        line += u'  <- %s' % detail
    print(line)
    _OUT.append(line)
    return bool(cond)


def sec(t):
    print(u'\n-- %s --' % t)
    _OUT.append(u'\n-- %s --' % t)


try:
    from PyQt5.QtWidgets import QApplication
except Exception as _e:
    print(u'[FATAL] PyQt5 不可用: %s' % _e)
    sys.exit(2)

_app = QApplication.instance() or QApplication(sys.argv)
IS_REAL = (os.environ.get('QT_QPA_PLATFORM') == 'windows')
_box = {}


def _snap(tag, note):
    pet = _box.get('pet')
    rec = {'tag': tag, 'note': note, 'png': None}
    try:
        scr = _app.primaryScreen()
        if IS_REAL and scr is not None:
            pm = scr.grabWindow(0)
            if pm is not None and not pm.isNull():
                p = os.path.join(_FR, u'%s.png' % tag)
                pm.save(p, 'PNG')
                rec['png'] = p
    except Exception as e:
        rec['err'] = str(e)
    try:
        b = getattr(pet, 'npc_errand', None)
        r = getattr(pet, 'npc_roam', None)
        rec['scene_id'] = pet._npc_scene_id()
        rec['board_len'] = len(b) if b is not None else None
        rec['board_active'] = sorted(b.by_npc().keys()) if b is not None else None
        rec['resident_ralsei'] = (r.resident_of('ralsei') if r is not None else None)
        # ★★ 窗口几何：让帧**可定位**（透明分层窗口在抓屏里"看不出在哪"，
        #    但几何永远准 —— 本项目 §73.8 已裁定）。同时在帧上看不出变化时，
        #    "几何没变"就是"没多出窗口 / 没全屏化"的硬证据。
        try:
            geo = pet.frameGeometry()
            rec['pet_geo'] = [geo.x(), geo.y(), geo.width(), geo.height()]
        except Exception:
            rec['pet_geo'] = None
        try:
            rec['pet_visible'] = bool(pet.isVisible())
        except Exception:
            rec['pet_visible'] = None
        try:
            rec['screen'] = [_app.primaryScreen().size().width(),
                             _app.primaryScreen().size().height()]
        except Exception:
            rec['screen'] = None
    except Exception as e:
        rec['state_err'] = str(e)
    _SNAPS.append(rec)
    print(u'   [snap] %-20s scene=%s board=%-22s resident_ralsei=%s\n'
          u'          pet_geo=%s visible=%s screen=%s png=%s'
          % (tag, rec.get('scene_id'), rec.get('board_active'),
             rec.get('resident_ralsei'),
             rec.get('pet_geo'), rec.get('pet_visible'), rec.get('screen'),
             os.path.basename(rec['png']) if rec['png'] else u'(离屏无帧)'))
    return rec


# ===========================================================================
sec(u'A. 真机起实例')
print(u'   [sandbox] 数据根 = %s' % _SANDBOX)
print(u'   [sandbox] `data_store.vault_root` 已拦成 None = %s（True ⇒ 用户档安全）'
      % _VAULT_PATCHED)
# ★★ 首启的**托盘气泡**会盖住桌宠：它就在托盘区，而 Ralsei 也贴右下角，
#    于是帧里只能看到那句"我到托盘里待着啦～"，看不到人（实测抓到）。
#    这里在沙箱 config 里预置"已提示过" ⇒ 不弹 ⇒ 帧里能看到桌宠。
#    ★ 只影响**帧的清晰度**，与本事无关，**不动一行产品代码**。
try:
    import io as _io
    _cfg = os.path.join(_SANDBOX, 'config.json')
    with _io.open(_cfg, 'w', encoding='utf-8') as _fh:
        _fh.write('{"ui": {"tray_hint_shown": true}}')
    print(u'   [setup] 已预置沙箱 config ⇒ 抑制首启托盘气泡（否则它会盖住桌宠）')
except Exception as _e:
    print(u'   [warn] 预置 config 失败（气泡可能盖住桌宠）: %r' % (_e,))

try:
    import main as _M
    from modules import npc_persona as _NP
    from modules import npc_system as _NSYS
    pet = _M.RalseiPet()
    _box['pet'] = pet
    # ★★★ 真机入口（`main.py` 尾部）是 `window = RalseiPet(); window.show()`
    #    —— 本脚本**必须照做**，否则窗口 `isVisible() = False`，抓屏里
    #    **根本没有桌宠**（第一版就是这样：6 帧全是"纯壁纸照"，等于没录像）。
    pet.show()
    for _ in range(8):
        _app.processEvents()
        time.sleep(0.05)
except Exception as e:
    import traceback
    traceback.print_exc()
    print(u'[FATAL] 起实例失败: %s' % e)
    sys.exit(3)

board = getattr(pet, 'npc_errand', None)
roam = getattr(pet, 'npc_roam', None)
ok(u'A1 实例起来了', pet is not None)
ok(u'A2 差事看板就位', board is not None)
ok(u'A3 驻留表就位（差事落地的地方）', roam is not None)
ok(u'A4 别名表就位（派发入口要靠它认名字）',
   bool(getattr(pet, '_npc_aliases', None)),
   u'n=%d' % len(getattr(pet, '_npc_aliases', {}) or {}))
_ALIASES = _NP.address_aliases(
    [(n.id, n.name, n.name_cn) for n in pet.npc_registry.all()])
_SUSIE = _ALIASES.get(u'苏西')
ok(u'A5 别名表里「苏西」有归属', isinstance(_SUSIE, str), u'-> %s' % _SUSIE)
ok(u'A6 开关默认开', bool(_M.RalseiPet.NPC_ERRAND_ENABLED))
ok(u'A7 开局看板为空（没派过 ⇒ 零行为变化）',
   board is not None and len(board) == 0,
   u'len=%s' % (len(board) if board is not None else None))


def _alias_of(npc_id):
    """从别名表里挑一个**能被人说出口**的写法（优先中文名，其次最短）。"""
    cand = [a for a, i in _ALIASES.items() if i == npc_id]
    if not cand:
        return npc_id
    cand.sort(key=lambda a: (a.isascii(), len(a)))
    return cand[0]


_PAP = u'ut_papyrus'
_ALIAS_PAP = _alias_of(_PAP)
ok(u'A8 别名表里 Papyrus 有归属（跨作品回家的主角）',
   _ALIAS_PAP != _PAP and _ALIASES.get(_ALIAS_PAP) == _PAP,
   u'别名=%r -> %s' % (_ALIAS_PAP, _PAP))
# ★★★ "帧里真的有桌宠"的护栏 —— 否则整份录像就是**空证据**
#     （离屏平台没有"屏幕"概念 ⇒ 只要求窗口已 show，不要求像素）。
_scr = _app.primaryScreen()
_scr_w, _scr_h = (_scr.size().width(), _scr.size().height()) if _scr else (0, 0)
_geo0 = pet.frameGeometry()
_inside = (0 <= _geo0.x() < _scr_w and 0 <= _geo0.y() < _scr_h) if _scr else True
ok(u'A9 ★★ 桌宠窗口**真的在屏幕上**（否则 6 帧都是纯壁纸，录像等于空证据）',
   bool(pet.isVisible()) and _inside,
   u'visible=%s geo=[%d,%d,%d,%d] screen=%dx%d'
   % (pet.isVisible(), _geo0.x(), _geo0.y(), _geo0.width(), _geo0.height(),
      _scr_w, _scr_h))

# ★★ 显式短路 `_errand_ack`（no-op 必须打印出来 —— 不许静默）
_ACK_CALLS = []


def _fake_ack(*a, **k):
    _ACK_CALLS.append(a)
    print(u'   [noop] `_errand_ack` 已短路（本项只验机制；"台词由模型生成"'
          u'由 check114 H8 覆盖）  args=%r' % (a[:3],))


pet._errand_ack = _fake_ack
print(u'   [setup] 已把实例的 `_errand_ack` 换成记录器（类方法未被改动）')
_snap(u'k000_boot', u'起实例后（未派差事）')

# ===========================================================================
sec(u'B. ★★★ 门控的拒绝面（用户点名的例子：暗之民无球不能进光世界）')
pet._npc_talking = _SUSIE           # 让"苏西"是发起者（不能派自己 ⇒ 派 Ralsei）
_r_ralsei_before = roam.resident_of(u'ralsei') if roam is not None else None
_n_board_before = len(board)
_hist_before = len(pet.npc_memory.history(u'ralsei')) if pet.npc_memory else 0
_scene_b = pet._npc_scene_id()

_hit = pet.handle_errand_command(u'让 ralsei 去三角符文 拿点东西')
ok(u'B1 ★ 这句话**被识别为派活**（入口认出来了）', bool(_hit))

# ★★ 目的地落在哪个世界：交给产品自己判（不在这里复算）
_dest_b = pet._errand_scene_in(u'ch1')
ok(u'B2 目的地解析到三角符文那一侧（ch1.*）',
   isinstance(_dest_b, str) and _dest_b.startswith(u'ch1.'),
   u'dest=%s' % _dest_b)
_world_b = pet._npc_errand_world(_dest_b) if _dest_b else None
ok(u'B3 该目的地的世界 = light（所以 Ralsei 无球进不去）',
   _world_b == u'light', u'world=%s' % _world_b)

ok(u'B4 ★★★ **门控真拦住了**：看板里没多出这条差事',
   len(board) == _n_board_before and board.active_of(u'ralsei') is None,
   u'len %d -> %d' % (_n_board_before, len(board)))
ok(u'B5 ★★ 位置真源**没被改写**（他没被"送出去"）',
   roam is not None and roam.resident_of(u'ralsei') == _r_ralsei_before,
   u'%s -> %s' % (_r_ralsei_before, roam.resident_of(u'ralsei') if roam else None))
ok(u'B6 ★ 与显示解耦（被拒也不动我的画面）', pet._npc_scene_id() == _scene_b)

_hist_after = len(pet.npc_memory.history(u'ralsei')) if pet.npc_memory else 0
_has_deny = False
if pet.npc_memory is not None:
    for _it in pet.npc_memory.history(u'ralsei'):
        if isinstance(_it, dict) and (u'去不了' in (_it.get('text') or '')):
            _has_deny = True
_B7 = ok(u'B7 ★★ "办不成"也**留下结果**：他记忆里多了一条"去不了"',
         _hist_after > _hist_before and _has_deny,
         u'hist %d -> %d  命中=%s' % (_hist_before, _hist_after, _has_deny))
if not _B7:
    print(u'   [note] 这一条是**产品缺口**（不是判据问题）：'
          u'`handle_errand_command` 是"先问路、后派人"，被拒时**不会**走到 '
          u'`assign_errand`，而"去不了"原本只写在 `assign_errand` 内部。')
ok(u'B8 ★ 回应仍交给模型（`_errand_ack` 真被调过）', len(_ACK_CALLS) >= 1,
   u'calls=%d' % len(_ACK_CALLS))
_snap(u'k001_denied', u'Ralsei 无球被派去光世界 ⇒ 被拒（看板仍空）')

# ===========================================================================
sec(u'C. ★★★ 门控的放行面（用户主用例：让 ralsei 去 oneshot 办事）')
# ★ 发起者仍是苏西（不能派自己）——用户主用例说的就是"**让 ralsei** 去"。
_n_board_c = len(board)
_hit2 = pet.handle_errand_command(u'让 ralsei 去 oneshot 帮我拿个东西')
ok(u'C1 ★ 识别为派活', bool(_hit2))
_e = board.active_of(u'ralsei') if board is not None else None
ok(u'C2 ★★★ 看板里真多了这位被派的人', _e is not None,
   u'active=%s' % (sorted(board.by_npc().keys()) if board else None))
ok(u'C3 ★★ 目的地落在 oneshot 那一侧',
   _e is not None and _e.dest_scene.startswith(u'oneshot.'),
   u'dest=%s' % (getattr(_e, 'dest_scene', None),))
ok(u'C4 ★ "事"被解析出来了（不是空串）',
   _e is not None and bool((_e.what or u'').strip()),
   u'what=%r' % (getattr(_e, 'what', None),))
ok(u'C5 ★ 立刻 = traveling（不是瞬移）',
   _e is not None and _e.status == u'traveling',
   u'status=%s' % (getattr(_e, 'status', None),))
ok(u'C6 ★★ 与显示解耦：**我的当前场景一字不变**',
   pet._npc_scene_id() == _scene_b,
   u'%s -> %s' % (_scene_b, pet._npc_scene_id()))
ok(u'C7 ★ 看板比派活前多了一条', len(board) > _n_board_c,
   u'%d -> %d' % (_n_board_c, len(board)))
ok(u'C8 ★ 回应交给模型（`_errand_ack` 被调过第 2 次）', len(_ACK_CALLS) >= 2,
   u'calls=%d' % len(_ACK_CALLS))
# ★★ B/C 成对：同一个 ralsei —— 光世界**进不去**，别的暗世界**能去**
ok(u'C9 ★★★ **B/C 成对**：同一个人（ralsei），光世界被拒、别的暗世界被放行 ⇒ '
     u'门控是"按世界判"而不是"一刀切拦住"',
   _e is not None and _world_b == u'light' and pet._npc_errand_world(_e.dest_scene) == u'dark',
   u'B世界=%s（拒） C世界=%s（放行）'
   % (_world_b, pet._npc_errand_world(_e.dest_scene) if _e else None))
_snap(u'k002_dispatched', u'Ralsei 被派去 oneshot（traveling）')

# ===========================================================================
sec(u"C'. ★★★ 跨作品回家（第114轮修掉的别名缺口，成对正负控制）")
_world_pap_ut = pet._npc_errand_world(u'ut.rooms.room_start')
_g_pap_ut = _NSYS.world_gate(pet.npc_registry.get(_PAP), _world_pap_ut,
                             scene_id=u'ut.rooms.room_start', carried=False)
ok(u"C'1 ★★ `ut` 这一侧的世界判成 dark（保守侧：判不出 ⇒ 不许去）",
   _world_pap_ut == u'dark', u'world=%s' % _world_pap_ut)
ok(u"C'2 ★★★ **修好后**：Papyrus 回自己作品那侧**放行**",
   bool(_g_pap_ut), u'ok=%s detail=%s' % (_g_pap_ut.ok, _g_pap_ut.detail))
ok(u"C'3 ★ 放行理由码就是 `home_production:ut`（走的是别名归一那一条）",
   _g_pap_ut.detail == u'home_production:ut', u'detail=%s' % _g_pap_ut.detail)

# ---- 负控制一：把别名表拆干净 ⇒ 同一句必须翻成拒绝 ----
_BAK = dict(_NSYS.CHAPTER_ALIASES)
_NSYS.CHAPTER_ALIASES.clear()
_g_off = _NSYS.world_gate(pet.npc_registry.get(_PAP), _world_pap_ut,
                          scene_id=u'ut.rooms.room_start', carried=False)
ok(u"C'4 ★★★ 负控制：**拆掉别名表** ⇒ 同一句必须翻成**拒绝**"
     u'（隔离别名就是这条通路的原因，否则 C\'2 是恒真的）',
   (not _g_off.ok) and _g_off.reason == _NSYS.REASON_FOREIGN_DARK,
   u'ok=%s reason=%s' % (_g_off.ok, _g_off.reason))
_NSYS.CHAPTER_ALIASES.update(_BAK)
_g_on = _NSYS.world_gate(pet.npc_registry.get(_PAP), _world_pap_ut,
                         scene_id=u'ut.rooms.room_start', carried=False)
ok(u"C'5 ★★ 还原 ⇒ 又放行（证明 C'4 只改了别名表，不是把别的状态弄坏了）",
   bool(_g_on) and _g_on.detail == u'home_production:ut',
   u'ok=%s detail=%s' % (_g_on.ok, _g_on.detail))
ok(u"C'6 ★ 还原彻底（`CHAPTER_ALIASES` 与备份逐键相等）",
   dict(_NSYS.CHAPTER_ALIASES) == _BAK,
   u'keys=%s' % (sorted(_NSYS.CHAPTER_ALIASES),))

# ---- 端到端：真从对话层派他回家 ----
pet._npc_talking = u'ralsei'
_n_board_cp = len(board)
_hist_pap_before = len(pet.npc_memory.history(_PAP)) if pet.npc_memory else 0
_hit3 = pet.handle_errand_command(u'让 %s 去 ut 看看' % _ALIAS_PAP)
ok(u"C'7 ★★ 端到端：这句话被识别为派活", bool(_hit3))
_ep = board.active_of(_PAP) if board is not None else None
ok(u"C'8 ★★★ 端到端：看板里真多了 Papyrus，且目的地是 `ut.*`",
   _ep is not None and _ep.dest_scene.startswith(u'ut.'),
   u'dest=%s' % (getattr(_ep, 'dest_scene', None),))
ok(u"C'9 ★ 看板多了一条", len(board) > _n_board_cp,
   u'%d -> %d' % (_n_board_cp, len(board)))

# ---- 负控制二：另一部作品的暗世界 ⇒ 必须拒绝 + 留痕 ----
_n_board_ct = len(board)
_hit4 = pet.handle_errand_command(u'让 %s 去 oneshot 看看' % _ALIAS_PAP)
ok(u"C'10 ★ 负控制：这句话也被识别为派活（不是没认出）", bool(_hit4))
ok(u"C'11 ★★★ 负控制：但**看板不动**（Papyrus 进不去别人的暗世界）",
   len(board) == _n_board_ct and board.active_of(_PAP) is not None
   and board.active_of(_PAP).dest_scene.startswith(u'ut.'),
   u'len %d -> %d' % (_n_board_ct, len(board)))
_hist_pap_after = len(pet.npc_memory.history(_PAP)) if pet.npc_memory else 0
_has_deny2 = False
if pet.npc_memory is not None:
    for _it in pet.npc_memory.history(_PAP):
        if isinstance(_it, dict) and (u'去不了' in (_it.get('text') or '')):
            _has_deny2 = True
ok(u"C'12 ★★ 负控制也**留下结果**（他被拒时记忆里多一条「去不了」）",
   _hist_pap_after > _hist_pap_before and _has_deny2,
   u'hist %d -> %d  命中=%s' % (_hist_pap_before, _hist_pap_after, _has_deny2))
ok(u"C'13 ★ 显示仍没被切（两次派活全程）", pet._npc_scene_id() == _scene_b,
   u'scene=%s' % pet._npc_scene_id())
_snap(u'k003_home_production', u'Papyrus 被派回 ut（跨作品回家）')

# ===========================================================================
sec(u'D. 落地 + "我中途进去能看到过程"')
_r_ralsei_b2 = roam.resident_of(u'ralsei') if roam is not None else None
_r_pap_b = roam.resident_of(_PAP) if roam is not None else None
_now = time.time()
pet._npc_errand_tick(_now + 200.0)     # travel 默认 90s ⇒ 推到 working
ok(u'D1 ★★★ 到达 ⇒ 位置真源变成目标场景（两个人都到了）',
   roam is not None
   and roam.resident_of(u'ralsei') == _e.dest_scene
   and roam.resident_of(_PAP) == _ep.dest_scene,
   u'ralsei %s -> %s（目标 %s）｜%s %s -> %s（目标 %s）'
   % (_r_ralsei_b2, roam.resident_of(u'ralsei') if roam else None, _e.dest_scene,
      _PAP, _r_pap_b, roam.resident_of(_PAP) if roam else None, _ep.dest_scene))
_expect = {(u'ralsei', _e.dest_scene), (_PAP, _ep.dest_scene)}
ok(u'D2 ★ 过程可观察（working 期间查得到"谁在哪、在办什么"）',
   set(board.working_positions()) == _expect,
   u'pos=%s' % (sorted(board.working_positions()) if board else None))
pet._npc_errand_tick(_now + 260.0)
ok(u'D3 ★ 在办期间重复推进**不抖**（幂等：还在那儿、还在办）',
   roam.resident_of(u'ralsei') == _e.dest_scene
   and roam.resident_of(_PAP) == _ep.dest_scene
   and board.working_of(u'ralsei') is not None
   and board.working_of(_PAP) is not None)

_n_other = pet._npc_seed_bodies(_ep.dest_scene)
_bodies = getattr(pet, 'npc_bodies', None) or {}
_in_other = (_PAP in _bodies)
_ral_seen = (u'ralsei' in _bodies)
pet._npc_seed_bodies(_scene_b)         # ★ 复原当前场景的身体表
ok(u'D4 ★★★ 「我中途进去能看到过程」：按驻留表在**目标场景**重建身体 ⇒ 他在里面',
   _in_other, u'%s 场景 %d 个 NPC，含 %s=%s（ralsei 也在里面=%s）'
   % (_ep.dest_scene, _n_other, _PAP, _in_other, _ral_seen))
ok(u'D5 ★ 与显示解耦（推进全程没切我的画面）', pet._npc_scene_id() == _scene_b)
_snap(u'k004_working', u'两个人都到了、正在办事（位置真源 = 各自目标场景）')

# ===========================================================================
sec(u'E. 落盘（真写盘 + 真读回；★ 写的是沙箱，不是用户档）')
_path = getattr(pet, '_npc_errand_path', None)
ok(u'E0 落盘路径已注入且**在沙箱里**',
   bool(_path) and os.path.abspath(_path).startswith(os.path.abspath(_SANDBOX)),
   u'path=%s' % (_path,))
_n_before_save = len(board)
_okw = pet._npc_errand_save(force=True)
ok(u'E1 ★ `_npc_errand_save(force=True)` ⇒ True', bool(_okw))
ok(u'E2 ★★ 盘上真有这个文件', bool(_path) and os.path.isfile(_path))
_raw = None
try:
    import io as _io
    with _io.open(_path, encoding='utf-8') as _fh:
        _raw = json.load(_fh)
except Exception as _e2:
    print(u'   [warn] 读盘异常: %r' % (_e2,))
ok(u'E3 ★★ 盘上结构 = `{enabled, active, done}`（差事自己的档）',
   isinstance(_raw, dict) and {u'enabled', u'active', u'done'} <= set(_raw),
   u'keys=%s' % (sorted(_raw) if isinstance(_raw, dict) else None))
ok(u'E4 ★ 盘上条数与内存看板一致',
   isinstance(_raw, dict) and len(_raw.get(u'active') or []) == _n_before_save,
   u'盘=%s 内存=%s' % (len((_raw or {}).get(u'active') or []), _n_before_save))
_reloaded = pet._npc_errand_load()
ok(u'E5 ★★ 读回成功且条数一致',
   _reloaded is not None and len(_reloaded) == _n_before_save,
   u'读回=%s 期望=%s' % (len(_reloaded) if _reloaded is not None else None,
                        _n_before_save))
_stepped = None
try:
    _stepped = _reloaded.step(time.time() + 1.0) if _reloaded is not None else None
    ok(u'E6 ★ 读回的档**能继续跑**（step 不抛、结构可用）',
       isinstance(_stepped, dict) and u'arrived' in _stepped)
except Exception as _e3:
    ok(u'E6 ★ 读回的档**能继续跑**（step 不抛、结构可用）', False, repr(_e3))
pet.npc_errand = board               # ★ 复原：别让读回的那份影响后面的反例

# ===========================================================================
sec(u'F. 反例：不是派活 ⇒ 什么都不发生（零回归）')
_n_before_f = len(board)
_scene_f = pet._npc_scene_id()
_hit5 = pet.handle_errand_command(u'今天天气不错，一会儿去吃饭')
ok(u'F1 ★ 普通闲聊 ⇒ 返回 False（不是派活）', not _hit5)
_hit6 = pet.handle_errand_command(u'让苏西去')
ok(u'F2 ★ 有角色没地点 ⇒ 返回 False（宁可漏判，不可误判）', not _hit6)
ok(u'F3 ★ 看板一字不动', len(board) == _n_before_f,
   u'%d -> %d' % (_n_before_f, len(board)))
ok(u'F4 ★ 显示场景一字不动', pet._npc_scene_id() == _scene_f)
# ★★ 帧的**几何**不变量：透明分层窗口在抓屏里"看不出在哪"（§73.8），
#    所以"没多出窗口 / 没被全屏化"要用**几何**证，而不是用肉眼比对图片。
#    ⚠️ 第一版判据写的是"六个快照几何**逐个相等**" —— **太脆**：桌宠窗口按当前
#       精灵帧自适应宽高，换一帧就变（实测三次跑出 144x98 / 100x100 / 39x83）。
#       真正要守的不变量是"**没有任何一个窗口是接近全屏的**"（全屏 = 切了场景画布）。
_geos = [tuple(s['pet_geo']) for s in _SNAPS if s.get('pet_geo')]
_scr_rec = (_SNAPS[0].get('screen') or [0, 0]) if _SNAPS else [0, 0]
_thw = max(320, int(_scr_rec[0]) // 2)
_thh = max(320, int(_scr_rec[1]) // 2)
_big = [g for g in _geos if g[2] >= _thw or g[3] >= _thh]
ok(u'F5 ★★ **每个**快照都取到了窗口几何（非恒真护栏：不许 `None` 混进集合里蒙混）',
   len(_geos) == len(_SNAPS) and len(_SNAPS) >= 5,
   u'取到几何 %d/%d 条' % (len(_geos), len(_SNAPS)))
ok(u'F6 ★★★ 没有任何一次快照出现"接近全屏"的窗口'
     u'（全屏 = 切了场景画布 ⇒ "与显示解耦"就被打破了）',
   bool(_geos) and not _big,
   u'阈值 %dx%d｜最大边长 %s｜出现过的几何=%s'
   % (_thw, _thh,
      max((max(g[2], g[3]) for g in _geos), default=None),
      sorted(set(_geos))))
_snap(u'k005_noop', u'反例：闲聊与半句话都不触发派活')

# ===========================================================================
sec(u'G. 收尾')
try:
    pet.close()
except Exception:
    pass
ok(u'G1 ★ 收尾无异常；沙箱留在原地备查（绝不 rmtree —— 本机清理守卫会拦）',
   os.path.isdir(_SANDBOX), u'sandbox=%s' % _SANDBOX)

_report = {
    'round': 114, 'is_real': IS_REAL, 'pass': _N['p'], 'fail': _N['f'],
    'scene': _scene_b, 'susie': _SUSIE, 'papyrus_alias': _ALIAS_PAP,
    'deny_dest': _dest_b, 'sandbox': _SANDBOX, 'vault_patched': _VAULT_PATCHED,
    'snaps': _SNAPS, 'lines': _OUT,
}
_rp = os.path.join(_EV, 'rec114_report.json')
with open(_rp, 'w', encoding='utf-8') as fh:
    json.dump(_report, fh, ensure_ascii=False, indent=1)
print(u'\n---- rec114：%d PASS / %d FAIL  真机=%s  PNG=%d ----'
      % (_N['p'], _N['f'], IS_REAL, len([s for s in _SNAPS if s.get('png')])))
print(u'报告 = %s' % _rp)
sys.exit(1 if _N['f'] else 0)
