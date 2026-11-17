# NPC 能力盘点（第194轮）

数据来源：`assets/npc/_registry.json`（96 条）、`assets/sprites/dr/_npc_frames.json`、`assets/faces/<id>/`、`assets/npc/persona/*.txt`。**全部从磁盘真实算，无一处手填。**

## 一、素材齐备度（逐人差异只在这里）

| 项 | 有 | 缺 | 覆盖率 |
|---|---|---|---|
| 人设文件 | 77 | 19 | 80% |
| 立绘：有帧 | 18 | 78 | 19% |
| 立绘：原作就没图（`no_art`） | 8 | — | — |
| 立绘：不是人（`not_a_person`） | 8 | — | — |
| 立绘：未做（外来作品，manifest 里没登记） | 62 | — | — |
| 表情套（faces/<id>） | 29 | 67 | 30% |

## 二、按作品分布

| 作品 | 人数 | 有人设 | 有立绘 | 原作无图 | 未做 | 有表情 |
|---|---|---|---|---|---|---|
| 暗世界 | 30 | 11 | 13 | 8 | 1 | 0 |
| Oneshot | 21 | 21 | 0 | 0 | 21 | 21 |
| 黄魂 | 15 | 15 | 0 | 0 | 15 | 8 |
| UT | 14 | 14 | 0 | 0 | 14 | 0 |
| Outertale | 11 | 11 | 0 | 0 | 11 | 0 |
| 光世界 | 5 | 5 | 5 | 0 | 0 | 0 |

## 三、逐人明细

