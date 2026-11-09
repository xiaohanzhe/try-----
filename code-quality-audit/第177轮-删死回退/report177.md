# 第177轮 · 删掉 `load_scene()` 里那条**从来没执行过**的 `original_room_id` 回退

> 一句话：这段代码不是"写错了"，是**写完之后就被第175轮架空了**。
> 删它的理由不是"少几行好看"，而是**它会把「文件缺字段」这件事悄悄盖住**。

---

## 1. 要删的是什么

`ralsei_pet/modules/scene_system.py` · `load_scene()`（共 4 处改动，`21 +/18 -`）：

```python
# 来源 1：独立文件
if os.path.isfile(path):
    ...
    scene = SceneState.from_dict(raw)
    scene.dir_path = base
    scene.hidden_objects = load_obj_visible(base)
-   if scene.original_room_id is None and isinstance(entry, dict):
-       _oid = entry.get('original_room_id')
-       if isinstance(_oid, int):
-           scene.original_room_id = _oid          # ← 拿索引里的值顶上
    return scene

# 来源 2：区域分片
if isinstance(entry, dict):
    chapter_id = entry.get('chapter_id')
    area_id = entry.get('area_id')
    if chapter_id and area_id:
-       scene = load_zone(chapter_id, area_id, base).get(scene_id)
-       if scene is not None and scene.original_room_id is None:
-           _oid = entry.get('original_room_id')
-           if isinstance(_oid, int):
-               scene.original_room_id = _oid      # 同上，第二处
-       return scene
+       return load_zone(chapter_id, area_id, base).get(scene_id)
```

另两处只改注释 / docstring（`:param entry:` 补一句"第177轮起它**只**用于定位是哪一片"）。

## 2. 它为什么是死的（三条证据，都能复算）

| # | 证据 | 实测 |
|---|---|---|
| ① | 两条来源**全部自带** `original_room_id` | 独立文件 **88/88**、分片 **2078/2078**，合计 **2166/2166** |
| ② | 自带的值 **逐条等于** `_index.json` 的登记值（不是"值合理"） | 不符 **0** 条 |
| ③ | 第175轮才把独立文件补齐（87 个文件各 `+1 行 / -0 行`） | 那之前只有**独立文件**这一支缺字段 |

`if ... is None` 是**入口条件** —— 2166 个场景没有一个是 `None`，这个分支从第175轮起**一次都没进去过**。
所以删它是**行为不变的删除**：`check177 C1`（88 个文件 `load_scene(sid)` 与 `load_scene(sid, entry=带随机 rid)` 逐条相同）、
`C2`（分片抽 76 片、把 entry 的 rid 换成哨兵 ⇒ 一个都不变）在**删之前也是绿的**。

## 3. 那为什么非删不可

留着它的坏处不是"多 8 行"，而是**它把"文件本身不自足"这件事悄悄盖住**：

- 将来新增一个场景、忘了写 `original_room_id` ⇒ 渲染层会用索引里的值顶上，**看起来一切正常**；
- 而"文件缺字段"这个事实**谁都看不见** —— 第175轮补字段的全部意义就是让文件自己说得清；
- 更糟的是**回退只在"独立文件"这一支生效过**，分片那一支是复制粘贴出来的第二份，
  两份逻辑一旦有人只改一处，就会出现"独立文件能补、分片不能补"的**静默不对称**。

⇒ 现在改成**如实返回 `None`**：缺字段就显形（`C3` / `C4` 钉这个，见 §5）。

## 4. ★★★ `entry` 形参**不能删**

这是本轮最容易做错的一步。`entry` 除了"补 rid"，还承担**分片定位**：

```python
chapter_id = entry.get('chapter_id')   # 决定读 _zone.<章>.<区域>.json 哪一片
area_id    = entry.get('area_id')
```

删了它 → **2078 个分片场景全部加载失败**（76 片全返回 `None`）。
两条不变式钉住：`B3`（`entry.get('chapter_id')` / `('area_id')` 各至少一处）、`B5`（签名里仍有 `entry`）。
变异 `M2`（删掉 `area_id` 取值）实测红在 `B3` ✔。

## 5. ★★ 本轮我自己踩的坑：D5 第一版是**恒真判据**

路径穿越守卫原本这样验：

```python
load_scene('../etc/passwd') is None and load_scene('a/b') is None and load_scene('..') is None
```

**这三个文件本来就不存在** ⇒ 就算把守卫整段删掉，`os.path.isfile()` 也返回 False、照样 `None`。
⇒ 这条判据**没有任何鉴别力**，是标准的恒真判据。

怎么发现的：变异 `M7`（删掉守卫）跑出来 **rc=0、全绿**。这就是"夹具不保真 ⇒ 判据看着绿、其实什么都没测"。

改法（先让穿越**真的能成功**，再断言它被拦）：

```python
_sneak_dir = os.path.join(_tmp2, 'sub'); os.makedirs(_sneak_dir, exist_ok=True)
json.dump({'schema_version': SS.SCENE_SCHEMA_VERSION, ...},
          open(os.path.join(_sneak_dir, 'sneaky.json'), 'w'))
check('D5a 夹具就位：sub/sneaky.json 真实存在（否则 D5b 恒真）', os.path.isfile(...))
check('D5b 场景 id 带分隔符 / `..` ⇒ None（路径穿越守卫还在）',
      load_scene('sub/sneaky', ...) is None and ...)
```

