# -*- coding: utf-8 -*-
"""第114轮变异测试：证明本轮判据**真的有鉴别力**（不是恒真）。

★ 纪律（历轮血泪）：
  · **"夹具不保真 = 报假问题"**、**"夹具不破坏 = 全绿比报红更危险"** ⇒ 每个变异
    必须让**至少一条**判据报红；没报红的如实登记 `MISSED`。
  · 变异一律**改副本**（系统 temp），**绝不改工作区真文件**。
  · 变异锚点**禁用 `replace(old,new,1)`** —— 一律唯一长锚点 + 断言恰好命中 1 处。
  · 跑完**必须还原**（`finally` 兜底 + 逐文件 sha256 回验）。
  · ★ 锚点换行无关：`npc_errand.py` / `npc_system.py` 是 LF、`main.py` /
    `dialogue_ui.py` 是 CRLF，`sub_once` 两种都试。

覆盖的六条线（对 `check114` 的 A~H 段）：
  A 世界判定 · B 门控 · C 别名归一 · D main 接线 · E 落盘 ·
  G/H 派发入口与对话层接线 · （外加 `npc_errand.abort` 机制）

跑法：
    C:\\Python311\\python.exe mutate114.py
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PY = sys.executable if sys.executable else 'C:/Python311/python.exe'

REL = {
    'errand': os.path.join('ralsei_pet', 'modules', 'npc_errand.py'),
    'system': os.path.join('ralsei_pet', 'modules', 'npc_system.py'),
    'ui': os.path.join('ralsei_pet', 'modules', 'dialogue_ui.py'),
    'main': os.path.join('ralsei_pet', 'src', 'main.py'),
}


def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()


def read(p):
    return io.open(p, 'r', encoding='utf-8', newline='').read()


def write(p, s):
    io.open(p, 'w', encoding='utf-8', newline='').write(s)


def sub_once(text, old, new, tag):
    """只替换一次，且**断言恰好命中 1 处**。

    ★★ CRLF 陷阱：`main.py`/`dialogue_ui.py` 是 CRLF、两个 modules 是 LF
    ⇒ 锚点两种换行都试。
    """
    variants = [old]
    if '\n' in old and '\r\n' not in old:
        variants.append(old.replace('\n', '\r\n'))
    for v in variants:
        if text.count(v) == 1:
            nl = '\r\n' if '\r\n' in v else '\n'
            return text.replace(v, new.replace('\n', nl), 1)
    n = text.count(old)
    raise AssertionError(u'[%s] 锚点命中 %d 次（应为 1）：%r' % (tag, n, old[:70]))


def run_check(timeout=300):
    r = subprocess.run([PY, 'check114.py'], cwd=TMP_TOOLS,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return r.returncode, r.stdout.decode('utf-8', 'replace')


# ---------------------------------------------------------------------------
# ★★ 每次建**唯一**临时目录（`mkdtemp`）—— **绝不 `rmtree`**：
#    本环境的清理守卫会累计"删除次数"，到阈值后**整个 python 进程在 import 期被 SIGTERM**
#    （症状 = 零输出 + 退出码 1，极难查；见详版「清理守卫」条）。
TMP = tempfile.mkdtemp(prefix='mutate114_')
TMP_TOOLS = os.path.join(TMP, 'code-quality-audit',
                         u'第114轮-差事世界门控与派发', '_tools')

_orig_hash = {k: sha(os.path.join(ROOT, v)) for k, v in REL.items()}

shutil.copytree(os.path.join(ROOT, 'ralsei_pet'), os.path.join(TMP, 'ralsei_pet'))
os.makedirs(TMP_TOOLS)
shutil.copy2(os.path.join(HERE, 'check114.py'), os.path.join(TMP_TOOLS, 'check114.py'))


def tpath(key):
    return os.path.join(TMP, REL[key])


print(u'==== mutate114 ====')
print(u'临时区 = %s' % TMP)

results = []


def mutate(tag, key, old, new, expect_red=True):
    """施加一个变异 ⇒ 跑 check114 ⇒ 记录是否报红 ⇒ **还原**。"""
    p = tpath(key)
    before = read(p)
    h_before = sha(p)
    try:
        after = sub_once(before, old, new, tag)
    except AssertionError as e:
        print(u'[SKIP] %s：%s' % (tag, e))
        results.append((tag, 'SKIP', ''))
        return
    write(p, after)
    try:
        rc, out = run_check()
        red = (rc != 0) or ('[FAIL]' in out)
        n_fail = out.count('[FAIL]')
        if expect_red:
            status = 'CAUGHT' if red else 'MISSED'
        else:
            status = 'OK(no-op)' if not red else 'UNEXPECTED-RED'
        print(u'[%s] %s  (FAIL=%d)' % (status, tag, n_fail))
        if status in ('MISSED', 'UNEXPECTED-RED'):
            print(u'    ---- 首个 FAIL ----')
            for ln in out.splitlines():
                if ln.startswith('[FAIL]'):
                    print(u'    ' + ln)
                    break
            print(u'    ---- 末尾 ----')
            for ln in out.strip().splitlines()[-4:]:
                print(u'    ' + ln)
        results.append((tag, status, u'FAIL=%d' % n_fail))
    finally:
        write(p, before)
        assert sha(p) == h_before, u'还原失败: %s' % key


# ===========================================================================
# M0 no-op 对照（证明"跑一次不报红"是可能的 ⇒ 判据不是恒红）
# ===========================================================================
mutate(u'M0 no-op（注释级改动，**应当不报红**）',
       'errand',
       u"FILENAME = 'npc_errands.json'\n",
       u"FILENAME = 'npc_errands.json'  # noqa\n",
       expect_red=False)

# ===========================================================================
# A 世界判定线（`_npc_errand_world_uncached` 的三条口径）
# ===========================================================================
mutate(u'A-M1 迁入章兜底由 `dark` 改成 `light`'
       u'（Ralsei 去 oneshot 会在光世界分支被"要球"拦死 ⇒ A6/B1 应报红）',
       'main',
       u"        except Exception as e:\n"
       u"            _log.debug('差事目的地世界判定失败（按暗世界处理）: %s', e)\n"
       u"        return npc_system_mod.WORLD_DARK\n",
       u"        except Exception as e:\n"
       u"            _log.debug('差事目的地世界判定失败（按暗世界处理）: %s', e)\n"
       u"        return npc_system_mod.WORLD_LIGHT\n")

mutate(u'A-M2 空 / 非字符串目的地早返回由 `dark` 改成 `light`（A7 应报红）',
       'main',
       u"        if not isinstance(dest_scene, str) or not dest_scene:\n"
       u"            return npc_system_mod.WORLD_DARK\n",
       u"        if not isinstance(dest_scene, str) or not dest_scene:\n"
       u"            return npc_system_mod.WORLD_LIGHT\n")

mutate(u'A-M3 忽略 `overrides`（桌面不再判成 light ⇒ A2 应报红）',
       'main',
       u"            if dest_scene in ov and ov[dest_scene] in ('light', 'dark'):\n"
       u"                return ov[dest_scene]\n",
       u"            if False:\n"
       u"                return ov[dest_scene]\n")

# ===========================================================================
# B 门控线（`_npc_errand_gate`）
# ===========================================================================
mutate(u'B-M4 门控**恒放行**（用户点名的例子拦不住 ⇒ B2 应报红）',
       'main',
       u"        if g.ok:\n"
       u"            return True, g.detail or ''\n"
       u"        return False, (g.detail or '他去不了那里')\n",
       u"        return True, ''\n")

mutate(u'B-M5 门控**恒拒绝**（主用例也被拦 ⇒ B1 应报红）',
       'main',
       u"        if g.ok:\n"
       u"            return True, g.detail or ''\n"
       u"        return False, (g.detail or '他去不了那里')\n",
       u"        return False, 'nope'\n")

mutate(u'B-M6 不喂 `carried`（写死 False ⇒ "只加球就放行"那条成对判据 B3 应报红）',
       'main',
       u"            carried = npc_id in (self._npc_carried_ids() or [])\n",
       u"            carried = False\n")

mutate(u'B-M7 喂**错的世界**（一律 light ⇒ 暗世界那一批结论全翻 ⇒ B 段应报红）',
       'main',
       u"        world = self._npc_errand_world(dest_scene)\n",
       u"        world = npc_system_mod.WORLD_LIGHT\n")

# ===========================================================================
# C 别名归一线（`npc_system`）
# ===========================================================================
mutate(u'C-M8 `chapter_matches` 退回逐字比（`ut`/`uty` 与全名不再等价'
       u'⇒ B5（UT 角色回不了家）应报红）',
       'system',
       u"    for n in (names or ()):\n"
       u"        if same_chapter(ch, n):\n"
       u"            return True\n"
       u"    return False\n",
       u"        return ch in (names or ())\n")

mutate(u'C-M9 `CHAPTER_ALIASES` 清空（别名表没了 ⇒ B5/B6 应报红）',
       'system',
       u"CHAPTER_ALIASES = {\n"
       u"    'ut': ('undertale',),\n"
       u"    'uty': ('undertale_yellow',),\n"
       u"}\n",
       u"CHAPTER_ALIASES = {}\n")

mutate(u'C-M10 `world_gate` 的 `home_production` 分支退回**逐字比**'
       u'（走另一条老写法，证明两处都守住了 ⇒ B5 应报红）',
       'system',
       u"        if ch is not None and chapter_matches(ch, npc.chapters):\n"
       u"            return GateResult(True, REASON_OK, 'home_production:%s' % ch)\n",
       u"        if ch is not None and ch in npc.chapters:\n"
       u"            return GateResult(True, REASON_OK, 'home_production:%s' % ch)\n")

# ===========================================================================
# D main 接线线
# ===========================================================================
mutate(u'D-M11 每拍**不再过门控**（`roam.put` 前面那道闸没了 ⇒ C5 应报红）',
       'main',
       u"                _ok, _why = self._npc_errand_gate(nid, dest)\n",
       u"                _ok, _why = True, ''\n")

mutate(u'D-M12 被拦下**不 `abort`**（那人会被永久钉在进不去的场景 ⇒ C 段应报红）',
       'main',
       u"                    board.abort(nid)\n",
       u"                    pass\n")

mutate(u'D-M13 被拦下**不落记忆**（"办不成"静默丢弃 ⇒ C 段应报红）',
       'main',
       u"                self._npc_errand_note(\n"
       u"                    nid, '我本来要去 %s，但去不了 —— %s' % (dest, _why))\n",
       u"                pass\n")

mutate(u'D-M14 顺序变了之后**不落盘**（差事只活在内存 ⇒ C 段应报红）',
       'main',
       u"                self._npc_plan_save()\n"
       u"                # ★★ 第114轮：差事也落盘（自己的档 = `npc_errands.json`）。\n"
       u"                #    与生活档案分开两本的理由见 `npc_errand.FILENAME` 的注释。\n"
       u"                self._npc_errand_save()\n",
       u"                self._npc_plan_save()\n")

mutate(u'D-M15 读回时**不继承当前开关**（复活档里的 enabled ⇒ C8 应报红）',
       'main',
       u"                _er.enabled = (bool(RalseiPet.NPC_ERRAND_ENABLED)\n"
       u"                               and bool(RalseiPet.NPC_AUTONOMOUS_MOVE))\n",
       u"                _er.enabled = True\n")

mutate(u'D-M16 `assign_errand` **派发当场不再问路**（用户当场收不到"去不了"'
       u'⇒ B 段/rec114 那条路径应报红）',
       'main',
       u"        ok, why = self._npc_errand_gate(npc_id, dest_scene)\n"
       u"        if not ok:\n"
       u"            _log.info('差事被门控拒绝：%s → %s（%s）', npc_id, dest_scene, why)\n"
       u"            self._npc_errand_note(npc_id,\n"
       u"                                  '我本来要去 %s，但去不了 —— %s' % (dest_scene, why))\n"
       u"            return None\n",
       u"        pass\n")

# ===========================================================================
# G/H 派发入口线
# ===========================================================================
mutate(u'G-M17 去掉"不能派自己"这一步（人能把自己派出门 ⇒ G7 应报红）',
       'main',
       u"        if target_id == (self._npc_talking or 'ralsei'):\n"
       u"            return None\n",
       u"        if False:\n"
       u"            return None\n")

mutate(u'G-M18 去掉**地点词的词边界**（`but` 里的 `ut` 被当成地名 ⇒ G9 应报红）',
       'main',
       u"                if not ((b.isascii() and b.isalnum())\n"
       u"                        or (a.isascii() and a.isalnum())):\n"
       u"                    ph.append((len(alias), i, prefix))\n",
       u"                if True:\n"
       u"                    ph.append((len(alias), i, prefix))\n")

mutate(u'H-M19 入口被拒时**不落记忆**（就是本轮修掉的那个真缺口 ⇒ H13 应报红）',
       'main',
       u"            self._npc_errand_note(target_id,\n"
       u"                                  '我本来要去 %s，但去不了 —— %s' % (dest_scene, why))\n",
       u"            pass\n")

mutate(u'H-M20 `dialogue_ui` 不再去取入口（对话层断开 ⇒ H11/H12 应报红）',
       'ui',
       u"            _errand_fn = getattr(self.parent, 'handle_errand_command', None)\n",
       u"            _errand_fn = None\n")

# ===========================================================================
# 机制线（`npc_errand.abort`）
# ===========================================================================
mutate(u'D-M21 `abort` 变成空操作（半途作废失效 ⇒ D2/D3 应报红）',
       'errand',
       u"        return self._active.pop(npc_id, None)\n",
       u"        return None\n")

# ===========================================================================
n_caught = sum(1 for r in results if r[1] == 'CAUGHT')
n_missed = sum(1 for r in results if r[1] == 'MISSED')
n_skip = sum(1 for r in results if r[1] == 'SKIP')
n_noop = sum(1 for r in results if r[1] == 'OK(no-op)')

# ---- 还原核验：工作区真文件 sha256 必须与开始时一致 ----
_dirty = [k for k, v in REL.items()
          if sha(os.path.join(ROOT, v)) != _orig_hash[k]]
print(u'==== mutate114: 变异 %d ｜ CAUGHT=%d ｜ MISSED=%d ｜ SKIP=%d ｜ no-op=%d ｜ 工作区%s ===='
      % (len(results), n_caught, n_missed, n_skip, n_noop,
         u'干净' if not _dirty else u'**脏** %s' % _dirty))

if n_missed or n_skip or _dirty:
    sys.exit(1)
sys.exit(0)
