

### §23.13 速查本压缩镜像（第 34 轮收尾，供压缩后回查）

> 背景：`MEMORY.md` 超注入上限被截断。按 skill `agent-memory-compaction`
> **先把细则补进详版，再压速查本**。以下三段是从速查本 §5 / §7 / §11 **原文搬来的展开版**，
> 速查本只保留"不可违的铁律 + 指针"。**内容与压缩前完全一致，无信息丢失。**

#### §23.13.1 人味改造线全文（速查本 §5 原展开）

回归锁 `persona_chat`(156) / `s8_stream`(69) / `s7_event_speech`(138)，**均进 G2、不联网、不调 Ollama**。

- **人设单一真源 = `assets/ralsei_persona.md`**（每次对话读出来当 `system`）。
  **别只写 Modelfile** —— Ollama 用 messages 的 system **整体替换** Modelfile 的 SYSTEM
  ⇒ 写进模型的人设**一次都不生效**。
  persona **是 prompt 不是文档**（不许 markdown，`**` 会被学走，锁 **A11**）。
  **❗用户与 Ralsei 平级：不许叫"主人"**（persona + 代码两层）。
  **体积上限 K3 < 10000 B**（现 **9946 B**）⇒ **加内容前必须先瘦身**。
- **世界观** = `ralsei_worldview.md` + `modules/worldview_recall.py`（`MAX_BLOCKS=2`、**无命中返回空串**）。
- **关系演进** = `modules/relationship.py`（四档、`TRUST_INITIAL=0.12` 起于 distrust；**信任度不可见**、
  唯一写入口 `note(event)`；**勿把下界抬到 TRUST_INITIAL** → `harsh` 变死事件）。
- **S7 事件台词** `modules/event_speech.py`：档位表是**白名单**、唯一出口 `speak_event(kind,pool,face)`；
  **`pool=None` = 不给内置台词**（AI 失败/判退 → 返回 `""` 沉默）；**禁 import Qt / 项目内模块**。
- **底座 = `ralsei:v4`（7B，第 31 轮起默认）**；旧 `ralsei:v3`（4B）仍在，**回退只需改 `config.json`**。
  **采样参数必须落 Modelfile**（`/v1/chat/completions` **静默忽略 `num_ctx`/`repeat_penalty`**）；
  **换底座必须 `ollama create <新tag> -f ralsei.modelfile`**（复用 blob，**不重下**）。
- ★★ **失真头号来源 = persona 里"可逐字搬走的固定例句"**（真机 24 条：开头复读 **62% → 33%**）。
  **铁律：persona 示例区不许出现"按场合分组 + 冒号 + 固定例句"**（该**格式本身**就在教模型照搬）
  ⇒ 只能改成"情形描述 + 每次自己现造"。锁 **A12d**。
- ★★ **"口癖多"要分两类**：**真口癖**（人物真实性，别砍；真结巴仅 **8.3%**）vs
  **固定模板句**（失真，必须砍；「诶？」起头 75% / 省略号 83%）。取证 §22.1，处置 §20.4。
- ★★ **反"伪造共同经历"**：用户**没去过黑暗世界**，模型会写成"我们那时候一起…"。锁 **A12e**。
  ⚠️ 第 31 轮实测 7B 仍会犯，且**护栏管不了它** → 属 persona 服从性问题，**需继续观察**。
- **护栏 `_clean_ai_reply(reply, recent=)`（顺序 = 优先级）**：0a 句中括号动作 → 0b 剥 markdown → 0c 禁说清单
  （**与事件链路同源，不许另立第二份**）→ 1 自问自答截断 → 2 车轱辘话判退（**只看 recent 重复**）→ 3 超长截断；
  **判退后必须重采样一次**、**判退不 append 进 recent**。❗**0a 必须先于 0b**。**S8 流式**：`iter_lines(chunk_size=1)`。
- ★ **括号旁白三形态**：甲 动作词开头 → `_ACTION_PAREN_RE`；乙 句首括号 → `looks_like_narration` 整句作废；
  丙 描述性旁白 → `_NARRATION_INNER`。★ **判据是「抓形态特征」不是「首词白名单」**（窄白名单**误杀合法心里话**）。
  **分界 = 这段是不是角色的「话语」**：第一人称 → 留；外部描述自己 → 删。**误杀比漏过更糟。**
  锁 A22e（正）+ A22f（反）+ A22g（防放宽误杀）。
  ★ 第 31 轮补漏 `（轻叹）`：**"修饰语+动词"的组合形态是另一类洞**。修饰语表补 `轻`、
  动词表补 `哼|嗤|摸|轻笑`；❗**刻意不加裸 `笑`**（会误杀 `（笑不出来）`）。**真函数名 = `strip_action_parentheticals`**。
- **❗篇幅上限 = `main.AI_REPLY_MAX_CHARS`，现 220**；**换底座/调 num_predict 必须重跑 `measure_token_ratio.py`**。
- ⚠️ 已处置：`_clean_ai_reply` 在 `start_autonomous_speech._on_reply`(`main.py:4620`) 曾**未传 `recent`**（B13b 锁）。

