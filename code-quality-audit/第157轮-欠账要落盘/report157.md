# 第157轮 · 欠账要落盘

> 落点：`report156.md §9` 第 1 条遗留 —— **欠账只存内存，重启就丢**。
> 用户口径仍是那句「**按照人类的逻辑来就好**」。
> 分支：`local-157`。改动面：`main.py` +148/−1（18837 行，全 CRLF）、机制层**零改动**。

## 1. 结论

第156轮把欠账挂进了 prompt 尾部（治好了"记忆窗口裁掉"），但它**只活在一次运行里**。
本轮先把它量出来：派三次 → 落盘 → 新宿主读回 ⇒ **在办差事 1 条（活了）、欠账 0 件（死了）**；
而且"靠记忆兜底"这条退路也不成立 —— 重启后再聊 12 句，两件欠账**都出窗**。

改法一个字都不碰机制层：落盘时把 `ErrandBoard` 的形状**原样包一层**、多补一个 `given_up` 键。

| 量 | 改前 | 改后 |
|---|---|---|
| 跨重启后欠账 | **0 件** | **2 件**（顺序老→新，事由一字不差） |
| 存档顶层键 | `[active, done, enabled]` | `[active, done, enabled, given_up]` |
| 在办差事 | 1 条 | 1 条（没被影响） |
| `npc_errand.py` | 不变 | **不变**（一个字节没动） |

## 2. 改前实测（`probe157.py --before`）

```
== 改前基线 ==
派三次之后（**同一进程、未重启**）：欠账 2 件 ⇒ [('oneshot.barrens.Blue', '擦柜台'),
                                                ('ut.rooms.room_area1', '收杯子')]
落盘：True
存档顶层键：['active', 'done', 'enabled']
重启之后：在办差事 1 条 / 欠账 0 件 ⇒ []
```

`P2` 是关键对照：**丢的不是整个看板，是"欠账这件事从来没进过档"**。
`P4` 说明"他会记得"也不成立 —— `history_block(max_lines=12)` 只取最后 12 条。

## 3. 改法：一个包装文档，机制层零改动

```python
class _ErrandDoc(object):          # 落盘用的一次性文档
    __slots__ = ('_board', '_given_up')
    def to_dict(self):
        d = self._board.to_dict()          # {enabled, active, done} 原样
        d['given_up'] = self._given_up     # 多补一个键
        return d
```

- 写：`npc_plan_store.save(path, _ErrandDoc(board, _errand_given_up_dump(self, now=now)))`
  —— 原子写（`.tmp` + `os.replace`）照旧复用，没另写一套写盘。
- 读：`_npc_errand_load` 里先 `_errand_given_up_restore(self, raw.get('given_up'))`，再照旧建看板。
- `_errand_given_up_dump` / `_errand_given_up_restore` 都是**模块级**（第156轮第 4 次
  `AttributeError` 的教训：写成方法 ⇒ 轻宿主当场炸）。

**为什么不去改 `ErrandBoard.to_dict()`**：`npc_errand.py` 是机制层，它不该认识"欠账"这种
人类叙事（第156轮定的边界，`check156 C7` / `check157 C3` 都守着）；而
`ErrandBoard.from_dict` 本来就**忽略**它不认识的键 ⇒ **新旧档双向兼容**：

| 情形 | 结果 |
|---|---|
| 老档（无 `given_up`）被新代码读 | 空账，看板照建（`A8` 端到端钉住） |
| 新档被老版本产品读 | 看板照常，`given_up` 被忽略（不炸） |

### 3.1 ★★★ 本轮最容易踩的坑：JSON 里没有 tuple

`json.dump` 把元组写成**数组**，读回来是 `list`；而 `_errand_given_up_of` 的判据是
`isinstance(it, tuple)` ⇒ **不转就静默全丢**：盘上明明有，界面上永远不提。
`A2` 同时钉两头（"盘上元素是 `list`" + "内存里元素是 `tuple`"），`C5` 是它的结构性对照。
负控制 `M2`（把 `append((...))` 改成 `append([...])`）一次红 8 条 —— 其中 `B3` 红得很说明问题：
内存里存 list 之后，**下一次落盘**会把账整个写空（dump 只认 tuple），越存越少。

### 3.2 TTL 与上限：**两侧都过滤**

- 写侧（dump）：过期账不写进档 ⇒ 文件不随时间膨胀；
- 读侧（restore）：手改档/老档塞进来的过期账也不进内存表；
- 两侧都按 `ERRAND_GIVEN_UP_MAX` 截断。

读侧这两条用的是**内存表长度**而不是"返几件"—— 因为查询侧（`_errand_given_up_of`）
还会再滤一次，只看返回值的话拆掉 restore 的过滤**也不会红**（恒真）。

## 4. 四处"差一点写错"

### ① ★★★ `A2` 直接下标取 ⇒ 崩掉整套

第一版写 `_raw1['given_up']['ralsei'][0]`。当破坏是"save 退回裸 board"时，`given_up` 键
**整个不存在** ⇒ `KeyError` 把套件炸掉，后面 20 多条判据根本没跑。
`mutate157 --dry` 当时显示 `M1 ⇒ 红：A1`，**看起来"只红一条"** —— 那是崩溃点，不是守卫点。
改成 `.get(...) or []` + `getattr(x, '__name__', '缺')`：缺失时**判红**而不是抛。
（改完 M1 立刻红 8 条，才是真实的破坏面。）