| # | id | 中文名 | tier | 作品 | 人设(KB) | 立绘 | 表情 | 活动范围 |
|---|---|---|---|---|---|---|---|---|
| 1 | `os_alula` | Alula | main | Oneshot | 17.5 | 未做 | 1 | non_dark |
| 2 | `os_calamus` | Calamus | main | Oneshot | 14.8 | 未做 | 1 | non_dark |
| 3 | `os_cedric` | Cedric | main | Oneshot | 18.5 | 未做 | 1 | non_dark |
| 4 | `os_george` | George | main | Oneshot | 13.4 | 未做 | 6 | non_dark |
| 5 | `os_kelvin` | Kelvin | main | Oneshot | 15.5 | 未做 | 1 | non_dark |
| 6 | `os_kip` | Kip | main | Oneshot | 16.2 | 未做 | 1 | non_dark |
| 7 | `os_lamplighter` | 灯夫 | main | Oneshot | 16.3 | 未做 | 1 | non_dark |
| 8 | `os_ling` | Ling | main | Oneshot | 15.4 | 未做 | 1 | non_dark |
| 9 | `os_magpie` | Magpie | main | Oneshot | 15.7 | 未做 | 1 | non_dark |
| 10 | `os_maize` | Maize | main | Oneshot | 16.9 | 未做 | 1 | non_dark |
| 11 | `os_mason` | Mason | main | Oneshot | 18.5 | 未做 | 1 | non_dark |
| 12 | `os_niko` | Niko | main | Oneshot | 16.4 | 未做 | 1 | all |
| 13 | `os_prophetbot` | 先知机器人 | main | Oneshot | 15.7 | 未做 | 1 | non_dark |
| 14 | `os_prototype` | Prototype | main | Oneshot | 16.9 | 未做 | 1 | non_dark |
| 15 | `os_rowbot` | Rowbot | main | Oneshot | 15.9 | 未做 | 1 | non_dark |
| 16 | `os_rue` | Rue | main | Oneshot | 17.8 | 未做 | 1 | non_dark |
| 17 | `os_shepherd` | 牧羊人 | main | Oneshot | 16.5 | 未做 | 1 | non_dark |
| 18 | `os_silver` | Silver | main | Oneshot | 17.6 | 未做 | 1 | non_dark |
| 19 | `os_the_author` | The Author | main | Oneshot | 18.9 | 未做 | 1 | non_dark |
| 20 | `os_the_world_machine` | The Entity / 本体 | main | Oneshot | 19.1 | 未做 | 1 | non_dark |
| 21 | `os_watcher` | Watcher | main | Oneshot | 15.4 | 未做 | 1 | non_dark |
| 22 | `ot_alphys` | Alphys | main | Outertale | 21.9 | 未做 | **缺** | non_dark |
| 23 | `ot_asgore` | Asgore | main | Outertale | 20.2 | 未做 | **缺** | non_dark |
| 24 | `ot_asriel_twinkly` | Asriel Dreemurr 与 Twinkly | main | Outertale | 20.8 | 未做 | **缺** | non_dark |
| 25 | `ot_kidd` | Kidd | main | Outertale | 19.0 | 未做 | **缺** | non_dark |
| 26 | `ot_mettaton` | Mettaton | main | Outertale | 19.7 | 未做 | **缺** | non_dark |
| 27 | `ot_muffet` | Muffet | main | Outertale | 19.0 | 未做 | **缺** | non_dark |
| 28 | `ot_napstablook` | Napstablook | main | Outertale | 20.3 | 未做 | **缺** | non_dark |
| 29 | `ot_papyrus` | Papyrus | main | Outertale | 18.3 | 未做 | **缺** | non_dark |
| 30 | `ot_sans` | Sans | main | Outertale | 18.9 | 未做 | **缺** | non_dark |
| 31 | `ot_toriel` | Toriel | main | Outertale | 19.1 | 未做 | **缺** | non_dark |
| 32 | `ot_undyne` | Undyne | main | Outertale | 21.4 | 未做 | **缺** | non_dark |
| 33 | `ut_alphys` | Alphys | main | UT | 21.3 | 未做 | **缺** | non_dark |
| 34 | `ut_asgore` | Asgore Dreemurr | main | UT | 19.6 | 未做 | **缺** | non_dark |
| 35 | `ut_chara` | Chara | main | UT | 20.1 | 未做 | **缺** | non_dark |
| 36 | `ut_flowey` | Flowey | main | UT | 20.0 | 未做 | **缺** | non_dark |
| 37 | `ut_frisk` | Frisk | main | UT | 15.4 | 未做 | **缺** | non_dark |
| 38 | `ut_gaster` | W.D. Gaster | main | UT | 20.8 | 未做 | **缺** | non_dark |
| 39 | `ut_mettaton` | Mettaton | main | UT | 18.6 | 未做 | **缺** | non_dark |
| 40 | `ut_monster_kid` | Monster Kid | main | UT | 16.5 | 未做 | **缺** | non_dark |
| 41 | `ut_muffet` | Muffet | main | UT | 17.8 | 未做 | **缺** | non_dark |
| 42 | `ut_napstablook` | Napstablook | main | UT | 19.6 | 未做 | **缺** | non_dark |
| 43 | `ut_papyrus` | Papyrus | main | UT | 17.7 | 未做 | **缺** | non_dark |
| 44 | `ut_sans` | Sans | main | UT | 18.1 | 未做 | **缺** | non_dark |
| 45 | `ut_toriel` | Toriel | main | UT | 18.7 | 未做 | **缺** | non_dark |
| 46 | `ut_undyne` | Undyne | main | UT | 20.6 | 未做 | **缺** | non_dark |
| 47 | `asgore` | 艾斯戈尔 | main | 光世界 | 18.0 | 12 帧 | **缺** | home |
| 48 | `kris` | 克里斯 | main | 光世界 | 17.0 | 12 帧 | **缺** | home |
| 49 | `noelle` | 诺艾尔 | main | 光世界 | 13.9 | 16 帧 | **缺** | home |
| 50 | `susie` | 苏西 | main | 光世界 | 18.7 | 16 帧 | **缺** | home |
| 51 | `toriel` | 托丽尔 | main | 光世界 | 19.0 | 16 帧 | **缺** | home |
| 52 | `berdly` | 伯德利 | main | 暗世界 | 16.7 | 16 帧 | **缺** | home |
| 53 | `flowery` | 花 | main | 暗世界 | 16.5 | 原作无图 | **缺** | home |
| 54 | `gerson` | 格森 | main | 暗世界 | 13.5 | 4 帧 | **缺** | home |
| 55 | `king` | 黑桃王 | main | 暗世界 | 11.3 | 2 帧 | **缺** | home |
| 56 | `knight` | 咆哮骑士 | main | 暗世界 | **缺** | 未做 | **缺** | home |
| 57 | `lancer` | 兰瑟 | main | 暗世界 | 18.8 | 4 帧 | **缺** | home |
| 58 | `mike` | 迈克 | main | 暗世界 | 18.1 | 1 帧 | **缺** | home |
| 59 | `queen` | 女王 | main | 暗世界 | 11.9 | 16 帧 | **缺** | home |
| 60 | `ralsei` | 雷尔赛 | main | 暗世界 | 12.2 | 原作无图 | **缺** | home |
| 61 | `rouxls` | 鲁尔斯·卡德 | main | 暗世界 | 15.4 | 1 帧 | **缺** | home |
| 62 | `spamton` | 斯帕姆顿 | main | 暗世界 | 16.8 | 原作无图 | **缺** | home |
| 63 | `tenna` | 天娜 | main | 暗世界 | 15.2 | 2 帧 | **缺** | home |
| 64 | `hy_ace` | Ace | main | 黄魂 | 19.6 | 未做 | 6 | non_dark |
| 65 | `hy_axis` | Axis | main | 黄魂 | 22.1 | 未做 | 9 | non_dark |
| 66 | `hy_bowll` | Bowll | main | 黄魂 | 17.2 | 未做 | **缺** | non_dark |
| 67 | `hy_ceroba_ketsukane` | Ceroba Ketsukane | main | 黄魂 | 22.2 | 未做 | 57 | non_dark |
| 68 | `hy_chujin_ketsukane` | Chujin Ketsukane | main | 黄魂 | 18.1 | 未做 | 13 | non_dark |
| 69 | `hy_clover` | Clover | main | 黄魂 | 20.9 | 未做 | **缺** | non_dark |
| 70 | `hy_dalv` | Dalv | main | 黄魂 | 24.1 | 未做 | **缺** | non_dark |
| 71 | `hy_ed` | Ed | main | 黄魂 | 17.8 | 未做 | 8 | non_dark |
| 72 | `hy_flowey` | Flowey | main | 黄魂 | 21.5 | 未做 | **缺** | non_dark |
| 73 | `hy_guardener` | Guardener | main | 黄魂 | 20.8 | 未做 | **缺** | non_dark |
| 74 | `hy_martlet` | Martlet | main | 黄魂 | 23.9 | 未做 | **缺** | non_dark |
| 75 | `hy_mooch` | Mooch | main | 黄魂 | 20.6 | 未做 | 15 | non_dark |
| 76 | `hy_moray` | Moray | main | 黄魂 | 21.8 | 未做 | 12 | non_dark |
| 77 | `hy_sousborg` | Sousborg | main | 黄魂 | 17.6 | 未做 | **缺** | non_dark |
| 78 | `hy_starlo` | Starlo | main | 黄魂 | 19.3 | 未做 | 44 | non_dark |
| 79 | `addison_tea` | 艾迪森 | plain | 暗世界 | **缺** | 2 帧 | **缺** | home |
| 80 | `castle_cafe` | 咖啡店老板 | plain | 暗世界 | **缺** | 非人物 | **缺** | home |
| 81 | `catti` | 卡蒂 | plain | 暗世界 | **缺** | 原作无图 | **缺** | home |
| 82 | `conbini` | 便利店店员 | plain | 暗世界 | **缺** | 非人物 | **缺** | home |
| 83 | `doubter` | 质疑者 | plain | 暗世界 | **缺** | 原作无图 | **缺** | home |
| 84 | `dumpster` | 垃圾桶 | plain | 暗世界 | **缺** | 非人物 | **缺** | home |
| 85 | `hammerguy` | 锤子哥 | plain | 暗世界 | **缺** | 4 帧 | **缺** | home |
| 86 | `mansion_room` | 宅邸房间 | plain | 暗世界 | **缺** | 非人物 | **缺** | home |
| 87 | `npc_room` | 空房间 | plain | 暗世界 | **缺** | 非人物 | **缺** | home |
| 88 | `police` | 警察 | plain | 暗世界 | **缺** | 原作无图 | **缺** | home |
| 89 | `puzzlemaster1` | 谜题大师·甲 | plain | 暗世界 | **缺** | 原作无图 | **缺** | home |
| 90 | `puzzlemaster2` | 谜题大师·乙 | plain | 暗世界 | **缺** | 原作无图 | **缺** | home |
| 91 | `rabbits` | 兔子们 | plain | 暗世界 | **缺** | 2 帧 | **缺** | home |
| 92 | `rudy` | 鲁迪 | plain | 暗世界 | **缺** | 16 帧 | **缺** | home |
| 93 | `sign` | 告示牌 | plain | 暗世界 | **缺** | 非人物 | **缺** | home |
| 94 | `susiedark` | 暗之苏西 | plain | 暗世界 | **缺** | 4 帧 | **缺** | home |
| 95 | `wrapper` | 包装怪 | plain | 暗世界 | **缺** | 非人物 | **缺** | home |
| 96 | `zapper` | 电击者 | plain | 暗世界 | **缺** | 非人物 | **缺** | home |
