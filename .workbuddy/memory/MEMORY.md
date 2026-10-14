# 项目记忆 — ralsei_pet（Deltarune Ralsei 桌宠）

> **全文在 `参考-契约与历轮（详版）.md`**（不注入）。留铁律+索引+裁定。
> ⚠️ **别为凑"上限"削语义**；真口径＝**JS 长度**；读文件**字节忠实**（`newline=''`）。❗❗**只许 Write/Edit**；**当日日志 append-only**（细则 skill `agent-memory-compaction`）。
## 0. 铁律
- 每轮改动即 **commit+push**；称呼"用户"；技术细节我拍板；不可逆/对外动作先说影响面。
- ❗**仓库根=`try - 副本`**（`ralsei_pet` 子目录）⇒**G2 cwd=仓库根**。远端 `github.com/xiaohanzhe/try-----.git`（★公开）。真机起＝`src/main.py`（单实例锁 `Global\RalseiPetMutex`；透明非置顶⇒**甩飞/抛物线只可离屏断言**）。
- ★★★ **按键账本 API（84轮）**：`self.soul`=`SoulOverlay`⇒**只能 `release_all()`**；`soul.state`=`SoulState`⇒**只能 `clear_keys()`**。写错=静默 `AttributeError` 被吞（`check84 D5`）。
- 改码前先跑 G2 `regress/run_all.py`（须**全 IDENTICAL**）；改断言/文案→`--only <suite> --update`。★★ **新增合法零依赖模块撞两闸**：`round5_smoke`（模块数）＋`scene_p0` **A6 白名单**（手加 `_CTL_ALLOWED`）。★ **只读优先、改动最小**；★"写了 N 个文件"须 `os.listdir` 查盘；★★ **回归套件不许依赖临时区/外部盘**⇒**蒸馏进仓库**。❗❗**改过"重要核心文件"必复检**（skill `core-file-recheck`）。★★★ **改两层登记前先查重复键**（`json` 取最后一个⇒静默错值）；★★ **老套件 BASE 可能硬编码⇒worktree 里测错树**。
## 1. 环境（细则 §1/§18/§19/§21/§23.10/§37/§65.2）
- ⚠️ **Bash 常整体坏掉**（`ls/head/cat` 全 127）→ **一律 Python+Write/Read**。❗别从 Bash 调 PowerShell；❗❗**别内联 `python -c`**（反引号/`\n` 被吞）。Python 一律 **`C:\Python311\python.exe`**；起进程 `&`+`run_in_background`，杀进程用 psutil。❗❗❗ **未提交文件绝不能 `git checkout --`**（109轮抹掉 4 门改写）⇒ 改重要文件前先 commit/留备份。
- ★★ **写入通道会整体失效**（~25min 自愈；E 盘瞬时 `Errno 22`）：已有文件写/改/移全拒、**新建正常**⇒只产新文件+换名。
- ❗❗**临时/备份绝不放工作区**（`git add -A` 记为删除并提交）⇒ 一律 `E:\Download\_tmp\`；**提交前必看 `git diff --cached --numstat`**。❗**清理守卫累计删（50）**：症状=**import 期被 SIGTERM、零输出**⇒**改名归档**。
- ⭐⭐ **代理端口逐端口实测 CONNECT 再选**。⭐⭐ **编辑保持原 EOL**；中文路径⇒`git ls-files -z`+`surrogateescape`。
- ★★★ **游戏文件+UTMT⇒详版 §87.10(a)/§76.2/§76.3**（`UndertaleModCli.exe` **只认 `load <data> -s <script.csx>`**·**stdout 须落文件**）。
## 2. git push（skill `win-git-utf8-push`；**§39.5/§37.13/§71.4/§101.13**）
- ★★ **一把跑完 = `…/第38轮-场景系统审查/_tools/gitpush.py <msgfile> [--proxy <url>] [--allow-del N]`**。提交信息用 **Write 写 UTF-8+`git commit -F`**（`-m` 假成功）。⛔ **绝不循环重试 push**。★★★ **worktree 下已修**：原 `REPO` 硬编码＋refspec 固定 `main`⇒**全绿却假成功**；现 `HEAD:main`+自证 `[0r]`。
- ★ `--allow-del` **带数字**；超限先 `numstat` 归因。❗**核验命令自己会说谎**⇒`ls-remote` **独立构造**+3~5 重试+`rev-parse origin/main` 交叉验证＋**必带 CA**（否则 TLS 假阴性）。
- ★★ 两根因（**细节 §39.5**）：**TLS**⇒`sslBackend=openssl`+HTTP/1.1；**凭据**⇒直取 GCM；`subprocess.run(input=…)` **必喂 bytes**。
## 3. 勿回退契约（13 组；**原文见详版 §75.10**+§4.1–§4.12/§10/§23.9）
① `availableGeometry()` 只返主屏⇒用 `_virtual_screen_rect()`；★ **首帧落点**＝`pick_corner_screen_work_area()`；② **建楼**：`floor_visible_contains` 唯一判据·禁 `WindowStaysOnTopHint`·甩飞必 `_fall_reason=None`·先 `show()` 再调 z 序·⚠️ **`climb_1_*`=朝右／`climb_0_*`=朝前**；③ `data_store` 唯一入口（vault=`E:\RalseiMemory\`，迁移**只复制**）· 裸进程脚本**先建 `QApplication`**；④ **G2 有 `HERMETIC_IDS`**·`save_baseline` **合并模式**·**新套件必须 `print('[PASS] %s')` 字面量**·判据名禁自带标记·置 `<轮次>/`⇒`ROOT=join(HERE,'..','..')`；⑤ ★★ 量桌宠/浮层**先声明 DPI 感知**；★★★ **透明分层窗口⇒屏幕工具"可见面积"失效**（几何仍准）⇒Win32 `IsWindowVisible`+内省对账（§73.8）。
**误报清单（勿改）**：`learn_new_skill`｜`_on_ai_reply`（已 `pyqtSignal`）｜`reset_special_states`｜`pet_interaction.py`（**零接线**）。
## 4. 验证脚本教训（**原文见详版 §75.9+§95.13+§96b.1+§107.7+§108.6/§108.7**）
- ⭐**能上 AST 就上 AST**（`code_only_src()` 剥 STRING⇒断言字面量恒假；含字面量走 `code_no_comment()`）。★★★ **"禁某 API 出现"类判据禁纯文本扫**（注释/串一提名字即误报；**已五次**，§108.6）。★ 复检**不许改变被测状态**（`py_compile` 产 `.pyc`⇒用 `ast.parse`）。
- ★★★ **恒真判据比不写还危险**（85轮 `{}=={}`）；**判据过窄=误报**；**正/负控制成对**·**断行为不断赋值**·**A/B 先断言 A≠B**·**负控制输入必真落进被测分支**·**no-op 必显式打印**。★★★ **负控制必须"拆干净"**：多道防线**同拆**才复现（§95.13；107轮再证）；**观察量须由产品代码判**；临时变量**别用 `_n`**。❗**报红三步**：夹具真破坏？→ ★★**再疑判据本身** → 命中真守卫？★★★ **夹具不保真=报假问题**（`mutate85`⇒**全绿比报红更危险**）⇒**破坏必报红**。★★ **"判据也是被测物"**⇒ **DIFF 必看**。
- ★★★ **反汇编/解析器先过 A/B 锚点**；**新套件进 `SUITES` 必 `--update`**；**全量回归须机器统计比对列**；**新写的 `try/except` 分支须独立验证**（93轮 `numScreens()` 被吞）；**判据禁回显随时相变绝对值**（含**行号**）；**夹具别绑注释字面量**⇒AST 定位；★ **`ast.walk+break` 抓"第一个匹配"是陷阱**（§96b.1）；★★ **token 回验允许等价写法**；★★ **CRLF 锚点必先 `_lf()`**。★★★ **取新增状态位一律 `getattr(x,'k',None)`**／**变异锚点禁 `replace(old,new,1)`+禁"全文唯一"**／**桩比产品旧＝假红**（107轮，§107.7）。★★★ **判据只判"提到某名字"＝恒真**（108轮 `F6`/`C2b`：改判 **AST 结构化**）。★★ **`run_all.py --only` 是 `action='append'`**⇒须**两次 `--only`**。
## 5. 人味改造线（细则 **§23.13.1+§6.1–§6.10**）
回归锁 `persona_chat`／`s8_stream`／`s7_event_speech`。★ **两条人设线**：**Ralsei 本人**=`assets/ralsei_persona.md`（单一真源，system **替换**它）；**NPC** 见 §7。**禁 markdown**、**❗不许叫"主人"**。★★ **失真头号来源="可逐字搬走的固定例句"**（锁 **A12d**）；**口癖多≠全砍**（8.3% 是真结巴）。护栏 `_clean_ai_reply(reply, recent=)` **顺序即优先级**；**判退必重采样**、**不 append 进 recent**；`AI_REPLY_MAX_CHARS`=220。
## 6. H4/H5 拆分（休眠线）⇒ 详版 §8.1–§8.6；勿重测。
## 7. 场景/伙伴/道具/球/人设/幽灵线 ★ **动手前必 Read 详版 §87.11（令牌全表）**
口径：**「把原作的世界搬到桌面上…桌面也是一个场景」**＋**「一切根据原作」**＋**「任何素材都从这里找」**。★ 令牌全在 §87.11：
- ★★★ **桌面 4 个门（§109.2）**：**只 4 个**＝三角符文(小镇中心)/OneShot(Niko家下方车厢)/UT(坠落处)+**Niko的家**(例外)；**挨屏幕边框**；**当原作门逐门寻路（禁瞬移）**；★★★ **Niko 的家＝彩蛋**（原作无素材⇒用原作 Niko 回家光门做门，三连确认**永远进不去**，选"我确定"⇒爆炸特效后变回"我再考虑考虑"）；**只 5 章**。★ **已落地(109)**：`desktop.json` 4 扇(正上A/正下B/正左C/正右D、贴边、外观＝任意门`spr_darkdoor`44×56、`anim`3帧)+`_routes.json` 桌面 4 条(总872→867)：A→`oneshot.mainline.INIT`｜B→…`.Start`｜C→`ut.rooms.room_start`｜D→`ch1.hometown.town_mid`。
- ★★★ **相机/换房/拓扑**：**背景移动＝相机平移不是视差**；门＝`Data.Rooms` **下标偏移**（A+1/B-1/C+2）；**无门＝不可达**；**对象索引跨章不稳⇒按名字**。
- ★★ **世界门控**：光世界谁都能去**不需球**（**Ralsei 例外必须靠球**）／暗世界只进自己登记的章；★ **球缩放由 `fit_scale` 反推，禁硬用 1.55**；★★ **桌面闸排 `world_gate` 第0条**。
- ★★★ **人设/幽灵**：真源 `assets/npc/persona/*.txt`（**76**）+`_registry.json`（**96**）；★★ 切块**不能按 `---`**；★★★ **两层登记**都要；★ 幽灵已接线（轴＝**与 Kris 接触时长**）。
- ★★★ **R5 附身＋R6 带灵魂走**：**附身＝换方向键的消费方**（`possession.py` **零依赖**）；**`POSSESSION_KINDS` 全 `KIND_CONSENT`**；**R5/R6 成对互斥**；R6＝**轨迹延迟采样**（**未带路⇒`step` 返 None**）。
- ★★★ **I1~I10 / B6 / R1 家**：**移速是表不是常量**（暗段1 `+2`、段3 `+5`）；**I10 只记不毁**⇒**NPC 一律放行、无出场门控**；B6 走**同一条** `npc_speak`、**失败必 `loop.abort`**；R1 `home`≠`scene`、`home_of()`＝**登记 home > 回落 scene > None**、★★★ **`npc_roam._call` 两参约定**、★★ **`by_source()` 只数站位**。
- ★★★ **「灵魂视角」＝显示切换的唯一驱动**（§109.5；机制层已落 §113）：**只有灵魂/我的视角移动才切显示**；★★ **NPC 自主移动不切显示但≠不存在**（**持续存在/持续生活**）；可派**任何角色**去别世界办事并产生结果（★「派 Ralsei」只是**举例**）、**中途进场能看到过程**。
## 8. 性能线 ★ 铁律⇒**动手前 Read §78.11**
- ★★★ **首字/并发/`keep_alive` 三铁律**：冷热差 23~190 倍·`NUM_PARALLEL=1`⇒并发＝排队·`keep_alive` 必走原生 `/api/chat`（底座 `ralsei:v4`·`api.timeout≥60`）。
## 9. 用户口径（**优先于我的技术判断**）
- **「prompt 尽量完整」**⇒提速只靠**缓存／后端／模型**（不许砍 prompt）。**「用 7B 就是要他贴合人物且不出 bug」**。**「结巴」**=**减少但不许到 0**⇒**待排期**。**「开机自启」＝选项非硬性**。★★ **当前主轴见 §7**；**这阶段 ok 才进下一阶段**。★★ **工作方式**：「**测完了没问题后按你的计划来**」⇒ **测绿即连续推进**。★ **范围**：暗世界也做⇒**全部 1,251 间**。
## 10. 历轮索引（**全表/要点见详版 §72~§78/§87/§91~§107**）
**锁号速查**（新→旧）：`check114`(**84**)+`mutate114`(**22/21**)·`check108`(**52**)+`mutate108`(**10/10**)·`check107`(**71**)+`mutate107`(16/16)+`verify107`(21)·`check106`(36)·`check105`(44)+`mutate105`(9)·`check104`(28)·`check103`(44)·`check102`(29)·`check99`(36)。
**近轮要点**（85~94 见 §11）：95＝3 真 bug＋**G2 首次零 DIFF**｜96/96b/97＝§96~§97｜99＝§16｜100/101＝§100/§101｜102＝光照归因更正＋7,805 物件普查｜103/104/105＝§16｜106＝非瞬移＋全屏化初版｜**107/108/109~112＝§19**｜**113＝§113**｜**114＝§20**。
## 11. 待裁定/已裁定（★**已裁定的绝不重问**；全文见详版 §71+§*.9）
**★★★ 口径澄清（81/96轮）**：「记忆不要随便修改」＝**角色的记忆**（`data_store`）**非**助手记忆文件⇒**助手记忆＝该记就记**，已裁定**不许再问**。动记忆门槛：**实证超限/被要求＋先补详版＋逐令牌回验＋守恒**；★★ **`check95 A2` 是硬闸**（`js_len ≤ 10000`＝**UTF-16 码元数**）。❗别说成"尊重用户口径"。
**已落地**（§87.10(b)）：room 排序/连接/传送门/选层按原作（首站 `room_town_north`）；**ch3 room 暂不投用**；黄魂；**N1~N4**；**Q3 废除**＋**`NPC_AUTONOMOUS_MOVE` 默认开**＋**Q1 OneShot 263 已迁入**；**6 slug 区**＋**层4**；**R5 Z 键附身**；**A2·A3**｜❗平铺画布待议。
**🟢 已裁定细目（详版 §87.10(c)/§79/§93/§99.11）**：I10 **不接线为出场门控**、未做 **I3/I6/I7/I8/I9**（`check85 F2`）；**出场门控彻底取消**；R1「**迁入场景后再找对应的，npc 按原作分布规律来**」＋「**oneshot 放光门后面**」、`ot_*` 11 人⇒`outertale_pending`；`has_ball` **不删**、`move_to_edge_and_shrink()` **零调用⇒只记不修**、**TRAE 协同**（沙箱跑 `main.py` 被拦杀 **≠ 产品 bug**）；**99 置顶窗口** vs 契约②**有张力⇒待澄清**。
**各轮遗留池**（完整见详版 `§47.11`~`§108.11`）：★★ **跨作品贴图已抽**（`assets/sprites/`）、**背景/门见 §87.12**；**并发闸不做**；BGM/版权/`罐头皮`/`src/` 杂项**禁批量删**；自启+预热；35 角色未登记 `home`（回落 `scene`）。
## 16. 99/103/104/105·下沉索引 ⇒ **全文详版 §99＋§103＋§104＋§105**
（99 cover+K_ROOM_FILL+`spr`漏`vis`｜103 栅格/锚点/切帧379/接线7804｜104 opacity/blend｜105 code-201/420 边。）
## 19. 107/108/110/112·场景全屏化＋全局缩放（宠物/场景/UI 同源）⇒ **详版 §107＋§108＋§110＋§112续四**
- ★★★ 口径（用户逐字 6 条，**全文详版 §107**）：**场景全屏**（非跟随窗口）·**按比例铺满留黑边**·**相机跟随宠物**·**非桌面场景不透壁纸/图标/任务栏**·**全局放大**·**UI 对话框也放大**。★★★ **原作 UI 其实不缩放**（`scr_dbox`/`scr_texttype` 全固定像素）⇒「UI 随场景放大」是**我们的产品口径**，不许假装还原原作。★★ **未做**：隐字母。
- ★★★ **【112续四】已落地**：门**彻底拆出**场景（`_desktop_screen_doors` 只吃屏幕尺寸·贴屏满屏）·room **0.5 档**（`SCENE_FIT_FRACTION`）·非桌面**黑边**／桌面**透明**·宠物最长边 **≤144px**（`PET_MAX_LONG_SIDE_PX`＋`clamp_scale_factor_for_max_side`，**只减不增**）＝Ralsei 144×98。★ **三条回归陷阱**：`fit_fullscreen` 限制轴用 **`<=`**（写 `max`⇒溢出裁画面）·**禁 `fit_fullscreen(sw*fr,…)`**·**`resize(整屏)` 必排 `set_plan` 后**。★ 缩放/UI 详见 **详版 §107/§108**（`camera.scale=out_w/320`·`ui_scale()`＝**平方根**钳 `[0.5,3.0]`·**UI 幂等＝基准快照+每次重算**）。
## 20. 114·差事「世界门控＋派发入口＋独立落盘」⇒ **详版 §114**
- ★★★ **门控** `world_gate(npc,world,scene_id,carried)` **四条按序**：**⓪桌面**（`DESKTOP_ALLOWED_IDS`=ralsei/kris/susie/lancer，**必先于光世界**判，否则 Ralsei 回不了自己家）→①光世界（`light_needs_bubble` 假即放行；真＝**仅 Ralsei**+`escape_via_bubble`，须 `carried`）→②暗世界（先 `roam_scope`：`ALL`**仅 Niko**；再 `chapter_matches`；再 `free_dark_roam`**仅 Ralsei**）。★ **迁入章判不出⇒保守归 `dark`**（≠`world_of_scene` 的 `None`；`A8` 锁"不是复制品"）。
- ★★★ **跨作品章名**（本轮修真缺口）：场景侧 `ut`/`uty` ↔ 角色侧 `undertale`/`undertale_yellow` ⇒ **在比较处归一**（`CHAPTER_ALIASES`/`chapter_matches`），**两边数据都不动**；不归一＝UT/UTY 角色**回不了自己家**。
- ★★★ **入口/落盘**：`handle_errand_command` 挂 `dialogue_ui.send_message`（**回显后、指令前**）；"先问路后派人"⇒**拒分支也必落一次记忆**（`if not ok: _npc_errand_note / elif assign_errand(...) is None:`，两处**互斥**）；台词**全交 `chat_with_ai`**（`_errand_ack` 分流 `speaker=None`）；`npc_errands.json` **写**复用 `npc_plan_store.save`、**读**走 `json`+`from_dict`（`load` 只认 `schema_version==1`⇒**恒空**）；`_npc_errand_tick` 排 `_npc_roam_tick` **之后**。★★★ **录像铁律**：**必 `pet.show()`**（否则帧＝纯壁纸）；沙箱**三件套**＝`RALSEI_DATA_DIR`→tmp＋`vault_root→None`＋**`import main` 在其后**（＋`tray_hint_shown=true` 抑气泡）；分层窗口⇒按 `frameGeometry()` 证几何。

