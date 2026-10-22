# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **全文在 `参考-契约与历轮（详版）.md`**（不注入）。留铁律+索引+裁定。
> ⚠️ 真口径＝**JS 长度**（含 CRLF）；**别为凑上限削语义**；读文件**字节忠实**（`newline=''`）。❗❗**只许 Write/Edit**；**日志 append-only**。
## 0. 铁律
- 每轮改动即 **commit+push**；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- ❗**仓库根=`try - 副本`**（`ralsei_pet` 子目录）⇒**G2 cwd=仓库根**。远端 `github.com/xiaohanzhe/try-----.git`（★公开）。真机起＝`src/main.py`（单实例锁 `Global\RalseiPetMutex`；透明非置顶⇒**甩飞/抛物线只可离屏断言**）。
- ★★★ **按键账本 API**：`self.soul`=`SoulOverlay`⇒**只能 `release_all()`**；`soul.state`=`SoulState`⇒**只能 `clear_keys()`**。写错=静默 `AttributeError` 被吞（`check84 D5`）。
- 改码前先跑 G2 `regress/run_all.py`（须**全 IDENTICAL**）；改断言/文案→`--only <suite> --update`。★★ **新增合法零依赖模块撞两闸**：`round5_smoke`（模块数）＋`scene_p0` **A6 白名单**（手加 `_CTL_ALLOWED`）。★ **只读优先、改动最小**；★"写了 N 个文件"须 `os.listdir` 查盘；★★ **回归套件不许依赖临时区/外部盘**⇒**蒸馏进仓库**。❗❗**改过"重要核心文件"必复检**（skill `core-file-recheck`）。★★★ **改两层登记前先查重复键**（`json` 取最后一个⇒静默错值）；★★ **老套件 BASE 可能硬编码⇒worktree 里测错树**。
## 1. 环境（细则 §1/§18/§19/§21/§23.10/§37/§65.2）
- ⚠️ **Bash 常整体坏掉**（`ls/head/cat` 全 127）→ **一律 Python+Write/Read**。❗别从 Bash 调 PowerShell；❗❗**别内联 `python -c`**（反引号/`\n` 被吞）。Python 一律 **`C:\Python311\python.exe`**；后台 `&`+`run_in_background`，杀用 psutil。❗❗❗ **未提交文件绝不能 `git checkout --`**⇒ 改重要文件前先 commit/留备份。
- ★★ **写入通道会整体失效**（~25min 自愈）：已有文件写/改/移全拒、**新建正常**⇒只产新文件+换名。
- ❗❗**临时/备份绝不放工作区**（`git add -A` 记为删除）⇒ 一律 `E:\Download\_tmp\`；**提交前必看 `git diff --cached --numstat`**。❗**清理守卫累计删（50）**：症状=**import 期被 SIGTERM、零输出**⇒**改名归档**。
- ⭐⭐ 代理**逐端口实测 CONNECT** 再选。⭐⭐ **编辑保持原 EOL**；中文路径⇒`git ls-files -z`+`surrogateescape`。
- ★★★ **游戏文件+UTMT⇒详版 §87.10(a)/§76.2/§76.3**（`UndertaleModCli.exe` **只认 `load <data> -s <script.csx>`**·**stdout 须落文件**）。
## 2. git push（skill `win-git-utf8-push`；**§39.5/§37.13/§71.4/§101.13**）
- ★★ **一把跑完 = `…/第38轮-场景系统审查/_tools/gitpush.py <msgfile> [--proxy <url>] [--allow-del N]`**。提交信息用 **Write 写 UTF-8+`git commit -F`**（`-m` 假成功）。⛔ **绝不循环重试 push**。★★★ **worktree 已修**（`REPO` 硬编码／refspec 固定 `main`⇒假成功）：`HEAD:main`+自证 `[0r]`。
- ★ `--allow-del` **带数字**；超限先 `numstat` 归因。❗**核验命令自己会说谎**⇒`ls-remote` **独立构造**+3~5 重试+`rev-parse origin/main` 交叉验证＋**必带 CA**（否则 TLS 假阴性）。
- ★★ 两根因（**细节 §39.5**）：**TLS**⇒`sslBackend=openssl`+HTTP/1.1；**凭据**⇒直取 GCM；`subprocess.run(input=…)` **必喂 bytes**。
## 3. 勿回退契约（13 组；**原文见详版 §75.10**+§4.1–§4.12/§10/§23.9）
① `availableGeometry()` 只返主屏⇒用 `_virtual_screen_rect()`；★ **首帧落点**＝`pick_corner_screen_work_area()`；② **建楼**：`floor_visible_contains` 唯一判据·禁 `WindowStaysOnTopHint`·甩飞必 `_fall_reason=None`·先 `show()` 再调 z 序·⚠️ **`climb_1_*`=朝右／`climb_0_*`=朝前**；③ `data_store` 唯一入口（vault=`E:\RalseiMemory\`，迁移**只复制**）· 裸进程脚本**先建 `QApplication`**；④ **G2 有 `HERMETIC_IDS`**·`save_baseline` **合并模式**·**新套件必须 `print('[PASS] %s')` 字面量**·判据名禁自带标记·置 `<轮次>/`⇒`ROOT=join(HERE,'..','..')`；⑤ ★★ 量桌宠/浮层**先声明 DPI 感知**；★★★ **透明分层窗口⇒屏幕工具"可见面积"失效**（几何仍准）⇒Win32 `IsWindowVisible`+内省对账（§73.8）。
**误报清单（勿改）**：`learn_new_skill`｜`_on_ai_reply`（已 `pyqtSignal`）｜`reset_special_states`｜`pet_interaction.py`（**零接线**）。
## 4. 验证脚本教训（**原文见详版 §75.9+§95.13+§96b.1+§107.7+§108.6/§108.7**）
- ⭐**能上 AST 就上 AST**（`code_only_src()` 剥 STRING⇒断言字面量恒假；含字面量走 `code_no_comment()`）。★★★ **"禁某 API 出现"类判据禁纯文本扫**（注释/串提名字即误报；**已五次**，§108.6）。★ 复检**不许改变被测状态**（`py_compile` 产 `.pyc`⇒用 `ast.parse`）。
- ★★★ **恒真判据比不写还危险**；**判据过窄=误报**；**正/负控制成对**·**断行为不断赋值**·**A/B 先断言 A≠B**·**负控制输入必真落进被测分支**·**no-op 必显式打印**。★★★ **负控制须"拆干净"**（多道防线**同拆**才复现）；**观察量须由产品代码判**；临时变量**别用 `_n`**。❗**报红三步**：夹具真破坏？→**再疑判据**→命中真守卫？★★★ **夹具不保真=报假问题**⇒**破坏必报红**；**判据也是被测物**⇒**DIFF 必看**。★★★ **判据别被"标题/注释/别处"喂饱**（115轮 `A4`）；**变异锚点禁 `replace(old,new,1)`+禁"全文唯一"假设**。
- ★★★ **反汇编/解析器先过 A/B 锚点**；**新写的 `try/except` 分支须独立验证**；**判据禁回显随时相变绝对值**；★ **`ast.walk+break` 抓"第一个匹配"是陷阱**；★★ **CRLF 锚点必先 `_lf()`**；★★★ **取新增状态位一律 `getattr(x,'k',None)`**／**桩比产品旧＝假红**；★★ **`--only` 是 `action='append'`**⇒须**两次 `--only`**；★★★ **阈值别用"代理量"**⇒**重标定+配正控**、**不许为变绿放宽**。
## 5. 人味改造线（细则 **§23.13.1+§6.1–§6.10**）
回归锁 `persona_chat`／`s8_stream`／`s7_event_speech`。★ **两条人设线**：**Ralsei 本人**=`assets/ralsei_persona.md`（单一真源，system **替换**它）；**NPC** 见 §7。**禁 markdown**、**❗不许叫"主人"**。★★ **失真头号来源="可逐字搬走的固定例句"**（锁 **A12d**）；**口癖多≠全砍**（8.3% 是真结巴）。护栏 `_clean_ai_reply(reply, recent=)` **顺序即优先级**；**判退必重采样**、**不 append 进 recent**；`AI_REPLY_MAX_CHARS`=220。
## 6. H4/H5 拆分（休眠线）⇒ 详版 §8.1–§8.6；勿重测。
## 7. 场景/伙伴/道具/球/人设/幽灵线 ★ **动手前必 Read 详版 §87.11（令牌全表）**
口径：**「把原作的世界搬到桌面上…桌面也是一个场景」**＋**「一切根据原作」**＋**「任何素材都从这里找」**。
- ★★★ **桌面只 4 门（§109.2）**＝三角符文(小镇中心)/OneShot(Niko家下方车厢)/UT(坠落处)+**Niko的家**(例外)；**挨屏幕边框**；**当原作门逐门寻路（禁瞬移）**；★★★ **Niko 的家＝彩蛋**（三连确认**永远进不去**，选"我确定"⇒爆炸后变回）；**只 5 章**。★ `desktop.json` 4 扇(正上A/正下B/正左C/正右D、贴边、**全静态无 anim**)＋`_routes.json` 4 条。
- ★★★ **相机/换房/拓扑**：**背景移动＝相机平移不是视差**；门＝`Data.Rooms` **下标偏移**（A+1/B-1/C+2）；**无门＝不可达**；**对象索引按名字**。
- ★★ **世界门控**：光世界**不需球**（**Ralsei 例外必须靠球**）／暗世界只进自己登记的章；★ **球缩放由 `fit_scale` 反推，禁硬用 1.55**。
- ★★★ **人设/幽灵**：真源 `assets/npc/persona/*.txt`（**76**）+`_registry.json`（**96**）；★★ 切块**不能按 `---`**；★★★ **两层登记**都要；★ 幽灵已接线（轴＝**与 Kris 接触时长**）。
- ★★★ **R5 附身＋R6**：**附身＝换方向键的消费方**（`possession.py` **零依赖**）；**`POSSESSION_KINDS` 全 `KIND_CONSENT`**；**R5/R6 互斥**；R6＝**轨迹延迟采样**（**未带路⇒`step` 返 None**）。
- ★★★ **I1~I10 / B6 / R1**：**移速是表不是常量**（暗段1 `+2`、段3 `+5`）；**I10 只记不毁**⇒**NPC 一律放行、无出场门控**；B6 走**同一条** `npc_speak`、**失败必 `loop.abort`**；R1 `home`≠`scene`、`home_of()`＝**登记 home > 回落 scene > None**、★★★ **`npc_roam._call` 两参**、★★ **`by_source()` 只数站位**。
- ★★★ **「灵魂视角」＝显示切换的唯一驱动**（§109.5/§113）：**只有灵魂/我的视角移动才切显示**；★★ **NPC 自主移动不切显示但≠不存在**；可派**任何角色**去别世界办事（「派 Ralsei」只是**举例**）、**中途进场能看到过程**。
## 8. 性能线 ★ 铁律⇒**动手前 Read §78.11**
- ★★★ **首字/并发/`keep_alive` 三铁律**：冷热差 23~190 倍·`NUM_PARALLEL=1`⇒并发＝排队·`keep_alive` 必走原生 `/api/chat`（底座 `ralsei:v4`·`api.timeout≥60`）。★ **115轮**：首字瓶颈＝**prompt 长度**（冷 prefill 21~27s·热 3~10s·冷载入 77s），**换大模型更慢**。
## 9. 用户口径（**优先于我的技术判断**）
- **「prompt 尽量完整」**⇒提速只靠**缓存／后端／模型**（不许砍 prompt）。**「用 7B 就是要他贴合人物且不出 bug」**。**「结巴」**=**减少但不许到 0**⇒**待排期**。**「开机自启」＝选项非硬性**。★★ **当前主轴见 §7**；**工作方式**「**测完了没问题后按你的计划来**」⇒**测绿即连续推进**、这阶段 ok 才进下一阶段。★ **范围**：暗世界也做⇒**全部 1,251 间**。
## 10. 历轮索引
**锁号速查**（新→旧）：`check118`(**31**)+`check118_rec`(**36**)+`mutate118`(**7/7**)+`mutate118_rec`(**10/10**)·`check117`(**40**)+`mutate117`(**14/14**)·`check116`(**40**)+`mutate116`(**11/11**)·`check115`(**25**)·`check114`(**84**)；113 及更早见详版 §72~§114。
**近轮指针**：95＝3 真 bug＋**G2 首零 DIFF**｜96/99~105＝详版同名节（`K_ROOM_FILL`·379帧·7804接线·opacity/blend·code-201/420）｜102＝光照归因＋7,805 普查｜106＝非瞬移＋全屏初版｜107 起见 §19~§22。
## 11. 待裁定/已裁定（★**已裁定的绝不重问**；全文见详版 §71+§*.9）
**★★★ 口径（81/96轮）**：「记忆不要随便修改」＝**角色的记忆**（`data_store`）**非**助手记忆⇒**该记就记**、**不许再问**。动记忆门槛：**实证超限/被要求＋先补详版＋逐令牌回验＋守恒**；★★ **`check95 A2` 硬闸**（`js_len ≤ 10000`＝**UTF-16 码元数**）。❗别说成"尊重用户口径"。
**已落地/🟢已裁定/遗留池 ⇒ 正文与令牌全在详版 `§71补`**（115轮下沉）。速查留三条：**`has_ball` 不删** / `move_to_edge_and_shrink()` **零调用⇒只记不修** · **35 角色未登记 `home`**（回落 `scene`）· **99 置顶窗口** vs 契约②**有张力⇒待澄清**。
## 19. 107/108/110/112·全屏化＋全局缩放⇒ **详版 §107/§108/§110/§112续四**
- ★★★ 口径 6 条（全文 §107）：场景全屏·按比例铺满留黑边·相机跟随宠物·非桌面不透壁纸/图标/任务栏·全局放大·UI 也放大。★★★ **原作 UI 不缩放**＝**我们的产品口径**，不许假装还原。★未做：隐字母。
- ★★★ **【112续四】已落地**（详版 §112续四；锁 `check107`/`check112`）：门拆出场景·room **0.5 档**（`SCENE_FIT_FRACTION`）·非桌面**黑边**／桌面**透明**·`PET_MAX_LONG_SIDE_PX` **≤144px**（**只减不增**）·`camera.scale=out_w/320`·`ui_scale()`＝**√**钳 `[0.5,3.0]`（**幂等＝快照+重算**）。
## 20. 114·差事「门控＋派发＋落盘」⇒ **详版 §114**
- ★★★ **门控** `world_gate(npc,world,scene_id,carried)` **四条按序**：**⓪桌面** `DESKTOP_ALLOWED_IDS`=ralsei/kris/susie/lancer（**必先于光世界**）→①光世界 `light_needs_bubble` 假即放行、真＝**仅 Ralsei**+`escape_via_bubble`+`carried`→②暗世界 `roam_scope`：`ALL`**仅 Niko**→`chapter_matches`→`free_dark_roam`**仅 Ralsei**；迁入章判不出⇒**保守归 `dark`**（`A8`）。★ 章名 `ut`/`uty`↔`undertale`/`undertale_yellow` 在**比较处归一**（`CHAPTER_ALIASES`，数据不动）。
- ★★★ **入口/落盘**：`handle_errand_command` 挂 `send_message`（**回显后、指令前**）；**拒分支也必落一次记忆**（`_npc_errand_note` 在 `if` / `assign_errand` 在 `elif`，**互斥**）；台词全交 `chat_with_ai`（`speaker=None`）；`npc_errands.json` 必须 `json`+`from_dict`（`load` 只认 `schema_version==1`⇒**恒空**）；`_npc_errand_tick` 排 `_npc_roam_tick` **之后**。

## 21. 115·AI人味训练（受控A/B⇒改人设）⇒ **详版 §115**
- ★★★ **L1 先做**（persona＋参数＋护栏）；**L3 未攒够数据集前禁谈**。
- ★★★ **写进 prompt 的字面都会被照着说 ⇒要写就写"你想要的"那句**（反面例句=毒药）；**「就该说X而不是Y」的对照式示范有效**。
- ★★★ **`HTTP_PROXY`⇒urllib 连 localhost 也丢代理**=502 假故障（必 `ProxyHandler({})`）；**沙箱结束拆进程树**。★**新口径**：知道是游戏·**不悲观**。
- ★ **115 遗留**见详版 §115：Q6 **1/4**·`tail_sha256`/`apply115_npc` **19/0**·L2／L3／流式未做。
- ★★ **115 判据教训**：**判据"崩掉"比"报红"更糟**（缺文件如实 FAIL）；**出戏闸禁放"身份词"**（`机器人` 拦死 4 位）。

## 22. 116~117·门贴图（黑底/黑光）＋四门放大＋沙箱 ⇒ **详版 §116＋§117**
- ★★★ **沙箱真源头=`RALSEI_MEMORY_DIR`**（`data_store` 只是包装层）⇒ **三把闸在 `import main` 之前**（`vault_guard` 指纹量）。
- ★★★ **桌面画布吃 `availableGeometry()`**（铺满⇒被当全屏⇒任务栏 5.72Hz 翻）；`raise_()` 只许在 `_just_shown`。
- ★★★ **原作贴图本身是黑底卡片**（门 C/D 纯黑 76.4%/82.6%）⇒ 桌面变体 `desk_door_ut`/`desk_door_deltarune`（尺寸不变）·**原件不改**（暗世界在用）；**门 D＝巨门框**（§116）。
- ★★★ **门 A=`objs/desk_door_oneshot_black.png`**（`niko_door_portal` 黑光变体：同 192×128·**alpha 逐像素一致**·`R=4+96t/G=2+24t/B=6+84t`）；门 B/C **不动**；`spr_darkdoor_0` 留盘。
- ★★★ **门大小唯一旋钮 `DOOR_FIT_CAP` 1.2→1.6**（「大一点都」＝四门都大）：pet(144,98)·k=1.0116·D 182×157（§117.3）。
- ★★★ **真机像素对账**：`drawPixmap`＝**最近邻**⇒判据须 **NEAREST+腐蚀1px 只比内部**（§117.9）。
- ★★ **对话框**：`fade_plan` 唯一真源·`STEADY_EPS=0.05`·判据禁只看"提到 `setOpacity`"（§116.3）。
- ★★ 老套件改口径见 §116：`check89` A→(64,0)·`check112` N15/N18a；**CRLF 锚点带 `\r\n`**。
- ★★★ **判"看不看得见"须 1:1 带上下文**（缩略拼图抹掉 17.5% 的金框 ⇒ 误判"门 D 看不见"、差点改下限 `MIN_ALPHA`；已回退 0.14，ΔE 11~14 够）；**对话框避让门 B**＝门不挪·框上抬（遮挡 0%）⇒ §117.11。


## 23. 118·门可达性＋录屏复核 ⇒ **详版 §118**
- ★★★ **桌面门按屏幕几何选** `_desktop_door_pick`：灵魂恒停⇒站哪都进三角符文。
- ★★★ **每帧驱动 `update()` + 重建道具先 `release`**：否则推一次门⇒**交互永久失灵**。
- ★★★ 彩蛋选择框＝`dr_choice`（原作框+红心），**禁 QMessageBox**；桌面 actor=`pet`；**框让位对话气泡**（`_dialogue_rect`+`GAP_PX=10`；旧叠 61px）。
- ★★★ **录屏三坑**：同一 QTimer 不能在自己槽里重入（模态零帧⇒`singleShot(0)`）·`QImage` 是 BGRA⇒喂 `PIL` 当 RGB **红蓝颠倒**·`pet.show()`+`frameGeometry()` 证几何。
- ★★ 判据先 append detail 再 print（否则 **FAIL 不打印**）；**不能评估就如实 FAIL，禁 `if got:` 静默跳过**（变异漏判）。