改后 `M7` 红在 `D5b` ✔，extra 里还打出 `穿越一步可读=True`（证明夹具真的能读到）。

## 6. 变异测试 8/8

| 变异 | 红在哪 | 期望 | 结果 |
|---|---|---|---|
| M1 **整文件换回 `git show HEAD:`**（回退原样还在） | B1 B2 C3 C4 | 同 | ✔ |
| M2 删掉 `area_id` 取值 | B3 | B3 | ✔ |
| M3 独立文件分支 `return None` | C1 C3 C5 D1 | 含 D1 | ✔ |
| M4 `from_dict` 缺 rid 猜 0（补值逻辑换个地方长出来） | A4 C3 C4 | 含 A4 | ✔ |
| M5 只"读一下" `entry.get('original_room_id')`（不赋值） | B2 | B2 | ✔ |
| M6 删掉 schema 版本守卫 | D3 | D3 | ✔ |
| M7 删掉路径穿越守卫 | **D5b** | D5b | ✔（改 D5 前是"无红"） |
| M8 分片分支**无条件**用 entry 覆盖 rid | B1 B2 C2 C4 | 含 C2 | ✔ |

★ `M1` 是这一轮最硬的一条：不是手工把那 8 行拼回去（拼错了就是假夹具），
而是 `git show HEAD:ralsei_pet/modules/scene_system.py` 整文件换回 —— 拿到的是**真的改前状态**，
并且先断言 `'original_room_id = _oid' in txt` 与 `txt != 工作区`，否则 M1 前提不成立。

★ 每条变异跑完都 `shutil.copy2` 还原 + **sha1 相同 + 全文逐字相同**双核；备份落 `D:\_tmp\mut177\`（不在工作区）。

## 7. 判据 29 条（五段）

| 段 | 条数 | 内容 |
|---|---|---|
| A 自足率 | 6 | 分母（2166 = 88 + 2078）· 两条来源各自 100% 自带 · **逐条等于索引** · `from_dict` 抹掉 rid 后不许偷偷填 |
| B 机制已消失 | 6 | AST 扫 `load_scene` **函数体**：不许有 `scene.original_room_id = ...`、不许读 `entry[...]`；但 `chapter_id`/`area_id` **必须在**；★ 负控制：同一扫描器喂合成源码必须命中 |
| C 行为已改 | 5 | **C3**（独立文件缺 rid + entry 带 555 ⇒ 必须 `None`）· **C4**（分片缺 rid + entry 带 666 ⇒ 必须 `None`）· C5 反向控制（带 rid=777 ⇒ 必须读到 777）· C1/C2 说明性 |
| D 其余语义不变 | 7 | 不给 entry 也能加载 88 个 · 2078 片一片不少 · schema 守卫 · JSON 坏掉永不抛 · **D5a/D5b 穿越拦截** · 空 id 不抛 |
| E 自检 | 6 | 无 BOM / UTF-8 / AST 可解析 · **AST 查恒真**（第二参不许是常量真）· 单一 harness · 条数下限 · 零外部盘零网络（令牌拼接构造，防扫到自己）· 不构造真机、不 import 主程序 |

**删前 `PASS=25 FAIL=4` → 删后 `PASS=29 FAIL=0`**（红的就是 B1/B2/C3/C4 这四条靶子）。

★ E 段两处按第138/146轮的规矩**去掉了会漂移的量**：E1 原来回显 `bytes=<文件体积>`、
E4 原来回显 `实测 <条数>` —— 这两个数**每改一次就变**，判定没变也会报 DIFF，已删。

## 8. 全量回归

- 新套件已注册进 `regress/run_all.py` 的 `SUITES`（`offscreen: True`，不构造 `RalseiPet()`），
  并 `--only check177 --update` 建基线（合并模式，其余套件基线不动）。
- 全量：**`PASS=7859 FAIL=0`，套件 = 175，175/175 IDENTICAL**（rc=0）。
- 没有任何老锁被撞 —— 本轮只动了一个函数里的两段死代码，不改数据结构、不改路由表。

## 9. 遗留

- `spr_doorAny*` 素材仍未导出（第173/174轮登记的遗留，与本轮无关）。
- `E:\_tmp88` 目录仍在（不是第176轮那片死区，本轮未动）。
- `load_scene` 现在**依赖"文件自足"**。若将来有工具批量生成场景文件，必须自带 `original_room_id`；
  建议在生成侧也加一道断言（不在本轮范围）。

## 证据清单（`_evidence/`）

| 文件 | 内容 |
|---|---|
| `check177_out.txt` | 29 条判据完整输出（PASS=29 FAIL=0） |
| `mutate177_out.txt` | 8 条变异完整输出（8/8 被抓 + 还原后复跑全绿） |
| `g2_177_summary.txt` | 全量 G2 摘要（PASS=7859 FAIL=0 套件=175） |