### ② ★★ `check156` 报 DIFF：判据输出回显"规模量"第 N 次复发

本轮新增两个 `_errand_` 前缀的模块级函数 ⇒ `check156 A0` 的 extra `模块级=%d 个` 从 5 变 7
⇒ **判定一个字没变，stdout 变了** ⇒ 全量回归报 `DIFF`。
按第138/146轮的口径：不改判定、只改 extra —— 改成"**缺几个**"（健康态恒 0，产品增删函数不再漂移）。
`check156` 的 `--update` 已单独重定基线，并在 `H8f` 留痕。

### ③ `A7` 的说明又写成 `%` 表达式

`'…只留最近 %d 件…' % (MAX,)` 是 `BinOp`，不是字面量 ⇒ `D1` 当场判红。
第156轮 `A8` 同款。挪到 detail。

### ④ 恢复侧判据差点写成恒真

"过期账恢复后返 0 件"—— 但查询侧本来就会滤掉过期项 ⇒ 即使 restore 不过滤也返 0 件。
改成看**内存表长度**（`A6b` / `A7b`），`M8` / `M9` 才能各自把它打红。

## 5. 判据怎么切的（四段，机器数出来的）

| 段 | 条数 | 守什么 |
|---|---|---|
| A 真跑 | 15 | 跨重启两件都回来 · **类型还原**（list→tuple）· 地点事由一字不差 · 看板不受影响 · 空账写 `{}` · TTL 过期不落盘 · 上限截断 · **老档兼容** · 坏一条丢一条 · 非 dict 不抛 · 幂等 · 按人分槽 · 恢复侧 TTL / 上限（看表长度） |
| B 存档形状 | 4 | 四个键都在 · `given_up` 全是 JSON 原生类型 · 原子写产物可读 · ★ `ErrandBoard.to_dict()` 仍只有**三个键** |
| C AST | 7 | 写走 `save` · 读走 `from_dict` 且不碰 `load` · 机制层不出现 `given_up` · 模块级 · tuple 转换在位 · 传的是 `_ErrandDoc` · 不自己写盘 |
| D 自检 | 5 | 判据名非空字面量 · 只用 `check()` · 无 BOM 全 LF · 零外部盘 |

**31/0**。

## 6. 负控制：10 处破坏，逐条断言**恰好**变红

| # | 破坏 | 红在哪 |
|---|---|---|
| M1 | save 退回**传裸 board** | A1 A2 A3 A5 A11 A12 B1 C6 |
| M2 | restore **不转回 tuple** | A1 A2 A3 A9 A11 A12 B3 C5 |
| M3 | dump **不过 TTL** | A6 |
| M4 | dump **不截断** | A7 |
| M5 | restore **坏一条就整表放弃** | A9 |
| M6 | restore **不校验 dict** | A10 |
| M7 | load **不调 restore** | A1 A2 A3 A11 A12 B3 |
| M8 | restore **不过 TTL** | A6b |
| M9 | restore **不截断** | A7b |
| M10 | `_ErrandDoc` **丢掉 board 形状** | A4 B1 |

`M1` 多红 `A5`（空账时键都没有 ⇒ `None != {}`）与 `C6`（save 里不再有 `_ErrandDoc` 调用）；
`M2` 多红 `B3`（内存里存 list ⇒ 下一次落盘把账写空）；`M7` 多红 `B3`（同上，读回是空表再存）。
都是**同一条闸的第二个观测面**，按实得写死。`Z1` 还原后全绿 · `Z2` sha1 与开工前一致。

## 7. 复检（改过 `main.py` 主链路，按用户口径必做）

`recheck157_core.py`：改动面 / 体积 / 语法 / 编码 / 结构 / 令牌 / 恒真 / 卫生 八段。

## 8. 回归

全量 G2：**PASS=7204 / FAIL=0 / 156 套件全 IDENTICAL**（上一轮 7173/0/155，+31 = `check157`）。

## 9. 遗留 / 结转

1. **落盘时机与差事同寿命**：改派只改内存，落盘走 `_npc_errand_save` 的 120s 节流或退出
   `force=True`。改派后立刻断电，这一件会丢（差事本身也丢）—— 本轮**刻意**不另开写入时机，
   避免"改派一次写一次盘"。
2. 老档被新代码读一次后，下一次 `save` 才会补上 `given_up`（良性，无迁移脚本）。
3. 第156轮遗留：`check156` 里那三条 ack 的"用户不在场也照样发起"仍未统一。
4. 第150~153轮结转未动：纯空格 `npc_id` 不拒；地点别名只到作品级前缀；否定闸整句从严；
   `_item_enter_scene` 无内部调用者；`current_scene` 双语义；`max_sentences` 读了不用。

## 10. 证据

| 文件 | 内容 |
|---|---|
| `_tools/check157.py` | 31 条判据（A15/B4/C7/D5），零网络 / 零 UI / 零外部盘 |
| `_tools/mutate157.py` | 10 处破坏 + Z1/Z2 |
| `_tools/probe157.py` | `--before` / 改后 两套口径：0 件 → 2 件、键 3 → 4 |
| `_tools/recheck157_core.py` | 核心文件复检 |
| `main.py` | +148/−1（18837 行，全 CRLF，裸 LF=0） |
