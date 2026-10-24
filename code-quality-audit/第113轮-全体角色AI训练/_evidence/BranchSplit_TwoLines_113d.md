# 两条线分叉与合流方案（第113轮d）

> 取证时间：2026-10-25 04:4x　取证方式：只读 `git` 对象（不 checkout、不 merge、不 push）
> 结论一句话：**「try - 副本」是一条在第110轮被上游抛下的旁支；远端 main 已经走到第118轮。**

---

## 1. 事实

| 项 | 本地这棵树 | 远端 `origin/main` |
|---|---|---|
| HEAD | `1238a24` 第113轮c：记忆压回注入上限内 | `c88292b` 交接：第118轮收口 + 2026-10-24 交接单 |
| 领先对方 | **14 条** | **28 条** |
| 共同祖先 | `0efda6b` 记忆：第110轮当日工作日志（2026-10-12） | 同 |
| 自祖先起改过文件 | 538 | 710 |
| **两边都改过的文件** | **90** | 同 |

`git merge-base --is-ancestor HEAD origin/main` ⇒ **NO**（确认分叉，不是"本地落后"）。

### 1.1 远端独有的轮次（我们完全没有）

```
c88292b 交接：第118轮收口 + 2026-10-24 交接单
7580251 第118轮：桌面四门「看得见 = 走得到」＋ 僵尸锁 ＋ 原作式选择框
97c0369 第117轮：OneShot 门换「黑光」变体 + 四门统一放大（用户口径四条）
b5e6dbf 第117轮：真机录屏逐帧检查 30/0 + 两个口径发现
3ce0ad9 第116轮：沙箱补漏（真源头 RALSEI_MEMORY_DIR）＋ 用户真机四缺陷逐帧定位修复
4eab6a6 第116轮补记：gitpush.py 的 GCM 路径硬编码失效（PortableGit 1.2.0 → 1.3.0）
817625c 第115轮后续：AI 逐项全量扫（96 位）+ 真机逐项录屏重放 + 出戏闸真 bug 修复
529b2a4 第115轮：AI 人味训练（受控 A/B ⇒ 改人设真源）
844bda0 第114轮：差事「世界门控 + 派发入口 + 独立落盘」
ac3b9e3 第113轮：§109.5「灵魂视角」机制层 —— NPC 差事（npc_errand）
6b37346 第112轮：#47 续 —— 门渐显 + 门贴图重做 + Niko 家准入/问答（+ G2 修复）
```

★ 注意 `4eab6a6`：**远端早在第116轮就修过同一个 GCM 路径硬编码问题**，本轮 `db5a67c` 是重复劳动。
★ 注意 `6b37346` 与我们本地 `50c821a` **标题完全相同** —— 同一个需求被两边各做了一遍。

### 1.2 本地这条线是不是白干？—— 不是

远端 `ralsei_pet/modules/npc_persona.py` = **34477** 字节；本地 = **44473** 字节。

两边 `def` 列表**逐项一致**，唯一差异：

- 本地独有 3 个函数：`training_patch()` / `relation_patch()` / `evolution_patch()`
- 本地 `build_system_prompt()` 多 3 个**带默认值**的尾参：`patch='', relation='', evolution=''`

⇒ **纯增量、向后兼容**：远端的调用方不传新参数也照常工作。

本地独有的数据面（远端完全没有）：

```
ralsei_pet/assets/npc/_training/          （训练卡 + _index.json）
ralsei_pet/assets/npc/_relations/         （_attitude / _evolution / _index / _manifest / 两份 source）
ralsei_pet/assets/npc/_rooms/room_memories113.json
code-quality-audit/第113轮-全体角色AI训练/  （48 轮剧本 + 训练器 + 全部 raw30/transcripts30）
```

⇒ 两条线是**互补**，不是重复：远端 115 轮走"受控 A/B 定位出戏 + 改人设真源"，本地 113 轮走
"逐角色 48 轮对练 + 关系演化卡 + 训练纠正块"。

