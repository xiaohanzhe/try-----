# -*- coding: utf-8 -*-
"""第113轮变异测试：证明本轮判据**真的有鉴别力**（不是恒真）。

★ 纪律（历轮血泪）：
  · **"夹具不保真 = 报假问题"**、**"夹具不破坏 = 全绿比报红更危险"** ⇒ 每个变异
    必须让**至少一条**判据报红；没报红的如实登记 `MISSED`。
  · 变异一律**改副本**（系统 temp），**绝不改工作区真文件**。
  · 变异锚点**禁用 `replace(old,new,1)`** —— 一律唯一长锚点 + 断言恰好命中 1 处。
  · 跑完**必须还原**（`finally` 兜底 + 逐文件 sha256 回验）。
  · ★ 锚点换行无关：`npc_errand.py` 是 LF、`main.py` 是 CRLF，`sub_once` 两种都试。

跑法：
    C:\\Python311\\python.exe mutate113.py
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
    'npc_errand': os.path.join('ralsei_pet', 'modules', 'npc_errand.py'),
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

    ★★ CRLF 陷阱：`main.py` 是 CRLF、`npc_errand.py` 是 LF ⇒ 锚点两种换行都试。
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
    """在**临时副本**上跑 check113。"""
    r = subprocess.run([PY, 'check113.py'], cwd=TMP_TOOLS,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return r.returncode, r.stdout.decode('utf-8', 'replace')


# ---------------------------------------------------------------------------
# ★★ 每次建**唯一**临时目录（`mkdtemp`）—— **绝不 `rmtree`**：
#    本环境的清理守卫会累计"删除次数"，到阈值后**整个 python 进程在 import 期被 SIGTERM**
#    （症状 = 零输出 + 退出码 1，极难查；见详版「清理守卫」条）。
TMP = tempfile.mkdtemp(prefix='mutate113_')
TMP_TOOLS = os.path.join(TMP, 'code-quality-audit',
                         u'第113轮-灵魂视角差事', '_tools')

_orig_hash = {k: sha(os.path.join(ROOT, v)) for k, v in REL.items()}

shutil.copytree(os.path.join(ROOT, 'ralsei_pet'), os.path.join(TMP, 'ralsei_pet'))
os.makedirs(TMP_TOOLS)
shutil.copy2(os.path.join(HERE, 'check113.py'), os.path.join(TMP_TOOLS, 'check113.py'))


def tpath(key):
    return os.path.join(TMP, REL[key])


print(u'==== mutate113 ====')
print(u'临时区 = %s' % TMP)

results = []


def mutate(tag, key, old, new, expect_red=True):
    """施加一个变异 ⇒ 跑 check113 ⇒ 记录是否报红 ⇒ **还原**。"""
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
            print(u'    ---- 末尾 ----')
            for ln in out.strip().splitlines()[-6:]:
                print(u'    ' + ln)
        results.append((tag, status, u'FAIL=%d' % n_fail))
    finally:
        write(p, before)
        assert sha(p) == h_before, u'还原失败: %s' % key


# ===========================================================================
# M0 no-op 对照（证明"跑一次不报红"是可能的 ⇒ 判据不是恒红）
# ===========================================================================
mutate(u'M0 no-op（注释级改动，**应当不报红**）',
       'npc_errand',
       u"import collections\n",
       u"import collections  # noqa\n",
       expect_red=False)

# ===========================================================================
# A 零依赖线
# ===========================================================================
mutate(u'M1 顶层多 import 一个项目模块（A1/A3 应报红）',
       'npc_errand',
       u"import collections\n",
       u"import collections\nimport data_store\n")

mutate(u'M2 函数内 import（A2 应报红）',
       'npc_errand',
       u"    return '%s 在 %s 办完了「%s」。' % (npc_id, dest_scene, what)\n",
       u"    import json\n    return '%s 在 %s 办完了「%s」。' % (npc_id, dest_scene, what)\n")

# ===========================================================================
# B 生命周期线
# ===========================================================================
mutate(u'M3 traveling 期也返回 dest（"在路上"变成"已到达" ⇒ B2 应报红）',
       'npc_errand',
       u"        return self.dest_scene if self.status in (WORKING, DONE) else None\n",
       u"        return self.dest_scene\n")

mutate(u'M4 scene_now 恒 None（working 也拿不到位置 ⇒ B5 应报红）',
       'npc_errand',
       u"        return self.dest_scene if self.status in (WORKING, DONE) else None\n",
       u"        return None\n")

mutate(u'M5 working_positions 恒空（宿主永远压不上覆盖 ⇒ B6 应报红）',
       'npc_errand',
       u"        return [(e.npc_id, e.dest_scene) for e in self._active.values()\n"
       u"                if e.status == WORKING]\n",
       u"        return []\n")

mutate(u'M6 完成时 result 恒空（"产生结果"落空 ⇒ B8 应报红）',
       'npc_errand',
       u"                e.result = e.custom_result or default_result(\n",
       u"                e.result = '' and default_result(\n")

# ===========================================================================
# C 主体泛化线（用户口径「任何人都可以」）
# ===========================================================================
mutate(u'M7 assign 加角色白名单（违背"任何人都可以" ⇒ C1/C2 应报红）',
       'npc_errand',
       u"        if not (isinstance(dest_scene, str) and dest_scene):\n            return None\n",
       u"        if not (isinstance(dest_scene, str) and dest_scene):\n"
       u"            return None\n        if npc_id != 'ralsei':\n            return None\n")

# ===========================================================================
# D 解耦线
# ===========================================================================
mutate(u'M8 模块里出现显示侧名字 switch（D1 应报红）',
       'npc_errand',
       u"        self.enabled = bool(enabled)\n",
       u"        self.enabled = bool(enabled)\n        self.switch = None\n")

# ===========================================================================
# E 接线线（main）
# ===========================================================================
mutate(u'M9 errand_tick 插到 roam_tick **之前**（顺序反 ⇒ E5 应报红）',
       'main',
       u"        self._npc_roam_tick(current_time)\n",
       u"        self._npc_errand_tick(current_time)\n"
       u"        self._npc_roam_tick(current_time)\n")

mutate(u'M10 _npc_errand_tick 不调 roam.put（在办的人压不上 ⇒ E2 应报红）',
       'main',
       u"                roam.put(nid, dest, now,\n",
       u"                roam.get(nid, dest, now,\n")

mutate(u'M11 _npc_errand_tick 不调 roam.drop（办完不撤覆盖 ⇒ E3 应报红）',
       'main',
       u"                roam.drop(nid)\n",
       u"                roam.get(nid)\n")

mutate(u'M12 _npc_errand_tick 不重建身体（人到了画还在旧场景 ⇒ E4 应报红）',
       'main',
       u"                self._npc_seed_bodies(self._npc_scene_id())\n"
       u"                self._npc_plan_save()\n"
       u"        except Exception as e:\n"
       u"            _log.debug('差事推进异常（本节拍跳过）: %s', e)\n",
       u"                self._npc_plan_save()\n"
       u"        except Exception as e:\n"
       u"            _log.debug('差事推进异常（本节拍跳过）: %s', e)\n")

mutate(u'M13 _npc_errand_commit 不调 remember（结果不落记忆 ⇒ E6 应报红）',
       'main',
       u"            mem.remember(npc_id, '（%s）' % txt, who=npc_id)\n",
       u"            pass  # mem.remember(npc_id, '（%s）' % txt, who=npc_id)\n")

mutate(u'M14 assign_errand 不调 board.assign（唯一入口变空壳 ⇒ E7 应报红）',
       'main',
       u"            return board.assign(now, npc_id, dest_scene, what, **kw)\n",
       u"            return None\n")

mutate(u'M15 开关不被 _npc_errand_tick 读（假开关 ⇒ E9 应报红）',
       'main',
       u"        if not RalseiPet.NPC_ERRAND_ENABLED:\n"
       u"            return {'arrived': [], 'finished': []}\n"
       u"        board = getattr(self, 'npc_errand', None)\n",
       u"        board = getattr(self, 'npc_errand', None)\n")

# ===========================================================================
# F 零回归线
# ===========================================================================
mutate(u'M16 关闸失效：assign 无视 enabled（F2 应报红）',
       'npc_errand',
       u"        if not self.enabled:\n            return None\n"
       u"        if not (isinstance(npc_id, str) and npc_id):\n",
       u"        if not (isinstance(npc_id, str) and npc_id):\n")

mutate(u'M17 关闸失效：step 无视 enabled（F2 应报红）',
       'npc_errand',
       u"        out = {'arrived': [], 'finished': []}\n"
       u"        if not self.enabled:\n            return out\n"
       u"        try:\n            now = float(now)\n",
       u"        out = {'arrived': [], 'finished': []}\n"
       u"        try:\n            now = float(now)\n")

# ===========================================================================
# G 序列化线
# ===========================================================================
mutate(u'M18 坏数据被"半成品还原"（缺时间字段也收 ⇒ G2 应报红）',
       'npc_errand',
       u"        except (TypeError, ValueError, KeyError):\n            return None\n",
       u"        except (TypeError, ValueError, KeyError):\n"
       u"            start = arrive_at = finish_at = 0.0\n")

# ===========================================================================
n_caught = sum(1 for r in results if r[1] == 'CAUGHT')
n_missed = sum(1 for r in results if r[1] == 'MISSED')
n_skip = sum(1 for r in results if r[1] == 'SKIP')
n_noop = sum(1 for r in results if r[1] == 'OK(no-op)')

# ---- 还原核验：工作区真文件 sha256 必须与开始时一致 ----
_dirty = [k for k, v in REL.items()
          if sha(os.path.join(ROOT, v)) != _orig_hash[k]]
print(u'==== mutate113: 变异 %d ｜ CAUGHT=%d ｜ MISSED=%d ｜ SKIP=%d ｜ no-op=%d ｜ 工作区%s ===='
      % (len(results), n_caught, n_missed, n_skip, n_noop,
         u'干净' if not _dirty else u'**脏** %s' % _dirty))

if n_missed or n_skip or _dirty:
    sys.exit(1)
sys.exit(0)
