# Mac 每日冷备（ralsei_pet）— 执行记录

任务：跑 `code-quality-audit/第197轮-Mac冷备节点/_tools/mac_backup.py --keep 7 --json D:\_tmp\backup_result.json`，
判读输出（要 `=== BACKUP_OK` + `差异=0`/`IDENTICAL`），成功/失败各一行追加到当日日志。

## 历史

- **2026-11-18 23:00** — OK。files=3380 packed=28.1MB sha=a07cfa73be61，双端 sha256 一致，
  hash 多重集差异 0，远端轮转后 dirs=1 packs=1。已追加日志行（LF 文件，二进制追加，未改动原有内容）。
- **2026-11-19 23:00** — OK。files=4100 packed=30.7MB sha=55b3323d2b86（传输 shasum 一致、
  差异=0 / IDENTICAL），含 199、200 两轮审计目录，远端 dirs=2 packs=2。日志纯追加 1 行（numstat 1/0），
  文件仍为 LF。文件数较昨日 +720，属新增两轮审计产物，正常。

## 操作要点（下次照做）

- 工作目录必须是仓库根 `try - 副本`（脚本按 `HERE/../../..` 推 REPO）。
- 成功判据只看 stdout 的 `=== BACKUP_OK` 与 `差异=0`，退出码单独不可信。
- 失败排查顺序：ssh/ConnectTimeout（Mac 不在局域网属预期）→ 磁盘满 → 脚本报错；最多再试一次。
- 脚本若在前几步失败**不会写 json**（`_emit` 只在成功与差异≠0 时调用），此时别把"缺 json"当新故障。
- 追加日志用二进制 append（该文件是 LF、结尾多空行），不要用会重写整份的工具。
- 不做 git commit/push。