### 1.3 重叠的 90 个文件里，产品代码有 31 项

```
npc_persona.py 之外的 py：door_reveal.py / item_interact.py / niko_home.py / src/main.py
desktop.json / 6 份 persona txt / 20 张 objs png（niko_* / spr_realisticexplosion_* / ut_castle_realdoor_0）
```

其中 `door_reveal.py`、`niko_home.py`、`desktop.json`、persona txt、png —— 远端 114~118 轮改得**更晚更全**
⇒ **一律以远端为准**，不许拿本地旧版覆盖。

只有 `src/main.py` 是双方都改、且**两边都不能丢**：远端有 114~118 的接线，本地有本轮的 5 行 patch 调用。

---

## 2. 推送为什么失败（已定位，不是网络）

`gitpush.py --push-only` 实测链：

1. `[5] cred user='236837805' pw_len=40` ⇒ **凭据正常**（`_find_gcm()` 自动探测生效）
2. `[6.1] rc=128 fatal: unable to access ...: error adding trust anchors from file:
   C:/Users/23002/AppData/Local/Temp/win_root_ca.pem`
   ⇒ **CA 文件被 Temp 清理掉了**（`gitpush.py` 只引用、不会重建）
3. 用 PowerShell 重建：155 张证书 / 252458 字节 ⇒ TLS 通
4. 再推 ⇒ `! [rejected] HEAD -> main (non-fast-forward)`：
   **"branch is behind its remote counterpart"** ⇒ 真因是 §1 的分叉，不是网络

⇒ 教训：`win_root_ca.pem` 落在 `%TEMP%` 里会消失，**push 前要存在性自检**，否则每次都误报"网络/TLS"。

---

## 3. 合流方案（不动任何一侧历史，只做文件级移植）

**不做** `git merge`（会造出 14 条重复轮次 + 90 文件冲突），**不做** `push --force`（会毁掉远端 28 条更新的提交）。

步骤：

1. 以 `origin/main`（第118轮）为基线建 **worktree**（或新克隆目录），不碰本树。
2. **整文件搬**（零冲突，远端没有这些路径）：
   - `ralsei_pet/modules/npc_persona.py`（纯增量，向后兼容）
   - `ralsei_pet/assets/npc/_training/`、`_relations/`、`_rooms/room_memories113.json`
   - `code-quality-audit/第113轮-全体角色AI训练/`（训练证据与数据）
3. **手工适配唯一一处**：`ralsei_pet/src/main.py` —— 在远端 118 版上补回本轮的
   `npc_persona_mod.build_system_prompt(..., patch=, relation=, evolution=)` 三参调用
   （CRLF 保持，改完验 `lone_lf=0`）。
4. **其余重叠文件一律保留远端版**（`door_reveal / niko_home / desktop.json / persona txt / png`）。
5. 在新树上跑 G2 全量 + `check113`，须 **全 IDENTICAL**；`check95 A2` 的 `js_len` 也要重新量
   （远端 `MEMORY.md` 自身 9906 字符口径与本地不同，合并记忆时要重新压）。
6. 通过后才 push。

---

## 4. 本次训练产物还有没有用

**有。** `raw30/*.jsonl`、`transcripts30/*.md` 是**数据**，与产品代码版本无关；
只要 `npc_persona.py` 的 patch 接口一致（已确认一致），搬到第118轮的树上直接可用。

⇒ 因此**不中止**当前冒烟，跑完再统一合流。

---

## 5. 需要用户拍板的一件事

这条旁支的 14 条历史（含 `e681222` / `db5a67c` / `1238a24` 等）是：

- **(A)** 保留为独立分支（`git branch local-113`）留档，主干跟远端 —— 推荐；或
- **(B)** 直接丢弃，只把文件内容移植过去。

两者对最终产品无差别，差别只在"还能不能回查这条线的过程"。
