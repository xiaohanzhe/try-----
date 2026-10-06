# 第94轮 · 证据：G2 出现「3 假 DIFF + 1 假 FAIL」的根因 = worktree 行尾（CRLF vs LF）

> 只读取证，落盘于 `第94轮-基础宠物真机全功能验收/_evidence/`。
> 结论：**不是代码回归**，是本会话的 worktree 行尾与"基线冻结时的行尾环境"不一致。

## 1. 现象

换窗口后按交接单 §F 第一步复跑全量 G2，实测（`g2_after_revert_normalize.txt`）：

```
合计：PASS=4555 FAIL=1  套件=85
【问题】
  - persona_chat: 输出与基线不一致（无基线文本）… + persona_chat: 套件自身 FAIL（exit=1, fail=1）
  - check75c:     输出与基线不一致（无基线文本）…
  - check78:      输出与基线不一致（无基线文本）…
  - check89:      输出与基线不一致（无基线文本）…      ← 这个是**已知**随机项
```

交接单 §C 预期是「85 套件 / FAIL=0 / 84 IDENTICAL / 1 DIFF（check89）」。**多了 2 个 DIFF + 1 个 FAIL。**

## 2. 三条独立证据链

### 2.1 同一 commit，两棵工作树行尾不同

| 文件 | 本会话 worktree | Desktop 检出（上一窗口用的） |
|---|---|---|
| `ralsei_pet/assets/ralsei_persona.md` | **10136 B**（CRLF） | **9991 B**（LF） |
| `ralsei_pet/src/main.py` | 856142 B（CRLF） | （LF 为主） |

`git cat-file -s HEAD:…persona` = **9991**（LF）。10136 − 9991 = **145** = 该文件行数
⇒ 差值**恰好是每行一个 `\r`**，是行尾膨胀，不是内容增长。

### 2.2 全树 EOL 普查（`_tools` 外的只读脚本）

共同文件 2347 个（文本类扩展名）：
```
LF -> CRLF                1483      ← 本树被整体转成 CRLF
CRLF -> CRLF               730
LF -> LF                    19
MIXED -> CRLF                ~60     （多为 assets/npc/persona/*.txt）
```
⇒ **本 worktree 几乎整棵是 CRLF，而规范树以 LF 为主。**

### 2.3 逐条 diff：差异全部"非语义"

以 Desktop 的 `_out/*.baseline.txt` 为参照（那里有基线文本，本树没有）：

**check78**（69 行 → 69 行）差异只有两处：
```
 [PASS] B1 decide() 是模块级函数
+[PASS] B1 decide() 是模块级函数        ← 4 个尾随空格
 [PASS] G3 被测文件在盘上且非空    21634 B
+[PASS] G3 被测文件在盘上且非空    22182 B   ← 22182 − 21634 = 548 = 该文件行数
```

**check75c**（56 行 → 56 行）差异只有一处：
```
 [PASS] D2b …   <- idx: persona=0 who=4139 speak=4318
+[PASS] D2b …   <- idx: persona=0 who=4146 speak=4325    ← 纯下标平移
```

**persona_chat** 唯一 FAIL：
```
[FAIL] K3 persona 常驻体积已下降（世界观移出后 < 10KB）   size=10136
```
判据源码：`verify_persona_chat.py:906  os.path.getsize(PERSONA_MD) < 10000`。
10136 − 145(CR) = **9991 < 10000** ⇒ 按**内容**衡量是达标的。

⇒ 三条全是"**被读文件的字节数 / 字符下标**"，正是唯一会被行尾影响的量。

## 3. 机制

- `git config core.autocrlf` = **true**，仓库**无 `.gitattributes`**。
- ⇒ **每次 worktree 检出都会把仓库里的 LF 写成工作区 CRLF**。
- 基线（`code-quality-audit/regress/baseline.json` 的 sha256）是在**上一窗口那棵 LF 工作树**上冻的
  ⇒ 本树 CRLF 一跑，凡"打印字节数/下标"的判据立刻假红。
- 为什么 Desktop 那棵是 LF 且 `git status` 干净：那些文件当初是**经 git add 落盘**的，
  索引 stat 缓存已刷新 ⇒ `status` 不再逐字节复核。（本树重写文件后 stat 失效，
  `autocrlf=true` 会用"smudge 后的 CRLF 形态"去比对，于是 2298 个文件一度显示为 ` M`。）

## 4. 处置与验证

1. 逐文件比对两树：**内容（按 `\n` 归一后）逐字节相同**的文件才用规范树的行尾覆盖本树；
   内容不同的**一律不动**。实测：仅行尾差异 **2296** 个，内容真不同 **1** 个
   （`_evidence/g2_after_revert_normalize.txt` —— 那正是本次新跑出来的 G2 输出，属预期）。
2. 还原后 `git add -A` 刷新 stat 缓存 ⇒ `git status --porcelain` 仅剩 2 项真实改动
   （本轮新写/新跑的文件），`git diff --cached --numstat` = 2 行 ⇒ **零内容改动**。
3. 复跑 4 个受影响套件：

```
persona_chat   0  156  0  IDENTICAL
check75c       0   37  0  IDENTICAL
check78        0   38  0  IDENTICAL
check89        0   63  0  DIFF        ← 已知随机项，保持如实 DIFF，不掩盖
```

⇒ 与交接单 §C 的预期**逐条一致**。

## 5. 教训（值得写进记忆）

- ★★★ **换 worktree 就等于换行尾**：`autocrlf=true` + 无 `.gitattributes` 的仓库，
  新检出必然全 CRLF；而基线是在 LF 树上冻的 ⇒ 所有"字节数/下标"型判据会集体假红。
- **归因方法**：先看**差值是否等于行数**（`10136-9991=145`、`22182-21634=548` 都是行数）
  —— 这是行尾膨胀的指纹。
- **修法**：还原成与基线一致的形态（不是改判据、更不是 `--update` 掩盖），
  并用 `git add -A` 刷新 stat 缓存让工作区重新干净。
- ⛔ 这次**没有**用 `--update` 把 CRLF 指纹冻进基线：那会同时把 `persona_chat` 的
  **FAIL 状态**合法化，正是用户明令禁止的"抹掉行为让基线变绿"。
