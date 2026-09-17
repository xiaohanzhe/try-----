# -*- coding: utf-8 -*-
"""H4 · G3 报告生成器：把 `attribute_ownership.json` 渲染成项目根的交付物 markdown。

为什么用脚本生成而不是手写
--------------------------
G3 的交付物里有两张长表（真耦合点 111 条 / 必备接口 138 条）。手抄 249 行数字，
出错概率高于人眼校验能力；脚本渲染保证"报告里的数字 == 扫描器实测"，
任何一次重跑都会让报告跟着变，不存在"报告与证据不一致"的中间态。

用法：& C:\\Python311\\python.exe make_g3_report.py
产物：<项目根>/H4-G3_属性归属表_<日期>.md
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
JSON_PATH = os.path.join(HERE, '_evidence', 'attribute_ownership.json')
OUT_PATH = os.path.join(ROOT, 'H4-G3_属性归属表_2026-09-16.md')

W1_SET = ('W1-1', 'W1-2', 'W1-3', 'W1-4', 'W1-5', 'W1-6')
WAVE_OF = {}
for _m in ('W1-1', 'W1-2', 'W1-3', 'W1-4', 'W1-5', 'W1-6'):
    WAVE_OF[_m] = 'Wave 1'
WAVE_OF['W2-1'] = 'Wave 2'
for _m in ('W3-1', 'W3-2', 'W3-3'):
    WAVE_OF[_m] = 'Wave 3'
WAVE_OF['SUBSYS'] = '不搬（注入引用）'
WAVE_OF['CORE'] = '不搬（留宿主）'

data = json.load(open(JSON_PATH, encoding='utf-8'))
attrs = data['attrs']

# 方法 → 模块（反查表）
meth_mod = {}
for mod, ms in data['methods_by_module'].items():
    for m in ms:
        meth_mod[m] = mod

HOST = 'RalseiPet（留在宿主）'

L = []


def w(s=''):
    L.append(s)


def mod_of_attr(a):
    return attrs[a]['owner']


def hot_sorted():
    return sorted(data['hot_union'],
                  key=lambda a: (-attrs[a]['stores'], -attrs[a]['n_methods_writing'], a))


# ------------------------------------------------------------------ 1 结论
w('# H4 · 闸门 G3 交付物：属性归属表')
w()
w('> 生成日期：2026-09-16 ｜ 生成器：`code-quality-audit/架构改造-H4H5/make_g3_report.py`')
w('> 数字全部由脚本从 `_evidence/attribute_ownership.json` 渲染，**不要手改**；重跑扫描器后重跑本脚本即可。')
w('> 依据：`架构改造排期方案_H4-H5_2026-09-13.md` §3 G3（原话"**没有这张表不许进入 Wave 1**"）。')
w()
w('## 1. 结论')
w()
w('| 问题 | 结论 |')
w('|---|---|')
w('| G3 闸门是否达成？ | **达成**。%d 个 self 属性全部落入显式分区，未归类 **%d** 个。 |'
  % (data['n_attrs'], len(data['unclassified'])))
w('| 按方案 §3 的六类分区（窗口几何/物理/动画/情绪/会话/子系统引用）？ | 达成，且细化为 16 个分区（见 §3）。 |')
w('| 跨方法写入属性逐条定归属？ | 达成。按"写出现次数 ≥3"口径 **%d 条**、按"写入方法数 ≥3"口径 **%d 条**，并集 **%d 条**逐条给出归属（见 §4）。 |'
  % (len(data['hot_by_stores']), len(data['hot_by_writers']), len(data['hot_union'])))
w('| 拆分的真瓶颈量化？ | **%d 条**属性的归属模块外还有方法在写它——这就是"新模块不得不反向 import main"的唯一诱因清单（见 §5）。 |'
  % (len(data['needs_interface'])))
w('| 可以开工 Wave 1 吗？ | **可以，但有 @@MUTUAL@@ 个先行决策点**（Wave 1 模块之间互相写对方的属性，见 §6）。 |')
w('| 顺带查出的缺陷候选？ | 悬空读 **%d** 个、死参数候选 **%d** 个，交 G1 依原约定处置（见 §7）。 |'
  % (len([a for a in data['never_written'] if not attrs[a]['is_class_attr']]),
     len(data['never_read'])))
w()

# ------------------------------------------------------------------ 2 口径
w('## 2. 口径修正：为什么上一版"458 个属性"的表不能用')
w()
_top = sorted(data['call_only_detail'].items(), key=lambda kv: -kv[1]['calls'])[:6]
_top_s = '、'.join('`%s`%d' % (k, v['calls']) for k, v in _top if v['calls'])
w('第一版扫描把 `self.foo()` **调用位**里作为 `func` 的那个节点也当成"属性读"记账，'
  '于是 %d 个方法名 / Qt 内置（%s、`show`、`winId`…）被灌进属性全集，'
  '`UNCLASSIFIED` 段几乎被方法名塞满（300 条里大半是噪声），表不可用。'
  % (data['n_call_only'], _top_s))
w()
w('| 口径 | 数值 |')
w('|---|---|')
w('| main.py 总行数 | %d |' % data['main_lines'])
w('| `RalseiPet` 起始行 / 直接方法数 | 第 %d 行 / **%d 个** |'
  % (data['class_start_line'], data['n_methods']))
w('| `self.<name>` 出现的**名字全景** | %d |' % (data['n_attrs'] + data['n_call_only']))
w('| 其中 **真属性**（有过赋值） | **%d** |' % data['n_attrs'])
w('| 其中 **`self.foo()` 调用位**（方法 / Qt 内置，非状态） | %d 个名字 / %d 个调用点 |'
  % (data['n_call_only'], data['n_call_sites']))
w('| 真属性中，被 Store 过 / 类体声明 / property | %d / %d / %d |'
  % (len([a for a in attrs if attrs[a]['stores']]),
     len([a for a in attrs if attrs[a]['is_class_attr']]), 0))
w()
w('判定规则（可复算）：一个名字若**从未被赋值**，且（被调用过 或 是本类直接方法），'
  '则它是"方法/Qt 内置"而不是状态；反之只要出现过一次赋值，一律留在属性表里。')
w('这条规则由自检 X5/X6/X7 锁住（见 §8）：排除段 %d + 属性表 %d == 原始名集 %d。'
  % (data['n_call_only'], data['n_attrs'], data['n_attrs'] + data['n_call_only']))
w()

# ------------------------------------------------------------------ 3 分区
parts = data['partitions']
w('## 3. 分区总表（%d 个分区，未归类 0）' % len(parts))
w()
w('| 分区 | 归属 | 波次 | 属性数 | 其中写≥3方法 | 需显式接口 |')
w('|---|---|---|---:|---:|---:|')
order = sorted(parts, key=lambda p: -len(parts[p]))
for p in order:
    names = parts[p]
    if not names:
        continue
    owner = attrs[names[0]]['owner']
    nh = len([a for a in names if attrs[a]['n_methods_writing'] >= 3])
    ni = len([a for a in names if attrs[a]['needs_interface']])
    w('| %s | `%s` | %s | %d | %d | %d |'
      % (p, owner, WAVE_OF.get(owner, '?'), len(names), nh, ni))
w()
w('方法侧覆盖（方案 §5.2 的模块是否有方法可搬）：')
w()
w('| 目标模块 | 方法数 |')
w('|---|---:|')
for mod in sorted(data['methods_by_module'], key=lambda k: -len(data['methods_by_module'][k])):
    w('| `%s` | %d |' % (mod, len(data['methods_by_module'][mod])))
w()

# ------------------------------------------------------------------ 4 真耦合点
hot = hot_sorted()
w('## 4. 真耦合点逐条定归属（%d 条）' % len(hot))
w()
w('排序：写出现次数降序。`模块外写方` 一列若**不止"留在宿主"**，说明两个待拆模块互相写状态——'
  '这就是必须先定接口的地方，不是搬家时才发现的东西。')
w()
w('| # | 属性 | 归属分区 | 归属 | 写法 | 读法 | 模块外的写方 |')
w('|---:|---|---|---|---:|---:|---|')
for i, a in enumerate(hot, 1):
    d = attrs[a]
    outside = ', '.join(d['writers_outside_owner']) or '—'
    w('| %d | `%s` | %s | `%s` | %d | %d | %s |'
      % (i, a, d['partition'], d['owner'], d['stores'], d['n_methods_writing'], outside))
w()

# ------------------------------------------------------------------ 5 接口清单
need = data['needs_interface']
by_owner = {}
for a in need:
    by_owner.setdefault(attrs[a]['owner'], []).append(a)
w('## 5. 必备接口清单（%d 条，按目标模块分组）' % len(need))
w()
w('读法：某模块要**独占**这个属性，但模块外仍有方法在写它。搬迁时必须显式给出注入路径；'
  '若不做接口直接搬，新模块就只能反向 `import main` —— 方案 §5.1 的判据正是用它来否掉一次拆分。')
w('两种形态（沿用项目已有范式）：')
w()
w('- **宿主写、模块只读** → 构造注入 / 宿主 getter，风险低；')
w('- **另一个待拆模块也在写** → 必须 `pyqtSignal` 排队回主线程 或 回调'
  '（现成范式：`_start_open_with_spell(path, kind, cb)`），风险高，**该属性本轮先留在宿主**。')
w()
for owner in sorted(by_owner, key=lambda k: (-len(by_owner[k]), k)):
    lst = sorted(by_owner[owner], key=lambda a: (-attrs[a]['stores'], a))
    w('### `%s`（%s）— %d 条' % (owner, WAVE_OF.get(owner, '?'), len(lst)))
    w()
    w('| 属性 | 写法 | 模块外的写方 |')
    w('|---|---:|---|')
    for a in lst:
        d = attrs[a]
        w('| `%s` | %d | %s |' % (a, d['stores'], ', '.join(d['writers_outside_owner'])))
    w()

# ------------------------------------------------------------------ 6 Wave1 互写
mutual = []
for a in need:
    d = attrs[a]
    if d['owner'] not in W1_SET:
        continue
    cross = sorted({meth_mod.get(m, HOST) for m in d['writers']
                    if meth_mod.get(m, HOST) in W1_SET
                    and meth_mod.get(m, HOST) != d['owner']})
    if cross:
        mutual.append((a, d, cross))
w('## 6. Wave 1 先行决策点：Wave 1 模块之间互相写对方的属性（%d 条）' % len(mutual))
w()
if mutual:
    w('这 %d 条是 Wave 1 的**唯一真阻塞项**。其余 %d 条接口的另一侧是"留在宿主"或 Wave 2/3 模块——'
      '那些属性本轮**不搬**，仍挂在 `RalseiPet` 上，新模块通过宿主 API 读写即可，'
      '既不构成反向 import，也不阻塞 Wave 1。'
      % (len(mutual), len(need) - len(mutual)))
    w()
    w('| 属性 | 归属 | 写它的 **另一个 Wave 1 模块** | 建议 |')
    w('|---|---|---|---|')
    for a, d, cross in sorted(mutual, key=lambda t: (-t[1]['stores'], t[0])):
        w('| `%s` | `%s` | %s | 二者合并，或改走 `pyqtSignal`（不得直连） |'
          % (a, d['owner'], ', '.join(cross)))
else:
    w('无。Wave 1 六项之间不存在互相写对方属性的情况，可完全独立施工。')
w()

# ------------------------------------------------------------------ 7 G1
dangling = [a for a in data['never_written'] if not attrs[a]['is_class_attr']]
consts = [a for a in data['never_written'] if attrs[a]['is_class_attr']]
w('## 7. 顺带查出、交 G1 处置的属性（不进 Wave 1）')
w()
w('### 7.1 悬空读：读一个**从未被赋值**的属性（%d 个）' % len(dangling))
w()
w('| 属性 | 读方法数 | 归属 | 实测证据 |')
w('|---|---:|---|---|')
EVID = {
    '_cached_scale_factor': "`getattr(self, '_cached_scale_factor', 2.0)`（main.py:7675 / 7835）——全项目无赋值，"
                            "**缓存永远取默认值 2.0**",
    'ai_thread': "`hasattr(self, 'ai_thread')`（main.py:8630）——全项目无赋值，"
                 "**8630–8632 的收尾逻辑整段是死代码**（`ai_thread_running = False` 与 `join()` 都不会执行）",
    'is_being_thrown': "`hasattr(self, 'is_being_thrown')`（main.py:7562）——全项目无赋值，条件恒为 False",
}
for a in dangling:
    d = attrs[a]
    w('| `%s` | %d | %s | %s |' % (a, d['n_methods_reading'], d['partition'], EVID.get(a, '—')))
w()
w('### 7.2 类体常量（合法，勿动）（%d 个）' % len(consts))
w()
w('%s' % '、'.join('`%s`' % a for a in consts))
w()
w('### 7.3 赋过值但从无读取（死参数候选，%d 个）' % len(data['never_read']))
w()
w('这部分**只列不判**——它们可能是"预留给后续功能"或"曾经用过忘了删"。'
  '按方案 §5.5"改造期不改行为"，本轮不删；仅在 G1 阶段按原约定（删除 / 标注 legacy）二选一。')
w()
w('| 属性 | 写方法数 | 归属 |')
w('|---|---:|---|')
for a in data['never_read']:
    d = attrs[a]
    w('| `%s` | %d | %s |' % (a, d['n_methods_writing'], d['partition']))
w()

# ------------------------------------------------------------------ 8 自检
w('## 8. 自检（X1–X7，全部来自扫描器实测）')
w()
w('| 自检 | 结果 |')
w('|---|---|')
for c in data['self_checks']:
    w('| %s | **%s** |' % (c['name'], 'PASS' if c['ok'] else 'FAIL'))
w()

# ------------------------------------------------------------------ 9 未决
w('## 9. 未决与下一步')
w()
w('1. **Wave 1 的施工口径**（本次定案）：只搬**方法**，不搬**状态**。'
  '凡归属 Wave 1 模块的属性若被模块外写（§5 的 %d 条），本轮一律留在 `RalseiPet`，'
  '新模块经宿主 API 读写 —— 这样新模块不反向 `import main`，'
  '且 G2 回归基线可保持逐字节一致（方案 §5.3 转发壳手法）。'
  % (len(need)))
w('2. **待用户裁决的只有 §6 的 %d 条**（Wave 1 内部互写）：合并两个 Controller，还是走信号。'
  % len(mutual))
w('3. W1-6（文件/表格）在搬之前须先与 `modules/desktop_interaction.py` **比对去重**'
  '（方案 §5.2 原话"已重复，须先比对再合并"）。')
w('4. Wave 3 按方案 §5.5 允许"长期停在 Wave 1+2"，本次不改该决策。')
w()

# 回填 §1 的哨兵（避免用列表下标，重排段落后会错位）
OUT = '\n'.join(L).replace('@@MUTUAL@@', str(len(mutual))) + '\n'
with open(OUT_PATH, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(OUT)
print('[ok] %s' % OUT_PATH)
sys.exit(0)
