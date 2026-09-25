# -*- coding: utf-8 -*-
"""第48轮 · 回归套件「鉴别力体检」——逐条把要守的东西改坏，确认它真的报红。

为什么必须做（本项目纪律）：
    一个守不住的判据比不写还危险 —— 它看着在守，其实恒绿。
    ⇒ **鉴别力体检必改文件**：改盘上真文件、跑真套件、看真报红，再还原。

做法：对每个病例 ① 备份原文（内存）→ ② 精确替换 → ③ 跑套件收集 `[FAIL] <id>`
→ ④ **写回原文** → ⑤ 记下"期望报红的判定 id"与"实得"。最后统一校验：
还原后 hash 与初始一致 + 套件回到 FAIL=0。

用法（在仓库根跑）::

    C:\\Python311\\python.exe "code-quality-audit/第48轮-道具与背包系统/_tools/disc_items48.py"
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROUND))
PET = os.path.join(REPO, 'ralsei_pet')
MOD = os.path.join(PET, 'modules')
ITEMS = os.path.join(PET, 'assets', 'items')
SCENES = os.path.join(PET, 'assets', 'scenes')
SUITE = os.path.join(ROUND, 'verify_items48.py')
PY = sys.executable

CASES = [
    {
        'id': 'P1', 'what': '把用户原话改一个字（神秘力量）',
        'path': os.path.join(MOD, 'item_system.py'),
        'old': "MSG_MYSTERY = '一股神秘的力量阻止了你'",
        'new': "MSG_MYSTERY = '一股神秘的力量阻止了你们'",
        # ★ 只该命中 C2 —— 它是全套件**唯一**把用户原话写成字面量的锚点；
        #   C3/C5 用 `IS.MSG_MYSTERY` 比较（守通路，不守字面值）。
        'expect': ['C2'],
    },
    {
        'id': 'P2', 'what': '把 use() 里的优先级反转（先判异域、后判垃圾）',
        'path': os.path.join(MOD, 'item_system.py'),
        'old': ("""        if slot.junked:
            return UseOutcome(VERDICT_JUNK, VERDICT_MESSAGE[VERDICT_JUNK],
                              slot.item, 0, False, index)

        reason = self.blocked_reason(slot, world)
        if reason is not None:
            self.mystery_hits += 1
            _log.info('使用道具被阻止（%s）：%s', reason, slot.display_name)
            return UseOutcome(VERDICT_MYSTERY, MSG_MYSTERY, slot.item, 0, False, index)
"""),
        'new': ("""        reason = self.blocked_reason(slot, world)
        if reason is not None:
            self.mystery_hits += 1
            _log.info('使用道具被阻止（%s）：%s', reason, slot.display_name)
            return UseOutcome(VERDICT_MYSTERY, MSG_MYSTERY, slot.item, 0, False, index)

        if slot.junked:
            return UseOutcome(VERDICT_JUNK, VERDICT_MESSAGE[VERDICT_JUNK],
                              slot.item, 0, False, index)
"""),
        'expect': ['C4'],
    },
    {
        'id': 'P3', 'what': '把「设置不应用」的开关打开',
        'path': os.path.join(MOD, 'item_menu.py'),
        'old': '\nINCLUDE_SETTINGS = False\n',
        'new': '\nINCLUDE_SETTINGS = True\n',
        'expect': ['D1'],
    },
    {
        'id': 'P4', 'what': '动作页用"动作光标"当道具槽位（复现那个真 bug）',
        'path': os.path.join(MOD, 'item_menu.py'),
        'old': "            msg = self._perform(self.action, self.slot_index)",
        'new': "            msg = self._perform(self.action, self.cursor)",
        'expect': ['D5'],
    },
    {
        'id': 'P5', 'what': '让菜单键表收下裸 s（与全局开关键打架）',
        'path': os.path.join(MOD, 'item_menu.py'),
        'old': "    'menu': 'menu', 'm': 'menu',\n",
        'new': "    'menu': 'menu', 'm': 'menu', 's': 'down',\n",
        'expect': ['D7'],
    },
    {
        'id': 'P6', 'what': '把全局热键改成裸字母 s（会系统级劫持 S 键）',
        'path': os.path.join(MOD, 'global_hotkey.py'),
        'old': "HOTKEY_DEFAULT_MENU = 'ctrl+alt+s'",
        'new': "HOTKEY_DEFAULT_MENU = 's'",
        'expect': ['G2'],
    },
    {
        'id': 'P7', 'what': '让零依赖模块引一个白名单外的库',
        'path': os.path.join(MOD, 'item_menu.py'),
        'old': 'import collections\nimport logging\nimport random\n',
        'new': 'import collections\nimport logging\nimport os\nimport random\n',
        'expect': ['G1'],
    },
    {
        'id': 'P8', 'what': '手改产品道具数据的 kind（绕过生成器）',
        'path': os.path.join(ITEMS, 'ch1.json'),
        'json': lambda d: d['items']['dark']['1'].__setitem__('kind', 'heal_all'),
        'expect': ['A4'],
    },
    {
        'id': 'P9', 'what': '把一个光世界房间标成暗世界（数据层说谎）',
        'path': os.path.join(SCENES, '_worlds.json'),
        'json': lambda d: d['rooms']['ch1'].__setitem__('2', 'dark'),
        'expect': ['F2', 'F3', 'F7'],
    },
    {
        'id': 'P10', 'what': '摘掉场景切换时的钩子调用（回光世界不再变垃圾）',
        'path': os.path.join(MOD, 'scene_controller.py'),
        'old': '            self._fire_switch_hooks(scene_id, scene)\n',
        'new': '            pass  # DISC: 钩子被人为摘掉\n',
        'expect': ['G4'],
    },
    {
        'id': 'P11', 'what': '让交互异常路径"假装成功"（全局锁再也不释放）',
        'path': os.path.join(MOD, 'companion.py'),
        'old': ("""        except Exception:
            # ★ 设计律 2：其它异常也必须落到"解锁"这条路上，
            #   否则整个交互系统永久瘫痪（一次异常 = 所有可交互物全部失灵）。
            _log.exception('on_interact 抛异常（key=%s）⇒ 立即解锁', self.key)
            opened = False
