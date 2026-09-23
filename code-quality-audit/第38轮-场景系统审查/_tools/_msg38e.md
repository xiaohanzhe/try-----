第38轮续三：修掉"记忆注入上限"的错判据（代码实证 200 行 / 25,000 字节）

## 事故
会话开头系统提示 MEMORY.md 超限被截断。我据速查本里自己写的旧判据
（"上限看字符数，实测 ~12000"）判定"影响读取"，把 MEMORY.md 从 11,446
重写到 12,252 字符 —— 体积涨了、却丢了 4 个可检索令牌：

  真机打点落 CSV / 真背景原样提取 / chapter*10000 / prefill 远慢于 decode

## 根因
把自己"估"的数字当成了实测上限。

## 代码实证（权威）
resources/app.asar.unpacked/cli/dist/codebuddy-headless.js 里
buildAgentMemoryPrompt 的定义：
  ep="MEMORY.md", eh=200, ef=25e3
  if (Buffer.byteLength(ea,"utf-8") > ef) { ...截到 25000 字节... }
⇒ MEMORY.md 注入上限 = 200 行 / 25,000 字节（utf-8 字节数，不是字符数）。
实测事故后文件 = 111 行 / 20,932 字节 ⇒ 本来就在限内，那轮压缩是纯损失。

服务端那句 "exceeded the size limit ... truncated during injection"
在本地产物里 grep 全 resources/ 无命中 ⇒ 来自服务端链路，阈值未证实。

## 处置
1. 4 个令牌逐个回填速查本；头部错误判据改成代码实证口径。
2. 详版新增 §39.11（含事故表、代码片段、证据脚本路径、教训）。
3. skill agent-memory-compaction 同轮修正（它写着同样的错判据），
   新增「上限的真实来源」一节 + 复现脚本 find_mem_limit.py。
4. 新增 _tools/recheck_mem38.py：38 项复检（体积/行数/编码/结构/令牌/
   负面控制/指针），当前 38 PASS / 0 FAIL。
5. 新增 find_mem_limit.py / find_mem_limit2.py / mem_sections.py /
   verify_mem_tokens.py 四个取证脚本。

## 复检
recheck_mem38.py → PASS=38 FAIL=0
  quick.bytes=20932 (<=25000) / quick.lines=111 (<=200)
  无 BOM / 无 U+FFFD / 纯 LF / 12 个 ## 标题齐全 / 无粘连
  假令牌 ai.github、CLOSED_NONE_PLACEHOLDER_X 均查不到（判据有鉴别力）
