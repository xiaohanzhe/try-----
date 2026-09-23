第38轮收尾：P0 接线（场景系统真的跑起来）+ 3 处代码瑕疵 + 原作房间表修正

## 一、P0 接线（本轮核心）

问题：SceneController.load() / load_routes() 早已写好，但**调用点 = 0**
⇒ 产品进程实测 _scene_loaded=False、current_scene=None，索引躺在磁盘上，
场景系统等于不存在。这是「函数写对了但产品用不上」的第 5 次。

改动（ralsei_pet/src/main.py，init_systems() 末尾，+18 行注释 + 2 行调用）：
    self.scene.load()          # 索引（1,014 场景）+ 默认场景 desktop
    self.scene.load_routes()   # 路由表（26 条 + 兜底）

安全性（P0 判据「不切场景时零行为变化」）：两者只做「读 JSON + 写宿主状态字段」，
不注册定时器 / 不改渲染路径 / 不碰物理 / 不调 Qt；写入的 current_scene /
scene_objects 零消费者；两者永不抛且幂等 ⇒ 失败只记日志、场景系统降级为空态。
顺序有意义：先 load() 再 load_routes()（路由的 destinations() 用索引过滤）。

真机验证 10/10 PASS（offscreen，产品进程内）：
    _evidence/真机_P0接线验证.txt
    含 L9 负控制：未调 load() 的控制器仍为 False ⇒ 证明 True 来自接线而非构造自带。
    L7 切进"区域分片里"的场景成功 ⇒ 证明 switch() 真把 entry 传给了数据层。

## 二、3 处代码瑕疵

1. scene_routing._FALLBACK_PRIORITY = 10000 —— 零引用死常量
   （全仓 1 次 = 定义本身；_routes.json 实为 100~900，无一用 10000）⇒ 删除，
   并在 match() 兜底分支注明「兜底不参与 priority 排序」。
2. switch() 里 self.refresh_objects() if hasattr(self,'refresh_objects') else []
   —— refresh_objects 全仓无定义 ⇒ hasattr 恒假 ⇒ scene_objects 恒 []，
   形如"在刷新"实则空转；且与正式入口 resolve_objects(screen_rect) 双名
   ⇒ 改显式 pet.scene_objects = [] + 注明由 resolve_objects 填。
3. main.py 注释写「这 6 个」字段，实为 9 个（6 场景 + 3 路由）
   ⇒ 改 9 + 逐名列出；控制器 docstring 与 run_all.py 注释/desc 同步。

新增断言（场景系统-P0/verify_scene_p0.py，80 → 90 项）：
    J4 字段名 6→9 / J6 J6b P0 接线真的存在 / J6c 负控制（抹掉后判据必变假）
    J7 J7b 全仓无 refresh_objects / _FALLBACK_PRIORITY 标识符
    J7c J7d 负控制（合成源码必被识别 / 只在注释里的不算数）
    ⚠️ J7b 第一版假红：纯文本口径被**我自己的修复注释**判红 ⇒ 改走 AST。

## 三、_original_rooms.json 修正

依据 _evidence/scr_roomname_覆盖核对.txt + ch5漏登记与ch2多登记.txt：
    ch2 多录 2 条（199/200，两条同名且 scr_roomname 无此分支）→ 删
    ch5 漏录 5 条 → 补：
        205 room_dw_fcastle_right_penultimate → Flower Castle - Right View
        222 room_dw_fcastle_top_entrance      → Top of Castle - Beginning
        224 room_dw_fcastle_green_checkpoint  → Top of Castle - Green's Shop
        225 room_dw_fcastle_final_save        → Top of Castle - Castle Top
        230 room_dw_fcastle_pinkroom          → Top of Castle - Boss?
修正后逐章条数 = 20/20/9/20/26 = scr_roomname 分支数。
ch5 rooms 顺手按 id 升序（原先 144 排在 150 之后）。
ch5.areas.flower_castle 并上 "Top of Castle" 前缀 —— 已核对那 5 个房间在全量房间表里
都是 cls=scene / area_id=flower_castle ⇒ 索引不需要新增区域。
meta.corrections 增补 4 条留痕；文本级替换（不 json.dump 重排），保持纯 LF。

新增回归锁（第36轮/verify_scene_route_original.py，55 → 57 项）：
    A4b 逐章条数 == scr_roomname 分支数（原作脚本的分支个数，不是会漂的计数）
    A4c 每章 id 唯一（防重复录入 —— 199/200 就是这么来的）

## 四、行号漂移：一条假 DIFF 的根治

round34b_move_beat 的 A2 判据消息里印了绝对行号；我们在 main.py 头部插入 19 行后，
该套件与"节拍有没有回退"无关地报 DIFF。判据消息改成报**处数**，不再印绝对行号 ——
假 DIFF 会养成"看都不看就 --update"的坏习惯，那才是回归锁失去鉴别力的路径。

## 五、记忆侧

见前一次提交 af12a3b。本次同步：速查本 G2 计数 1505→1517、§7 加「P0 接线已落」、
§11.9 更新（P0 部分结清，剩路由重建 + #17）；详版追加 §39.12；
新增当日日志 .workbuddy/memory/2026-09-24.md。
复检 recheck_mem38.py：40 PASS / 0 FAIL（4 个曾丢失的令牌现在速查本与详版都有）。

## 六、回归

G2 全量：**32 套件 / PASS=1517 / FAIL=0 / 全 IDENTICAL**
记忆复检 40/40；真机 10/10；工作区无 .pyc 残留。
本轮 8 次判据失真全部在判据侧（详见报告 §11）。

## 七、报告

第三十八轮场景系统全量落地与P0接线报告_2026-09-24.md（项目根）