"""),
        'new': ("""        except Exception:
            _log.exception('on_interact 抛异常（key=%s）', self.key)
            opened = True
"""),
        'expect': ['E5'],
    },
    {
        'id': 'P12', 'what': '让 classify() 对认不出的名字硬猜一个分类',
        'path': os.path.join(MOD, 'item_interact.py'),
        'old': '    return None\n\n\ndef is_interactive(src):',
        'new': "    return {'kind': 'interactable', 'in_data': False}\n\n\ndef is_interactive(src):",
        'expect': ['E1'],
    },
]

FAIL_RE = re.compile(r'^\[FAIL\]\s+(\S+)', re.M)


def _snapshot(path):
    with io.open(path, 'rb') as fh:
        return fh.read()


def _restore(path, blob):
    with io.open(path, 'wb') as fh:
        fh.write(blob)


def _run_suite():
    proc = subprocess.run([PY, SUITE], cwd=ROUND, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    out = proc.stdout.decode('utf-8', 'replace')
    return proc.returncode, out, FAIL_RE.findall(out)


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    base = {p: _snapshot(p) for p in {c['path'] for c in CASES} | {SUITE}}

    rc0, out0, fails0 = _run_suite()
    print('初始：exit=%d FAIL=%d' % (rc0, len(fails0)))
    if fails0:
        print('⚠️ 初始就报红，体检中止（先让套件全绿）')
        return 2

    bad = []
    for c in CASES:
        path, blob = c['path'], base[c['path']]
        try:
            if 'json' in c:
                d = json.loads(blob.decode('utf-8'))
                c['json'](d)
                text = json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True)
                # `_worlds.json` 由生成器写成无尾换行；这里保持同形状便于还原后比对
                new_blob = text.encode('utf-8')
            else:
                text = blob.decode('utf-8')
                if c['old'] not in text:
                    print('[SKIP] %s 目标文本没找到：%s' % (c['id'], c['what']))
                    bad.append((c['id'], '目标文本没找到'))
                    continue
                new_blob = text.replace(c['old'], c['new'], 1).encode('utf-8')
            _restore(path, new_blob)
            rc, out, fails = _run_suite()
        finally:
            _restore(path, blob)
        hit = sorted(set(fails))
        want = set(c['expect'])
        ok = want <= set(hit)
        print('[%s] %s  %s —— 期望 %s，实得 %s（共 %d 项报红）'
              % ('OK' if ok else 'MISS', c['id'], c['what'],
                 ','.join(sorted(want)), ','.join(hit) or '无', len(hit)))
        if not ok:
            bad.append((c['id'], '未命中 %s' % sorted(want - set(hit))))

    # 还原校验
    dirty = [p for p, b in base.items() if _snapshot(p) != b]
    rc1, out1, fails1 = _run_suite()
    print()
    print('还原校验：脏文件 %d 个；套件 FAIL=%d（应为 0）' % (len(dirty), len(fails1)))
    if dirty:
        for p in dirty:
            print('   [DIRTY] %s' % p)
    print()
    if bad or dirty or fails1:
        print('体检结论：不通过（%s）' % ('; '.join('%s %s' % b for b in bad) or '还原不干净'))
        return 1
    print('体检结论：%d/%d 病例全部精确报红，且还原干净、套件回到全绿。'
          % (len(CASES), len(CASES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
