# G2 回归基线

一条命令跑完全部回归套件，并对**归一化后的输出**做逐字节比对。

这是 `架构改造排期方案_H4-H5_2026-09-13.md` §3 G2 的产物。
H4（上帝类拆分）的安全性判据是"行为完全不变"，只能靠"改造前后跑同一套回归、输出逐字节一致"来证明；
此前项目的 9 个手工冒烟脚本 + 每轮 verify 脚本各自为政、且没有一个能一键跑，这是拆分最大的障碍。

## 用法

```bash
# 用装了 PyQt5 的 Python 跑（本机是 C:\Python311\python.exe）
python code-quality-audit/regress/run_all.py              # 跑全部 + 与基线比对
python code-quality-audit/regress/run_all.py --list       # 只列套件
python code-quality-audit/regress/run_all.py --only s1    # 只跑名字含 s1 的
python code-quality-audit/regress/run_all.py --verbose    # 附带原始输出
python code-quality-audit/regress/run_all.py --show-diff s1   # 看某套件的差异
python code-quality-audit/regress/run_all.py --update     # 重建基线（仅当改版是有意的）
```

退出码：`0` = 全部 PASS 且与基线一致；`1` = 有套件 FAIL / DIFF / 出错。

## 三项判定

每个套件都要同时满足才算 `IDENTICAL`：

| 项 | 说明 |
|---|---|
| `exit` | 子进程退出码 |
| `pass` / `fail` | 输出里的 `[PASS]` / `[ OK ]` 与 `[FAIL]` 计数 |
| `sha256` | **归一化后**文本的哈希 |

## 为什么要"归一化"

不然每次跑哈希都不一样，比对就没意义。归一化会抹掉：

- 时间戳（`2026-09-13 20:04:58`）
- 内存地址（`0x7ff...`）
- 耗时（`耗时: 1.23 秒`）
- 绝对路径（统一成 `<ROOT>`）、临时目录（`<TMP>`）、PID、内存占用
- 行尾空白与连续空行

## 为什么要固定随机种子

`verify_round5_fixes.py` 的 V2b 用 `random.choice([...])` 挑承接语：
两次运行分别给出 `你想查看系统的哪个具体指标？` 与 `需要我再次检查系统状态吗？`，
**不改就会让基线永远 DIFF**。

因此所有套件统一经 `_seed_runner.py` 启动（`random.seed(20260913)`），
并由 `run_all.py` 注入 `PYTHONHASHSEED=0`，把 `set` 的字符串迭代顺序也钉死。

## 套件清单

| id | 来源 | 覆盖 |
|---|---|---|
| `round5_smoke` | `第五轮/smoke_import_round5.py` | 22 个 modules 全量导入 + 2 个源码不变量 |
| `round5_verify` | `第五轮/verify_round5_fixes.py` | 16 项缺陷修复断言 |
| `round6_verify` | `第六轮/verify_round6_fixes.py` | 39 项行为修复断言 |
| `s1_anim_miss` | `架构改造-H4H5/verify_s1_animation_miss.py` | 动画名未命中自检 17 项 + 501 样本等价性 |
| `s2_anim_json` | `架构改造-H4H5/verify_s2_animations_json.py` | animations.json 与硬编码表深度等价 |
| `s3_alias_legacy` | `架构改造-H4H5/verify_s3_alias_legacy.py` | alias_of / legacy 显式化后语义等价 |

脚本不存在时该套件记 `SKIP`（不判 FAIL），便于边加边跑。

## 当前基线

`baseline.json`：4 个套件、**94 PASS / 0 FAIL**，连续两次运行均 `IDENTICAL`。

产物落在 `_out/`（已 gitignore）：`<suite>.txt` 原始输出、`<suite>.diff.txt` 差异、
`<suite>.baseline.txt` 上一次的归一化文本（供 `--show-diff` 做行级对比）。