#### §23.13.2 场景系统线全文（速查本 §7 原展开）

用户口径：**「把原作的世界搬到桌面上…桌面也会被我当成一个场景」** + **「一切根据原作」**。

- **P0**（`0aba480`）：`scene_system.py`（数据层纯函数）+ `scene_controller.py`（接线层）+ `assets/scenes/*.json`；
  ★★ **P0 判据 =「不切场景时零行为变化」**：`switch()` **只写状态**、不动画面/定时器/物理。
- **路由层**（`52d5514`，锁 `scene_routing` 106 项）：`modules/scene_routing.py`（**纯标准库、零 Qt**）+
  `assets/scenes/_routes.json`。★★ **路由是数据，不是代码**（规则全在 JSON，代码只做「读 + 匹配」）。
  语义：`when_scene/area/chapter` 相等 + `"*"` 通配；`when_mood/event` 单值或数组；
  **`when_keywords` 是 OR**（与其余键的 AND **刻意不同**）；排序 = `priority` 升序 → 命中数降序 → 声明序。
  **三律**：① 匹配不到返回 `None`（**绝不伪造默认路线**）② 坏规则跳过 ③ 未知键放行。
  ★ **只有 `follow_route` 允许调 `switch`**；**`destinations()` 过滤未登记场景**。
  ★ **`_as_set()` 坑**：`set("abc")` → `{'a','b','c'}` ⇒ 字符串一律当**单个值**。
- ★ **原作机制**（GML 实证 `scr_roomname`）：房间 ID **扁平整数**；**同一 id 不同章是不同房间**
  ⇒ **id 必须与 chapter 联合才唯一**。**房间数 Ch1~Ch5 = 20/20/8/19/20，合计 87 间**
  （`原作场景线路研究_2026-09-22.md`）。
- ★ **为什么现在不登记原作场景**：**素材还没做** → 切过去 = **一个空场景** = 「**世界突然变白**」，**比不切更糟**。
  **落地三步（零改代码）**：① `_index.json` 登记 → ② 放 `<scene_id>.json` → ③ `_routes.json` 加规则。
- ★ **游戏源文件**：`C:\Users\23002\Desktop\项目文件夹\niko的秘密\DELTARUNE_183049\DELTARUNE`
  （含 `data.win` + 代码参考）。⚠️ 已解析的 `ROOM/SPRT/OBJT.json` **不可信**（指针基址错）→ §22.3。

#### §23.13.3 待裁定清单全文（速查本 §11 原展开）

1. **场景美术素材来源**（**P1 开工前唯一阻塞项**）：`<仓根>/deltarune_ralsei/` 1111 张 PNG **全是角色精灵**；
   `assets/sprites/`、`assets/faces/` **空目录**；全仓库搜 `bg_`/`tileset`/`room_`/`map_` **零命中**
   → **A 程序化生成 / B 用户截图 / C 重绘 → 推荐 A+B**。
2. 另：场景粒度 ｜ 是否要 BGM（现 `sound_manager` **只有 3 音效、无 BGM 能力**）｜ 原作版权尺度。
3. **动态结巴率**（见 §9）：是否接进 `relationship.py` 档位。
4. **沿用第 26 轮**：`dialogue_ui._rule_reply()` 罐头皮 ⇒ 「AI 关必沉默」是否也管"用户主动打字"。
5. **待办**：真机手感实测（用户侧）｜`.gitattributes` 换行口径（**先议后动**）｜`src/` 顶层 `.bak`/`test_*`/
   `monitor_*.txt` 存量（**等用户点头，不得批量删**）｜H4「文件反应」专项。
6. **开机自启 + 预热**（用户口径：**「后期等咱项目结束的时候」**）—— 实现留到项目收尾。
7. 是否试 **Vulkan 后端**（已实测：**救不回冷 prefill**）。
8. ★ **第 34 轮遗留（P3 技术债）**：死函数批量清理 / 空闲分支补 3 条件 / 5 个孤儿状态位复位 /
   **楼层 2 处"区间口径不一致"**（`nearest_visible_point` 与 `get_jump_destinations` 的
   `QRect.bottom()/right()` **闭区间** vs `_rect_tuple` **半开区间**）
   —— **均属低危（差 1px 不可能改"站得住"判定），建议同批处理，勿单独动**。详见 §23.9。
   （原列的 `_index_of_floor` 返 -1 **已在第 34 轮升级为真缺陷 F7 并修复**，见 §23.9.1。）
9. ★★ **第 34 轮续 · 新增裁定项**：`pet_interaction.py`（364 行，**全模块零接线**，AST 已实证）
   → **A 删除** / **B 接线**（死模块里那套**更完整**：6 手势 vs 产品 3 种、alpha 遮罩动态分区 vs 硬编码矩形、
   有长按 PULL/PINCH）/ **C 暂缓**。**我的建议 = C**，理由 = 用户本阶段口径"先做好移动行为、保证不出错再加别的"，
   接线属"加功能"。详见 §23.12.2 / §14.4。
