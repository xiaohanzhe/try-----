sweetsilence = 0;
clover = 1;
if (global.flag[7] == 1)
{
    clover = 0;
}
if (obj_mainchara.kill == 1)
{
    clover = -1;
}
irememberyourneutrals = 0;
if (global.kills > 10)
{
    irememberyourneutrals = 1;
}
if (global.kills > 20)
{
    irememberyourneutrals = 2;
}
if (global.kills > 30)
{
    irememberyourneutrals = 3;
}
if (global.kills > 40)
{
    irememberyourneutrals = 4;
}
if (global.kills > 50)
{
    irememberyourneutrals = 5;
}
global.typer = 5;
global.facechoice = 0;
global.faceemotion = 0;
global.msc = 0;
ghostchoose = choose(0, 1);
global.msg[0] = "* 不 知 怎 么 的 ， 出 错 了 。/%%";
if (clover == -1)
{
    scr_charface(0, 4);
    global.msg[1] = "* 继 续 前 进 。/%%";
}
if (clover == 1)
{
    if (ghostchoose == 0)
    {
        scr_charface(0, 0);
        global.msg[1] = "* 没 有 时 间 可 以 浪 费 了 。/%%";
    }
    else
    {
        if (scr_murderlv() >= 2 || irememberyourneutrals > 1)
        {
            scr_cloface(0, 6);
        }
        else
        {
            scr_cloface(0, 0);
        }
        global.msg[1] = "* 我 们 快 走 吧 。/%%";
    }
}
if (clover == 0)
{
    if (ossafe_file_exists("system_information_963"))
    {
        scr_charface(0, 0);
    }
    else
    {
        scr_charface(0, "F");
    }
    global.msg[1] = "* 还 是 没 厌 倦 我 ？/%%";
}
if (global.ghost == 1 || scr_murderlv() >= 13 || room == room_mysteryman)
{
    sweetsilence = 1;
}
switch (room)
{
    case room_area1:
        if (global.plot < 9.2 && global.flag[210] == 0)
        {
            scr_charface(0, 6);
            global.msg[1] = "* 我 们 到 了 。/";
            global.msg[2] = "* 恭 喜 你 &  白 跑 了 这 一 趟 路 。/";
            scr_cloface(3, 9);
            global.msg[4] = "* 嗯 ^1.^1.. 你 认 为 其 他 人 类 &  都 坠 落 到 &  这 同 一 个 地 方 了 ？/";
            scr_charface(5, 4);
            global.msg[6] = "* 是 这 样 的 ^1。& 我 们 现 在 可 以 走 了 吗 ？/";
            scr_cloface(7, 6);
            global.msg[8] = "* .../";
            scr_charface(9, 5);
            global.msg[10] = "* .../";
            scr_cloface(11, 3);
            global.msg[12] = "* 是 啊 ^1。&* 我 们 走 吧 。/%%";
            global.flag[210] = 1;
        }
        else if (instance_exists(obj_torinteractable7) && global.flag[7] == 0)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* .../";
            scr_charface(2, 3);
            global.msg[3] = "* 没 必 要 纠 结 于 此 。/%%";
        }
        else if (clover == 0)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 这 真 有 趣 。/";
            global.msg[2] = "* 据 说 那 些 &  爬 上 这 座 山 的 人 &  再 也 没 回 来 过 。/";
            global.msg[3] = "\\E7* ... 早 在 有 人 失 踪 之 前 &  就 有 个 人 了 。/";
            global.msg[4] = "\\E1* 人 类 都 是 偏 执 狂 。/";
            global.msg[5] = "* 他 们 为 那 些 永 远 不 会 发 生 &  的 事 情 做 着 准 备 。/";
            global.msg[6] = "\\E8* 他 们 对 于 假 设 感 到 愤 怒 。/";
            global.msg[7] = "\\EB* 这 也 许 就 是 战 争 发 生 &  的 原 因 。/";
            global.msg[8] = "\\E1* 我 想 这 一 点 是 没 有 变 化 的 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 1);
                global.msg[1] = "* .../";
                global.msg[2] = "\\E0* 你 和 我 认 识 的 大 多 数 人&  都 不 一 样 。/";
                global.msg[3] = "\\EF* 我 很 感 谢 你 是 那 样 的 人 。/%%";
            }
            if (global.flag[39] > 0)
            {
                scr_charface(0, "M");
                global.msg[1] = "* 老 实 说^1 ， 我 不 理 解 &  他 为 什 么 这 么 做 。/";
                global.msg[2] = "* 也 许 这 是 他 的 一 厢 情 愿 ？/";
                global.msg[3] = "\\EF* .../%%";
            }
        }
        else if (clover == -1 || (global.kills >= 14 && global.flag[45] < 4))
        {
            scr_charface(0, 3);
            global.msg[1] = "* .../";
            global.msg[2] = "\\E4* .../%%";
        }
        else if (global.plot >= 9.2)
        {
            scr_charface(0, 7);
            global.msg[1] = "* 你 回 来 干 什 么 ？/";
            scr_cloface(2, 8);
            global.msg[3] = "* 为 了 回 忆 .. ？/";
            scr_charface(4, 7);
            global.msg[5] = "* 他 是 要 回 忆 脸 着 地&  摔 下 来 的 时 候 。/";
            scr_cloface(6, 1);
            global.msg[7] = "* ... 对 吗 ？/";
            scr_charface(8, "D");
            global.msg[9] = "* 我 真 希 望 你 刚 才&  把 你 的 头 摔 得 更 重 些 。/%%";
            if (global.kills == 0)
            {
                global.msg[9] = "* 当 然 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 你 为 什 么 那 么%";
                scr_charface(2, 5);
                global.msg[3] = "* 停 。/";
                global.msg[4] = "\\E6* 别 说 了 。/";
                scr_cloface(5, 3);
                global.msg[6] = "* .../%%";
                if (global.kills == 0)
                {
                    scr_charface(0, "D");
                    global.msg[1] = "* 我 们 现 在 可 以 走 了 吗 ^1？&* 还 是 你 想 在 这 浪 费&  更 多 时 间 ？/%%";
                }
            }
        }
        break;
    case room_area1_2:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* Flowey.../";
            global.msg[2] = "\\E0* 我 怎 么 也 看 不 透 他 。/";
            global.msg[3] = "\\E9* 我 是 说 ^1，他 曾 经 &  在 我 的 旅 途 中 &  帮 过 我 很 多 ！/";
            scr_charface(4, 0);
            global.msg[5] = "* 难 道 他 这 样 做 不 是 出 于 &  一 个 不 可 告 人 的 动 机 吗 ？/";
            scr_cloface(6, 9);
            global.msg[7] = "* .../";
            global.msg[8] = "\\E3* 我 最 好 还 是 别 去 想 那 个 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 你 肯 定 有 自 己 的 想 法 。/";
                scr_cloface(2, 9);
                global.msg[3] = "* .../";
                global.msg[4] = "\\E3* .../%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
            if (ossafe_file_exists("file8"))
            {
                scr_cloface(0, 9);
                global.msg[1] = "* Flowey.../";
                global.msg[2] = "* 想 想 这 就 是 &  他 一 开 始 时 候 的 目 标 .../%%";
            }
        }
        break;
    case room_ruins1:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 太 棒 了 ^1，不 是 吗 ？/";
            scr_charface(2, 3);
            global.msg[3] = "* 遗 迹 的 阴 影 &  隐 约 出 现 在 上 方 .../";
            global.msg[4] = "\\E7* 我 想 这 的 确 是 &  很 独 特 的 景 色 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 2);
                global.msg[1] = "* 我 们 继 续 冒 险 吧 ！/";
                scr_charface(2, "C");
                global.msg[3] = "* 你 .../";
                global.msg[4] = "\\ED* 确 实 是 个 很 独 特 的 人 。/";
                scr_cloface(5, 1);
                global.msg[6] = "* 哦 ， 谢 谢 ！/";
                scr_charface(7, "G");
                global.msg[8] = "* 那 ...并 不 是 在 夸 你 。/%%";
            }
            if (global.kills > 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins2:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 为 数 不 多 的 可 以 接 受 的 &  谜 题 之 一 ^1， &  这 是 她 自 己 解 开 的 。/";
            global.msg[2] = "\\E7* 难 以 置 信 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 她 也 曾 帮 我 &  解 决 过 这 个 谜 题 。/";
                global.msg[2] = "\\E5* ...她 也 曾 这 样 &  帮 助 过 所 有 人 吗 ？/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins3:
        if (global.plot < 9.2 && global.flag[210] == 0)
        {
            scr_charface(0, 5);
            global.msg[1] = "* ...你 就 没 有 什 么 &  更 好 的 事 情 去 做 吗 ？/";
            global.msg[2] = "* 其 他 什 么 事 都 可 以 。/";
            scr_charface(3, 4);
            global.msg[4] = "* 你 ^1！ 这 是 在 ^1！&  浪 费 ^1！时 间 ！/";
            scr_cloface(5, 1);
            global.msg[6] = "* 你 这 么 急 干 什 么 ？/";
            global.msg[7] = "\\E2* 你 又 没 别 的 事 可 做 。/";
            scr_charface(8, 6);
            global.msg[9] = "* 好 耶 。 我 现 在 得 面 对 &  一 个 傻 子 和 一 个 &  自 以 为 很 聪 明 的 人 了 。/%%";
        }
        else if (clover == 0 && !ossafe_file_exists("system_information_963"))
        {
            scr_charface(0, "F");
            global.msg[1] = "* 我 觉 得 这 里 就 是 &  你 和 Clover 的 旅 程 &  分 道 扬 镳 的 地 方 。/";
            global.msg[2] = "\\EI* 我 想 知 道 .../%%";
            if (global.flag[427] > 0)
            {
                global.msg[1] = "* 如 果 你 走 了 和 他 一 样 的 路 线&  你 的 旅 程 会 怎 么 样 ？/%%";
            }
        }
        else if (!ossafe_file_exists("system_information_963"))
        {
            scr_charface(0, 0);
            global.msg[1] = "* 多 么 复 杂 的 谜 题 啊 。/";
            global.msg[2] = "\\E9* 我 为 所 有 在 这 上 面 &  失 败 的 人 感 到 担 忧 。/";
            scr_cloface(3, "H");
            global.msg[4] = "* .../";
            scr_charface(5, "C");
            global.msg[6] = "* 什 么 ？/";
            scr_cloface(7, "D");
            global.msg[8] = "* 那 不 是 我 的 错 ！/";
            global.msg[9] = "* 我 哪 知 道 地 板 会 塌 陷 ！？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 地 板 ...&  塌 了 ？/";
                scr_cloface(2, 5);
                global.msg[3] = "* 是 的 。/";
                global.msg[4] = "\\E7* 嘿 ^1！ 也 没 有 那 么 糟 ！/";
                global.msg[5] = "* 我 的 旅 途 也 很 不 错 ！/";
                scr_charface(6, "D");
                global.msg[7] = "* 考 虑 到 你 已 经 死 了 ^1，&  我 对 此 很 怀 疑 。/";
                scr_cloface(8, "H");
                global.msg[9] = "* 嗯 ^1， 我 以 前 也 死 过 ^2。&\\E1* 你 会 适 应 的 ！/";
                scr_charface(10, "D");
                global.msg[11] = "* ....../%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* (幸 好 你 没 有 &  从 这 里 掉 下 去 ...)/%%";
            }
        }
        break;
    case room_ruins4:
        if (global.plot < 9.2 && global.flag[210] == 0)
        {
            scr_charface(0, 5);
            global.msg[1] = "* 回 来 这 边 &  没 有 任 何 重 要 的 东 西 。/";
            scr_charface(2, 3);
            global.msg[3] = "* 你 纯 在 浪 费 时 间 。/%%";
        }
        else if (clover == 1)
        {
            if (global.flag[14] != 2)
            {
                scr_cloface(0, 6);
                scr_charface(2, 0);
                global.msg[3] = "* 真 是 无 意 义 的 练 习 。/";
                global.msg[4] = "\\E7* 我 能 理 解 他 拒 绝 配 合 。/%%";
            }
            else
            {
                scr_charface(0, 0);
                global.msg[1] = "* 真 是 无 意 义 的 练 习 。/";
                global.msg[2] = "\\E0* 尽 管 我 理 解 这 是 为 了 &  解 释 如 何 处 理 战 斗 .../";
                global.msg[3] = "\\E7* 这 对 激 发 批 判 性 思 维 &  毫 无 帮 助 。/";
                scr_cloface(4, 9);
                global.msg[5] = "* 我 想 你 说 得 对 。/";
                global.msg[6] = "\\E1* 不 过 &  它 的 初 衷 是 好 的 ！/";
                scr_charface(7, 5);
                global.msg[8] = "* \"好 的 初 衷 \" 不 应 该 是 &  设 计 糟 糕 的 借 口 。/%%";
            }
            if (global.flag[14] == 0)
            {
                global.msg[1] = "* 所 以 ^1，你 为 什 么 &  逃 离 了 假 人 ？/";
            }
            if (global.flag[14] == 1)
            {
                global.msg[1] = "* 你 真 的 有 必 要 &  这 样 破 坏 它 吗 ？/";
            }
            if (global.flag[14] == 3)
            {
                global.msg[1] = "* 为 什 么 你 只 是 .^1.^1.&\\E9* 站 在 这 里 不 动 ？/";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins5:
        if (global.plot < 9.2 && global.flag[210] == 0)
        {
            scr_charface(0, 5);
            global.msg[1] = "* 你 傻 吗 ^1？&* 这 是 错 误 的 路 。/%%";
        }
        else if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 那 些 是 .^1.^1.&  真 的 刺 吗 ？/";
            scr_charface(2, 3);
            global.msg[3] = "* 你 要 想 试 试 的 话 &  可 以 自 己 去 感 受 一 下 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 你 也 太 粗 鲁 了 ^1。 它 们 到 底 &  怎 么 样 你 了 ？/";
                scr_charface(2, "B");
                global.msg[3] = "* 每 有 两 秒 &  它 们 就 会 让 我 感 到 很 厌 烦 。/";
                global.msg[4] = "\\E3* 它 们 还 让 我 想 起 了&  我 其 他 的 烦 恼 。/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins6:
        if (global.plot < 9.2 && global.flag[210] == 0)
        {
            scr_charface(0, 5);
            global.msg[1] = "* 真 的 ^1？ 你 真 的 「 那 么 」&  想 和 别 人 说 话 吗 ？/%%";
            if (ossafe_file_exists("file6"))
            {
                scr_charface(0, 7);
                global.msg[1] = "* 我 没 兴 趣 和 你 们&  讨 论 道 德 。/";
                global.msg[2] = "\\E3* 爱 干 什 么 干 什 么 吧 。/%%";
            }
            if (instance_exists(obj_tordogcall))
            {
                if (obj_tordogcall.dogtimer >= (150 * obj_tordogcall.factor))
                {
                    scr_charface(0, "D");
                    global.msg[1] = "* 你 真 的 打 算 要 等 她 吗 ？/";
                    scr_cloface(2, 7);
                    global.msg[3] = "* 我 不 觉 得 那 有 什 么 问 题 。/";
                    scr_charface(4, "B");
                    global.msg[5] = "* .../%%";
                }
            }
        }
        else if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* Toriel 锻 炼 你 的 方 法 ^1.^1.^1.&\\E3  真 新 奇 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 你 骗 了 我 们 &  让 我 们 在 这 里 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 这 意 味 着 他 在 &  这 件 事 上 有 一 个 选 择 。/";
                global.msg[4] = "\\E3* .../";
                global.msg[5] = "\\E4* 如 果 你 在 这 件 事 上 &  有 选 择 的 话 .../";
                global.msg[6] = "* 我 会 想 办 法 &  让 你 也 和 我 们 一 样 &  变 成 鬼 魂 的 。/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        else
        {
            scr_charface(0, "C");
            global.msg[1] = "* 什 么 ^1？ 你 希 望 我 鼓 励 你 ^1？&*\\E8 真 有 趣 。/";
            global.msg[2] = "\\EH* 顺 便 一 提 ^1， Clover 在 这 方 面&  比 我 强 得 多 ^1， &  所 以 你 为 什 么 不 -%";
            global.msg[3] = "\\E0* .../";
            global.msg[4] = "\\E2* 好 吧 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 2);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins7:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 这 些 星 星 .^1.^1.&* 它 们 到 底 是 什 么 ？/";
            scr_charface(2, "B");
            global.msg[3] = "* 我 告 诉 过 你 不 要 再 &  问 问 题 了 。/";
            global.msg[4] = "\\E3* 尽 管 如 此 ^1， 你 还 是 能 &  看 见 它 们 吗 ?/";
            scr_cloface(5, 0);
            global.msg[6] = "* 对 啊 ^1， 它 们 和 Flowey 的 &  一 样 。/";
            global.msg[7] = "\\E7* 他 之 前 经 常 把 它 们 留 给 我 &  以 供 我 [存 档 ]。/";
            scr_charface(8, 3);
            global.msg[9] = "* 嗯 .../";
            global.msg[10] = "* 我 想 我 会 把 它 们 描 述 为 .../";
            global.msg[11] = "* ...一 个 人 意 志 的 表 现 。/";
            scr_cloface(12, 0);
            global.msg[13] = "* 真 有 趣 。 /%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* ... 等 等 , 那 么 我 为 什 么 &  看 不 见 它 们 ？！/";
                scr_charface(2, 9);
                global.msg[3] = "* ...我 们 还 是 继 续 前 进 吧 。/%%";
            }
            if (global.kills >= 14 || ossafe_file_exists("file6"))
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins7A:
        if (clover == 1)
        {
            if (global.flag[34] >= 1 && global.flag[34] < 4)
            {
                scr_charface(0, 9);
                global.msg[1] = "* 你 为 什 么 不 把 所 有 &  糖 果 都 带 走 呢 ？/";
                global.msg[2] = "\\EE* 你 肯 定 还 没 满 足 。/";
                if (global.flag[34] == 1)
                {
                    global.msg[2] = "* 你 肯 定 不 会 满 足 于 &  只 拿 一 个 。/";
                }
                scr_cloface(3, 7);
                global.msg[4] = "* 我 觉 得 这 已 经 够 了 。/%%";
                if (global.flag[34] == 1)
                {
                    global.msg[4] = "* 你 会 习 惯 的 ！/";
                }
                scr_charface(5, "C");
                global.msg[6] = "* .../";
                global.msg[7] = "\\EG* ？？？/%%";
            }
            else if (global.flag[34] >= 4)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 这 可 不 好 了 ! /";
                global.msg[2] = "\\E3* 你 应 该 留 一 些 给 .../";
                global.msg[3] = "* ^1.^1.^1.\\E5别 在 意 ^2。&*\\E8 抱 歉 ^2。&* 真 奇 怪 。/";
                scr_charface(4, 7);
                global.msg[5] = "* .../%%";
            }
            else
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 糖 果 ！/";
                scr_charface(2, 3);
                global.msg[3] = "* 我 还 是 更 喜 欢 巧 克 力 .../";
                global.msg[4] = "\\E8* 但 这 也 是 我 &  第 二 喜 欢 的 。/%%";
            }
            if (global.kills >= 14 || ossafe_file_exists("file6"))
            {
                scr_charface(0, 7);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins8:
        if (clover == 1)
        {
            scr_charface(0, 3);
            global.msg[1] = "* 以 下 是 如 何 一 步 步 &  破 解 这 个 谜 题 的 指 南 ：/";
            global.msg[2] = "* 第 一 步 ^1：&  \\E4摔 断 你 的 腿 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 8);
                global.msg[1] = "* 我 承 认 这 不 是 最 好 的 谜 题 。/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins9:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 这 些 谜 题 是 真 的 麻 烦 。/";
            global.msg[2] = "\\E7* 我 不 喜 欢 它 们 。/";
            scr_cloface(3, 0);
            global.msg[4] = "* 我 倒 觉 得 它 们 &  挺 有 趣 的 ！/";
            global.msg[5] = "* 不 过 呃 ^1， 它 们 可 能 会 &  有 点 难 。/";
            scr_charface(6, 0);
            global.msg[7] = "* “ 有 点 ” 绝 对 是 个 &  保 守 的 说 法 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 你 没 在 ^1.^1..寻 求 &  帮 助 ^1， 是 吧 ？/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins10:
        if (clover == 1)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 嗯 ^1， 我 算 是 明 白 了 。/";
            global.msg[2] = "* 前 面 的 房 间 只 是 &  对 真 正 的 谜 题 的 介 绍 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "B");
                global.msg[1] = "* 我 没 有 说 我 喜 欢 它 们 。/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins11:
        if (clover == 1)
        {
            scr_charface(0, "D");
            global.msg[1] = "* 别 太 得 意 ^1。&* 你 能 通 过 先 前 的 谜 题&  纯 属 是 碰 巧 了 。/";
            global.msg[2] = "* 你 可 别 以 为 &  一 点 脑 子 都 不 用 动 &  就 能 解 决 谜 题 。/";
            scr_cloface(3, 0);
            global.msg[4] = "* 要 是 你 来 的 话 会 怎 么 &  设 计 这 个 谜 题 呢 ？/";
            scr_charface(5, "B");
            global.msg[6] = "* 反 正 比 这 个 好 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 我 相 信 你 的 能 力 .../";
                global.msg[2] = "\\E1* ...能 推 动 &  这 些 石 头 ！/%%";
            }
            if (global.flag[33] == 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 会 说 话 的 石 头 ^1， 嗯 ？/";
                global.msg[2] = "\\E8* 你 确 定 你 没 疯 吗 ？/";
                scr_charface(3, 8);
                global.msg[4] = "* 哈 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 我 记 住 了 ！/";
                    global.msg[2] = "\\E0* 你 等 着 吧 ^1， 我 马 上 &  就 让 你 笑 起 来 ！/";
                    scr_charface(3, 7);
                    global.msg[4] = "* 你 开 了 个 不 错 的 玩 笑 。/";
                    global.msg[5] = "\\E0* 我 只 是 出 于 礼 貌 &  稍 稍 回 应 了 你 。/%%";
                }
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 我 们 ..^2. 晚 点 再 说 。/%%";
            }
        }
        break;
    case room_ruins12A:
        if (clover == 1 && scr_murderlv() < 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 啾 啾 。/";
            scr_charface(2, 1);
            global.msg[3] = "* 你 真 是 .^1.^1.\\E7 &  有 很 独 特 的 幽 默 感 。/%%";
            global.flag[447] = 1;
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 2);
                global.msg[1] = "* 啾 ~ 啾 。/";
                scr_charface(2, "D");
                global.msg[3] = "* 你 是 在 故 意 惹 我 吗 ？/";
                scr_cloface(4, "B");
                global.msg[5] = "* 我 吗 ？ 我 可 从 来 &  不 会 做 这 种 事 情 ！/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 对 不 起 ^1.&* 现 在 没 有 心 情 。/%%";
            }
        }
        else if (!ossafe_file_exists("system_information_963") && !ossafe_file_exists("system_information_964") && global.flag[479] > 0)
        {
            scr_charface(0, 8);
            global.msg[1] = "* ^1.^1.^1./";
            global.msg[2] = "* \\EH啾 啾 。/%%";
            global.flag[447] = 10;
            if (global.flag[447] == 10)
            {
                scr_charface(0, "H");
                global.msg[1] = "* 不 说 了 。/";
                global.msg[2] = "\\EE* 别 再 这 样 做 了 。/%%";
            }
        }
        break;
    case room_ruins12:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 一 只 幽 灵 ？/";
            scr_charface(2, 1);
            global.msg[3] = "* 你 的 猜 测 并 不 正 确 。/";
            scr_cloface(4, 6);
            global.msg[5] = "* 我 可 什 么 都 没 说 ！/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 所 以..^2. 他 看 不 见 我 们 ^1？&* 为 什 么 ？/";
                scr_charface(2, 1);
                global.msg[3] = "* 我 会 告 诉 你 的 ^1，如 果 &  将 来 你 再 提 起 这 件 事 。/%%";
                global.flag[273] = 1;
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, "D");
                global.msg[1] = "* 那 你 为 什 么 不 现 在 说 呢 。/";
                scr_charface(2, "H");
                global.msg[3] = "* 因 为 我 不 想 。/%%";
            }
            if (global.flag[36] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* Napstablook 看 起 来 &  是 个 善 良 的 人 ！/";
                global.msg[2] = "* 我 总 是 尊 重 那 些&  寻 求 宁 静 的 人 。/%%";
            }
            if (global.kills >= 14)
            {
                scr_charface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins12B:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* ...我 以 前 见 过 &  这 些 家 伙 们 吗 ?/";
            scr_charface(2, 1);
            global.msg[3] = "* 地 下 世 界 里 的 蜘 蛛 &  还 是 有 很 多 的 。/";
            global.msg[4] = "\\E0* 就 算 你 见 过 &  这 也 不 是 很 震 惊 的 事 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 嗯 .../%%";
            }
            if (global.flag[89] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 支 持 当 地 商 贩^1&  挺 好 的 不 是 吗 ？/%%";
                global.flag[220] = 1;
            }
            if (global.flag[210] >= 1.5)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 希 望 它 们 没 有 被&  困 在 这 里 。/";
                global.msg[2] = "* 我 们 离 我 之 前 看 到 它 们&  的 地 方 挺 远 的 。/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 你 不 会 ..^1. 伤 害&  它 们 的 ， 对 吧 ？/%%";
            }
        }
        break;
    case room_ruins13:
        if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* 据 我 猜 测 ^1，&  你 曾 走 过 的 那 条 路 &  并 不 是 最 常 走 的 。/";
            scr_cloface(2, 0);
            global.msg[3] = "* 我 在 旅 途 中 ^1.^1..&\\E6  遇 到 了 一 些 麻 烦 。/";
            scr_charface(4, 0);
            global.msg[5] = "* 这 么 说 你 从 没 来 过 这 里 ？/";
            scr_cloface(6, 6);
            global.msg[7] = "* .../";
            global.msg[8] = "* 我 想 说 我 确 实 没 有 ^1。&\\E8* 因 为 的 确 ！/";
            global.msg[9] = "\\E9* 但 是 .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 为 什 么 我 感 觉 这 么 熟 悉 ？/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 也 许 以 后 再 聊 ？/%%";
            }
        }
        break;
    case room_ruins14:
        if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* 我 要 说 ^1：&  这 些 谜 题 实 在 太 无 聊 了 。/";
            scr_cloface(2, 1);
            global.msg[3] = "* 我 不 知 道 .^1.^1.&* 我 开 始 爱 上 它 们 了 。/";
            scr_charface(4, 5);
            global.msg[5] = "* 停 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 你 遇 到 了 些 麻 烦 ^1， &  是 吗 ？/%%";
            }
            if (global.flag[36] == 2)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 幽 灵 可 以 飞 ^1？？&* 我 居 然 一 直 都 不 知 道 ！/%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 搞 笑 的 是 我 就 是 个 幽 灵 。/";
                    global.msg[2] = "* 而 且 我 现 在 就 在 飞 。/";
                    global.msg[3] = "* 这 就 像 是 ， &  “ 他 们 怎 么 不 知 道 ” -%";
                    scr_charface(4, 0);
                    global.msg[5] = "* 你 真 无 聊 ，&  搞 得 我 很 难 受 。/%%";
                }
                if (global.flag[427] == 2)
                {
                    scr_charface(0, "H");
                    global.msg[1] = "* 搞 笑 的 是 我 就 是 个 幽 灵 。/";
                    global.msg[2] = "* 因 此 ^1， 我 没 法 从 物 理 层 面 &  感 觉 到 任 何 东 西 。/";
                    global.msg[3] = "* 所 以%";
                    scr_cloface(4, "P");
                    global.msg[5] = "* 我 忍 不 住 注 意 到 了 &  你 偷 了 别 人 的 东 西 。/";
                    scr_charface(6, 9);
                    global.msg[7] = "* 我 有 吗 ^1？&* 我 也 太 蠢 了 。/%%";
                }
                if (global.flag[427] > 2)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 别 再 提 那 个 了 。/%%";
                }
            }
            if (global.flag[100] == 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 你 觉 得 那 是 &  怎 么 在 这 里 的 ？/";
                scr_charface(2, 0);
                global.msg[3] = "* 那 个 缎 带 ^1？\\E5 那 可 能 &  曾 经 属 于 一 个 人 类 。/";
                scr_cloface(4, 9);
                global.msg[5] = "* 然 后 呢 .../";
                global.msg[6] = "\\E8* 我 是 说 ^1， 你 不 会 说 &  他 死 在 这 里 了 ^1， 对 吧 ？/";
                scr_charface(7, 0);
                global.msg[8] = "* 我 哪 知 道 ？/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* .../";
                    scr_charface(2, 3);
                    global.msg[3] = "* 有 什 么 事 吗 ？/";
                    scr_cloface(4, 9);
                    global.msg[5] = "* 啊 ..^2.&\\E6* 不 ^2。 没 什 么 。/%%";
                }
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 对 不 起 ^1.&* 现 在 没 有 心 情 。/%%";
            }
        }
        break;
    case room_ruins15A:
        if (clover == 1)
        {
            if (obj_readable_room1.read > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 视 角 的 旋 转 .../%%";
            }
            else
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 那 个 标 志 写 的 是 什 么 ？/";
                global.msg[2] = "\\EA* 视 角 的 旋 转 .../%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* .../";
                scr_charface(2, 0);
                global.msg[3] = "* 我 感 觉 我 要 &  目 睹 一 些 蠢 事 的 发 生 了 。/%%";
            }
            if (global.kills >= 14)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 没 什 么 好 讨 论 的 。/%%";
            }
        }
        break;
    case room_ruins15B:
        if (clover == 1)
        {
            scr_charface(0, "C");
            global.msg[1] = "* 你 在 .^1.^1. \\EG做 什 么 ？/";
            scr_cloface(2, 7);
            global.msg[3] = "* 你 是 什 么 意 思 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "G");
                global.msg[1] = "* .../";
                scr_cloface(2, "I");
                global.msg[3] = "* .../%%";
            }
            if (global.kills >= 14)
            {
                scr_charface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins15C:
        if (clover == 1)
        {
            scr_charface(0, 7);
            global.msg[1] = "* 你 一 点 也 不 好 笑 。/";
            scr_cloface(2, "M");
            global.msg[3] = "* 我 ^1- 我 不 知 道 &  你 在 说 什 么 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "H");
                global.msg[1] = "* 你 也 太 幼 稚 了 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* .../%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_ruins15D:
        if (clover == 1)
        {
            scr_charface(0, "H");
            global.msg[1] = "* 这 个 谜 题 的 设 计 很 聪 明 ^1，&  至 少 我 可 以 接 受 。/";
            scr_cloface(2, 2);
            global.msg[3] = "* 我 就 知 道 你 也 &  有 这 本 事 ！/";
            scr_charface(4, "E");
            global.msg[5] = "* 你 到 底 是 什 么 意 思 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 我 不 敢 相 信 &  你 把 我 也 扯 进 来 了 。/";
                global.msg[2] = "\\ED* 我 看 起 来 跟 个 傻 子 一 样 。/";
                scr_cloface(3, 8);
                global.msg[4] = "* 没 人 看 得 见 你 的 ！/";
                global.msg[5] = "\\E1* 而 且 ^1， 这 很 有 趣 ，&  不 是 吗 ？/%%";
            }
            if (global.kills >= 14)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 对 不 起 ^1.&* 现 在 没 有 心 情 。/%%";
            }
        }
        break;
    case room_ruins15E:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 你 就 不 能 一 次 通 过 吗 ？/";
            scr_cloface(2, 8);
            global.msg[3] = "* 没 关 系 ^1！&* 你 一 直 都 可 以 重 来 的 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 7);
                global.msg[1] = "* 你 到 底 还 在 等 什 么 ？/%%";
            }
            if (global.kills >= 14)
            {
                scr_charface(0, 4);
                global.msg[1] = "* 起 来 。/%%";
            }
        }
        break;
    case room_ruins16:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* ...你 真 的 很 会 说 话 。/";
            scr_charface(2, 0);
            global.msg[3] = "* 你 是 指 我 的 用 词 吗 ？/";
            global.msg[4] = "\\E3* 我 想 你 可 以 这 么 说 。/";
            global.msg[5] = "\\E7* 但 那 又 怎 样 ？/";
            scr_cloface(6, 7);
            global.msg[7] = "* 没 什 么 ^1， 我 只 是 ^1.^1.^1.&  有 点 惊 讶 。/";
            global.msg[8] = "\\E1* 如 果 你 不 那 么 喜 怒 无 常 &  你 会 很 有 魅 力 的 ！/";
            scr_charface(9, 3);
            global.msg[10] = "* 你 也 能 变 得 &  少 让 人 讨 厌 一 点 .../";
            global.msg[11] = "\\E4* 如 果 你 不 再 装 那 种 口 音 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* !!!/";
                global.msg[2] = "* 我 ^1-我 没 有 装 ！/";
                scr_charface(3, "H");
                global.msg[4] = "* 随 你 怎 么 说 吧 。/%%";
            }
        }
        break;
    case room_ruins17:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 你 想 聊 些 什 么 ^2？&* 这 个 房 间 里 可 没 什 么 &  东 西 值 得 去 聊 。/%%";
            if (instance_exists(obj_smallfrog))
            {
                scr_charface(0, 0);
                global.msg[1] = "* 有 什 么 好 聊 的 ？&* 这 个 房 间 里 没 有 任 何 &  值 得 关 注 的 东 西 。/";
                global.msg[2] = "* 除 非 你 觉 得 &  一 只 Froggit 也 值 得 关 注 。/";
                scr_cloface(3, 5);
                global.msg[4] = "* 你 属 实 有 点 刻 薄 了 。/";
                scr_charface(5, "H");
                global.msg[6] = "* 啊^1 ， 我 道 歉^1 ，&  我 敢 肯 定 那 只 Froggit &  一 定 因 此 受 了 很 大 的 打 击 。/";
                global.msg[7] = "\\ED* 你 还 记 得 没 人 &  听 的 见 我 们 说 话 吧 ^1，&  你 忘 了 吗 ？/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_ruins18OLD:
        if (clover == 1)
        {
            scr_cloface(0, "B");
            global.msg[1] = "* 哇 .../";
            global.msg[2] = "* 我 一 直 不 知 道 &  遗 迹 有 这 么 大 ！/";
            scr_charface(3, 1);
            global.msg[4] = "* 毕 竟 这 个 地 方 曾 经 是 首 都 。/";
            global.msg[5] = "\\ED* 还 有 ^1， 别 吵 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 我 们 要 欣 赏 风 景 吗 ？/%%";
            }
        }
        break;
    case room_ruins19:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 这 地 方 属 实 有 点 .../";
            global.msg[2] = "\\E6* 奇 特 ^1？&* 但 同 时 也 有 些 许 悲 伤 。/";
            scr_charface(3, "L");
            global.msg[4] = "* ...这 确 实 让 人 很 伤 感 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* ...怎 么 了 ？/%%";
            }
        }
        break;
    case room_torhouse1:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 多 么 舒 适 的 地 方 啊 ！/";
            scr_charface(2, 1);
            global.msg[3] = "* .../";
            scr_cloface(4, 0);
            global.msg[5] = "* ...你 还 好 吗 ？/";
            scr_charface(6, 1);
            global.msg[7] = "* 没 事 ^1。&* 我 只 是 在 思 考 .^1.^1./";
            scr_cloface(8, 6);
            global.msg[9] = "* 哦 。/";
            global.msg[10] = "\\E8* .^1.^1.你 刚 才 在 &  思 考 什 么 ？/";
            scr_charface(11, 8);
            global.msg[12] = "* 从 这 楼 梯 上 摔 下 去 &  能 生 还 的 几 率 有 多 大 。/";
            scr_cloface(13, 6);
            global.msg[14] = "* 噢 。 /%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 等 等 ， 我 们 刚 才 说 到 &  哪 里 了 来 着 ？！？/%%";
            }
        }
        else if (scr_murderlv() > 0)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* .../";
            scr_charface(2, 6);
            global.msg[3] = "* .../";
            scr_cloface(4, 8);
            global.msg[5] = "* ...你 还 好 吗 ？/%%";
            if (global.flag[427] > 0 || scr_murderlv() > 1)
            {
                scr_charface(0, 6);
                global.msg[1] = "* 走 。/%%";
            }
        }
        if (global.flag[45] == 4)
        {
            scr_cloface(0, 3);
            global.msg[1] = "* .../%%";
        }
        break;
    case room_torhouse2:
        if (clover == 1)
        {
            scr_cloface(0, 5);
            global.msg[1] = "* ^1.^1.^1.为 什 么 ？/";
            global.msg[2] = "* 为 什 么 这 一 切 都 .../";
            global.msg[3] = "\\E9* ...让 我 感 觉 这 么 熟 悉 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* ^1.^1.^1./";
                scr_charface(2, "G");
                global.msg[3] = "* 你 在 .^1.^1.哭 吗 ？/";
                scr_cloface(4, 4);
                global.msg[5] = "* ^1.^1.^1./%%";
            }
            if (global.flag[45] == 4)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        else if (scr_murderlv() > 0)
        {
            scr_cloface(0, 3);
            global.msg[1] = "* 嘿 。 /";
            global.msg[2] = "* 我 们 不 能 待 在 这 里 吗 ？/";
            scr_charface(3, 3);
            global.msg[4] = "* .../";
            scr_cloface(5, 4);
            global.msg[6] = "* 求 你 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 6);
                global.msg[1] = "* .../%%";
            }
            if (global.flag[45] == 4)
            {
                scr_cloface(0, "F");
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_torhouse3:
        if (clover == 1)
        {
            scr_cloface(0, "A");
            global.msg[1] = "* Toriel 有 孩 子 吗 ？/";
            scr_charface(2, 0);
            global.msg[3] = "* 因 为 这 个 &  额 外 的 房 间 ？/";
            scr_cloface(4, 6);
            global.msg[5] = "* 是 的 ^1， 还 有 .../";
            global.msg[6] = "\\E7* 她 很 有 母 性 。/%%";
            if (global.flag[45] == 4)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        else if (scr_murderlv() > 0)
        {
            scr_charface(0, 3);
            global.msg[1] = "* 快 走 吧 。/%%";
        }
        break;
    case room_torielroom:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* Toriel 真 好 。/";
            scr_charface(2, 0);
            global.msg[3] = "* 她 还 想 让 你 &  永 远 都 留 在 这 里 。/";
            scr_cloface(4, 7);
            global.msg[5] = "* 那 ^1.^1..真 的 是 &  一 件 坏 事 吗 ？/%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 你 觉 得 被 困 在 这 里 &  就 是 好 事 了 ？/";
                scr_cloface(2, 9);
                global.msg[3] = "* ... 也 许 吧 ？/";
                scr_charface(4, 0);
                global.msg[5] = "* 这 个 问 题 只 有 肯 定 &  与 否 定 的 回 答 。/";
                scr_cloface(6, 9);
                global.msg[7] = "* 这 只 是 .../";
                global.msg[8] = "* ..^2.算 了 。/";
                scr_charface(8, 1);
                global.msg[9] = "* .../%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 们 快 走 吧 。/%%";
            }
            if (global.flag[427] == 5)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 正 在 等 待 某 件 事 情&  的 发 生 吗 ？/%%";
            }
            if (global.plot == 25)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 我 们 还 有 &  更 重 要 的 事 情 去 做 。/%%";
            }
            if (global.flag[45] == 4)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        else if (scr_murderlv() > 0)
        {
            scr_cloface(0, "E");
            global.msg[1] = "* 我 之 前 是 认 真 的 。/";
            global.msg[2] = "\\EF* 我 不 会 原 谅 你 。/";
            scr_charface(3, 3);
            global.msg[4] = "* 你 在 试 图 说 服 他 吗 ？/";
            scr_cloface(5, "J");
            global.msg[6] = "* 为 什 么 你 一 点 都 不 在 乎 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 4);
                global.msg[1] = "* 是 你 在 乎 得 太 多 。/%%";
            }
            if (global.plot == 25)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 我 们 还 有 &  更 重 要 的 事 情 去 做 。/%%";
            }
            if (global.flag[45] == 4)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_asrielroom:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 她 这 么 做 只 是 为 了 我 们 ？/";
            scr_charface(2, 1);
            global.msg[3] = "* 你 的 意 思 是 ^1， 为 了 他 ？/";
            scr_cloface(4, 6);
            global.msg[5] = "* 哦 ^2。 \\E8是 的 ^1， 我 就 是 &  这 个 意 思 。/%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 她 也 会 为 你 这 么 做 的 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* ..^2.是 啊 。/";
                scr_charface(4, 1);
                global.msg[5] = "* 我 想 ^1， 有 些 东 西 &  永 远 都 不 会 改 变 。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_charface(0, 0);
                global.msg[1] = "* .../%%";
            }
            if (global.flag[427] == 5)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 你 还 在 等 什 么 ？/";
            }
            if (global.plot == 25)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 我 们 还 有 &  更 重 要 的 事 情 去 做 。/%%";
            }
            if (global.flag[45] == 4)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        else if (scr_murderlv() > 0)
        {
            scr_cloface(0, 3);
            global.msg[1] = "* .../";
            global.msg[2] = "* 你 要 知 道 ，&  我 从 来 没 有 这 样 过 。/";
            scr_charface(3, 3);
            global.msg[4] = "* .../";
            scr_cloface(5, 6);
            global.msg[6] = "* 拜 托 ^1。&* 做 正 确 的 事 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 6);
                global.msg[1] = "* .../%%";
            }
            if (global.plot == 25)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 我 们 还 有 &  更 重 要 的 事 情 去 做 。/%%";
            }
        }
        break;
    case room_kitchen:
        global.msc = 3028;
        break;
    case room_basement1:
    case room_basement2:
    case room_basement3:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* ...你 又 在 想 什 么 ？/";
            global.msg[2] = "\\E9* 我 能 理 解 你 。/%%";
            if (instance_exists(obj_torieltrigger8))
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 一 个 类 似 于 地 下 室 的 地 方 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 你 可 以 从 这 条 路 &  离 开 这 里 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 这 里 唯 一 的 出 口 &  就 在 前 面 。/%%";
                if (instance_exists(obj_torieltrigger8))
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* .../%%";
                }
            }
            if (global.flag[45] == 4)
            {
                scr_charface(0, 5);
                global.msg[1] = "* .../%%";
            }
            if (global.flag[45] == 5)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* .../%%";
            }
        }
        if (scr_murderlv() == 1)
        {
            if (room == room_basement1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 你 仍 然 可 以 回 心 转 意 ^1-%";
                scr_charface(2, 4);
                global.msg[3] = "* 闭 嘴 吧 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "F");
                    global.msg[1] = "* 你 真 的 开 始 让 我 &  很 反 感 了 。/%%";
                }
            }
            else
            {
                scr_cloface(0, "F");
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_basement4:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 看 来 事 情 已 经 解 决 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "L");
                global.msg[1] = "* .../%%";
            }
            if (global.flag[45] == 4)
            {
                scr_charface(0, 6);
                global.msg[1] = "* .../%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 7);
                    global.msg[1] = "* 快 走 吧 。/%%";
                }
            }
            if (global.flag[45] == 5)
            {
                scr_charface(0, 7);
                global.msg[1] = "* .../%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 我 们 .^1.^1.走 吧 。/%%";
                }
            }
        }
        if (scr_murderlv() == 2)
        {
            scr_cloface(0, "B");
            global.msg[1] = "* .../%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 4);
                global.msg[1] = "* 前 进 。/%%";
            }
        }
        break;
    case room_basement5:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* .../%%";
            if (global.flag[45] == 5)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 我 .^1.^1.很 高 兴 &  你 能 和 平 地 处 理 事 情 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 1);
                    global.msg[2] = "* .../";
                    global.msg[1] = "\\EB* 别 那 样 看 着 我 。/%%";
                }
            }
        }
        if (scr_murderlv() == 2 || global.flag[45] == 4)
        {
            scr_cloface(0, "E");
            global.msg[1] = "* 别 跟 我 说 话 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 现 在 不 是 闲 聊 的 时 候 。/%%";
            }
        }
        break;
    case room_ruinsexit:
        if (clover == 1)
        {
            scr_charface(0, "L");
            global.msg[1] = "* 真 是 个 ...有 趣 的 家 伙 。/";
            scr_cloface(2, 5);
            global.msg[3] = "* 是 啊 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* ...他 刚 才 真 的 &  吓 到 我 了 。/%%";
            }
            if (instance_exists(obj_floweytrigger2))
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 是 Flowey.../%%";
            }
            if (ossafe_file_exists("file8"))
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_tundra1:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 门 被 关 上 了 。/";
            scr_cloface(2, 5);
            global.msg[3] = "* 和 以 前 一 样 。/";
            scr_charface(4, 3);
            global.msg[5] = "* 嗯 ？/";
            scr_cloface(6, "H");
            global.msg[7] = "* 没 什 么 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 7);
                global.msg[1] = "* 在 这 里 等 着 &  毫 无 意 义 。/";
                scr_cloface(2, 7);
                global.msg[3] = "* 他 说 的 对 ^2。&* 我 们 走 吧 ！/%%";
            }
            if (global.flag[19] == 4)
            {
                scr_charface(0, 7);
                global.msg[1] = "* .../%%";
            }
            if (global.plot >= 36)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 你 为 什 么 又 回 来 了 ？/";
                global.msg[2] = "* 这 毫 无 意 义 ^1。&* 你 以 为 这 扇 门 会 打 开 吗 ？/";
                scr_cloface(3, 5);
                global.msg[4] = scr_gettext("obj_chara_13");
                global.msg[5] = "\\E8* 也 许 他 想 回 去 ^1， &  但 他 知 道 这 不 可 能 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 或 者 者 者 者 他&  只 是 在 观 光 ^2。&  我 完 全 无 法 读 懂 他 的 表 情 。/";
                    scr_charface(2, 3);
                    global.msg[3] = "* 无 论 如 何 ^1， 这 都&  不 重 要 ^2。 让 我 们&  离 开 这 吧 。/%%";
                }
            }
        }
        break;
    case room_tundra2:
        if (clover == 1)
        {
            if (obj_mainchara.x > 2200)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 那 个 哨 所 .^1.^1.&  看 起 来 好 熟 悉 。/";
                global.msg[2] = "\\E6* 它 没 有 那 么 花 哨 ^1， &  但 是 .../";
                scr_charface(3, 1);
                global.msg[4] = "* 你 是 什 么 意 思 ？/";
                scr_cloface(5, 7);
                global.msg[6] = "* 没 什 么 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "A");
                    global.msg[1] = "* 所 以 这 就 是 &  形 状 便 利 的 灯 .../";
                    scr_charface(2, "I");
                    global.msg[3] = "* 又 或 者 该 说 你 的 体 型 &  和 那 盏 灯 很 相 似 ？/";
                    scr_cloface(4, "B");
                    global.msg[5] = "* !?/";
                    scr_charface(6, 0);
                    global.msg[7] = "* 怎 么 了 ^1？ 这 也 让 我 &  很 困 惑 。/%%";
                }
            }
            else if (obj_mainchara.x < 2200)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 森 林 属 实 有 点 可 怕 .../%%";
                if (global.kills == 0)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* 虽 然 树 林 让 你 感 到 不 安 .../";
                    global.msg[2] = "\\E8* 前 方 的 路 使 你 充 满 了 &  决 心 。/";
                    scr_cloface(3, 8);
                    global.msg[4] = "* ...如 果 你 觉 得 无 聊 ^1， 你 &  可 以 和 我 聊 天 ^1， 明 白 吗 ？/";
                    scr_charface(5, "H");
                    global.msg[6] = "* 才 不 是 呢 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* 我 想 ^1， &  我 们 都 有 自 己 的 爱 好 。/";
                        scr_charface(2, "G");
                        global.msg[3] = "* 你 的 肯 定 没 我 的 好 。/";
                        scr_cloface(4, "D");
                        global.msg[5] = "* 哦 ^1， 是 这 样 吗 ？/%%";
                    }
                }
                if (global.flag[19] == 4)
                {
                    scr_charface(0, 7);
                    global.msg[1] = "* .../%%";
                    global.flag[427] -= 1;
                }
            }
        }
        break;
    case room_tundra3:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 简 单 的 箱 子 。/";
            global.msg[2] = "\\E7* 当 你 有 太 多 东 西 要 带 的 &  的 时 候 ^1，这 是 个 有 用 &  的 工 具 。 /";
            global.msg[3] = "\\E1* 不 过 ^1，&  我 更 喜 欢 维 度 背 包 。/";
            scr_charface(4, "G");
            global.msg[5] = "* ???/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 1);
                global.msg[1] = "* 你 是 .../";
                global.msg[2] = "\\EC* 不 打 算 详 细 解 释 了 ？/";
                scr_cloface(3, "I");
                global.msg[4] = "* 不 说 了 。/";
                scr_charface(5, "D");
                global.msg[6] = "* .../%%";
            }
        }
        break;
    case room_tundra3A:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 一 个 钓 鱼 竿 ！/";
            scr_charface(2, "G");
            global.msg[3] = "* 真 有 趣 啊 ^2。&\\E3* 我 说 你 也 太 容 易 &  被 取 悦 了 吧 。/";
            scr_cloface(4, 1);
            global.msg[5] = "* 也 不 至 于 吧 。/";
            scr_charface(6, 4);
            global.msg[7] = "* .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 坐 在 这 里 看 水 流 流 过 &  真 是 惬 意 ^1，&  不 是 吗 ？/";
                scr_charface(2, "H");
                global.msg[3] = "* 至 少 比 听 你 废 话 强 。/";
                scr_cloface(4, "H");
                global.msg[5] = "* 你 也 太 固 执 了 。/%%";
            }
        }
        break;
    case room_tundra4:
        if (clover == 1)
        {
            scr_charface(0, "C");
            global.msg[1] = "* 多 好 的 介 绍 啊 。/";
            global.msg[2] = "\\E0* 我 感 觉 我 们 可 能 会&  被 卷 进 .../";
            global.msg[3] = "\\EC* 恶 作 剧 。/";
            scr_cloface(4, 5);
            global.msg[5] = "* 恶 作 剧 .../";
            global.msg[6] = "\\E1* 我 喜 欢 恶 作 剧 ！/";
            scr_charface(7, "D");
            global.msg[8] = "* 没 人 会 感 到 惊 讶 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 嘿 ，看 看 那 边 的 哨 所 。/%%";
            }
            if (global.plot < 39)
            {
                scr_charface(0, 0);
                global.msg[1] = "* .../%%";
            }
            if (obj_papcheckpoint.read > 0)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 那 个 东 西 .^1.^1. 我 在 犹 豫 &  该 不 该 叫 它 建 筑 ^2。&* 这 也 太 -%";
                scr_cloface(2, 1);
                global.msg[3] = "* 做 得 真 好 ^1！ 创 作 它 &  的 人 应 该 感 到 骄 傲 ！/";
                scr_charface(4, "D");
                global.msg[5] = "* .../";
                global.msg[6] = "* 你 知 道 没 人 听 得 见 我 们 ^1，&  对 吧 ？/";
                scr_cloface(7, 9);
                global.msg[8] = "* 这 是 最 基 本 的 礼 貌 ！/%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 他 确 实 是 个 手 工 大 师 -%";
                    scr_charface(2, "D");
                    global.msg[3] = "* 这 很 劣 质 。/";
                    scr_cloface(4, "D");
                    global.msg[5] = scr_gettext("obj_chara_15");
                    scr_charface(6, "B");
                    global.msg[7] = "* 好 吧 ^2。 这 并 不 劣 质 。/";
                    scr_cloface(8, 8);
                    global.msg[9] = "* 谢 谢 你 。 /";
                    scr_charface(10, "H");
                    global.msg[11] = "* 这 很 没 用 ^1， 可 怜 ^1，&  二 流 ， 垃 圾 ^1，&  草 率 ^1， 邋 遢 ^1，%";
                    global.msg[12] = "\\E9* 杂 碎 ^1， 粗 糙 ^1， 破 烂 ^1，&  凌 乱 ^1， 肮 脏 .../";
                    global.msg[13] = "\\EE* 而 且 劣 质 。/";
                    scr_cloface(14, "E");
                    global.msg[15] = "* .../%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* 要 不 我 再 列 举 &  几 个 合 适 的 描 述 ？/";
                    scr_cloface(2, 6);
                    global.msg[3] = "* 你 就 不 能 说 点 好 话 吗 ？/";
                    scr_charface(4, "H");
                    global.msg[5] = "* 这 给 了 我 一 个 &  练 习 用 词 的 机 会 。/";
                    global.msg[6] = "\\E8* 尤 其 是 负 面 的 词 汇 。/%%";
                }
            }
            if (global.plot >= 43 && scr_murderlv() < 2)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 这 个 房 间 ！/";
                global.msg[2] = "* ...让 我 很 晕 ！/";
                scr_charface(3, 8);
                global.msg[4] = "* 愚 蠢 的 游 戏 ^1，&  愚 蠢 的 奖 品 。 /%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 你 说 谁 蠢 ？/";
                    scr_charface(2, "A");
                    global.msg[3] = "* 我 的 智 商 显 然 比 你 的 高 。/";
                    scr_cloface(4, 7);
                    global.msg[5] = "* 哦 ^1， 当 然 了 。/";
                    global.msg[6] = "* 如 果 智 商 意 味 着 &  “ 更 善 于 说 话 ” 的 话 。/";
                    global.msg[7] = "* 我 倒 想 看 你 使 用 一 把&  六 发 左 轮 手 枪 。/%%";
                }
            }
        }
        break;
    case room_tundra5:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 保 持 警 惕 。/";
            global.msg[2] = "* 我 有 种 感 觉 &  附 近 还 有 别 人 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../%%";
            }
            if (global.plot >= 42)
            {
                if (global.flag[52] != 1)
                {
                    scr_cloface(0, "A");
                    global.msg[1] = "* 那 只 狗 是 怎 么 &  把 狗 粮 当 烟 抽 的 ？/";
                    scr_charface(2, 8);
                    global.msg[3] = "* 很 简 单 。&* 用 火 点 燃 ^1。/";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 但 是 ..^1. ^1！\\EC 好 吧 ， 算 了 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, "C");
                        global.msg[1] = "* 还 是 很 奇 怪 。/";
                        scr_charface(2, 0);
                        global.msg[3] = "* 我 可 没 有 那 样 断 言 过 。/%%";
                    }
                }
                else
                {
                    scr_charface(0, 3);
                    global.msg[1] = "* 这 真 的 有 必 要 吗 ^1.^1.^1./";
                    global.msg[2] = "\\E1* 别 在 意 我 。/";
                    scr_cloface(3, 3);
                    global.msg[4] = "* .../%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 3);
                        global.msg[1] = "* 我 建 议 我 们 继 续 前 进 。/";
                        global.msg[2] = "\\E1* .../";
                        scr_cloface(3, 5);
                        global.msg[4] = "* 他 只 是 站 在 那 里 没 动 。/";
                        global.msg[5] = "\\E3* 所 以 为 什 么 要 杀 他 .../%%";
                    }
                }
            }
        }
        break;
    case room_tundra6:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 我 会 小 心 那 些 冰 的 ^1！&  看 起 来 真 光 滑 。/";
            scr_charface(2, "C");
            global.msg[3] = "* ...你 应 该 说 湿 滑 。/";
            scr_cloface(4, 2);
            global.msg[5] = "* 才 不 呢 ！/%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, "D");
                global.msg[1] = "* 湿 滑 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* 光 滑 。/";
                scr_charface(4, "H");
                global.msg[5] = "* 湿 滑 。/";
                scr_cloface(6, "L");
                global.msg[7] = "* 光 滑 。/";
                scr_charface(8, "D");
                global.msg[9] = "* 湿 滑 ^1-&\\EB* 你 烦 死 了 。/";
                scr_cloface(10, "K");
                global.msg[11] = "* 嘻 嘻 ！/%%";
                global.flag[477] = 0.1;
            }
            else if (global.flag[427] > 1)
            {
                scr_charface(0, "D");
                global.msg[1] = "* 够 了 ^1。&* 别 再 说 那 个 了 。/";
                global.msg[2] = "\\EB* “ 光 滑 ”^1 ？ 你 认 真 的 ？/";
                scr_cloface(3, 1);
                global.msg[4] = "* 你 会 认 同 我 的 -%";
                scr_charface(5, "G");
                global.msg[6] = "* 闭 嘴 。/";
                global.msg[7] = "\\ED* 这 都 是 你 的 错 ^1， &  Clover。/%%";
                global.flag[477] = 1;
            }
        }
        break;
    case room_tundra6A:
        if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* 他 看 起 来 很 高 兴 。/";
            scr_cloface(2, 1);
            global.msg[3] = "* 这 不 是 很 好 吗 ！/";
            scr_charface(4, 3);
            global.msg[5] = "* 他 将 永 远 被 &  困 在 这 个 地 方 .../";
            global.msg[6] = "\\E7* 永 远 无 法 领 略 到 &  这 个 世 界 的 风 光 。/";
            global.msg[7] = "\\E3* 他 只 会 知 道 &  这 一 个 地 方 。/";
            scr_cloface(8, 6);
            global.msg[9] = "* ...就 你 这 性 格 ， &  你 在 派 对 上 &  肯 定 会 很 讨 喜 的 。/%%";
            if (global.flag[253] > 0)
            {
                scr_cloface(0, "E");
                global.msg[1] = "* .../%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 无 论 你 在 哪 里 &  都 应 该 保 持 快 乐 。/";
                global.msg[2] = "* 要 我 说 ^1，这 是 一 种 &  令 人 羡 慕 的 生 活 方 式 。/";
                scr_charface(3, 1);
                global.msg[4] = "* ^1.^1.^1.\\E8也 许 你 是 对 的 。/%%";
                if (global.flag[253] > 0)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_tundra7:
        if (clover == 1)
        {
            if (irememberyourneutrals > 0 || global.flag[249] < 20)
            {
                scr_charface(0, "D");
            }
            else
            {
                scr_charface(0, 8);
            }
            global.msg[1] = "* 又 是 他 俩 .../%%";
            if (instance_exists(obj_papyrus2))
            {
                if (obj_papyrus2.conversation == 21)
                {
                    scr_charface(0, "G");
                    global.msg[1] = "* ^1.^1../%%";
                }
            }
            if (global.plot >= 43)
            {
                scr_charface(0, 1);
                global.msg[1] = "* 这 个 谜 题 不 可 解 决 。/";
                scr_cloface(2, 0);
                global.msg[3] = "\\E1* 什 么 ？ /";
                scr_charface(4, 0);
                global.msg[5] = "* 这 个 迷 宫 ^2。\\E7 建 造 它&  的 时 候 设 计 就 有 问 题 。/";
                global.msg[6] = "\\E1* “ 解 决 它 ” 的 唯 一 办 法&  \\E5 而 且 我 只 是 随 口 说 说 ，/";
                global.msg[7] = "\\E3* 就 是 跑 的 时 候 &  一 头 扎 进 电 里 ， /";
                global.msg[8] = "* 在 历 练 和 犯 错 中 &  把 它 弄 明 白 。/";
                scr_cloface(9, 8);
                global.msg[10] = "* 你 的 标 准 真 高 。/";
                scr_charface(11, 7);
                global.msg[12] = "* 不 ^1， 这 只 是 普 通 的 标 准 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 我 现 在 想 明 白 了 ^1，&  你 说 的 有 道 理 。/";
                    scr_charface(2, "D");
                    global.msg[3] = "* 哦 ^1， 是 吗 ？/%%";
                }
            }
        }
        break;
    case room_tundra8:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 看 起 来 真 有 趣 ^1！&\\E0* 要 是 我 自 己 能 玩 就 更 好 了 。/";
            scr_charface(2, 0);
            global.msg[3] = "* 这 乍 一 看 很 简 单 &  但 是 .../";
            global.msg[4] = "\\E7* 那 个 球 比 它 看 起 来 &  难 控 制 多 了 。/";
            scr_cloface(5, 0);
            global.msg[6] = "* 哦 ^1？&\\E7* 你 是 有 &  什 么 经 验 吗 ？/";
            global.msg[7] = "\\E1* 我 都 不 知 道 &  你 也 会 找 乐 子 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "G");
                global.msg[1] = "* 我 确 实 知 道 怎 么 找 乐 子 。/";
                scr_cloface(2, "G");
                global.msg[3] = "* .../";
                scr_charface(4, 3);
                global.msg[5] = "* .../";
                global.msg[6] = "\\E4* 别 那 样 看 着 我 。/";
                scr_cloface(7, "D");
                global.msg[8] = "* 我 可 什 么 都 没 说 ！/%%";
            }
            if (instance_exists(obj_iceflag))
            {
                if (obj_iceflag.image_index == 0)
                {
                    if (global.flag[387] == 1)
                    {
                        scr_charface(0, 8);
                        global.msg[1] = "* 啊 ^1， 所 以 那 就 是 &  这 个 游 戏 的 目 的 。/";
                        global.msg[2] = "\\EI* 一 种 向 他 人 讲 述&  灵 魂 特 质 的 方 式 .../";
                        global.msg[3] = "\\E0* 同 时 提 供 娱 乐 。/";
                        scr_cloface(4, 6);
                        global.msg[5] = "* 等 等 ，我 的 灵 魂 ^1-&\\E9  曾 经 是 ^2？\\E6 黄 色 。/";
                        global.msg[6] = "\\E9* 这 是 否 意 味 着& 我 是 正 义 的 化 身 ？/";
                        scr_charface(7, "H");
                        global.msg[8] = "* ...真 合 适 。/%%";
                    }
                    else
                    {
                        scr_cloface(0, 9);
                        global.msg[1] = "* 所 以 你 提 到 的 这 些&  灵 魂 特 质 到 底 是 什 么 ？/";
                        scr_charface(2, 0);
                        global.msg[3] = "* 你 是 什 么^1 。&* 你 的 存 在 了 超 越 顶 点 。/";
                        scr_cloface(4, "K");
                        global.msg[5] = "* 你 和 Flowey &  说 的 话 真 像 。/";
                        scr_charface(6, "D");
                        global.msg[7] = "* ....当 我 什 么 都 没 说 。/%%";
                    }
                }
                if (obj_iceflag.image_index == 2)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 你 要 是 有 把 四 发 手 枪 &  就 不 好 了 ^1，&  伙 计 。/";
                    scr_charface(2, 1);
                    global.msg[3] = "* 四 发 手 枪 ？/";
                    scr_cloface(4, 7);
                    global.msg[5] = "* 你 听 到 我 说 的 了 。/%%";
                }
            }
        }
        break;
    case room_tundra8A:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 不 知 道 这 些 是 &  干 什 么 用 的 。/";
            scr_charface(2, 3);
            global.msg[3] = "* 有 危 险 。/";
            scr_cloface(4, 6);
            global.msg[5] = "* ...是 啊 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 7);
                global.msg[1] = "* 在 外 面 一 刻 也 不 要 &  放 松 你 的 警 惕 。/";
                scr_cloface(2, 8);
                global.msg[3] = "* 我 觉 得 你 担 心 的 &  有 点 太 多 了 。/%%";
            }
            if (global.plot >= 51)
            {
                if (global.flag[53] != 1)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 他 们 真 可 爱 ！/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 还 很 要 命 ^1。 人 不 可 貌 相 。/";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 想 想 Flowey&  你 就 明 白 了 。/";
                    scr_cloface(6, 5);
                    global.msg[7] = "* .../%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 8);
                        global.msg[1] = "* 还 有 ， 我 很 高 兴 你 能 够&  和 平 解 决 事 情 ../";
                        scr_charface(2, 1);
                        global.msg[3] = "* ...就 像 我 一 样 。/%%";
                    }
                }
                else
                {
                    scr_cloface(0, 5);
                    global.msg[1] = "* 我 ..^1.  知 道 他 们&  很 吓 人 。/";
                    global.msg[2] = "\\E3* 但 你 就 必 须 .../";
                    global.msg[3] = "\\E4* .../";
                    scr_charface(4, 3);
                    global.msg[5] = "* 和 平 解 决 或 许 不 可 能 。/";
                    global.msg[6] = "\\E7* 尤 其 是 当 对 方&  想 要 你 去 死 的 时 候 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 9);
                        global.msg[1] = "* 你 ... 和 Flowey &  说 的 话 真 像。/";
                        global.msg[2] = "* “ 不 是 杀 人 就 是 被 杀 ” 。 /";
                        scr_charface(3, 3);
                        global.msg[4] = "* 或 许 他 并 不 是 完 全 错 误 。/%%";
                    }
                    if (global.flag[427] > 1)
                    {
                        scr_cloface(0, 3);
                        global.msg[1] = "* .../%%";
                    }
                }
            }
        }
        break;
    case room_tundra9:
        if (clover == 1)
        {
            if (instance_exists(obj_papyrus3))
            {
                if (ghostchoose)
                {
                    scr_cloface(0, "C");
                }
                else
                {
                    scr_charface(0, "C");
                }
                global.msg[1] = "* 什 么 。/%%";
                global.flag[427] -= 1;
            }
            else if (instance_exists(obj_sans_room))
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 他 没 有 ^1.^1.^1.\\E6真 的 期 待 &  那 会 起 作 用 ^1， 是 吗 ？/";
                scr_charface(2, 0);
                global.msg[3] = "* 我 不 这 么 认 为 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "L");
                    global.msg[1] = "* 虽 然 ^1， &  我 也 不 确 定 ^1。/";
                    global.msg[2] = "\\EC* 我 不 知 道 &  他 是 怎 么 想 的 。/";
                    scr_cloface(3, "B");
                    global.msg[4] = "* 那 我 就 知 道 吗 ？/%%";
                }
            }
            else if (global.flag[274] == 1)
            {
                scr_charface(0, "D");
                global.msg[1] = "* 你 们 俩 真 是 白 痴 ^1。&  老 是 干 傻 事 .../";
                scr_cloface(2, "J");
                global.msg[3] = "* 我 可 什 么 都 没 说 ！/";
                scr_charface(4, "H");
                global.msg[5] = "* 你 没 说 话 也 是 白 痴 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 我 们 就 不 能 求 同 存 异 吗 ？/";
                    scr_charface(2, "A");
                    global.msg[3] = "* 我 不 能 允 许 你 干 傻 事 。/%%";
                }
            }
            else if (global.flag[274] == 2)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 我 还 是 不 理 解 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 有 什 么 不 理 解 的 ？/";
                global.msg[4] = "\\E9* 你 挑 了 一 堆 杂 物 。/";
                global.msg[5] = "\\EE* 像 一 个 彻 头 彻 尾 的 白 痴 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "A");
                    global.msg[1] = "* 我 只 是 说 说 ^1， &  如 果 我 是 [右 脑] 的 人 .../";
                    global.msg[2] = "\\E7* 你 们 都 是 [左 脑 ] 的 吗 ？/";
                    scr_charface(3, 8);
                    global.msg[4] = "* 你 走 的 是 正 确 的 路 。/";
                    global.msg[5] = "\\EA* 我 们 是 [全 脑 ] 的 ^1，&  而 你 是 [无 脑 ] 的 。/";
                    scr_cloface(6, "J");
                    global.msg[7] = "* 嘿 ！/%%";
                }
            }
        }
        break;
    case room_tundra_spaghetti:
        if (clover == 1)
        {
            scr_charface(0, "C");
            global.msg[1] = "* 别 吃 那 个 。/";
            scr_cloface(2, 0);
            global.msg[3] = "* 我 同 意 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 也 许 尝 一 口 &  也 没 什 么 问 题 .../";
                global.msg[2] = "\\E6* 但 是 说 真 的 ^1， 还 是 别 了 。/%%";
            }
        }
        break;
    case room_tundra_snowpuzz:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 我 希 望 你 没 有 很 冷 。/";
            global.msg[2] = "* 我 穿 过 雪 地 时 &  戴 了 帽 子 并 且 穿 了 夹 克 。/";
            global.msg[3] = "\\E5* 即 使 那 样 还 是 很 冷 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 注 意 你 的 体 温 。/";
                global.msg[2] = "\\E1* 你 的 效 率 会 变 得 .../";
                global.msg[3] = "\\E7* 不 够 理 想 ^1， 在 你 &  被 冻 结 的 时 候 。/";
                scr_cloface(4, 1);
                global.msg[5] = "* 啊 ， 你 居 然 关 心 他 ！/";
                scr_charface(6, 7);
                global.msg[7] = "* 只 是 因 为 那 样 &  效 率 会 变 低 罢 了 。/%%";
            }
        }
        break;
    case room_tundra_xoxosmall:
        if (clover == 1)
        {
            scr_charface(0, "G");
            global.msg[1] = "* 这 是 我 见 过 的 &  最 可 悲 的 谜 题 之 一 。/";
            scr_cloface(2, 0);
            global.msg[3] = "* 但 这 算 是 个 谜 题 吗 ？/";
            scr_charface(4, "C");
            global.msg[5] = "* 这 在 严 格 意 义 上 &  还 算 是 个 谜 题 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 8);
                global.msg[1] = "* 这 不 需 要 动 太 多 脑 筋 ^1，&  不 是 吗 ？/";
                scr_charface(2, 0);
                global.msg[3] = "* 是 的 ^1。 确 实 不 需 要 。/%%";
            }
        }
        break;
    case room_tundra_xoxopuzz:
        if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* 这 个 谜 题 显 然 比 &  之 前 那 个 好 些 了 。/";
            global.msg[2] = "\\E7* 仍 然 很 劣 质 ^1， &  但 确 实 好 些 了 。/";
            scr_cloface(3, 9);
            global.msg[4] = "* 你 一 定 要 对 这 些 谜 题 &  这 么 严 苛 要 求 吗 ？/";
            scr_charface(5, 3);
            global.msg[6] = "* 是 的 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 5);
                global.msg[1] = "* 稍 微 好 些 并 不 代 表&  可 以 接 受 。/";
                scr_cloface(2, "E");
                global.msg[3] = "* 你 就 不 能 说 点 好 话 吗 ？/";
                scr_charface(4, "H");
                global.msg[5] = "* 确 实 没 什 么 好 话 可 说 的 。/";
                global.msg[6] = "\\E8* 而 且 一 个 批 评 家 &  必 须 永 远 说 实 话 。/";
                scr_cloface(7, "C");
                global.msg[8] = "* ...你 能 放 下 你 那 &  高 高 在 上 的 架 子 吗 ？/%%";
            }
        }
        break;
    case room_tundra_randoblock:
        if (clover == 1)
        {
            scr_cloface(0, 5);
            global.msg[1] = "* 想 到 所 有 的 那 些 规 则 &  仍 然 会 让 我 头 疼 。/";
            scr_charface(2, 8);
            global.msg[3] = "* 咱 俩 这 一 次 &  想 法 一 致 了 。/";
            global.msg[4] = "\\E0* 过 于 复 杂 &  不 是 好 的 设 计 。/";
            global.msg[5] = "\\E7* 这 有 些 比 上 不 足 比 下 有 余 。/";
            scr_cloface(6, 6);
            global.msg[7] = "* 我 很 庆 幸 我 们 不 需 要 &  真 的 去 解 决 它 。/";
            global.msg[8] = "\\E9* 等 等 ^1， 你 说 的 &  ‘ 这 一 次 ’ 是 什 么 意 思 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 所 以 什 么 时 候 ‘ 复 杂 ’&  会 变 成 ‘ 太 过 复 杂 ’ 呢 ？/";
                scr_charface(2, 0);
                global.msg[3] = "* 太 过 主 观 ^1。&* 但 对 于 &  这 个 谜 题 嘛 ？/";
                global.msg[4] = "\\E9* 在 我 停 止 听 他 说 话 &  的 那 刻 起 。/";
                scr_cloface(5, "D");
                global.msg[6] = "* 我 想 听 的 是 一 个 &  更 准 确 的 答 案 。/%%";
                global.flag[471] = 1;
            }
            if (instance_exists(obj_papyrus4))
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 天 哪 。/%%";
                global.flag[427] -= 1;
            }
        }
        break;
    case room_tundra_lesserdog:
        if (clover == 1)
        {
            if (global.flag[55] == 0)
            {
                if (global.plot < 67)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 看 起 来 他 有 很 多 灵 感 ！/";
                    scr_charface(2, 3);
                    global.msg[3] = "* 没 有 技 能 的 支 持 &  灵 感 毫 无 意 义 。/";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 但 事 实 并 非 如 此 。/";
                    global.msg[6] = "\\E7* 即 使 你 一 开 始 并 不 擅 长 &  做 某 件 事 ^1，你 仍 然 &  可 以 不 断 进 步 。/";
                    global.msg[7] = "\\E8* 而 且 如 果 没 有 灵 感 ^1，&  你 要 怎 么 开 始 呢 ？/";
                    scr_charface(8, 9);
                    global.msg[9] = "* 纯 粹 的 意 志 力 。/";
                    scr_cloface(10, 8);
                    global.msg[11] = "* ...你 和 我 确 实 是 &  很 不 一 样 的 人 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 1);
                        global.msg[1] = "* 不 过 ，&  我 还 是 祝 他 好 运 。/";
                        scr_cloface(2, 1);
                        global.msg[3] = "* 哦 吼 。/";
                        scr_charface(4, 5);
                        global.msg[5] = "* 闭 嘴 。/%%";
                    }
                }
                else
                {
                    scr_charface(0, 6);
                    global.msg[1] = "* 他 ^1.^1. 他 已 经 放 弃 了 。/";
                    scr_cloface(2, 0);
                    global.msg[3] = scr_gettext("obj_chara_7");
                    scr_charface(4, 3);
                    global.msg[5] = "* 他 甚 至 没 有 &  尝 试 去 做 头 。/";
                    global.msg[6] = "* 这 被 遗 弃 了 。/%%";
                }
            }
            else if (global.flag[55] == 2)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 哇 .../";
                global.msg[2] = "\\E1* 这 些 冰 雕 真 的 &  让 人 印 象 深 刻 ！/";
                scr_charface(3, 0);
                global.msg[4] = "* 这 些 一 个 都 没 有 完 工 ^1。&  一 个 都 没 有 ！/";
                global.msg[5] = "\\E7* 这 到 底 让 人 印 象 深 刻 &  在 哪 里 ？/";
                scr_cloface(6, 0);
                global.msg[7] = "* 这 些 基 底 就 很 棒 ！/";
                global.msg[8] = "\\E1* 我 相 信 总 有 一 天 ^1，&  它 们 会 变 成 精 美 的 成 品 ！/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 7);
                    global.msg[1] = "* 如 果 他 再 也 不 回 来 &  继 续 做 它 们 了 呢 ？/";
                    scr_cloface(2, 0);
                    global.msg[3] = "* 那 我 猜 他 会 去 做&  其 他 更 好 的 事 情 。/";
                    global.msg[4] = "\\E7* 而 且 我 真 心 祝 他 好 运 。/";
                    global.msg[5] = "\\E9* 但 现 在 说 这 些 &  还 为 时 过 早 ！/";
                    scr_charface(6, 3);
                    global.msg[7] = "* ...但 你 刚 才 说 的 &  确 实 有 点 道 理 。/%%";
                }
            }
            else if (global.flag[55] == 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 里 好 空 荡 。/";
                global.msg[2] = "\\E3* 还 有 那 个 哨 所 .../";
                global.msg[3] = "\\E4* .../";
                scr_charface(4, 1);
                global.msg[5] = "* 木 已 成 舟 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 0);
                    global.msg[1] = "* 我 们 .../";
                    global.msg[2] = "* 我 们 还 是 离 开 这 里 吧 。/";
                    scr_charface(3, 4);
                    global.msg[4] = "* .../%%";
                }
            }
        }
        break;
    case room_tundra_icehole:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 这 两 个 家 伙 确 实 &  很 不 一 样 ^1， 不 是 吗 ？/";
            scr_charface(2, 3);
            global.msg[3] = "* 兄 弟 姐 妹 不 总 是 相 似 的 。/";
            scr_cloface(4, 0);
            global.msg[5] = "* 说 得 对 ^1， 搭 档 。/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 你 是 ...有 兄 弟 姐 妹 &  才 这 样 说 的 吗 ？/";
                scr_charface(2, 8);
                global.msg[3] = "* 我 有 吗 ！？/%%";
            }
            else if (global.flag[427] > 1)
            {
                scr_charface(0, 1);
                global.msg[1] = "* ...你 有 吗 ？/%%";
                global.flag[101] = 1;
            }
        }
        break;
    case room_tundra_iceentrance:
        if (clover == 1)
        {
            scr_charface(0, 9);
            global.msg[1] = "* 终 于 ^1， 可 算 有 一 个 &  能 算 是 谜 题 的 东 西 了 。/";
            global.msg[2] = "\\E7* 我 本 来 还 觉 得 这 里 &  没 什 么 像 样 的 挑 战 呢 。/";
            scr_cloface(3, 7);
            global.msg[4] = "* 其 他 的 是 有 什 么 问 题 吗 ？/";
            scr_charface(5, 3);
            global.msg[6] = "* 我 甚 至 都 没 打 算 &  回 答 这 个 问 题 。/";
            scr_cloface(7, 6);
            global.msg[8] = "* 不 ， 认 真 的 ， 什 么 ？！/%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 你 真 得 好 好 想 想 &  你 该 往 哪 个 方 向 走 。/";
                global.msg[2] = "\\E1* “ 四 个 方 向 中 &  你 觉 得 怎 么 走 最 好 ？”/";
                global.msg[3] = "\\E8* 而 且 不 能 靠 运 气 。/";
                global.msg[4] = "\\E5* 也 不 是 不 能 通 过 &  通 过 仔 细 的 推 理 找 到 &  问 题 的 解 决 方 法 。/";
                scr_cloface(5, "A");
                global.msg[6] = "* 走 对 角 线 ^1.^1.^1.&  \\EH怎 么 样 ？/";
                scr_charface(7, 3);
                global.msg[8] = "* ^1.^1.^1./";
                global.msg[9] = "\\E6* 哦 ， 赶 紧 的 吧 ！/%%";
            }
            else if (global.flag[427] > 1)
            {
                scr_charface(0, "D");
                global.msg[1] = "* 你 把 我 的 思 维 全 扰 乱 了 ^1。&  你 很 高 兴 是 不 是 啊 ？/";
                global.msg[2] = "\\EB* 别 让 我 看 到 它 。/%%";
                if (global.flag[477] == 1)
                {
                    scr_charface(0, "D");
                    global.msg[2] = "* 这 都 是 你 的 错 ^1，&  Clover 。/";
                    scr_cloface(3, "I");
                    global.msg[4] = "* 我 也 就 是 提 出 了 个 想 法 。/";
                    scr_charface(5, "D");
                    global.msg[6] = "\\EB* 我 不 管 ^1。&* 赶 紧 给 我 闭 嘴 。/%%";
                    global.flag[477] = 2;
                }
            }
        }
        break;
    case room_tundra_iceexit_new:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 我 觉 得 我 们 被 监 视 了 .../";
            scr_charface(2, 3);
            global.msg[3] = "* 因 为 确 实 如 此 。/";
            global.msg[4] = "* 墙 后 面 有 很 多 眼 睛 &  在 盯 着 我 们 。/";
            global.msg[5] = "\\E7* 他 们 甚 至 都 不 打 算 隐 蔽 。/";
            scr_cloface(6, 6);
            global.msg[7] = "* ...那 就 说 得 通 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 如 果 我 是 你 ，&  我 会 小 心 他 们 的 。/";
                scr_cloface(2, 5);
                global.msg[3] = "* 嘿 ， 就 因 为 &  他 们 在 看 着 我 们 .../";
                if (global.flag[9] == 0)
                {
                    global.msg[4] = "\\E8* 那 不 能 说 明 他 们&  想 伤 害 我 们 ！/%%";
                }
                else
                {
                    global.msg[4] = "\\E8* 那 不 能 说 明 &  他 们 想 伤 害 我 们 ！/";
                }
                scr_charface(5, 8);
                global.msg[6] = "* 把 这 句 话 跟 Flowey 说 。/%%";
            }
        }
        break;
    case room_tundra_iceexit:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 只 走 正 路 确 实 很 容 易 。/";
            global.msg[2] = "\\E8* 但 这 样 的 景 色 .../";
            global.msg[3] = "\\E0* 这 让 我 想 起 了 &  地 下 世 界 究 竟 有 多 大 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 7);
                global.msg[1] = "* 这 也 没 有 很 大 。/";
                scr_cloface(2, 5);
                global.msg[3] = "* 不 。/";
                global.msg[4] = "\\E3* 才 不 是 那 样 的 。/%%";
            }
            if (instance_exists(obj_npc_room))
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 我 记 得 她 ！/";
                global.msg[2] = "\\E6* 当 时 我 在 雪 镇 时 &  我 突 然 迷 路 了 。/";
                global.msg[3] = "\\E0* 那 时 看 样 子 &  她 也 迷 路 了 。/";
                global.msg[4] = "\\E5* 我 后 来 找 到 了 路 ^1，&  但 却 再 也 没 看 见 过 她 。/";
                global.msg[5] = "\\E8* 真 高 兴 她 最 终 找 到 了&  回 来 的 路 。/%%";
            }
        }
        break;
    case room_tundra_poffzone:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 它 们 就 像 ... &  巨 大 的 棉 花 糖 。/";
            scr_charface(2, 0);
            global.msg[3] = "* 这 其 实 只 是 雪 。/";
            scr_cloface(4, 9);
            global.msg[5] = "* 我 又 不 是 不 知 道 ！/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, "C");
                global.msg[1] = "* 现 在 我 饿 了 。/";
                scr_charface(2, "C");
                global.msg[3] = "* .../%%";
            }
            else if (global.flag[427] > 1)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 你 还 在 想 这 个 ^1， &  不 是 吗 ？/";
                scr_cloface(2, "D");
                global.msg[3] = "* 我 真 的 忍 不 住 啊 ！/%%";
            }
        }
        break;
    case room_tundra_dangerbridge:
        if (clover == 1 && global.plot >= 67)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 我 必 须 承 认 ^1， 当 Papyrus &  拿 出 那 些 的 时 候 .../";
            scr_charface(2, 8);
            global.msg[3] = "* 死 亡 陷 阱 ？/";
            scr_cloface(4, 6);
            global.msg[5] = "* 我 本 来 想 说 &  “ 谜 题 ” 的 ，但 &  好 像 也 可 以 这 么 说 。/";
            global.msg[6] = "\\EH* 我 刚 才 有 点 担 心 你 了 。/";
            scr_charface(7, 9);
            global.msg[8] = "* 有 点 担 心 ？/";
            global.msg[9] = "* 当 他 快 要 启 动 的 时 候 &  你 叫 的 可 带 劲 了-%";
            scr_cloface(10, "J");
            global.msg[11] = "* 我 才 没 有 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "E");
                global.msg[1] = "* 而 且 我 猜 你 一 点 都 &  不 害 怕 它 们 ？/";
                scr_charface(2, 0);
                global.msg[3] = "* 当 然 不 是 。/";
                global.msg[4] = "\\E8* 我 判 断 出 这 不 符 合 &  Papyrus 的 性 格 。/";
                scr_cloface(5, 9);
                global.msg[6] = "* 但 是 他 制 作 这 些 的 目 的 &  不 就 是 为 了 使 用 吗 ！/";
                scr_charface(7, 3);
                global.msg[8] = "* .../%%";
                global.msg[9] = "\\EC* 事 后 看 来 ^1， 可 能 它 比 我&  想 象 的 要 更 接 近 一 点 。/";
                scr_cloface(10, 8);
                global.msg[11] = "* 谢 谢 你 ！/%%";
            }
        }
        break;
    case room_tundra_town:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 这 里 有 这 么 多 事 情 能 做 .../";
            global.msg[2] = "\\E1* 虽 然 没 有 绿 洲 镇 大 ^1，&  但 充 满 了 快 乐 的 气 氛 ！/";
            scr_charface(3, 8);
            global.msg[4] = "* 或 者 他 们 只 是 想 &  转 移 注 意 力 。/";
            global.msg[5] = "* 他 们 真 正 感 受 到 的 &  是 一 种 潜 在 的 绝 望 感 。/";
            scr_cloface(6, 6);
            global.msg[7] = "* .../";
            global.msg[8] = "\\E1* 真 是 充 满 了 欢 乐 ！/";
            scr_charface(9, "H");
            global.msg[10] = "* 搞 清 楚 状 况 吧 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "I");
                global.msg[1] = "* 等 一 下 ^1， 你 刚 才 说 的 &  绿 洲 镇 是 什 么 ？/";
                scr_cloface(2, "A");
                global.msg[3] = "* 那 个 吗 ^2？ \\E7那 是 另 一 个 &  地 下 世 界 的 小 镇 ^1，&  它 位 于 沙 丘 。/";
                scr_charface(4, "D");
                global.msg[5] = "* 好 吧 ， 沙 丘 又 是 什 么 ？/%%";
            }
            if (scr_murderlv() == 7 && global.plot >= 101)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 明 白 你 想 扭 转 局 面 .../";
                global.msg[2] = "\\E9* 别 误 会 ， 我 很 高 兴 &  你 愿 意 这 么 做 ！/";
                global.msg[3] = "\\EE* 但 你 的 行 为 &  已 经 产 生 了 后 果 。/";
                global.msg[4] = "* 但 你 已 经 造 成 的 后 果 ^1.^1.^1.&  你 得 为 此 负 责 。/";
                global.msg[5] = "* 这 地 方 再 也 不 会 和 &  以 前 一 样 了 ^1， &  你 得 明 白 这 一 点 。/";
                global.msg[6] = "* 既 然 我 们 都 来 了 ^1，&  就 看 看 你 创 造 的 鬼 城 吧 。/";
                global.msg[7] = "\\EF* 而 且 不 要 忘 记 它 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "E");
                    global.msg[1] = scr_gettext("obj_chara_8");
                    scr_charface(2, 3);
                    global.msg[3] = "* .../";
                    scr_cloface(4, "E");
                    global.msg[5] = "* 现 在 我 们 走 吧 。/";
                    global.msg[6] = "* 你 也 要 做 些 赎 罪 的 事 。/";
                    scr_charface(7, 7);
                    global.msg[8] = "* ... 你 是 说 救 赎 吧 。/";
                    scr_cloface(9, "J");
                    global.msg[10] = "* 别 纠 结 用 词 了 ^1，&  快 走 吧 ，以 后 你 一 定 要 &  做 个 更 好 的 人 ！/%%";
                }
            }
        }
        break;
    case room_tundra_town2:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 等 一 下 ^1， \\E0我 认 识 &  这 只 怪 物 ！/";
            scr_charface(2, "I");
            global.msg[3] = "* 你 ...真 的 认 识 ？/";
            scr_cloface(4, 1);
            global.msg[5] = "* 是 的 ^1！ 当 时 我 还 在 冒 险 &  的 时 候 ， 他 就 已 经 开 始 &  扔 冰 块 了 ！/";
            global.msg[6] = "\\E6* 尽 管 我 从 不 知 道 为 什 么 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 这 种 体 力 劳 动 必 须 &  持 续 一 整 天 .../";
                global.msg[2] = "\\E8* 确 实 是 个 令 人 印 象 深 刻 &  的 怪 物 。/";
                scr_cloface(3, 6);
                global.msg[4] = "* 而 且 他 已 经 这 么 &  干 了 很 久 了 .../";
                global.msg[5] = "\\E1* 他 一 定 对 自 己 的 工 作 &  充 满 了 激 情 ！/%%";
            }
        }
        break;
    case room_tundra_dock:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 有 点 奇 怪 。/";
            global.msg[2] = "\\E9* 他 真 的 会 免 费 &  带 你 去 任 何 地 方 ？/";
            scr_charface(3, 0);
            global.msg[4] = "* 我 猜 他 会 从 中 &  得 到 一 些 其 他 的 东 西 。/";
            scr_cloface(5, 1);
            global.msg[6] = "* 你 是 说 他 在 意 的 是 过 程 ^1， &  而 不 是 结 果 ！/";
            scr_charface(7, 0);
            global.msg[8] = "* ...我 不 是 这 个 意 思 ^1，&  \\E8但 你 这 么 说 好 像 也 对 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 真 正 的 坐 船 之 旅 .../";
                global.msg[2] = "\\E1* ...应 该 是 我 们 一 路 走 来 &  所 交 的 朋 友 。/";
                scr_charface(3, "G");
                global.msg[4] = "* 你 在 胡 说 些 什 么 ？/%%";
            }
            if (!instance_exists(obj_dogboat_thing))
            {
                scr_charface(0, 1);
                global.msg[1] = "* 你 能 ... &  等 一 下 吗 ？/";
                global.msg[2] = "\\E3* 我 想 感 谢 这 里 的 清 静 。/";
                scr_cloface(3, 1);
                global.msg[4] = "* 什 么 ^1， 你 厌 倦 了 我 的 话-%";
                scr_charface(5, 5);
                global.msg[6] = "* 请 你 闭 嘴 。/";
                scr_cloface(7, 5);
                global.msg[8] = "* ^1.^1.^1./";
                scr_charface(9, 0);
                global.msg[10] = "* ^1.^1.^1./%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* ^1.^1.^1./";
                    scr_charface(2, 1);
                    global.msg[3] = "* ^1.^1.^1./";
                    global.msg[4] = "\\E7* 我 很 感 谢 你 。/%%";
                }
            }
        }
        break;
    case room_tundra_inn:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 现 在 是 休 息 一 下 的 &  最 佳 时 机 ！/";
            scr_charface(2, 7);
            global.msg[3] = "* 现 在 也 是 赶 紧 走 &  的 最 佳 时 机 。/";
            scr_cloface(4, 6);
            global.msg[5] = "* 好 好 休 息 能 让 你 &  为 将 来 做 好 准 备 。/";
            global.msg[6] = "\\E7* 我 不 会 那 么 快 &  就 否 定 它 的 价 值 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 8);
                global.msg[1] = "* 当 然 ^1， 你 也 不 能 太 懒 。/";
                scr_charface(2, "G");
                global.msg[3] = "* 所 以 这 是 说 我 们 &  现 在 可 以 走 了 吗 ？/";
                scr_cloface(4, 7);
                global.msg[5] = "* 也 许 稍 微 懒 惰 一 点 &  也 未 尝 不 可 。/";
                scr_charface(6, "D");
                global.msg[7] = "* 呃 啊 .../%%";
            }
        }
        break;
    case room_tundra_grillby:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 这 里 的 气 氛 &  相 当 的 温 暖 。/";
            scr_charface(2, 0);
            global.msg[3] = "* 会 不 会 跟 我 们 那 位 &  燃 烧 着 的 朋 友 有 关 ？/";
            scr_cloface(4, 6);
            global.msg[5] = "* 我 不 觉 得 气 氛 是 这 里 &  唯 一 温 暖 的 东 西 。/";
            global.msg[6] = "\\E1* 你 不 再 发 抖 了 ！/";
            scr_charface(7, 8);
            global.msg[8] = "* 的 确 如 此 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 我 现 在 火 急 火 燎 的 &  想 要 尝 尝 菜 单 上 的 东 西 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* 所 有 东 西 看 起 来&  都 挺 不 错 的 ！/";
                global.msg[4] = "\\E5* 等 等 ^1， 那 是 个 双 关 吗 ？/";
                scr_charface(5, 9);
                global.msg[6] = "* 我 是 想 取 悦 你 。/";
                scr_cloface(7, 7);
                global.msg[8] = "* 坦 白 了 说 ^1，&  我 不 这 么 认 为 。/";
                scr_charface(9, "H");
                global.msg[10] = "* 你 知 道 的 ^1，&  我 也 很 有 幽 默 感 。/";
                global.msg[11] = "\\EE* 至 少 比 你 的 好 。/";
                scr_cloface(12, "J");
                global.msg[13] = "* 嘿 ！/%%";
            }
            if (instance_exists(obj_grillbynpc_foodmonster))
            {
                if (obj_grillbynpc_foodmonster.sansmode == 1)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* Flowey 到 底 想 对 &  Papyrus 做 什 么 ^1？/";
                    global.msg[2] = "\\E5* 他 就 是 Sans所 说 的 ^1，&  对 吧 ？/";
                    scr_charface(3, 3);
                    global.msg[4] = "* 还 能 是 谁 呢 ^1？ 还 有 无 论 &  他 想 要 什 么 ^1， 可 以 肯 定 &  不 是 什 么 好 东 西 。/";
                    scr_cloface(5, 9);
                    global.msg[6] = "* 你 不 了 解 他 ^1。&* 我 敢 肯 定 他 会 -%";
                    scr_charface(7, 5);
                    global.msg[8] = "* 你 可 别 是 认 真 的 ^1。&* 你 已 经 见 过 他 的 &  真 面 目 了 。/";
                    scr_cloface(9, 9);
                    global.msg[10] = "* 也 许 吧 ^2。 你 可 以 说 我 &  很 天 真 ^1， 但 我 内 心 深 处 &  还 是 愿 意 相 信 他 .../";
                    global.msg[11] = "\\E8* 他 在 关 心 别 人 。/%%";
                    global.flag[19] = 10;
                }
            }
        }
        break;
    case room_tundra_library:
        if (clover == 1)
        {
            scr_charface(0, 7);
            global.msg[1] = "* 等 一 下 。/";
            scr_cloface(2, 0);
            global.msg[3] = "* 怎 么 了 ？/";
            scr_charface(4, "C");
            global.msg[5] = "* 这 里 的 招 牌 上 写 的 是 &  ‘ 图 书 倌 ’ 吗 ？/";
            scr_cloface(6, "B");
            global.msg[7] = "* 还 真 是 ^1？ 我 刚 才 还 以 为&  那 是 我 眼 花 了 。/";
            scr_charface(8, "G");
            global.msg[9] = "* 我 真 不 敢 相 信 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 至 少 里 面 很 正 常 。/";
                global.msg[2] = "\\E7* 而 且 还 有 这 么 多 &  书 可 以 读 ！/";
                if (global.ghostcolor == 1)
                {
                    global.msg[3] = "\\E1\\W* 为 什 么 我 们 不 休 息 一 下 &  然 后 \\Y随 便 看 几 本 ？/%%";
                }
                else
                {
                    global.msg[3] = "\\E1\\Y* 为 什 么 我 们 不 休 息 一 下 &  然 后 \\G随 便 看 几 本 ？/%%";
                }
            }
        }
        break;
    case room_tundra_garage:
        if (clover == 1)
        {
            scr_cloface(0, 8);
            global.msg[1] = "* 你 ^1.^1.^1.面 对 这 样 一 个 &  强 大 的 对 手 已 经 &  做 的 很 好 了 。/";
            scr_charface(2, "H");
            global.msg[3] = "* 别 给 他 找 借 口 了 ^1。&\\EE* 输 了 就 是 输 了 。/";
            scr_cloface(4, 5);
            global.msg[5] = "* 你 也 太 无 情 了 。/";
            scr_charface(6, 9);
            global.msg[7] = "* 但 我 是 在 说 实 话 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 不 过 这 里 的 &  住 宿 条 件 还 不 错 ！/";
                scr_charface(2, 7);
                global.msg[3] = "* 一 张 狗 床 可 不 能 说 是 &  ‘ 不 错 ’ 。/";
                scr_cloface(4, 6);
                global.msg[5] = "* 不 好 吗 ？/%%";
            }
        }
        break;
    case room_tundra_sanshouse:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 哇 。/";
            scr_charface(2, "I");
            global.msg[3] = "* 你 哇 什 么 ？/";
            global.msg[4] = "\\E0* 点 醒 我 ^2。&* 一 个 房 子 有 什 么 特 别 的 ？/";
            scr_cloface(5, 6);
            global.msg[6] = "* 你 看 不 出 来 吗 ？/";
            global.msg[7] = "\\E1* 这 房 子 虽 然 没 有 &  Ceroba 家 那 么 大 ， 但&  也 够 大 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* Clover ， 我 .../";
                global.msg[2] = "\\EH* ..^1.我 觉 得 这 已 经 很 大 了 。/";
                scr_cloface(3, 1);
                global.msg[4] = "* 我 知 道 ^1， 就 是 这 个 ！ ？ /%%";
            }
        }
        break;
    case room_tundra_paproom:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 这 也 太 .../";
            scr_charface(2, 0);
            global.msg[3] = "* 幼 稚 ？/";
            scr_cloface(4, 2);
            global.msg[5] = "* 太 酷 了 ！/";
            scr_charface(6, "C");
            global.msg[7] = "* ...我 不 这 么 认 为 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 1);
                global.msg[1] = "* 至 少 他 的 房 间 很 整 洁 。/";
                scr_cloface(2, "C");
                global.msg[3] = "* 你 总 是 关 注 &  最 无 聊 的 东 西 。/";
                scr_charface(4, 8);
                global.msg[5] = "* 我 更 喜 欢 “ 成 熟 ” 。/%%";
            }
        }
        break;
    case room_tundra_sansroom:
        if (clover == 1)
        {
            scr_charface(0, "B");
            global.msg[1] = "* 我 们 被 他 耍 了 。/";
            scr_cloface(2, "J");
            global.msg[3] = "* 他 明 明 之 前 &  对 我 们 那 么 好 ！/";
            scr_charface(4, "D");
            global.msg[5] = "* 我 们 三 个 居 然 都 上 当 了 ，&  我 太 失 望 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 我 们 可 别 把 这 &  告 诉 任 何 人 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* 我 同 意 。/";
                global.msg[4] = "\\E8* 但 是 ^1， 呃 ^1， 我 们 &  本 来 也 不 能 跟 别 的 &  任 何 人 说 话 .../";
                scr_charface(5, "D");
                global.msg[6] = "* 我 不 管 。/";
                global.msg[7] = "* 就 算 是 这 样 ，&  我 也 有 必 要 指 出 来 。/%%";
            }
        }
        break;
    case room_tundra_sansroom_dark:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 这 里 好 黑 .../";
            global.msg[2] = "* 这 会 通 向 哪 里 ？/";
            scr_charface(3, 0);
            global.msg[4] = "* 看 起 来 这 里 没 有 尽 头 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_tundra_sansbasement:
        if (clover == 1)
        {
            scr_cloface(0, 5);
            global.msg[1] = "* 我 们 ...不 该 来 这 里 。/";
            global.msg[2] = "\\E6* 我 觉 得 Sans 不 想&  让 我 们 找 到 这 个 地 方 。/";
            scr_charface(3, 0);
            global.msg[4] = "* 我 们 来 都 来 了 。/";
            global.msg[5] = "* 他 到 底 在 藏 些 什 么 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 我 们 该 走 了 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 这 里 的 一 切 都 .../";
                global.msg[4] = "\\E1* 真 令 人 好 奇 。/";
                scr_cloface(5, 9);
                global.msg[6] = scr_gettext("obj_chara_9");
                scr_charface(7, 3);
                global.msg[8] = "* 我 们 对 他 一 无 所 知 。/";
                global.msg[9] = "* 但 他 却 知 道 我 们 可 以 &  时 空 旅 行 。/";
                global.msg[10] = "* 这 太 不 公 平 了 。&  我 希 望 我 们 能 弥 补 &  对 对 方 认 知 上 的 差 距 。/";
                scr_cloface(11, 5);
                global.msg[12] = "* 擅 闯 这 里 是 不 对 的 ^2 。&\\E9* 快 带 我 们 离 开 这 。/%%";
            }
        }
        break;
    case room_fogroom:
        if (clover == 1)
        {
            if (global.plot < 101)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 保 持 警 惕 。/";
                global.msg[2] = "\\E6* Papyrus 一 定 就 在 前 面 。/";
                scr_charface(3, "I");
                global.msg[4] = "* 他 可 能 很 浮 躁 ^1，&  但 他 似 乎 不 容 易 被 打 败 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 我 们 赶 紧 把 事 情 &  解 决 掉 吧 。/%%";
                }
                if (global.flag[67] == -1)
                {
                    scr_cloface(0, 5);
                    global.msg[1] = "* 我 们 现 在 知 道 &  他 的 攻 击 方 式 了 。/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 他 只 能 坚 持 这 么 久 。/";
                    scr_cloface(4, 7);
                    global.msg[5] = "* 第 二 次 尝 试 会 有 好 运 的 ！/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 1);
                        global.msg[1] = "* 你 明 白 了 吧 ！/%%";
                    }
                }
                if (global.flag[67] < -1)
                {
                    scr_cloface(0, 5);
                    global.msg[1] = "* 好 吧 ^1， 你 可 能 是 努 力 了 ^2。&  但 你 只 努 力 了 一 点 。/";
                    scr_charface(2, "G");
                    global.msg[3] = "* 比 “ 只 有 一 点 ” 要 多 。/";
                    scr_cloface(4, 7);
                    global.msg[5] = "* 但 我 相 信 你 ！/";
                    scr_charface(6, 0);
                    global.msg[7] = "* 等 着 瞧 吧 .../%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, "D");
                        global.msg[1] = "* 请 你 这 次 把 这 件 事 做 好 。/%%";
                    }
                }
            }
            else if (scr_murderlv() == 7 && global.plot >= 101)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* Papyrus 给 了 你 一 次&  救 赎 的 机 会 。/";
                global.msg[2] = "\\EE* 别 浪 费 了 他 的 好 意 。/%%";
            }
            else if (global.flag[19] < 9)
            {
                if (global.flag[67] == 1)
                {
                    if (global.flag[211] == 1)
                    {
                        scr_cloface(0, "E");
                        global.msg[1] = "* 他 饶 恕 了 你 。/";
                        global.msg[2] = "\\EF* 你 的 生 命 从 未 受 到 过 威 胁 。/";
                        global.msg[3] = "* 所 以 你 为 什 么 要 杀 他 。/";
                        global.msg[4] = "\\EJ* 你 为 什 么 -/";
                        global.msg[5] = "\\E3* .../";
                        scr_charface(6, 1);
                        global.msg[7] = "* .../%%";
                        if (global.flag[427] > 0)
                        {
                            scr_charface(0, 1);
                            global.msg[1] = "* 我 想 我 们 最 好 赶 紧 走 。/%%";
                        }
                    }
                    else
                    {
                        scr_cloface(0, "B");
                        global.msg[1] = "* 他 ^1.^1.^1.他 .../";
                        global.msg[2] = "\\E3* .../";
                        scr_charface(3, 0);
                        global.msg[4] = "* ...Clover ？/";
                        global.msg[5] = "* 你 还 好 吗 -%";
                        scr_cloface(6, "E");
                        global.msg[7] = "* 我 们 走 吧 。/%%";
                        if (global.flag[427] > 0)
                        {
                            scr_cloface(0, "J");
                            global.msg[1] = "* 走 ！/";
                            scr_charface(2, 1);
                            global.msg[3] = "* .../%%";
                        }
                    }
                }
                else
                {
                    scr_cloface(0, "B");
                    global.msg[1] = "* 他 刚 才 ... 飞 起 来 了 ？/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 看 来 他 的 确 &  在 隐 藏 他 的 实 力 。/";
                    global.msg[4] = "* 谁 知 道 他 还 能 &  做 什 么 呢 ？/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, "G");
                        global.msg[1] = "* 他 飞 走 了 ？？？/";
                        scr_charface(2, 0);
                        global.msg[3] = "* 你 是 见 不 得 &  会 飞 的 骷 髅 吗 ？/%%";
                    }
                }
            }
            else if (global.flag[67] == 1)
            {
                scr_cloface(0, "E");
                global.msg[1] = "* 我 不 想 再 在 这 里 待 了 。/";
                scr_charface(2, 1);
                global.msg[3] = "* ...那 段 回 忆 真 糟 糕 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "E");
                    global.msg[1] = "* 我 们 可 以 走 了 吗 ？/";
                    global.msg[2] = "\\E3* 拜 托 ？/%%";
                }
            }
            if (global.flag[19] >= 9 && global.flag[67] != 1 && scr_murderlv() < 7)
            {
                global.msc = 3024;
            }
        }
        break;
    case room_water1:
        if (clover == 1)
        {
            if (global.flag[67] == 1)
            {
                scr_cloface(0, "E");
                global.msg[1] = "* 我 们 到 底 该&  聊 些 什 么 呢 ？/";
                global.msg[2] = "\\EF* 嗯 ？/";
                if (irememberyourneutrals < 1)
                {
                    scr_charface(3, 1);
                }
                else
                {
                    scr_charface(3, 0);
                }
                global.msg[4] = "* .../%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "E");
                    global.msg[1] = "* 你 只 管 继 续 前 进 。/%%";
                }
            }
            else if (scr_murderlv() >= 2)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 现 在 轻 松 多 了 .../";
                global.msg[2] = "\\E6* .../%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 从 现 在 开 始 好 好 反 思 &  你 的 所 作 所 为 ^1，&  好 吗 ？/%%";
                }
            }
            else
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 想 知 道 那 条 河&  通 向 哪 里 。/";
                global.msg[2] = "\\E0* 如 果 它 连 通 到 我 曾 经 &  走 过 的 那 条 河 ^1， 你 最 好 .../";
                global.msg[3] = "* 好 像 那 样 做 &  也 不 是 什 么 好 主 意 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 所 以 ^1， 我 们 可 能 会 坠 落 ，&  然 后 掉 到 一 个 沙 漠 里 。/";
                    global.msg[2] = "\\E1* 但 我 最 终 还 是 回 来 了 ！/%%";
                }
            }
        }
        break;
    case room_water2:
        if (clover == 1)
        {
            if (instance_exists(obj_sans_sentry2))
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 等 等 ^1， 我 还 以 为 Sans 的 &  岗 哨 在 雪 镇 呢 。/";
                scr_charface(2, 7);
                global.msg[3] = "* 他 一 直 在 跟 着 我 们 。/";
                global.msg[4] = "\\E3* 但 他 是 出 于 什 么 目 的 ？/%%";
                if (global.flag[89] == 3)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 我 刚 才 确 实 吓 了 一 跳 。/";
                    global.msg[2] = "\\E1* Sans 真 是 个 好 演 员 。/";
                    scr_charface(3, 1);
                    global.msg[4] = "* .../";
                    global.msg[5] = "\\E0* 他 确 实 是 。/%%";
                    if (ossafe_file_exists("system_information_963"))
                    {
                        scr_charface(3, 4);
                    }
                }
            }
            else
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
            if (instance_exists(obj_npc_room) && global.flag[67] != 1)
            {
                if (obj_npc_room.talkedto >= 1)
                {
                    cloweychance = round(random(100));
                    scr_cloface(0, "A");
                    global.msg[1] = "* 回 音 花 ^1， 是 吗 ？/";
                    global.msg[2] = "\\E7* 它 们 确 实 很 精 致 。/";
                    global.msg[3] = "\\E9* 你 能 想 象 到 吗 ？/";
                    global.msg[4] = "* 一 遍 又 一 遍 的 &  重 复 同 样 的 事 .../%%";
                    if (global.flag[427] > 3)
                    {
                        scr_cloface(0, "A");
                        global.msg[1] = "* 回 音 花 ^1， 是 吗 ？/";
                        global.msg[2] = "\\E7* 它 们 确 实 很 精 致 。/";
                        global.msg[3] = "\\E9* 你 能 想 象 到 吗 ？/";
                        global.msg[4] = "* 重 复 .../";
                        global.msg[5] = "\\E6* ...等 会 儿 。/%%";
                    }
                    if (global.flag[427] == 1)
                    {
                        if (cloweychance > 99)
                        {
                            scr_cloface(0, "N");
                            global.msg[1] = "* 然 后 一 遍 又 一 遍 &  一 遍 又 一 遍&  一 遍 又 一 遍 -%%";
                        }
                    }
                    if (ossafe_file_exists("file8") && global.plot < 200)
                    {
                        scr_cloface(0, 0);
                        global.msg[1] = "* 回 音 花 .../";
                        global.msg[2] = "\\E7* 我 不 喜 欢 他 们 。 /";
                        global.msg[3] = "\\E0* 你 会 理 解 的 ^1，&  我 想 。 /";
                        global.msg[4] = "\\EB* 听 着 未 曾 改 变 的 人&  说 着 完 全 相 同 的 话 。 /";
                        global.msg[5] = "* 每 次 都 是 同 样 的 方 式 。/%%";
                        if (global.flag[427] > 0)
                        {
                            scr_charface(0, "L");
                            global.msg[1] = "* .../%%";
                        }
                    }
                }
            }
        }
        break;
    case room_water3:
        if (clover == 1)
        {
            if (global.flag[67] == 0 && irememberyourneutrals < 2)
            {
                scr_cloface(0, 8);
                global.msg[1] = scr_gettext("obj_chara_10");
                global.msg[2] = "\\E1* 这 里 的 瀑 ^1， &  真 的 像 布 一 样 ！/";
                scr_charface(3, 9);
                global.msg[4] = "* 哦 ^1， 真 有 趣 。/%%";
                if (global.flag[427] == 1)
                {
                    scr_charface(0, "H");
                    global.msg[1] = "* 那 些 石 头 下 落 的 很 快 。/";
                    global.msg[2] = "\\EE* 几 乎 和 你 说 出 那 些 话 时 &  我 的 智 商 下 降 的 一 样 快 。/";
                    scr_cloface(3, 2);
                    global.msg[4] = "* 你 真 的 觉 得 你 的 智 商 &  很 值 得 炫 耀 吗 ？/";
                    scr_charface(5, "H");
                    global.msg[6] = "* 当 然 了 。/";
                    global.msg[7] = "\\E9* 此 外 ^1， 注 意 它 们 &  是 如 何 掉 进 深 渊 的 ^1，&  以 通 过 这 个 关 卡 。/";
                    scr_cloface(8, "D");
                    global.msg[9] = "* 不 错 ！/";
                    global.msg[10] = "\\E8* 真 得 有 个 人 &  让 你 放 下 架 子 。/";
                    scr_charface(11, 8);
                    global.msg[12] = "* 啐 。/";
                    global.msg[13] = "\\EH* 好 吧 ^1， 是 你 赢 了 。/%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 耶 ！/";
                    global.msg[2] = "\\E9* 等 会 ^1， 我 到 底 &  赢 了 些 什 么 ？/";
                    scr_charface(3, "H");
                    global.msg[4] = "* 我 哪 知 道 ^2？&\\EE* 是 你 开 启 的 对 话 。/";
                    scr_cloface(5, 7);
                    global.msg[6] = "* 不 是 我 ！/%%";
                }
            }
            if (global.flag[67] == 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 会 小 心 那 些 石 头 的 。/";
                global.msg[2] = "* 如 果 我 猜 得 没 错 ^1，&  它 们 会 让 你 摔 下 去 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "L");
                    global.msg[1] = "* ...如 果 你 猜 得 没 错 ？/";
                    global.msg[2] = "\\ED* 那 些 是 石 头 ^1。&* 它 们 还 能 怎 么 样 。/";
                    scr_cloface(3, 6);
                    global.msg[4] = "* ^1.^1.^1.\\E7和 你 谈 话 ？/";
                    scr_charface(5, 8);
                    global.msg[6] = "* 有 道 理 。/%%";
                }
            }
            else if (irememberyourneutrals >= 2)
            {
                scr_cloface(0, 8);
                global.msg[1] = scr_gettext("obj_chara_10");
                global.msg[2] = "\\E1* 这 里 的 瀑 ^1， &  真 的 像 布 一 样 ！/";
                scr_charface(3, 8);
                global.msg[4] = "* .../%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 你 看 看 那 个 ^2。&  你 会 笑 的 。/";
                    scr_charface(2, 3);
                    global.msg[3] = "* .../";
                    scr_cloface(4, "G");
                    global.msg[5] = "* 嗯 我 不 是 那 样 想 的& 我 没 有 恶 意 哈 哈 抱 歉 。/%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_charface(0, "D");
                    global.msg[1] = "* .../";
                    global.msg[2] = "\\EH* 接 受 道 歉 。/";
                    scr_cloface(3, "B");
                    global.msg[4] = "* 哦 ^1！ 谢 谢 ！/%%";
                }
            }
        }
        break;
    case room_water3A:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* .../";
            global.msg[2] = "\\E5* 一 个 衣 服 上 &  有 血 迹 的 人 .../";
            global.msg[3] = "\\E9* 可 能 会 把 衣 服 脱 下 来 ，&  对 吧 ？/";
            global.msg[4] = "\\E6* 我 是 说 ^1，&  为 了 避 免 被 抓 住 。/";
            scr_charface(5, 1);
            global.msg[6] = "* 你 的 意 思 是 ？/";
            scr_cloface(7, 6);
            global.msg[8] = "* 没 什 么 ^1。 我 只 是 ^1-&\\E5* 在 大 声 的 思 考 。/%%";
            if (global.flag[216] >= 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* ..^2.你 又 回 来 做 什 么 ？/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
            if (instance_exists(obj_npc_room))
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 看 起 来 你 找 到 了 一 个 &  很 好 的 藏 身 之 处 ！/";
                global.msg[2] = "\\E7* 这 里 玩 捉 迷 藏 很 不 错 。/";
                scr_charface(3, 3);
                global.msg[4] = "* 或 者 用 来 摆 脱 &  追 捕 你 的 人 。/%%";
                if (global.flag[67] == 1 || irememberyourneutrals >= 2)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 看 起 来 你 找 到 了 一 个 &  很 好 的 藏 身 之 处 ！/";
                    global.msg[2] = "\\EQ* 很 好 地 躲 避 了 &  你 屠 杀 行 为 的 后 果 ！ /%%";
                }
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 哦 ^1。 确 实 。/%%";
                    if (global.flag[67] == 1 || irememberyourneutrals >= 2)
                    {
                        scr_cloface(0, "Q");
                        global.msg[1] = "* .../%%";
                    }
                }
            }
        }
        break;
    case room_water4:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 我 有 种 不 祥 的 预 感 。/";
            scr_charface(2, 1);
            global.msg[3] = "* 这 一 点 ^1， 我 同 意 。/%%";
            if (global.plot == 106)
            {
                scr_cloface(0, "H");
                global.msg[1] = "* “ 太 棒 了 ” 这 个 词 &  用 的 真 不 错 。/";
                scr_charface(2, "H");
                global.msg[3] = "* 更 好 的 词 多 着 呢 ，&  只 是 他 不 会 用 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 你 还 在 等 什 么 呢 ，&  伙 计 ？/%%";
                }
            }
            if (instance_exists(obj_undyne1))
            {
                scr_cloface(0, 6);
                global.msg[1] = "* ...这 里 有 人 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* .../%%";
                }
                if (obj_undyne1.con == 6)
                {
                    scr_cloface(0, "H");
                    global.msg[1] = "* 可 怜 的 Papyrus .../";
                    scr_charface(2, "L");
                    global.msg[3] = "* ...尽 量 不 要 被 注 意 到 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* (小 心 点 ，别 发 出 声 音 。)/%%";
                    }
                    if (global.flag[67] == 1)
                    {
                        scr_cloface(0, 9);
                        global.msg[1] = "* 看 起 来 她 在 ..^2.&  等 某 个 人 。/%%";
                        if (global.flag[427] > 0)
                        {
                            scr_cloface(0, 9);
                            global.msg[1] = "* .../%%";
                        }
                    }
                }
                if (obj_undyne1.con == 39)
                {
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 9);
                        global.msg[1] = "* .../%%";
                    }
                    if (global.flag[19] < 10.25)
                    {
                        scr_cloface(0, "B");
                        global.msg[1] = "* 别 说 话 。/";
                        scr_charface(2, "N");
                        global.msg[3] = "* 这 也 太 近 了 。/%%";
                        if (global.flag[67] == 1)
                        {
                            scr_cloface(0, "E");
                            global.msg[1] = "* ...真 是 幸 运 。/%%";
                        }
                        global.flag[19] = 10.25;
                    }
                }
            }
        }
        break;
    case room_water_bridgepuzz1:
        if (clover == 1)
        {
            scr_cloface(0, "A");
            global.msg[1] = "* 当 四 颗 种 子 连 成 一 线 时 ，&  这 些 花 为 什 么 &  就 直 接 开 放 了 呢 ？/";
            scr_charface(2, "I");
            global.msg[3] = "* 这 确 实 是 .^1.^1.&\\EC* 一 个 好 问 题 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "E");
                global.msg[1] = "* 你 能 问 出 这 种 好 问 题 ^1， &  真 是 太 阳 从 西 边 出 来 了 。/%%";
            }
        }
        break;
    case room_water5:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 嘿 ^1， 这 确 实 是 个 &  不 错 的 谜 题 ^1， 对 吧 ？/";
            scr_charface(2, 1);
            global.msg[3] = "* 我 想 是 的 。/";
            global.msg[4] = "\\E0* 不 过 我 对 强 制 做 谜 题 &  的 决 定 表 示 质 疑 。/";
            scr_cloface(5, 6);
            global.msg[6] = "* 你 是 什 么 意 思 ？/";
            scr_charface(7, "I");
            global.msg[8] = "* 对 怪 物 们 来 说 ^1，&  这 是 唯 一 前 往 瀑 布 的 路 。/";
            global.msg[9] = "\\E0* 但 如 果 这 个 怪 物 &  没 有 手 呢 ？/";
            scr_cloface(10, 5);
            global.msg[11] = "* 就 比 如 我 们 刚 才 &  看 到 的 那 个 ？/";
            scr_charface(12, 8);
            global.msg[13] = "* 准 确 的 说 ^1。&* 他 们 将 无 法 .../";
            global.msg[14] = "\\E0* .../%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 怎 样 .^1.^1.&* 他 们 要 怎 样 &  才 能 通 过 这 里 ？/%%";
            }
        }
        break;
    case room_water5A:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 哦 ^1， 一 个 秘 密 房 间 ！/";
            scr_charface(2, 0);
            global.msg[3] = "* 你 是 说 一 条 死 路 ？/";
            scr_cloface(4, 2);
            global.msg[5] = "* 嗯 哼 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "D");
                global.msg[1] = "* 这 里 没 有 任 何 &  有 价 值 的 东 西 ^1。 &  这 就 是 条 死 路 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* 我 可 不 这 么 认 为 ^1！&* 比 如 ^1， 那 个 长 椅 下 面 &  是 个 什 么 ？/%%";
            }
            if (global.flag[104] == 1)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 你 知 道 那 东 西 &  已 经 在 地 上 放 很 久 了 ^1，&  对 吧 ？/";
                scr_cloface(2, 1);
                global.msg[3] = "* 所 以 呢 ^1？&* 又 不 是 不 能 吃 了 ！/";
                scr_charface(4, "G");
                global.msg[5] = "* .../%%";
            }
        }
        break;
    case room_water6:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 哇 .../";
            global.msg[2] = "* 这 地 方 太 美 了 ！/";
            scr_charface(3, 0);
            global.msg[4] = "* 你 真 这 么 觉 得 ？/";
            global.msg[5] = "\\E1* 怪 物 们 的 未 来 ^1，&  被 困 在 一 个 虚 假 的 &  天 空 之 下 .../";
            global.msg[6] = "* .../";
            global.msg[7] = "* 这 并 不 能 &  激 发 怪 物 们 的 希 望 。/";
            scr_cloface(8, 9);
            global.msg[9] = "* .../%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 嗯 .../";
                global.msg[2] = "\\E8* 我 们 该 许 个 愿 吗 ？/";
                scr_charface(3, 0);
                global.msg[4] = "* 你 要 许 什 么 愿 ？/";
                scr_cloface(5, 6);
                global.msg[6] = "* 如 果 你 想 要 什 么 东 西 ^1，&  许 个 愿 望 不 是 很 好 吗 ？/";
                global.msg[7] = "* 这 不 一 定 会 实 现 ^1，&  但 许 愿 总 没 有 坏 处 ！/";
                scr_charface(8, "H");
                global.msg[9] = "* 就 算 我 想 要 什 么 东 西 ^1， &  我 也 不 会 许 愿 。/";
                global.msg[10] = "\\E7* 我 会 采 取 行 动 。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 行 动 胜 于 言 语 ^1，&  哈 .../";
                global.msg[2] = "\\E0* 我 想 我 能 明 白 &  这 背 后 的 含 义 。/";
                scr_charface(3, 3);
                global.msg[4] = "* .^1.^1.&\\E7* 好 ^1， 非 常 好 。/%%";
                if (global.flag[249] < 30)
                {
                    global.msg[1] = "* 拜 托 ^1， 告 诉 我 ^1！&* 或 许 我 能 让 它 成 真 ！/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 那 我 希 望 你&  ^1别 再 说 话 了 。/";
                    scr_cloface(4, 1);
                    global.msg[5] = "* 无 事 发 生 ！/%%";
                }
            }
        }
        break;
    case room_water7:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 嘿 ^1， 墙 上 &  写 的 是 什 么 ？/";
            scr_charface(2, 7);
            global.msg[3] = "* 估 计 没 什 么 重 要 的 ^1。 &\\E0* 继 续 走 吧 。/";
            scr_cloface(4, 5);
            global.msg[5] = "* 你 确 定 吗 ^1？ 它 看 起 来 &  很 古 老 .../";
            global.msg[6] = "\\E7* 过 去 看 一 下 吧 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* ...所 以 ？/";
                global.msg[2] = "\\ED* 去 吧 ... 我 想 看 看 &  上 面 到 底 写 的 什 么 ！/";
                scr_charface(3, 7);
                global.msg[4] = "* 你 肯 定 读 不 懂 ^1。&  那 上 面 的 字 迹 &  你 很 难 看 的 清 。/%%";
            }
            if (obj_readable_room1.read > 0 && obj_readable_room5.read < 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 嘿 ^1， 剩 下 的 部 分 &  还 写 了 什 么 ？/%%";
            }
            if (obj_readable_room5.read > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 那 些 事 真 的 发 生 过 吗 ?/";
                global.msg[2] = "* 怪 物 吸 收 人 类 灵 魂 ？/";
                global.msg[3] = "\\E9* 那 一 定 不 是 真 的 。/";
                global.msg[4] = "\\E9* 怪 物 们 这 么 善 良 ，&  不 会 那 么 做 的 ！/";
                scr_charface(5, 5);
                global.msg[6] = "* 对 ^1， 但 人 类 对 “ 善 良 ”&  的 概 念 知 之 甚 少 。/%%";
                if (global.flag[365] == 1)
                {
                    global.msg[4] = "* 怪 物 的 灵 魂 是 由 &  爱 与 同 情 构 成 的 ^1， &  对 吗 ？/";
                    scr_charface(5, 5);
                    global.msg[6] = "* 而 且 人 类 已 经 证 明 了 &  人 类 灵 魂 无 需 这 些 东 西 &  就 能 存 在 。/%%";
                }
            }
            if (obj_mainchara.x > 600)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../";
                global.msg[2] = "\\E8* 很 抱 歉 ^1！&* 有 那 么 一 瞬 间&  我 觉 得 很 奇 怪 。/";
                global.msg[3] = "\\E6* 我 们 现 在 可 以 走 了 。/";
                if (irememberyourneutrals > 1 || global.flag[249] < 30)
                {
                    global.msg[3] = "\\E6* 我 们 现 在 可 以 走 了 。 /%%";
                }
                scr_charface(4, 1);
                global.msg[5] = "* 你 没 有 必 要 道 歉 。/";
                scr_cloface(6, 8);
                global.msg[7] = "* ...是 啊 ^1。 谢 谢 。/%%";
                if (global.flag[19] == 10.9)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 真 是 奇 怪 .../%%";
                }
                if (global.flag[19] == 11)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* .../%%";
                }
            }
        }
        if (clover == 0 && obj_mainchara.x > 600 && !ossafe_file_exists("system_information_963"))
        {
            scr_charface(0, "L");
            global.msg[1] = "* 哦 ^1, Clover.../";
            global.msg[2] = "\\EF* 走 吧 。/";
            global.msg[3] = "* 你 确 定 吗 ^1？ 它 看 起 来 &  很 古 老 .../%%";
        }
        break;
    case room_water8:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 我 有 种 不 祥 的 预 感 。/";
            global.msg[2] = "\\E6* 留 意 一 下 周 围 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../%%";
            }
            if (global.plot >= 110)
            {
                scr_cloface(0, "H");
                global.msg[1] = "* 她 太 邪 恶 了 。/";
                global.msg[2] = "\\E0* 你 成 功 逃 跑 了 ，&  干 得 好 。/";
                scr_charface(3, 8);
                global.msg[4] = "* 看 来 皇 家 守 卫 中&  还 是 有 一 位&  实 力 强 大 的 人 的 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 我 不 得 不 问 一 下 ^1，&  你 刚 才 怎 么 不 跑 起 来 ？/%%";
                }
            }
        }
        break;
    case room_water9:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 啊 ^1， 你 之 前 差 一 点 &  就 在 这 里 死 掉 了 ！/";
            scr_charface(2, 9);
            global.msg[2] = "* 真 是 快 乐 的 时 光 。/%%";
            if (global.plot < 111)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 你 不 能 再 离 她 这 么 近 了 。/";
                global.msg[2] = "\\E6* 至 少 也 是 为 了 我 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 5);
                    global.msg[1] = "* 很 幸 运 你 没 有 听 到 &  刺 耳 的 尖 叫 声 。/%%";
                }
            }
        }
        break;
    case room_water_savepoint1:
        if (clover == 1)
        {
            if (global.plot == 110)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 又 一 个 休 息 处 。/";
                scr_charface(2, "L");
                global.msg[3] = "* 被 追 了 那 么 久 ，&  我 觉 得 你 该 休 息 会 。/";
                global.msg[4] = "\\E8* 深 呼 吸 放 松 一 下 ^1。&  但 别 停 下 脚 步 。/";
                scr_cloface(5, 1);
                global.msg[6] = "* 是 个 合 理 的 建 议 ！/%%";
            }
            if (global.flag[447] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* ...啾 啾 ？/";
                scr_charface(2, "H");
                global.msg[3] = "* 之 前 不 好 笑 ^1，&  现 在 也 不 好 笑 。/%%";
                global.flag[447] = 2;
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 那 块 奶 酪 已 经 &  在 这 里 放 了 多 久 了 ？/";
                scr_charface(2, 7);
                global.msg[3] = "* 时 间 长 到 足 够 让 它 &  周 围 形 成 水 晶 。/";
                scr_cloface(4, 6);
                global.msg[5] = "* 那 ...并 不 能 真 正 &  回 答 这 个 问 题 。/%%";
            }
        }
        break;
    case room_water11:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 所 以 这 些 是 冰 川 石 .../";
            scr_charface(2, "C");
            global.msg[3] = "* 什 么 ？ 没 听 清 。/";
            scr_cloface(4, 1);
            global.msg[5] = "* 啊 哈 ^1！ \\E2我 知 道 一 些 &  你 不 知 道 的 东 西 ！/";
            scr_charface(6, 3);
            global.msg[7] = "* .../";
            scr_cloface(8, 1);
            global.msg[9] = "* 冰 川 石 是 冷 的 ！/";
            global.msg[10] = "\\E7* 它 们 就 是 雪 镇 和 &  瀑 布 产 生 的 原 因 。/";
            global.msg[11] = "\\E8* 总 之 就 是 很 冷 。/";
            global.msg[12] = "* 与 之 相 对 的 是 融 焦 石 .../";
            global.msg[13] = "\\E1* 它 们 让 环 境 更 热 ！/%%";
            if (irememberyourneutrals >= 2)
            {
                global.msg[7] = "* 我 们 真 的 有 时 间&  聊 这 些 吗 ？/%%";
            }
            if (global.flag[427] > 0 && obj_mainchara.pranked == 0)
            {
                scr_cloface(0, "M");
                global.msg[1] = scr_gettext("obj_chara_12");
                scr_charface(2, "D");
                global.msg[3] = "/";
                scr_cloface(4, "K");
                global.msg[5] = "/%%";
                if (irememberyourneutrals >= 2)
                {
                    scr_cloface(0, "C");
                    global.msg[1] = "* 为 什 么 我 要 &  跟 他 俩 较 劲 .../%%";
                }
            }
            if (obj_mainchara.pranked == 1)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 你 看 起 来 跟 个 小 丑 一 样 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* 他 说 你 说 的 没 错 ！/%%";
                if (irememberyourneutrals >= 1)
                {
                    scr_charface(0, 9);
                    global.msg[1] = "* 白 痴 。/";
                    scr_cloface(2, 7);
                    global.msg[3] = "* 这 是 你 自 找 的 。/%%";
                }
            }
        }
        break;
    case room_water_nicecream:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 看 上 去 这 里 是 个 山 洞 ？/";
            scr_charface(2, 0);
            global.msg[3] = "* 我 感 觉 好 像 &  本 来 该 有 人 在 这 里 的 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 真 是 奇 怪 。/%%";
            }
            if (instance_exists(obj_nicecreamguy))
            {
                scr_charface(0, 0);
                global.msg[1] = "* 真 是 个 糟 糕 的 销 售 员 。/";
                scr_cloface(2, 7);
                global.msg[3] = "* 我 曾 经 ... &  遇 到 过 一 个 比 他 更 好 的 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 也 许 在 山 洞 里 开 商 店 &  并 不 是 一 个 好 主 意 。/%%";
                }
            }
        }
        break;
    case room_water12:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 这 地 方 真 漂 亮 。/";
            scr_charface(2, 0);
            global.msg[3] = "* .../";
            scr_cloface(4, 6);
            global.msg[5] = "* .../";
            scr_charface(6, "E");
            global.msg[7] = "* 说 得 好 ， Clover 。/";
            scr_cloface(8, "D");
            global.msg[9] = "* 嘿 ~ .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 是 说 ... 这 里 并 不 &  寒 冷 ^1， 而 且 你 也 不 会 &  被 沙 子 呛 到 ， 所 以 .../";
                global.msg[2] = "\\E1* ...我 当 时 的 处 境 &  可 比 这 糟 多 了 ， 哈 哈 ！/";
                global.msg[3] = "\\E6* 我 真 希 望 我 活 着 &  的 时 候 能 在 这 里 。/%%";
            }
        }
        break;
    case room_water_shoe:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 一 条 死 路 ... ？/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
            if (global.flag[216] > 2)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
            if (global.flag[216] == 2)
            {
                scr_cloface(0, "H");
                global.msg[1] = "* 我 早 该 知 道 的 。/";
                global.msg[2] = "\\E9* 这 件 事 ...从 来 没 有 &  那 么 简 单 。/";
                scr_charface(3, 5);
                global.msg[4] = "* 有 时 候 ^1， 事 情 就 是 很 简 单 。/";
                global.msg[5] = "\\E7* 你 只 是 误 判 了 &  这 起 事 件 。/%%";
                if (irememberyourneutrals >= 1)
                {
                    global.msg[4] = "* 你 真 的 相 信 那 个 ？/";
                    global.msg[5] = "\\E7* 我 毫 不 怀 疑 他 会 &  为 所 欲 为 地 屠 杀 。/";
                    global.msg[6] = "* 然 后 再 以 “ 害 怕 ”&  为 借 口 躲 到 千 百 里 外 。/%%";
                }
                global.flag[216] = 3;
            }
            if (global.flag[216] == 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../";
                global.msg[2] = "\\E9* 他 曾 在 ...奔 跑 ？/";
                scr_charface(3, 7);
                global.msg[4] = "* 你 到 底 在 说 什 么 ？/";
                global.msg[5] = "\\E5* 说 清 楚 点 。/";
                scr_cloface(6, 9);
                global.msg[7] = "* .../";
                scr_charface(8, 3);
                global.msg[9] = "* 我 有 理 由 猜 测 &  一 个 人 类 曾 在 这 里 &  丢 失 了 性 命 。/";
                global.msg[10] = "\\E7* 那 就 是 你 的 &  结 论 ^1， 是 吗 ？/";
                global.msg[11] = "\\E1* 我 所 不 理 解 的 &  是 你 表 现 得 很 疑 惑 。/";
                global.msg[12] = "\\E0* 你 在 疑 惑 什 么 ^1，&  说 出 来 吧 。/";
                scr_cloface(13, 5);
                global.msg[14] = "* 他 曾 终 结 过 很 多 &  怪 物 的 生 命 。/";
                global.msg[15] = "\\E3* 所 以 我 此 前 ^1- 觉 得 &  他 很 邪 恶 ^1， 我 想 。/";
                global.msg[16] = "* 但 是 .^1.^1.&\\E4* 他 也 许 只 是 很 害 怕 &  才 这 样 做 的 。/%%";
                global.flag[216] = 2;
            }
        }
        break;
    case room_water_bird:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 真 可 爱 ！/";
            global.msg[2] = "\\E7* 也 好 强 壮 。/";
            scr_charface(3, 7);
            global.msg[4] = "* 就 没 人 想 到 过 &  在 这 里 建 一 座 桥 吗 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 那 只 鸟 干 这 么 重 的 活 &  却 得 不 到 应 得 的 报 酬 。/%%";
            }
        }
        break;
    case room_water_onionsan:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 你 回 来 看 河 马 了 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 你 根 本 就 没 用 心 。/%%";
            }
            if (global.flag[496] == 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 感 觉 这 个 房 间 里 &  还 有 其 他 人 。/";
                scr_charface(2, 3);
                global.msg[3] = "* .../%%";
            }
            if (global.flag[496] == 1)
            {
                scr_cloface(0, "G");
                global.msg[1] = "* .../";
                scr_charface(2, "C");
                global.msg[3] = "* 我 无 法 评 价 。/%%";
            }
            if (global.flag[496] == 2)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 瀑 布 确 实 有 &  很 特 别 的 地 方 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 我 同 意 ^2。&* 这 里 有 &  很 奇 特 的 气 氛 。/%%";
            }
            if (global.flag[496] == 3 || global.flag[496] == 4)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 啊 哦 ^1， 可 怜 的 家 伙 。/%%";
            }
            if (global.flag[496] == 5)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../";
                scr_charface(2, 0);
                global.msg[3] = "* .../";
                scr_cloface(4, 6);
                global.msg[5] = "* .../";
                global.msg[6] = "\\E7* 是 的 ^1。 那 肯 定 是 只 洋 葱 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* Onionsan 。/";
                    scr_cloface(2, "L");
                    global.msg[3] = "* Unyon 。/";
                    scr_charface(4, "D");
                    global.msg[5] = "* .../";
                    scr_cloface(6, "H");
                    global.msg[7] = "* Undyne 。/";
                    scr_charface(8, "D");
                    global.msg[9] = "* 那 就 不 是 同 一 个 人 。/%%";
                }
            }
        }
        break;
    case room_water14:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 好 安 静 啊 .../%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 留 意 一 下 周 围 。/%%";
            }
            if (global.plot >= 111)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 她 看 起 来 真 好 ！/";
                global.msg[2] = "\\E6* 她 就 住 在 这 附 近 吗 ？/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 0);
                    global.msg[1] = "* 顺 便 说 一 下 ^1， 那 是 &  两 只 独 立 的 怪 物 吗 ？/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 我 觉 得 是 。/";
                    scr_cloface(4, "A");
                    global.msg[5] = "* 另 一 只 怪 物 几 乎 没 动 过 .../%%";
                }
                if (global.flag[81] == 2)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 真 是 精 彩 的 演 出 ^1， 伙 计 ！/";
                    global.msg[2] = "\\E7* 那 吸 引 了 相 当 多 的 人 。/";
                    scr_charface(3, 9);
                    global.msg[4] = "* 可 惜 观 众 们 没 有&  留 下 来 要 签 名 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* Sans只 是 ^1.^1.&* 在 某 个 时 候 出 现 了 。/";
                        global.msg[2] = "\\E5* 我 发 誓 那 个 家 伙 可 以 传 送 。/";
                        scr_charface(3, "B");
                        global.msg[4] = "* 我 不 会 放 过 他 的 。/%%";
                        if (global.flag[67] == 1)
                        {
                            scr_cloface(0, 6);
                            global.msg[1] = "* 那 个 戴 兜 帽 的 人 .../";
                            global.msg[2] = "\\E9* ... /%%";
                        }
                    }
                }
                if (global.flag[81] == 1)
                {
                    scr_cloface(0, "J");
                    global.msg[1] = "* 她 只 是 躲 起 来 了 ！/";
                    global.msg[2] = "\\EE* 你 没 有 任 何 理 由 .../%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 7);
                        global.msg[1] = "* 现 在 不 是 闲 聊 的 时 候 。/";
                        global.msg[2] = "\\E3* 继 续 向 前 。/%%";
                    }
                }
            }
        }
        break;
    case room_water_piano:
        if (clover == 1)
        {
            global.msc = 3022;
        }
        break;
    case room_water_dogroom:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 刚 才 的 声 音 .^1.^1.&\\EI* 祝 你 好 运 。/%%";
            if (global.flag[268] > 2)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 还 挺 有 趣 的 ！/";
                scr_charface(2, "C");
                global.msg[3] = "* 多 么 ...^2独 特 的 出 场 啊 。/";
                scr_cloface(4, 6);
                global.msg[5] = "* 他 还 没 真 的 让 你 跳 舞 。 &  他 只 是 给 了 你 一 个 口 琴 。/";
                scr_charface(6, 0);
                global.msg[7] = "* 你 ...^2和 他 比 舞 了 ？/";
                scr_cloface(8, 1);
                global.msg[9] = "* 是 的 ^2！ 我 第 一 次 就 &  打 败 他 了 呢 ！/";
                global.msg[10] = "\\E6* ...我 想 是 的 。/%%";
                if (global.flag[268] == 4)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 跳 得 好^1， 搭 挡^1！&* 你 简 直 是 个 天 才 ！/";
                }
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 他 也 给 出 了 一 些 &  实 用 的 建 议 ^1， 不 是 吗 ？/";
                    global.msg[2] = "\\E7* 呵 ^1。 真 是 个 &  充 满 激 情 的 人 。/%%";
                }
            }
        }
        break;
    case room_water_statue:
        if (clover == 1)
        {
            if (global.flag[86] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 这 太 悲 伤 了 ^1，&  不 是 吗 ？/";
                scr_charface(2, 6);
                global.msg[3] = "* .../";
                scr_cloface(4, 6);
                global.msg[5] = "* ...不 是 吗 ？/%%";
            }
            else
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 嘿 ^1， 这 不 是 .../";
                global.msg[2] = "\\E5* 这 东 西 怎 么 会 在 这 里 ？/";
                scr_charface(3, 1);
                global.msg[4] = "* ...你 告 诉 我 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "J");
                    global.msg[1] = "* 我 要 踢 烂 干 这 件 事 &  的 人 。/";
                    scr_charface(2, "G");
                    global.msg[3] = "* 你 要 怎 么 这 样 做 呢 ？/";
                    scr_cloface(4, 9);
                    global.msg[5] = "* 我 会 .^1.^1.\\ED我 会 有 办 法 的 ！/%%";
                }
            }
        }
        break;
    case room_water_prewaterfall:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 一 个 雨 伞 ... 站 ？/";
            global.msg[2] = "\\E7* 确 实 很 有 用 ^2。&\\E6* 我 是 这 么 想 的 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 这 真 的 有 人 用 吗 ？/%%";
                if (global.flag[86] == 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 也 许 你 可 以 给 那 座 雕 像 &  也 来 一 把 ..？/";
                    if (global.kills > 0)
                    {
                        global.msg[1] = "* 也 许 你 可 以 给 那 座 雕 像 &  也 来 一 把 ..？/%%";
                    }
                    scr_charface(2, 1);
                    global.msg[3] = "* 确 实 .^1.^1.\\E7不 是 个 坏 主 意 。/%%";
                }
            }
        }
        break;
    case room_water_waterfall:
        if (clover == 1)
        {
            scr_charface(0, "C");
            global.msg[1] = "* 你 不 去 拿 把 伞 吗 ？/";
            global.msg[2] = "\\E1* 穿 着 湿 衣 服 前 进 .../";
            global.msg[3] = "\\EC* ... 你 可 比 我 勇 敢 多 了 。/%%";
            if (global.flag[85] == 1)
            {
                scr_cloface(0, "L");
                global.msg[1] = "* 啊 啊 啊 啊 ^1， 下 雨 了 .../";
                global.msg[2] = "* 踩 着 水 坑 ^1，&  无 忧 无 虑 .../";
                scr_charface(3, "C");
                global.msg[4] = "* 我 ...无 法 理 解 &  你 的 快 乐 。/";
                global.msg[5] = "\\ED* 我 讨 厌 头 发 被 淋 湿 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 有 什 么 问 题 吗 ？/";
                scr_charface(2, 0);
                global.msg[3] = "* 我 们 别 在 这 淋 雨 了 。/";
                global.msg[4] = "\\ED* 这 让 我 很 恼 火 。/";
                scr_cloface(5, 1);
                global.msg[6] = "* 嘶 ^1， 他 的 意 思 是 &  他 不 想 让 你 被 淋 湿 &  然 后 生 病 。/";
                scr_charface(7, "H");
                global.msg[8] = "* 我 不 是 这 意 思 。/%%";
                if (instance_exists(obj_mkid_actor))
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 你 和 别 人 在 一 起 的 时 候 ，&  和 我 们 说 话 有 点 不 礼 貌 了 。/%%";
                }
            }
        }
        break;
    case room_water_waterfall2:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 我 很 好 奇 那 朵 回 音 花 &  都 说 了 些 什 么 。/";
            scr_charface(2, 8);
            global.msg[3] = "* 我 们 可 能 永 远&  都 无 法 得 知 .../%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 除 非 能 有 人 带 你 飞 过 去 。/";
                scr_cloface(2, 0);
                global.msg[3] = "* 或 者 你 跳 过 去 。/";
                scr_charface(4, "H");
                global.msg[5] = "* 这 样 做 太 危 险 了 ，&  而 且 也 得 不 到 什 么 回 报 。/%%";
            }
            if (global.flag[427] == 2)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 在 地 下 世 界 ^1，&  没 人 会 跳 过 去 找 回 音 花 。/";
                global.msg[2] = "\\E7* 相 比 于 冒 着 生 命 危 险 &  走 在 正 路 上 还 是 更 安 全 .../";
                global.msg[3] = "\\EI* 仅 仅 是 出 于 你 的 好 奇 心 。/%%";
            }
            if (global.flag[427] > 2)
            {
                scr_charface(0, "D");
                global.msg[1] = "* ^2.^2.^2.什 么 ？/%%";
            }
        }
        break;
    case room_water_waterfall3:
        if (clover == 1)
        {
            scr_cloface(0, "B");
            global.msg[1] = "* 哇 .../%%";
            scr_charface(2, 1);
            global.msg[3] = "* 真 是 让 人 印 象 深 刻 &  的 景 色 。/";
            global.msg[4] = "* (即 使 过 了 &  这 么 长 时 间 ...)/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 1);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_water_waterfall4:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 真 是 一 次 愉 快 的 散 步 。/%%";
            scr_charface(2, 0);
            global.msg[3] = "* 也 是 条 不 错 的 死 路 。/%%";
            if (global.flag[427] > 0)
            {
                if (global.plot > 113)
                {
                    scr_cloface(0, "H");
                    global.msg[1] = "* 好 吧 ^1， 看 来 你 是 没 办 法&  再 上 去 了 。/%%";
                }
                else
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 嗯 .../%%";
                }
            }
            if (global.plot == 113)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 他 真 的 帮 了 我 们 很 多 。/";
                global.msg[2] = "\\E7* 我 希 望 他 能 去 见 到 &  Undyne 。/";
                scr_charface(3, 0);
                global.msg[4] = "* 是 的 ^1， 他 还 算 有 用 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 你 真 的 就 把 人 分 成 &  “ 有 用 ” 和 “ 没 用 ” &  两 类 吗 ？/";
                    scr_charface(2, "H");
                    global.msg[3] = "* 当 然 不 是 。/";
                    global.msg[4] = "\\E9* 我 把 他 们 分 为 &  “ 可 爱 的 白 痴 ” 和&  “ 可 恶 的 白 痴 ” 。/";
                    scr_cloface(5, 5);
                    global.msg[6] = "* 我 ...觉 得 这 更 好 点 ？/%%";
                    global.flag[246] = 1;
                }
            }
        }
        if (clover == 0 && global.flag[246] == 1 && !ossafe_file_exists("system_information_963"))
        {
            scr_charface(0, "F");
            global.msg[1] = "* Clover真 是 个&  讨 人 喜 欢 的 笨 蛋 ^1，&  不 是 吗 ？/";
            global.msg[2] = "\\E1* .../";
            global.msg[3] = "\\E2* .../%%";
        }
        break;
    case room_water_preundyne:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 他 真 的 帮 了 我 们 很 多 。/";
            global.msg[2] = "\\E7* 我 希 望 他 能 去 见 到 &  Undyne 。/";
            scr_charface(3, 0);
            global.msg[4] = "* 是 的 ^1， 他 还 算 有 用 。/%%";
            if (global.flag[86] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 仿 佛 还 能 听 到 &  那 个 八 音 盒 的 声 音 .../%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 你 真 的 就 把 人 分 成 &  “ 有 用 ” 和 “ 没 用 ” &  两 类 吗 ？/";
                scr_charface(2, "H");
                global.msg[3] = "* 当 然 不 是 。/";
                global.msg[4] = "\\E9* 我 把 他 们 分 为 &  “ 可 爱 的 白 痴 ” 和&  “ 可 恶 的 白 痴 ” 。/";
                scr_cloface(5, 5);
                global.msg[6] = "* 我 ...觉 得 这 更 好 点 ？/%%";
                if (global.flag[86] == 1)
                {
                    scr_cloface(0, 5);
                    global.msg[1] = "* 不 是 .^1.^1. 很 确 定&  那 为 什 么 有 可 能 。/%%";
                }
            }
        }
        break;
    case room_water_undynebridge:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 我 有 种 不 祥 的 预 感 。/";
            scr_charface(2, 0);
            global.msg[3] = "* 是 的 ^1。 我 也 有 。/";
            scr_cloface(4, 8);
            global.msg[5] = "* 你 这 次 会 跑 快 点 的 ^1， &  对 吧 ？/";
            global.msg[6] = "\\EP* 对 吗 ？/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, "P");
                global.msg[1] = "* ^1.^1.^1./";
                global.msg[2] = "\\EC* 你 的 微 笑 告 诉 了 我 &  我 需 要 知 道 的 一 切 .../%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, "C");
                global.msg[1] = "* 小 心 点 ^1，&  好 吗 ？/";
                scr_charface(2, 8);
                global.msg[3] = "* 我 都 不 用 看 他 的 脸 &  就 知 道 他 不 会 小 心 了 。/%%";
            }
        }
        break;
    case room_water_trashzone1:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 金 色 的 花 .../";
            global.msg[2] = "\\E6* 我 想 知 道 它 们 是 怎 么&  到 这 里 来 的 。/";
            scr_charface(3, 1);
            global.msg[4] = "* 你 和 我 想 的 一 样 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 它 们 和 遗 迹 里 的 那 些 一 样 ^1，&  对 吧 ？/";
                global.msg[2] = "\\E6* 真 奇 怪 .../%%";
            }
            if (global.flag[19] > 12)
            {
                scr_charface(0, "I");
                global.msg[1] = "* 你 说 你 ...&  认 识 这 个 地 方 ？/";
                scr_cloface(2, 5);
                global.msg[3] = "* 嗯 ^1， 说 不 上 是 认 识 ^1，&  但 是 .../";
                global.msg[4] = "\\E6* 不 知 为 何 ^1，&  我 感 觉 这 意 义 重 大 。/";
                scr_charface(5, 1);
                global.msg[6] = "* ...随 你 怎 么 说 吧 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "A");
                    global.msg[1] = "* 我 刚 才 大 声 说 出 那 些 话 &  的 时 候 ，确 实 感 觉 很 奇 怪 。/";
                    scr_charface(2, "C");
                    global.msg[3] = "* 我 不 会 再 去 &  想 这 种 事 了 。/";
                    global.msg[4] = "\\EH* 你 俩 在 一 起 就 必 有 &  奇 怪 的 事 情 发 生 。/";
                    global.msg[5] = "\\E0* .../";
                    global.msg[6] = "\\EE* 别 笑 了 。/%%";
                }
                if (irememberyourneutrals > 1)
                {
                    scr_charface(0, 7);
                    global.msg[1] = "* 你 是 怎 么 认 出&  这 个 地 方 的 ？/";
                    scr_cloface(2, 6);
                    global.msg[3] = "* 呃 ^1， 我 怎 么 知 道 ^1？ &  我 只 是 .^1.^1.这 么 觉 得 。/";
                    scr_charface(4, 0);
                    global.msg[5] = "* 当 然 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 0);
                        global.msg[1] = "* 走 吧 。/%%";
                        if (global.flag[249] > 50)
                        {
                            scr_charface(0, 8);
                            global.msg[1] = "* 也 许 是 因 为 你 觉 得&  这 里 的 垃 圾 堆&  有 家 的 感 觉 吧 。/";
                            scr_cloface(2, 2);
                            global.msg[3] = "* 哈 哈 ^1！哎 哟 ！/%%";
                        }
                    }
                }
            }
            if (global.flag[493] >= 10)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 我 无 话 可 说 了 。/";
                global.msg[2] = "* 这 是 迄 今 为 止 发 生 在 &  你 身 上 最 不 可 思 议 &  的 事 情 。/";
                scr_cloface(3, 5);
                global.msg[4] = "* ..^2.是 吗 ？ 我 觉 得&  更 奇 怪 的 事 情 &  早 就 发 生 过 了 。/";
                scr_charface(5, "C");
                global.msg[6] = "* 我 想 ^1， 但 至 少 &  这 更 好 解 释 了 。/";
                global.msg[7] = "* 我 可 以 给 你 示 范 ^1，&  但 我 需 要 12 个 文 本 框 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 走 吧 。/%%";
                    if (global.flag[249] > 90)
                    {
                        scr_charface(0, "D");
                        global.msg[1] = "* 谁 会 想 着 在&  这 种 地 方 约 会 ？？/";
                        scr_cloface(2, 7);
                        global.msg[3] = "* 去 哪 里 ^1-&\\E6* 我 的 意 思 是 如 果 你 在 ^1-&\\E5* .../";
                        global.msg[4] = "\\EA* 人 们 一 般 都 会&  去 哪 里 约 会 呢 ？/";
                        scr_charface(5, "G");
                        global.msg[6] = "* 我 也 不 知 道 ^1， &  餐 馆 之 类 的 地 方 ^1？&* 总 之 别 是 这 里 ？/%%";
                        if (global.flag[427] == 2)
                        {
                            scr_cloface(0, 6);
                            global.msg[1] = "* ...Frisk^2? 你 为 什 么&  要 那 样 看 着 我 ？/";
                            global.msg[2] = "\\E9* ..^1.你 说 “ 我 知 道 你 是 谁 ”&  是 什 么 意 思 ？？？/%%";
                        }
                        if (global.flag[427] > 2)
                        {
                            scr_cloface(0, 9);
                            global.msg[1] = "* ???/%%";
                        }
                    }
                }
            }
        }
        break;
    case room_water_trashsavepoint:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 这 里 有 个 存 档 点 ^1。 真 方 便 。/";
            scr_cloface(2, "K");
            global.msg[3] = "\\Tf* 我 来 帮 你 存 档 吧 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "G");
                global.msg[1] = "* 我 不 喜 欢 你 做 出 &  那 种 表 情 。/";
                scr_cloface(2, "B");
                global.msg[3] = "* 你 讨 厌 我 的 表 情 ？^1？&" + scr_gettext("obj_chara_0") + "^1, 我 好 伤 心 ！/";
                global.msg[4] = "\\EN* 这 个 怎 么 样 ？/";
                global.msg[5] = "\\EL* 或 者 这 个 ？/";
                global.msg[6] = "\\EI* 你 真 的 忍 心 讨 厌 我 吗 ？/";
                scr_charface(7, "I");
                global.msg[8] = "* ^1.^1.^1./";
                if (global.flag[249] > 40)
                {
                    global.msg[9] = "\\EE* 是 的 。 /";
                    global.msg[10] = "\\EA* 但 我 要 让 你 知 道 ^1，&  每 当 我 做 事 时 ^1，&  我 都 会 全 力 以 赴 。/";
                    global.msg[11] = "* 以 最 好 的 效 率 。/";
                    global.msg[12] = "\\E9* 所 以 从 现 在 开 始 ^1， &  我 们 就 是 死 敌 。/";
                    scr_cloface(13, 2);
                    global.msg[14] = "* 专 业 的 恨 ！/%%";
                    if (global.flag[427] > 1)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* ^1.^1.^1.你 在 开 玩 笑 ^1， 对 吗 -%";
                        scr_charface(2, "H");
                        global.msg[3] = "* 是 的 ， 那 是 个 玩 笑 。/%%";
                    }
                }
                else
                {
                    global.msg[9] = "\\EH* 不 值 得 费 力 。 /";
                    scr_cloface(10, "H");
                    global.msg[11] = "* 该 死 。/%%";
                }
                if (irememberyourneutrals > 1)
                {
                    if (global.flag[249] > 40)
                    {
                        scr_charface(4, "H");
                        global.msg[5] = "* 真 的 让 人 难 过 ^1。&* 你 一 定 很 伤 心 。/";
                        scr_cloface(6, 4);
                        global.msg[7] = "* 我 担 心 我 可 能 永 远&  都 无 法 恢 复 。/%%";
                    }
                    else
                    {
                        scr_charface(4, "D");
                        global.msg[5] = "* 那 是 完 全&  不 同 的 句 子 。/%%";
                    }
                }
            }
        }
        break;
    case room_water_trashzone2:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 嘿 ^1， 这 里 有 很 多&  来 自 地 面 上 的 东 西 。/";
            global.msg[2] = "\\EA* 那 些 垃 圾 &  是 怎 么 到 这 里 的 ？/";
            scr_charface(3, 3);
            global.msg[4] = "* 我 猜 这 些 水&  连 接 着 地 表 。/";
            global.msg[5] = "\\E7* 看 上 去 人 类 觉 得 &  把 垃 圾 扔 进 垃 圾 桶 &  还 是 太 难 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 至 少 怪 物 们 还 能 &  回 收 利 用 这 其 中 的 &  一 部 分 。/%%";
            }
            if (global.plot > 115)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 如 果 Napstablook &  没 救 下 你 .../";
                global.msg[2] = "\\E9* 你 是 不 是 会 被 &  永 远 困 在 这 里 ？/";
                scr_charface(3, 3);
                global.msg[4] = "* 这 在 技 术 上 &  是 有 可 能 的 。/";
                global.msg[5] = "\\E9* 但 这 力 量 并 没 有 强 到 &  能 够 将 我 们 永 远 困 住 。 /%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 你 居 然 也 会 有 &  乐 观 的 态 度 ！/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 态 度 ^2？ \\E9这 是 事 实 。/";
                    global.msg[4] = "\\EH* 你 也 没 意 识 到 我 &  做 出 的 贡 献 。/";
                    scr_cloface(5, "B");
                    global.msg[6] = "* 你 有 贡 献 吗 ？！？/%%";
                }
            }
        }
        break;
    case room_water_friendlyhub:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 这 里 看 上 去 像 是 &  一 个 休 息 片 刻 的 好 地 方 。/";
            scr_charface(2, 1);
            global.msg[3] = "* 你 可 以 在 这 里 &  补 充 一 些 资 源 。/";
            scr_cloface(4, 8);
            global.msg[5] = "* 别 去 打 扰 &  Napstablook ^1， 好 吗 ？/%%";
            if (global.flag[36] > 0)
            {
                scr_cloface(4, "A");
                global.msg[5] = "* 也 许 可 以 去 和 Napstablook &  打 个 招 呼 ？/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 很 奇 怪 ，我 们 到 现 在 &  才 在 瀑 布 见 到 过 &  这 几 个 房 子 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 你 是 不 是 忘 了 我 们 才 &  见 过 地 下 世 界 &  的 很 小 一 部 分 。/";
                global.msg[4] = "\\EH* 瀑 布 里 的 居 民 &  更 倾 向 于 隐 居 。/";
                global.msg[5] = "\\E0* 他 们 可 能 都 住 在 &  人 迹 罕 至 的 地 方 。/%%";
            }
        }
        break;
    case room_water_undyneyard:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 所 以 这 就 是 Undyne &  的 房 子 .../";
            global.msg[2] = "* 这 ...适 合 她 吗 ？/";
            scr_charface(3, "C");
            global.msg[4] = "* 你 ..^1. 可 以 这 么 说 。/%%";
            if (global.plot < 121)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 鱼 房 子 ？/";
                global.msg[2] = "\\E6* 鱼 房 子 。/";
                scr_charface(3, 0);
                global.msg[4] = "* 鱼 房 子 。/%%";
            }
            if (global.flag[350] == 1)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* (...你 为 什 么 要 ...)/%%";
            }
            if (global.flag[350] == 2)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* 我 希 望 她 没 事 ^1。&* 看 来 高 温 确 实 会 ^1， &  对 她 有 伤 害 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 看 起 来 她 不 在 家 。/%%";
                if (instance_exists(obj_undynedate_outside))
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 这 绝 对 不 可 能 出 错 。/%%";
                }
                if (global.plot < 121)
                {
                    scr_cloface(0, "M");
                    global.msg[1] = "* 你 还 想 问 什 么 ^1， &  我 们 已 经 说 的 够 清 楚 了 。/%%";
                }
                if (global.flag[350] == 1)
                {
                    scr_cloface(0, 3);
                    global.msg[1] = "* (...)/%%";
                }
                if (global.flag[350] == 2)
                {
                    scr_charface(0, "L");
                    global.msg[1] = "* 不 管 怎 样 ^1， &  这 里 没 什 么 事 可 做 了 。/%%";
                }
            }
            if (global.flag[389] >= 2)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 进 展 的 还 挺 顺 利 的 ！/";
                scr_charface(2, 9);
                global.msg[3] = "* 我 同 意 。/%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* Undyne 现 在 是 &  我 们 的 朋 友 了 ^1， 对 吧 ？/";
                    scr_charface(2, 9);
                    global.msg[3] = "* ^1.^1.^1./";
                    scr_cloface(4, "P");
                    global.msg[5] = "* ^1.^1.^1./%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_cloface(0, "C");
                    global.msg[1] = "* 你 看 到 她 的 房 子 被 烧 了&  很 高 兴 ^1， 是 吗 ？/";
                    scr_charface(2, "A");
                    global.msg[3] = "* 如 果 我 说 我 是 呢 ？/";
                    scr_cloface(4, 9);
                    global.msg[5] = "* 那 我 .../";
                    global.msg[6] = "\\EH* 不 得 不 承 认 ^1，&  那 确 实 挺 有 趣 的 。/%%";
                }
            }
        }
        break;
    case room_water_blookyard:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 哇 哦 ^1， 这 些 房 子 看 起 来 &  真 ..^2. \\E6独 特 。 /";
            scr_charface(2, "J");
            global.msg[3] = "* ...独 特 ！ ^2？ 他 们 是 艺 术 品 ！ /";
            scr_cloface(4, 0);
            global.msg[5] = "* /";
            global.msg[6] = "\\E6* /";
            global.msg[7] = "\\E5* /";
            global.msg[8] = "\\EG* 什 么 。/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 我 ^1- 我 真 的 不 知 道 &  那 是 不 是 讽 刺 。 /";
                scr_charface(2, "D");
                global.msg[3] = "* 为 什 么 会 是 讽 刺 ？ /";
                global.msg[4] = "\\EL* 你 看 不 出 来 吗 ？&  这 些 可 是 质 量 顶 尖&   的 建 筑 。/";
                scr_cloface(5, 5);
                global.msg[6] = "* 我 ^2- 我 不 -/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, "G");
                global.msg[1] = "* (他 到 底 是 不 是 认 真 的 ？ &  我 真 的 分 不 出 来 。 )/%%";
            }
        }
        if (clover == 0)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 哇 哦 ^1， 这 些 房 子 真 糟 糕 。 /";
            global.msg[2] = "\\EE* ..^2.你 为 什 么 要 那 样 看 着 我 ？/%%";
        }
        break;
    case room_water_blookhouse:
        if (clover == 1)
        {
            if (global.flag[273] == 1)
            {
                if (irememberyourneutrals < 2)
                {
                    scr_cloface(0, "A");
                    global.msg[1] = "* 所 以 呢 ？/";
                    scr_charface(2, "H");
                    global.msg[3] = "* 嗯 ？/";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 你 说 过 你 会 告 诉 我 &  为 什 么 他 看 不 见 我 们 。/";
                    scr_charface(6, "C");
                    global.msg[7] = "* 你 还 记 着 呢 ？/";
                    global.msg[8] = "\\E8* 你 记 性 真 好 。/";
                    scr_cloface(9, "D");
                    global.msg[10] = "* 你 说 的 这 句 话&  并 没 有 回 答 我 的 问 题 。/";
                    scr_charface(11, 7);
                    global.msg[12] = "* 对 ^1， 对 。^1/";
                    global.msg[13] = "\\EH* 这 样 想 ：/";
                    global.msg[14] = "* Napstablook 并 不 是 一 只&  传 统 意 义 上 的 鬼 魂 。/";
                    global.msg[15] = "\\E0* 他 从 未 “ 死 去 ” 。/";
                    global.msg[16] = "* 他 只 是 一 种&  没 有 肉 身 的 怪 物 。/";
                    global.msg[17] = "* 我 们 既 没 有 灵 魂&  也 没 有 肉 体 。/";
                    global.msg[18] = "\\EA* 这 就 是 为 什 么&  他 看 不 见 我 们 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 7);
                        global.msg[1] = "* 有 趣 ^1， 有 趣 。/";
                        scr_cloface(2, "H");
                        global.msg[3] = "* 是 的 ^1， 是 的 。/";
                        global.msg[4] = "* 快 点 走 吧 ^1，&  我 们 已 经 浪 费 了&  太 多 时 间 了 。/%%";
                        if (global.flag[249] > 40)
                        {
                            scr_cloface(0, 1);
                            global.msg[1] = "* 你 应 该 多 笑 一 笑 ^1！&  微 笑 的 你 更 美 丽 。/";
                            scr_charface(2, "G");
                            global.msg[3] = "* 你 根 本 就 没 听 我 的 话 ^1， &  不 是 吗 。/";
                            scr_cloface(4, 1);
                            global.msg[5] = "* 我 在 你 讲 一 半 &  的 时 候 走 神 了 ！/";
                            scr_charface(6, "D");
                            global.msg[7] = "* 唉 .../%%";
                        }
                    }
                }
                else
                {
                    scr_cloface(0, "A");
                    global.msg[1] = "* .../";
                    scr_charface(2, 0);
                    global.msg[3] = "* 什 么 ？/";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 感 — — 觉 我 好 像 &  忘 了 什 么 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* 可 能 是&  不 重 要 的 。/%%";
                    }
                }
            }
            else
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 看 来 这 个 房 子 里 &  有 着 够 一 个 幽 灵 生 活 的 &  所 有 基 本 物 资 。/";
                scr_charface(2, 7);
                global.msg[3] = "* 你 想 待 多 久 就 待 多 久 ^1。&\\E9* 我 不 想 再 听 到 &  某 人 一 直 废 话 了。/";
                scr_cloface(4, 9);
                global.msg[5] = "* 不 是 ^1， 我 .../";
                global.msg[6] = "\\E3* 我 不 想 再 一 个 人 呆 着 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* .../%%";
                }
                if (irememberyourneutrals > 2)
                {
                    scr_charface(2, 7);
                    global.msg[3] = "* 求 你 留 在 这 里 ^1。&* 这 会 让 你 的 旅 途&  轻 松 些 。/";
                    scr_cloface(4, "E");
                    global.msg[5] = "* 你 能 不 能 停 下 ^2？&* 我 已 经 受 够 了 。/%%";
                    if (global.flag[249] > 60)
                    {
                        scr_cloface(4, "D");
                        global.msg[5] = "* 对 的 ， 对 的 。/%%";
                    }
                }
            }
        }
        break;
    case room_water_hapstablook:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* ..^1.为 什 么 那 把 钥 匙 &  会 在 垃 圾 桶 里 ？/";
            scr_charface(2, 1);
            global.msg[3] = "* 住 在 这 里 的 人 可 能 &  就 没 打 算 回 来 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 1);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_water_farm:
        if (clover == 1)
        {
            if (global.flag[45] == 5)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 呵 ^1， Toriel 一 定 会 &  喜 欢 这 里 的 。/";
                scr_charface(2, 8);
                global.msg[3] = "* ...她 确 实 会 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* .../%%";
                }
            }
            if (global.flag[45] == 4)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 呵 ^1， Toriel 一 定 会 &  喜 欢 这 里 的 。/";
                global.msg[2] = "\\E6* .../";
                global.msg[3] = "\\E9* .../";
                scr_charface(4, "L");
                global.msg[5] = "* ..^2.是 的 ^2。&* 她 确 实 会 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_water_prebird:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 抓 虫 子 ？/";
            scr_charface(2, "I");
            global.msg[3] = "* 我 想 ..^2. 这 并 没 有 &  那 么 奇 怪 。/";
            scr_cloface(4, 5);
            global.msg[5] = "* 嗯 。/";
            global.msg[6] = "\\E0* 你 是 想 沿 这 条 路 &  继 续 走 吗 ？/";
            scr_charface(7, 0);
            global.msg[8] = "* 往 北 的 那 条 路 确 实 &  看 上 去 更 像 是 前 进 的 路 。/";
            scr_cloface(9, 7);
            global.msg[10] = "* 我 明 白 了 ^2！&* 那 你 就 应 该 继 续 走 这 条 路 。/";
            scr_charface(11, "G");
            global.msg[12] = "* 噢 。 /%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "G");
                global.msg[1] = "* 你 就 是 那 种 人 中 的 一 个 。/";
                global.msg[2] = "* 就 喜 欢 让 别 人 &  走 上 错 误 的 路 。/";
                scr_cloface(3, 7);
                global.msg[4] = "* 就 算 我 真 是 又 怎 么 样 ？/";
                scr_charface(5, 7);
                global.msg[6] = "* 在 这 里 浪 费 时 间 &  可 不 是 理 想 的 结 果 。/";
                scr_cloface(7, 6);
                global.msg[8] = "* 但 如 果 你 坚 持 走 正 路 ， &  你 会 错 过 很 多 东 西 的 ！/";
                global.msg[9] = "\\EI* 这 是 关 乎 整 趟 旅 程 ^1，&  而 不 是 ^1-%";
                scr_charface(10, "H");
                global.msg[11] = "* 不 ^3。 这 些 全 都 不 重 要 。/%%";
            }
        }
        break;
    case room_water_shop:
        if (clover == 1)
        {
            if (global.flag[19] > 14)
            {
                if (global.flag[359] == 1)
                {
                    if (irememberyourneutrals < 2)
                    {
                        scr_cloface(0, 8);
                        global.msg[1] = "* 很 抱 歉 我 没 有 早 点 &  询 问 你 的 名 字 ^1，&  Frisk 。/";
                        global.msg[2] = "* 我 完 全 忘 了 这 个 了 。/";
                        scr_charface(3, 0);
                        global.msg[4] = "* 我 也 应 该 为 此 道 歉 。/";
                        global.msg[5] = "\\EE* 我 总 是 被 某 人 &  毫 无 意 义 的 &  胡 言 乱 语 分 心 。/%%";
                        if (global.flag[477] == 2)
                        {
                            global.msg[5] = "\\EH* 我 一 直 在 被 分 心 。/";
                            global.msg[6] = "\\EE* 都 是 你 的 错 ^1，&  Clover。/";
                            scr_cloface(7, "G");
                            global.msg[8] = "* adsjlkanhsdkjxbz/%%";
                            global.flag[477] = 3;
                        }
                        if (global.flag[427] > 0)
                        {
                            scr_cloface(0, 1);
                            global.msg[1] = "* 继 续 前 进 吧 ^1， Frisk ！/%%";
                        }
                    }
                    else if (irememberyourneutrals == 2)
                    {
                        scr_cloface(0, 8);
                        global.msg[1] = "* 友 善 一 点 也 无 妨 ^1， &  Frisk./";
                        global.msg[2] = "\\E1* 至 少 这 是 交 朋 友 的 好 方 式 ！/";
                        global.msg[3] = "\\E7* 哈 哈 .../";
                        global.msg[4] = "\\E6* .../%%";
                        if (global.flag[427] > 0)
                        {
                            scr_cloface(0, 5);
                            global.msg[1] = "* ........../%%";
                        }
                    }
                    else if (irememberyourneutrals > 2)
                    {
                        scr_cloface(0, 9);
                        global.msg[1] = "* 说 真 的 ^1， Frisk。/";
                        global.msg[2] = "* 你 不 能 就 这 样 玩 弄&  别 人 的 生 命 。/";
                        global.msg[3] = "* 我 不 在 乎 你 能 不 能&  回 溯 或 者 什 么 的 。/";
                        global.msg[4] = "* 这 么 做 就 是 不 对 的 。/%%";
                        if (global.flag[427] > 0)
                        {
                            scr_cloface(0, 6);
                            global.msg[1] = "* .../%%";
                        }
                    }
                }
                if (global.flag[359] == 2)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 等 会 ^1， 你 是 怎 么 知 道 &  他 的 名 字 的 ？/";
                    scr_charface(2, 7);
                    global.msg[3] = "* 你 说 谁 知 道 ？/";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 你 啊 ^1。&* 你 不 是 才 说 的 吗 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, "E");
                        global.msg[1] = "* 好 吧 ^1。&* 留 着 你 的 秘 密 吧 。/%%";
                    }
                }
            }
            if (global.flag[71] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* Gerson^1， 是 吗 ？/";
                global.msg[2] = "\\E7* 我 记 得 他 。/";
                global.msg[3] = "\\E6* 不 过 有 点 难 过 的 是 ^1，&  我 只 见 过 他 一 次 。/%%";
            }
        }
        break;
    case room_water_dock:
        if (clover == 1)
        {
            scr_cloface(0, "A");
            global.msg[1] = "* 嗯 .../";
            global.msg[2] = "\\E0* 这 里 是 一 个 码 头 吗 ？/";
            scr_charface(3, "I");
            global.msg[4] = "* 码 头 ^2？&* 确 实 ^1， 很 有 可 能 &  就 是 这 样 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 我 想 知 道 这 到 底 是 &  用 来 干 什 么 的 。/%%";
            }
            if (instance_exists(obj_dogboat_thing))
            {
                scr_charface(0, 0);
                global.msg[1] = "* 顺 便 说 一 下 ^1，&  那 东 西 违 背 了 所 有 的 &  物 理 规 律 。/";
                scr_cloface(2, "A");
                global.msg[3] = "* 什 么 东 西 ？/";
                scr_charface(4, 7);
                global.msg[5] = "* 那 个 像 狗 一 样 的 ..^1. &  船 ..^1./";
                scr_cloface(6, 6);
                global.msg[7] = "* 哦 。/";
                global.msg[8] = "\\E7* 嗯 ^1， 我 其 实 没 怎 么 &  感 到 奇 怪 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 0);
                    global.msg[1] = "* 物 理 学 ， 分 裂 学 ^1，&  就 像 我 说 过 的 。/";
                    scr_charface(2, "G");
                    global.msg[3] = "* 你 根 本 没 说 过 。/";
                    global.msg[4] = "* 你 以 前 从 来 没 &  按 那 个 顺 序 说 出 过 &  这 些 词 。/%%";
                }
            }
        }
        break;
    case room_water15:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 瀑 布 确 实 写 满 了 历 史 ^1， &  不 是 吗 ？/";
            scr_charface(2, 8);
            global.msg[3] = "* 我 同 意 ^1， 这 相 当 不 错 。/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 不 过 ^1， 我 在 想 .../";
                global.msg[2] = "\\EI* 你 都 读 完 这 些 了 吗 ？/";
                global.msg[3] = "* 你 知 道 怎 么 去 阅 读 吧 ^1， &  Frisk ？/";
                scr_charface(4, "H");
                global.msg[5] = "* Clover^1， 别 搞 。/";
                global.msg[6] = "\\EE* 阅 读 太 无 聊 了 ^1，&  不 是 吗 ， Frisk ？/";
                global.msg[7] = "\\E9* 嘿 ^1， 我 有 个 想 法 。/";
                global.msg[8] = "* 你 应 该 装 作 已 经 读 完 了 ^1，&  然 后 走 到 别 人 面 前 .../";
                global.msg[9] = "\\EE* 然 后 直 接 撒 谎 来 &  编 造 上 面 写 的 是 什 么 。/";
                scr_cloface(10, 1);
                global.msg[11] = "* 我 喜 欢 这 个 想 法 。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 是 说 ^1， 比 你 聪 明 的 人 &  肯 定 早 都 读 过 了 。/";
                global.msg[2] = "* 然 后 他 们 会 告 诉 你 ，&  你 就 是 在 胡 说 八 道 。/";
                global.msg[3] = "\\E2* 别 到 那 时 候 才 想 起 来 &  要 加 倍 努 力 学 习 ，&  FRISK 。/";
                scr_charface(4, 8);
                global.msg[5] = "* 哈 哈 哈 ^2-&\\E0* 等 等 。/";
                global.msg[6] = "\\ED* 我 其 实 很 讨 厌 &  成 为 那 些 胡 编 乱 造 的 人 。/";
                scr_cloface(7, "H");
                global.msg[8] = "* 没 错 ^2。&* 那 会 很 讨 人 厌 的 。/";
                global.msg[9] = "\\E0* 呃 ^1， 没 关 系 的 。/";
                global.msg[9] = "\\EI* 做 那 种 事 情 的 人 .../";
                global.msg[10] = "* 甚 至 都 不 会 &  看 到 这 段 对 话 。/%%";
            }
        }
        break;
    case room_water16:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 神 奇 蘑 菇 谜 题 ！&      (tm)/";
            scr_charface(2, 8);
            global.msg[3] = "* “ 看 起 来 ^1， 确 实 是 个 &  像 样 的 谜 题 。 ”/%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 你 也 可 以 摸 黑 走 过 去 。/";
                global.msg[2] = "\\E8* 看 看 那 个 ^1， 这 可 比 &  Papyrus 的 那 个 隐 形 迷 宫 &  好 多 了 。/";
                global.msg[3] = "\\EE* 那 其 实 只 是 条 &  你 看 不 见 的 小 路 。/";
                scr_cloface(4, "D");
                global.msg[5] = "* 好 吧 ^1， 那 都 是 &  75 个 房 间 之 前 的 事 了 。/";
                global.msg[6] = "* 别 再 提 那 个 了 。/";
                scr_charface(7, "I");
                global.msg[8] = "* 让 我 思 考 一 下 。/";
                global.msg[9] = "* ^9.^9.^9.^9.^9.^9.^6./";
                global.msg[10] = "\\EH* 想 不 出 来 。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, "P");
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_water_temvillage:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 真 ... 可 爱 ？/";
            scr_charface(2, "D");
            global.msg[3] = "* 才 不 是 呢 。/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 得 了 吧 ^1， 他 们 真 的 &  太 可 爱 了 ！/";
                scr_charface(2, "C");
                global.msg[3] = "* 他 们 让 我 心 里 发 毛 。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 哦 ^1， 他 们 还 开 了 家 商 店 。/";
                global.msg[2] = "\\EA* 你 觉 得 你 可 以 在 这 里 &  卖 东 西 吗 ？/%%";
            }
        }
        break;
    case room_water17:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 魔 法 水 晶 谜 题 ！&      (专 利 申 请 中 )/";
            scr_charface(2, 0);
            global.msg[3] = "* “ 这 个 其 实 有 点 烦 人 了 。 ”/%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 我 对 此 的 评 价 &  就 这 么 多 了 。/%%";
            }
            if (global.flag[427] == 2)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 不 ^1， 我 是 认 真 的 。/%%";
            }
            if (global.flag[427] == 3)
            {
                scr_charface(0, "D");
                global.msg[1] = "* Frisk 。/%%";
            }
            if (global.flag[427] > 3)
            {
                scr_charface(0, "D");
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_water18:
        if (clover == 1)
        {
            scr_cloface(0, 8);
            global.msg[1] = "* 你 确 定 这 位 红 色 灵 魂 &  不 是 幸 运 的 化 身 ？/";
            global.msg[2] = "* 因 为 哇 ^1，&  你 的 好 运 也 太 多 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 嗯 ^1， 想 必 他 随 身 携 带 着 &  一 个 幸 运 符 。/";
                scr_cloface(2, "A");
                global.msg[3] = "* 是 吗 ？/";
                scr_charface(4, "G");
                global.msg[5] = "* ..^2.Clover 。/";
                scr_cloface(6, "H");
                global.msg[7] = "* 什 ^1-%";
                global.msg[8] = "\\E0* 哦 哦 哦 哦 哦 哦 哦 哦 哦 哦 哦 哦 &  哦 哦 哦 哦 哦 哦 哦 哦 哦 哦 哦 哦&  哦 哦 哦 哦 哦 哦 哦 哦 哦 哦 哦 哦 /";
                global.msg[9] = "\\E1* 真 好 笑 。/%%";
            }
            if (global.plot < 118)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 我 又 有 了 那 种 感 觉 。/";
                scr_charface(2, 3);
                global.msg[3] = "* 当 心 。/%%";
            }
        }
        break;
    case room_water19:
        if (clover == 1)
        {
            scr_cloface(0, 8);
            global.msg[1] = "* 愿 望 ^1， 好 多 愿 望 .../";
            global.msg[2] = "* 总 有 一 天 ^1， 我 很 确 定&  所 有 这 些 愿 望 都 能 成 真 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* Frisk ^2！ 告 诉 我 你 的 愿 望 ！/";
                global.msg[2] = "\\E6* .../";
                global.msg[3] = "\\EP* “ Jerry 的 彩 陶 ？ ”/";
                scr_charface(4, "A");
                global.msg[5] = "* 终 于 ^1， 有 个 我 可 以 &  支 持 的 东 西 了 ！/%%";
            }
        }
        break;
    case room_water20:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* .../%%";
            if (instance_exists(obj_monsterkidtrigger7))
            {
                if (obj_monsterkidtrigger7.con > 34)
                {
                    scr_cloface(0, "B");
                    global.msg[1] = "* 你 在 做 什 么 ？？&* 帮 助 他 ？？/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, "D");
                        global.msg[1] = "* ???/%%";
                    }
                }
            }
            if (global.plot == 120)
            {
                if (global.flag[98] == 1)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* 看 看 你 ^1，&  大 英 雄 。/";
                    scr_cloface(2, 1);
                    global.msg[3] = "* 你 做 得 真 好 ！/%%";
                }
                if (global.flag[98] == 2)
                {
                    scr_cloface(0, "F");
                    global.msg[1] = "* .../%%";
                }
                if (global.flag[98] == 2)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 你 这 么 做 不 太 好 。/";
                    global.msg[2] = "\\E6* 可 能 会 很 糟 糕 。/%%";
                }
                if (global.flag[427] > 0)
                {
                    if (global.flag[98] == 1)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* 你 能 和 她 一 样 英 勇 吗 ？/%%";
                    }
                    if (global.flag[98] == 2)
                    {
                        scr_charface(0, 1);
                        global.msg[1] = "* .../%%";
                    }
                    if (global.flag[98] == 2)
                    {
                        scr_charface(0, 8);
                        global.msg[1] = "* 但 并 没 有 什 么 事 。/";
                        scr_cloface(2, "P");
                        global.msg[3] = "* .../%%";
                    }
                }
            }
            if (global.plot > 120)
            {
                if (global.flag[98] == 1)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 这 就 是 你 救 了 那 个 小 孩 &  的 地 方 ！/";
                    global.msg[2] = "\\E7* 刚 才 真 是 吓 死 我 了 ^1。&* 做 得 好 ^1， 搭 档 ^1。/";
                    global.msg[3] = "\\EK* 你 可 真 是 正 义 啊 。/";
                    scr_charface(4, "D");
                    global.msg[5] = "* 那 不 是 个 动 词 。/%%";
                }
                if (global.flag[98] == 2)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 哦^1 ， 我 记 得 这 地 方 。/";
                    global.msg[2] = "* 这 是 你 让 那 个 小 孩&  掉 下 去 的 地 方 。/";
                    global.msg[3] = "\\EQ* 永 远 别 再 那 么 做 了 。/";
                    global.msg[4] = "\\E1* 明 白 吗 ？/%%";
                }
                if (global.flag[98] == 2)
                {
                    scr_cloface(0, "J");
                    global.msg[1] = "* 这 是 你 像 个 懦 夫&  一 样 逃 跑 的 地 方 。/";
                    global.msg[2] = "\\E6* 我 姑 且 认 为 你 无 罪 ^1，&  但 是 .../";
                    global.msg[3] = "\\E7* 以 后 你 一 定 要 努 力&  做 一 个 更 好 的 人 ！/";
                    global.msg[4] = "* 就 像 我 一 直 说 的 那 样 :/%%";
                }
                if (global.flag[427] > 0)
                {
                    if (global.flag[98] == 1)
                    {
                        scr_cloface(0, 1);
                        global.msg[1] = "* 如 果 你 多 锻 炼 语 言 表 达 ， &  一 切 都 可 以 是 动 词 ！/%%";
                    }
                    if (global.flag[98] == 2)
                    {
                        scr_charface(0, "C");
                        global.msg[1] = "* .../%%";
                    }
                    if (global.flag[98] == 2)
                    {
                        scr_charface(0, 8);
                        global.msg[1] = "* 什 么 ？/";
                        scr_cloface(2, "H");
                        global.msg[3] = "* 我 刚 说 话 的 时 候&  还 在 想 我 说 过 什 么 呢 。/";
                        global.msg[4] = "\\EG* 但 我 好 像 什 么 都 没 说 过 。/%%";
                    }
                }
            }
        }
        break;
    case room_water_undynefinal:
        if (clover == 1)
        {
            if (global.plot == 121)
            {
                scr_charface(0, 9);
                global.msg[1] = "* 她 上 来 就 直 奔 主 题 ^1，&  不 是 吗 ？/";
                scr_cloface(2, 2);
                global.msg[3] = "* 真 是 太 酷 了 ！/";
                global.msg[4] = "\\E5* 我 是 说 ， 呃 ^1-&\\E8* 你 能 行 的 ^1，&  Frisk ！/%%";
                if (global.kills > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* .../";
                    global.msg[2] = "\\E5* 说 实 话 ， 听 完 她 的 演 讲 ，&  我 估 计 你 都 吓 得 站 不 稳 了 。/";
                    scr_charface(3, 0);
                    global.msg[4] = "* 她 确 实 把 自 己 描 绘 成 了&  一 位 非 常 英 勇 的 女 英 雄 。/";
                    global.msg[5] = "\\E8* 是 时 候 为 你 所 犯 的 罪 行 &  付 出 代 价 了 。/%%";
                }
                if (global.flag[67] == 1)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* .../";
                    scr_cloface(2, "F");
                    global.msg[3] = "* .../%%";
                }
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* 我 能 够 理 解 &  你 被 这 种 情 况 所 吓 到 。/";
                    global.msg[2] = "\\E9* 但 你 必 须 要 前 进 ^1, &  不 是 吗 ？/%%";
                    if (global.kills > 0)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* 哦 ^1， 你 想 要 获 得 有 关 如 何&  与 她 战 斗 的 提 示 。/";
                        global.msg[2] = "\\E5* 呃/";
                        global.msg[3] = "\\E8* 别 ？/";
                    }
                    if (global.flag[67] == 1)
                    {
                        scr_cloface(0, "F");
                        global.msg[1] = "* .../";
                        global.msg[2] = "\\EE* 听 着 ^1，&  如 果 你 想 要 我 的 建 议 。/";
                        global.msg[3] = "* 逃 跑 ^1。 别 回 头 看 。/";
                        global.msg[4] = "* 因 为 说 实 话 ^1？&* 她 有 正 当 理 由&  杀 了 你 。/%%";
                    }
                }
            }
            if (global.plot < 121)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 随 时 可 以 前 进 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* .../%%";
                }
            }
            if (global.plot > 121 && global.flag[67] == 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 我 不 得 不 承 认 ^1，&  她 的 演 讲 真 的 很 不 错 。/";
                scr_cloface(2, "B");
                global.msg[3] = "* 你 瞎 说 什 么 ^2？&\\E2* 明 明 是 太 棒 了 ！！/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 2);
                    global.msg[1] = "* “ 你 ！ ”/";
                    scr_charface(2, "A");
                    global.msg[3] = "* “ 你 正 是 所 有 人 通 往 希 望 &  与 梦 想 之 路 上 的 绊 脚 石 ！ ”/%%";
                }
            }
            if (global.flag[350] == 1)
            {
                scr_charface(0, 3);
                global.msg[1] = "* .../%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "E");
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_water_undynefinal2:
    case room_water_undynefinal3:
        if (clover == 1)
        {
            if (global.flag[350] != 1)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 还 记 得 你 在 这 里 &  逃 命 的 时 候 吗 ？/";
                global.msg[2] = "\\E6* ...你 说 “ 不 ” 是 什 么 意 思 ？/";
                scr_charface(3, 8);
                global.msg[4] = "* 还 记 得 你 在 这 里 &  慢 慢 走 着 逃 命 的 时 候 吗 ？/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 2);
                    global.msg[1] = "* 没 错 ^1， 没 错 ^2。&* 这 之 间 有 很 大 的 区 别 ^1，&  我 明 白 了 。/%%";
                }
            }
            if (global.flag[350] == 1)
            {
                scr_cloface(0, "E");
                global.msg[1] = "* .../%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "E");
                    global.msg[1] = "* 我 们 不 要 在 这 里&  待 太 久 。/%%";
                }
            }
        }
        break;
    case room_fire1:
        if (clover == 1)
        {
            if (global.flag[67] != 1 && global.flag[350] == 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 如 果 Sans 不 那 么 神 秘 的 话 ，&  他 会 是 个 很 有 趣 的 人 的 。/";
                scr_cloface(2, 7);
                global.msg[3] = "* 至 少 他 是 在 照 顾 你 的 。/";
                global.msg[4] = "* 我 是 说 我 猜 这 可 能 不 是 &  他 自 己 做 出 的 决 定 ， 我 怀 疑 &  是 Papyrus 叫 他 这 么 做 的 。/";
                global.msg[5] = "\\E1* 哈 ^1， 你 能 想 象 到 &  他 们 会 怎 么 聊 吗 ？/";
                global.msg[6] = "\\EN\\TP\"SANS ^1， 我 需 要 你 去 &分 散 一 下 UNDYNE 的 &注 意 力 。\"/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* 你 ..^1. 真 的 很 擅 长 模 仿 。/";
                    scr_cloface(2, "I");
                    global.msg[3] = "\\TC%";
                    global.msg[4] = "* 不 管 怎 样 ^1， 谢 谢 你 ^2。&* 感 谢 你 的 赞 美 之 词 。/";
                    scr_charface(5, "A");
                    global.msg[6] = "* 但 是 有 些 东 西 .../";
                    global.msg[7] = "\\EK* 你 就 是 模 仿 不 了 。/";
                    scr_cloface(8, "M");
                    global.msg[9] = "* 是 的 ..^1. 我 .../";
                    global.msg[10] = "\\EC* 确 实 不 行 。/";
                    scr_charface(11, 9);
                    global.msg[12] = "* 真 是 个 笨 蛋 。/%%";
                }
            }
            else if (global.flag[67] == 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 看 起 来 像 Sans的 哨 所 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* .../%%";
                }
            }
            else if (global.flag[350] == 1)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* ...这 里 是 热 域 ^1。&* 因 为 这 里 是 个 区 域 ^1。 而 且&  很 热 ^2。 或 者 还 有 别 的 原 因 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* ...我 们 还 是 走 吧 。/%%";
                }
            }
        }
        break;
    case room_fire2:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 一 个 又 大 ^1， 水 又 清 澈 &  的 饮 水 机 。/";
            global.msg[2] = "\\E6* 别 的 没 东 西 了 。 /%%";
            if (global.flag[353] > 15)
            {
                global.msg[2] = "\\E7* 还 有 呃^1 ，你 搞 出 来 的 水 坑 。/%%";
            }
            if (global.flag[427] > 0)
            {
                if (global.flag[350] == 1)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* 真 是 奇 迹 ，你 在 这 种&  高 温 之 下 竟 然 &  一 点 事 都 没 有 。/";
                    global.msg[2] = "* 等 你 走 到 下 一 个 房 间 &  的 时 候 ， 水 都 几 乎 要 被 &  完 全 蒸 发 了 。/%%";
                }
                if (global.flag[350] == 2)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 我 仍 然 觉 得 你&  应 该 帮 助 Undyne 。/";
                    global.msg[2] = "* 但 我 想 她 应 该 &  不 会 有 问 题 的 。/%%";
                }
            }
            if (instance_exists(obj_undynefall))
            {
                if (global.flag[353] <= 19)
                {
                    scr_charface(0, 9);
                    global.msg[1] = "* 看 起 来 她 太 热 了 。/";
                    global.msg[2] = "* 如 果 你 执 意 要 救 她 .../";
                    global.msg[3] = "\\E8* 那 个 摆 放 便 利 的 饮 水 机 &  应 该 会 有 所 帮 助 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* 你 会 救 她 的 ^1， 对 吗 ？/%%";
                    }
                    if (scr_murderlv() > 7 || irememberyourneutrals > 2)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* 你 应 该 帮 助 她 。/";
                        global.msg[2] = "* 我 很 确 定 她 对 你 &  评 价 不 高 ^1，&  而 且 有 充 分 的 理 由 。/";
                        global.msg[3] = "* 但 我 怀 疑 她 会 在 这 里&  攻 击 你 。/%%";
                        if (global.flag[427] > 0)
                        {
                            scr_charface(0, 0);
                            global.msg[1] = "* 由 你 来 做 这 个 决 定 。/%%";
                        }
                    }
                }
                else
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* ^1.^1.^1.为 什 么 ？/";
                    scr_cloface(2, 9);
                    global.msg[3] = "* 那 很 邪 恶 ？？^1？&* 却 毫 无 理 由 ？？？/%%";
                }
            }
        }
        break;
    case room_fire_prelab:
        if (clover == 1)
        {
            if (global.plot >= 136)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 等 一 下 ^1。 我 是 不 是&  看 错 了 ？/";
                scr_cloface(2, 6);
                global.msg[3] = "* 嗯 哼 ^1？ 有 什 么 问 题 吗 ？/";
                scr_charface(4, "C");
                global.msg[5] = "* 实 验 室 附 近 的 地 面 ^1.^1.^1.&  是 不 是 颜 色 不 一 样 ？/";
                scr_cloface(6, 6);
                global.msg[7] = "* ...什 么 ？/%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, "B");
                    global.msg[1] = "* 什 么/";
                    scr_charface(2, "D");
                    global.msg[3] = "* 看 来 不 是 只 有 我 这 么 想 。/";
                    scr_cloface(4, "B");
                    global.msg[5] = "* 我 现 在 明 白 了/";
                    scr_charface(6, "B");
                    global.msg[7] = "* 哦 我 真 讨 厌 这 个 。/";
                    scr_cloface(8, "B");
                    global.msg[9] = "* 为 什 么/%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_charface(0, "B");
                    global.msg[1] = "* 这 是 我 一 生 中 &  最 糟 的 一 天 ！/%%";
                }
            }
            else if (instance_exists(obj_royal_rabbitbounce))
            {
                scr_charface(0, 0);
                global.msg[1] = "* 如 果 不 是 因 为 他 俩 &  在 那 边 挡 路 ^1， &  我 们 肯 定 能 更 快 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* 绕 点 远 路 也 没 什 么 &  不 好 的 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "H");
                    global.msg[1] = "* 相 信 我 ^1， 我 会 知 道 的 。/%%";
                }
            }
            if (global.flag[350] == 0 && global.flag[19] == 20)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 皇 家 实 验 室 ^1，&  对 吧 ？/";
                scr_cloface(2, 6);
                global.msg[3] = "* ...你 应 该 进 去 看 看  。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 你 看 起 来 很 忧 虑 。/";
                    scr_cloface(2, 9);
                    global.msg[3] = "* 因 为 我 的 确 很 忧 虑 。/%%";
                }
            }
        }
        break;
    case room_fire_dock:
        if (clover == 1 && instance_exists(obj_dogboat_thing))
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 真 神 秘 。/";
            scr_charface(2, "L");
            global.msg[3] = "* 如 果 你 出 于 什 么 原 因 &  要 回 到 某 个 地 方 .../";
            global.msg[4] = "\\E0* 这 似 乎 是 最 有 效 的 方 法 。 /%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 在 我 那 个 年 代 ^1， 你 需 要 &  把 自 己 邮 寄 去 &  你 想 去 的 地 方 。/";
                scr_charface(2, "C");
                global.msg[3] = "* ..^2.送 ？&* 怎 么 送 ？/";
                scr_cloface(4, 1);
                global.msg[5] = "* 通 过 邮 件 ！/";
                scr_charface(6, "D");
                global.msg[7] = "* ..^2.邮 件 。/";
                scr_cloface(8, 7);
                global.msg[9] = "* 是 的 。/";
                scr_charface(10, "C");
                global.msg[11] = "* 这 是 免 费 的 还 是 付 费 的 ？/";
                scr_cloface(12, 6);
                global.msg[13] = "* 我 想 那 是 免 费 的 ！/";
                scr_charface(14, 8);
                global.msg[15] = "* 真 不 错 。/";
                scr_cloface(16, 1);
                global.msg[17] = "* 怪 物 们 真 奇 怪 ^1，&  是 吧 ？/";
                scr_charface(18, 8);
                global.msg[19] = "* 你 说 的 没 错 。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 走 吧 ^1。 你 已 经 &  浪 费 够 多 时 间 了 。/%%";
            }
        }
        break;
    case room_fire_lab1:
        if (clover == 1)
        {
            if (instance_exists(obj_labdarkness))
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 那 难 道 是 一 个 ^2-%";
                scr_charface(2, 0);
                global.msg[3] = "* 这 个 屏 幕 在 监 视 我 们 ^1？ &  我 是 这 么 觉 得 的 。/";
                scr_cloface(4, 9);
                global.msg[5] = "* 真 吓 人 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 我 觉 得 你 该 去 &  找 个 开 关 把 灯 打 开 。/";
                    scr_charface(2, 3);
                    global.msg[3] = "* 我 更 关 心 的 是&  找 到 那 个 追 踪 你 的 人 。/%%";
                }
            }
            else if (global.plot == 126)
            {
                scr_cloface(0, "P");
                global.msg[1] = "* 一 个 杀 手 机 器 人 ，嗯 ？/";
                scr_charface(2, 9);
                global.msg[3] = "* 这 是 怎 么 了 ^1？& Clover^1 ，生 气 了 ^1？&* 真 不 符 合 你 的 性 格 啊 。/";
                scr_cloface(4, "D");
                global.msg[5] = "* 他 听 起 来 就 像 个 山 寨 的 ，仅 此 而 已 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 我 想 ^1，再 次 有 人 站 在&  我 们 这 边 是 件 好 事 。/";
                    scr_cloface(2, 7);
                    global.msg[3] = "* 是 啊 ^2。 这 趟 瀑 布 之 旅&  可 真 是 太 累 了 。/%%";
                }
            }
            else if (global.flag[493] >= 10 && global.flag[7] == 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 ...有 点 害 怕 。/";
                global.msg[2] = "\\E9* 这 有 点 像 是 最 终 的 结 局 ，&  对 吧 ？/";
                scr_charface(3, 1);
                global.msg[4] = "* 我 倾 向 于 同 意 。/";
                global.msg[5] = "\\E0* 让 我 们 把 这 事 了 结 了 吧 。/%%";
            }
            else
            {
                scr_charface(0, 5);
                global.msg[1] = "* 这 地 方 也 太 乱 了 吧 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* 其 实 真 的 想 乱 的 话 &  还 可 以 更 乱 一 点 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 你 的 要 求 也 太 高 了 。/";
                    if (irememberyourneutrals > 1)
                    {
                        scr_charface(2, "B");
                    }
                    else
                    {
                        scr_charface(2, 9);
                    }
                    global.msg[3] = "* 你 的 要 求 也 太 低 了 。/%%";
                }
            }
        }
        break;
    case room_fire_lab2:
        if (clover == 1)
        {
            if (global.flag[493] >= 11)
            {
                scr_charface(0, "B");
                global.msg[1] = "* 所 以 这 一 切 都 是 &  她 在 装 模 作 样 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* .../%%";
                }
            }
            else
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 到 底 都 是 些 什 么 ？/";
                global.msg[2] = "\\E9* 这 位 “ 皇 家 科 学 员 ”&  平 时 都 在 做 这 些 ？/";
                global.msg[3] = "* 我 不 明 白 这 哪 里 &  更 重 要 了 ^1，相 比 起 .../";
                global.msg[4] = "* ^1.^1../";
                scr_charface(5, 1);
                global.msg[6] = "* Clover^2？ &  你 ..^2.还 好 吗 ？ /";
                scr_cloface(7, "F");
                global.msg[8] = "* 这 没 有 任 何 意 义 。 /%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 这 真 的 是 &  实 验 室 的 全 部 吗 ?/";
                    scr_charface(2, 3);
                    global.msg[3] = "* 我 不 明 白 为 什 么 不 可 能 。/";
                    global.msg[4] = "\\EL* 即 使 它 只 是 一 团 糟 。 /";
                    scr_cloface(5, "E");
                    global.msg[6] = "* 一 团 糟 。 /";
                    global.msg[7] = "* 哈 。/%%";
                }
                if (global.flag[427] == 2)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 还 有 更 多 。 /";
                    scr_charface(2, 3);
                    global.msg[3] = "* 嗯 ？/";
                    scr_cloface(4, 9);
                    global.msg[5] = "* 去 真 实 验 室 ^2。 在 某 个 地 方 ^1,&  还 有 更 多 ^2。 &* 一 定 会 有 。 /%%";
                    scr_charface(6, 3);
                    global.msg[7] = "* 而 又 是 什 么 让 你 &  如 此 肯 定 ?/";
                    scr_cloface(8, "E");
                    global.msg[7] = "* ..../";
                    global.msg[10] = "* 姑 且 称 之 为 直 觉 吧 。 /%%";
                }
                if (global.flag[427] > 2)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_fire3:
        if (clover == 1)
        {
            if (global.flag[19] == 20)
            {
                if (global.flag[368] == 1)
                {
                    scr_cloface(0, 5);
                    global.msg[1] = "* 我 感 到 一 种 巨 大 的 扰 动 。/";
                    global.msg[2] = "* 仿 佛 有 几 十 条 短 信&  向 你 的 手 机 飞 奔 而 来 .../";
                    global.msg[3] = "* 然 后 突 然 寂 静 了 。/";
                    scr_charface(4, "C");
                    global.msg[5] = "* 这 得 感 谢 静 音 按 钮 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 0);
                        global.msg[1] = "* 你 可 以 随 时 再 打 开 通 知 。/";
                        scr_charface(2, 3);
                        global.msg[3] = "* 你 也 可 以 不 那 么 做 。/";
                        global.msg[4] = "\\EH* 说 实 话 ^1， &  我 想 禁 止 你 这 么 做 。/";
                        global.msg[5] = "* 你 必 须 接 受 你 的 选 择 。/%%";
                    }
                }
                else
                {
                    scr_charface(0, "D");
                    global.msg[1] = "* 我 恨 你 。/";
                    scr_cloface(2, 0);
                    global.msg[3] = "* 不 你 没 有 。/";
                    scr_charface(4, "C");
                    global.msg[5] = "* 我 有 点 不 喜 欢 你 。/";
                    scr_cloface(6, 1);
                    global.msg[7] = "* 一 项 改 进 建 议 ！/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, "C");
                        global.msg[1] = "* 你 仍 然 可 以 关 闭 通 知 ^2。&* 你 可 以 改 正 过 来 。/";
                        scr_cloface(2, 0);
                        global.msg[3] = "* 别 屈 服 ^1， Frisk./";
                        global.msg[4] = "\\EI* 那 就 别 关 了 。/";
                        global.msg[5] = "* 你 这 是 出 于 恶 意 。/%%";
                    }
                }
            }
            if (global.flag[19] > 20)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 实 验 室 的 这 一 边 &  看 上 去 没 那 么 可 怕 了 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 其 实 是 一 样 的 ，&  只 是 换 了 个 角 度 。/";
                scr_cloface(4, 6);
                global.msg[5] = "* 好 吧 ^1， 确 实 。/";
                global.msg[6] = "\\EA* 但 这 可 能 是 因 为 ^1，&  我 也 不 清 楚 。/";
                global.msg[7] = "\\E7* 我 们 穿 过 了 它 ，&  从 另 一 边 走 了 出 来 ，&  变 得 更 强 了 ？/";
                scr_charface(8, 0);
                global.msg[9] = "* 我 不 知 道 你 说 的 “ 更 强 ” &  是 什 么 ，但 是 .../";
                global.msg[10] = "\\E8* 我 们 的 装 备 的 确 更 好 了 。/";
                global.msg[11] = "* 你 手 机 里 的 那 些 次 元 箱 子 &  的 确 很 有 用 。/";
                global.msg[12] = "* 你 最 好 多 用 它 们 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 但 如 果 他 决 定 &  不 用 它 们 呢 ？/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 那 是 他 自 己 的 选 择 。/";
                    global.msg[4] = "\\EH* 我 不 管 ，&  他 爱 怎 么 样 就 怎 么 样 吧 。/";
                    scr_cloface(5, "P");
                    global.msg[6] = "* 你 当 然 不 管 。/";
                    global.msg[7] = "* 全 知 全 能 的 " + scr_gettext("obj_chara_5") + "&  永 远 不 会 做 出 &  糟 糕 的 选 择 。/";
                    scr_charface(8, 9);
                    global.msg[9] = "* 现 在 你 开 始 理 解 了 。/%%";
                }
            }
        }
        break;
    case room_fire5:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 传 送 带 ^2。&* 真 方 便 啊 ！/";
            scr_charface(2, 0);
            global.msg[3] = "* 当 你 不 用 它 们 的 时 候 ..^2.&* 你 懂 的 .../";
            global.msg[4] = "\\ED* 想 一 想 维 持 它 们 &  一 直 运 转 需 要 多 少 能 量 。/";
            global.msg[5] = "\\EH* 浪 费 这 么 多 能 源 而 不 &  选 择 仅 仅 是 让 居 民 们 &  多 走 点 路 。/";
            global.msg[6] = "\\EA* 不 考 虑 那 些 的 话 ^1， 确 实 ^1！&* 是 挺 方 便 的 ！/";
            scr_cloface(7, "D");
            global.msg[8] = "* 在 把 好 事 搞 砸 这 方 面 &  你 从 没 让 我 失 望 过 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "L");
                global.msg[1] = "* 我 必 须 请 求 你 的 原 谅 。/";
                global.msg[2] = "\\EH* 这 是 我 的 一 个 坏 毛 病 ^1， &  总 是 去 看 事 物 的 本 质 。/";
                global.msg[3] = "* 并 查 明 事 物 背 后 &  所 潜 在 的 问 题 .../";
                global.msg[4] = "\\E9* 我 确 实 不 该 &  担 心 这 么 多 的 。/";
                global.msg[5] = "\\EA* 我 就 应 该 让 你 &  活 在 无 知 的 幸 福 中 。/";
                scr_cloface(6, "P");
                global.msg[7] = "* 随 你 怎 么 说 吧 ^1，&  殿 下 。/";
                scr_charface(8, "N");
                global.msg[9] = "* 什 么 殿 下 ， &  我 又 不 是 个 王 子 。/";
                scr_cloface(10, "G");
                global.msg[11] = "* ???/%%";
            }
        }
        break;
    case room_fire6:
        if (clover == 1)
        {
            scr_cloface(0, "A");
            global.msg[1] = "* 我 们 要 怎 么 穿 过 &  这 些 裂 隙 呢 ？/";
            scr_charface(2, "I");
            global.msg[3] = "* 那 个 排 汽 口 上 面 有 一 个 &  突 出 的 箭 头 ^2。 为 什 么 &  不 试 着 去 踩 一 下 呢 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* ...？ /%%";
            }
            if (global.flag[19] >= 20.5)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 好 吧 ^1， 但 我 们 还 需 要 &  通 过 多 少 排 汽 口 呢 ？/";
                scr_charface(2, 0);
                global.msg[3] = "* 很 多 。/";
                scr_cloface(4, "D");
                global.msg[5] = "* 但 这 也 太 多 了 。/";
                scr_charface(6, 8);
                global.msg[7] = "* 真 是 个 爱 哭 的 小 孩 。/";
                scr_cloface(8, "J");
                global.msg[9] = "* 嘿 ！/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 你 为 什 么 这 么 刻 薄 ^2？&* 我 可 什 么 都 没 做 ！/";
                    scr_charface(2, "H");
                    global.msg[3] = "* 你 一 直 在 发 牢 骚 ^2。 &  跟 个 小 孩 一 样 。/";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 所 以 呢 ^2？ 你 觉 得 &  大 孩 子 不 能 发 牢 骚 吗 ？/";
                    scr_charface(6, 0);
                    global.msg[7] = "* 没 错 ^2。 我 就 是 &  这 么 想 的 。/";
                    scr_cloface(8, 8);
                    global.msg[9] = "* ...我 把 这 归 结 为 &  “ 我 的 幽 灵 室 友 &  受 到 了 精 神 创 伤 ”/";
                    scr_charface(10, "N");
                    global.msg[11] = "* 什 么 ^2- \\EJ嘿 ！/%%";
                }
            }
            if (global.plot > 163)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 我 必 须 为 让 你 忍 耐 而 道 歉 。/";
                global.msg[2] = "* 噩 梦 ^2。&* 这 些 排 汽 口 简 直 是 噩 梦 。/";
                scr_cloface(3, 8);
                global.msg[4] = "* 原 谅 并 遗 忘 ！/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* 看 着 他 们 让 我 感 到 头 晕 。/";
                    scr_cloface(2, "I");
                    global.msg[3] = "* 忍 一 忍 吧 。/";
                    scr_charface(4, "J");
                    global.msg[5] = "* 我 说 过 了 我 很 抱 歉 ！/%%";
                }
            }
        }
        break;
    case room_fire6A:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 看 看 那 边 ！/";
            global.msg[2] = "\\E7* 如 果 你 把 握 准 了 时 机 ^1，&  那 个 蒸 汽 排 汽 口 就 会 把 你 &  发 射 到 那 个 平 底 锅 上 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 去 吧 ^1！&* 我 相 信 你 能 行 的 ！/%%";
            }
            if (global.flag[110] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 恭 喜 啊 ！ /";
                scr_charface(2, 0);
                global.msg[3] = "* 真 是 惊 险 。/";
                global.msg[4] = "\\EH* 我 们 现 在 可 以 走 了 吗 ^2？&* 绕 这 次 远 路 ..^2.&  似 乎 有 点 没 必 要 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 也 许 绕 这 趟 路 &  非 常 值 得 -/";
                    scr_charface(2, "G");
                    global.msg[3] = "* 别 再 说 了 。/%%";
                }
            }
        }
        break;
    case room_fire_lasers1:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 我 不 觉 得 我 需 要 &  告 诉 你 要 小 心 激 光 。/";
            global.msg[2] = "* 尽 管 如 此 ， &  我 还 是 要 告 诉 你 。/";
            scr_cloface(3, 6);
            global.msg[4] = "* 只 要 错 一 步 ， &  一 切 就 都 完 了 。/";
            scr_charface(5, "L");
            global.msg[6] = "* 这 可 能 有 点 像 是 玩 笑 ^1， &  但 没 错 ^1，&  Clover 说 得 对 。/";
            scr_cloface(7, 9);
            global.msg[8] = "* .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 感 觉 这 似 曾 相 识 。/";
                global.msg[2] = "* 而 且 我 感 觉 不 妙 。/";
                global.msg[3] = "* 我 以 前 从 没 见 过 这 些 ！/";
                global.msg[4] = "* ...对 吗 ？/%%";
            }
            if (global.flag[371] == 1)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 我 本 来 还 以 为 &  你 无 法 通 过 这 里 的 ！/";
                scr_charface(2, 8);
                global.msg[3] = "* 真 的 吗 ^2？ 你 以 为 就 几 个 &  微 不 足 道 的 激 光 &  就 能 阻 止 他 ？/";
                scr_cloface(4, 6);
                global.msg[5] = "* 我 ^2- 实 际 上 ^1， 确 实 ^1，&  我 是 这 么 想 的 。/";
                global.msg[6] = "\\E9* 我 为 什 么 会 那 么 想 ？/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 他 三 下 五 除 二 &  就 解 决 了 这 个 谜 题 ！/";
                    scr_cloface(2, 9);
                    global.msg[3] = "* (所 以 我 为 什 么 会 觉 得 ..^2.&  很 害 怕 呢 ？ )/%%";
                }
            }
            if (global.flag[1] == 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* Frisk ^1， 你 还 是 &  把 它 们 关 上 吧 。/%%";
            }
        }
        break;
    case room_fire8:
    case room_fire9:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 除 了 往 前 走 ， &  别 无 他 法 。/";
            global.msg[2] = "\\E1* 现 在 是 解 谜 时 间 ！/";
            scr_charface(3, 9);
            global.msg[4] = "* 这 应 该 会 很 快 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "M");
                global.msg[1] = "* (终 于 啊 ^1， 有 更 多 的 &  谜 题 了 ！ )/%%";
            }
            if (global.flag[375] == 1)
            {
                scr_charface(0, 9);
                global.msg[1] = "* 我 们 的 力 量 &  足 以 击 溃 一 切 谜 题 。/";
                global.msg[2] = "* 更 何 况 这 个 谜 题 &  还 这 么 简 单 。/%%";
            }
            if (global.flag[374] == 1)
            {
                scr_charface(0, 9);
                global.msg[1] = "* 我 们 的 力 量 &  足 以 击 溃 一 切 谜 题 。/";
                global.msg[2] = "* 我 们 都 没 费 多 少 功 夫 &  就 把 它 解 决 了 。/%%";
            }
        }
        break;
    case room_fire_turn:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 看 起 来 这 里 &  没 有 可 以 返 回 的 路 。/";
            scr_cloface(2, 7);
            global.msg[3] = "* 在 你 踩 上 那 个 排 汽 口 &  之 前 ^1， 你 最 好 是 已 经 &  准 备 好 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 不 要 害 怕 去 得 到 更 多 ！/";
                scr_charface(2, 0);
                global.msg[3] = "* 或 者 ^1， 你 也 可 以 &  直 接 就 \\EJ踩 上 去 。/%%";
            }
            if (obj_mainchara.x > 520)
            {
                scr_cloface(0, "H");
                global.msg[1] = "* 不 Frisk ^1， 事 情 并 不 会 &  奇 迹 般 的 改 变 ， &  使 得 你 可 以 往 回 走 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* 那 确 实 太 烦 人 了 。/";
                global.msg[4] = "\\E7* 看 来 我 们 得 往 前 走 了 ！/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 拜 托 ^1， 你 没 法 &  走 这 条 路 回 去 。/%%";
                }
            }
        }
        break;
    case room_fire_cookingshow:
        if (clover == 1)
        {
            if (instance_exists(obj_cookshowevent))
            {
                if (obj_cookshowevent.con < 4)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 我 有 种 不 祥 的 预 感 。/";
                    scr_charface(2, 3);
                    global.msg[3] = "* 你 都 说 多 少 遍 这 句 话 了 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, 1);
                        global.msg[1] = "* 我 就 喜 欢 说 ，&  有 问 题 吗 ？/";
                        scr_charface(2, "G");
                        global.msg[3] = "* 你 就 是 个 白 痴 。/%%";
                    }
                }
                if (obj_cookshowevent.con == 17 || obj_cookshowevent.con == 42)
                {
                    scr_charface(0, 7);
                    global.msg[1] = "* 最 快 的 解 决 方 法 &  就 是 照 他 说 的 去 做 。/";
                    scr_cloface(2, 1);
                    global.msg[3] = "* 顺 便 说 一 下 ^1， &  我 一 直 都 想 当 个 厨 师 ！/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 0);
                        global.msg[1] = "* 赶 紧 把 这 事 了 结 了 吧 。/%%";
                    }
                }
            }
            else
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 在 我 的 厨 房 ..^1. &  快 乐 地 烹 饪 .../";
                scr_charface(2, "C");
                global.msg[3] = "* 你 在 哼 什 么 歌 ？/";
                scr_cloface(4, 6);
                global.msg[5] = "* 就 是 一 首 小 曲 ^2。&  我 刚 才 边 走 边 编 的 。/";
                global.msg[6] = "* 你 为 什 么 不 也 哼 两 句 呢 ？/";
                scr_charface(7, 3);
                global.msg[8] = "* 才 不 是 呢 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* .../";
                    global.msg[2] = "\\EL* .../";
                    global.msg[3] = "\\EM* (在 我 的 厨 房 ..^1. &  快 乐 地 烹 饪 ...)//%%";
                }
            }
        }
        break;
    case room_fire_savepoint1:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 真 是 壮 丽 的 景 色 。/";
            scr_charface(2, 0);
            global.msg[3] = "* 你 离 你 的 目 标 &  越 来 越 近 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 你 的 目 标 .^1.^1.&* 那 真 的 是 .../";
                global.msg[2] = "\\E6* 还 是 别 说 了 。/";
                scr_charface(3, "L");
                global.msg[4] = "* ...？ /%%";
            }
            if (global.flag[19] == 21)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 哦 ^1， 你 想 知 道 吗 ？/";
                global.msg[2] = "\\E6* 呃 ^1， 实 际 上 ^1， 他 们 之 前 &  曾 有 一 个 完 整 的 &  科 学 部 门 。/";
                global.msg[3] = "* 他 们 在 蒸 汽 工 厂 工 作 ^2！&* 做 一 些 科 学 类 的 事 情 。/";
                scr_charface(4, "E");
                global.msg[5] = "* 科 学 类 的 事 情 ？/";
                scr_cloface(6, "D");
                global.msg[7] = "* 这 挺 难 解 释 的 ^1，&  好 吗 ？！/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 实 际 上 ^1， 有 一 个 电 梯 &  连 接 着 蒸 汽 工 厂 与 热 域 。/";
                    global.msg[2] = "\\E7* 也 许 你 可 以 &  亲 自 去 看 一 看 ！/";
                    global.msg[3] = "\\E6* 也 许 ^2。&* 可 能 ^2。&\\E5* 我 希 望 你 能 去 。/";
                    scr_charface(4, "H");
                    global.msg[5] = "* 或 者 我 们 可 以 ^1。&\\EL* 你 知 道 的 ^1。&\\ED* 走 正 路 。/%%";
                }
            }
        }
        break;
    case room_fire_hotdog:
        if (clover == 1)
        {
            scr_charface(0, "I");
            global.msg[1] = "* 但 说 真 的 ^1， 他 是 怎 么&  一 直 比 我 们 快 的 ？/";
            scr_cloface(2, 6);
            global.msg[3] = "* 也 许 他 有 某 种 ^1—&  \\E1噢 噢 噢 噢 ， 热 狗 ！/";
            scr_charface(4, "C");
            global.msg[5] = "* 某 种 什 么 ？/";
            scr_cloface(6, 1);
            global.msg[7] = "* Frisk^1， 快 买 条 热 狗 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "G");
                global.msg[1] = "* Clover ？/";
                scr_cloface(2, "L");
                global.msg[3] = "* 热 狗 .../%%";
            }
            if (!instance_exists(obj_sans_room))
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 现 在 他 已 经 走 了 。/";
                scr_charface(2, "I");
                global.msg[3] = "* 这 背 后 肯 定 藏 着 &  某 种 秘 密 。/";
                scr_cloface(4, 6);
                global.msg[5] = "* 要 我 来 猜 的 话 ^1， &  可 能 是 什 么 &  他 独 有 的 能 力 。/";
                global.msg[6] = "\\E5* 我 还 从 来 没 见 过 任 何 人 &  能 够 无 视 时 间 和 空 间 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 可 能 吧 。/";
                    scr_cloface(2, 0);
                    global.msg[3] = "* 是 啊 。/";
                    scr_charface(4, 0);
                    global.msg[5] = "* .../";
                    scr_cloface(6, 6);
                    global.msg[7] = "* .../";
                    scr_charface(8, "J");
                    global.msg[9] = "* 又 或 许 他 —/";
                    scr_cloface(10, "C");
                    global.msg[11] = "* 够 了 别 说 了 .../%%";
                }
                if (global.flag[67] == 1)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 这 样 的 哨 所 &  真 的 有 很 多 .../";
                    global.msg[2] = "* .../";
                    scr_charface(3, 0);
                    global.msg[4] = "* 我 们 还 在 等 什 么 ？ &  这 里 没 什 么 可 做 的 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 7);
                        global.msg[1] = "* 我 们 为 什 么 还 待 在 这 里 ？/";
                        global.msg[2] = "* 因 为 我 不 知 道 。/%%";
                    }
                }
            }
        }
        break;
    case room_fire_walkandbranch:
        if (clover == 1)
        {
            scr_cloface(0, "A");
            global.msg[1] = "* 有 件 事 困 扰 了 我 好 久 。/";
            scr_charface(2, 0);
            global.msg[3] = "* 你 得 跟 全 班 同 学 &  分 享 一 下 。/";
            scr_cloface(4, 7);
            global.msg[5] = "* 哦 ^1， 饶 了 我 吧 。/";
            global.msg[6] = "\\EA* 但 说 真 的 ^1，&  这 里 到 处 都 是 熔 岩 .../";
            global.msg[7] = "\\E6* 这 会 使 伊 波 特 山&  变 成 火 山 吗 ？/";
            scr_charface(8, "I");
            global.msg[9] = "* 首 先 ^1， 你 说 那 是 熔 岩 ^1，&  其 实 你 指 的 是 岩 浆 。/";
            global.msg[10] = "* 熔 岩 是 突 破 至 地 表 的&  熔 融 岩 石 。/";
            scr_cloface(11, 7);
            global.msg[12] = "* 而 这 里 显 然 不 是 地 表 。/";
            scr_charface(13, 8);
            global.msg[14] = "* 没 错 ^2。 岩 浆 完 全 一 样 ^1，&  只 是 在 地 下 。/";
            scr_cloface(15, 1);
            global.msg[16] = "* 真 是 个 有 趣 的 冷 知 识 ！/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 所 以 ^1， 你 的 意 思 是&  这 真 的 是 一 座 火 山 ？/";
                scr_charface(2, 8);
                global.msg[3] = "* 你 说 得 对 。/";
                global.msg[4] = "\\E0* 但 你 先 别 急 ，&  它 不 会 喷 发 的 。/";
                scr_cloface(5, 6);
                global.msg[6] = "* 我 啥 时 候 急 了 ？/";
                global.msg[7] = "\\E0* 我 当 然 知 道 活 火 山&  和 死 火 山 的 区 别 。/";
                scr_charface(8, 8);
                global.msg[9] = "* 我 的 错 。/";
                global.msg[10] = "\\EE* 我 低 估 你 了 。/";
                scr_cloface(11, "D");
                global.msg[12] = "* 没 必 要 夸 人 都&  夸 得 这 么 含 蓄 ！/%%";
            }
        }
        break;
    case room_fire_sorry:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 发 现 秘 密 ！/";
            scr_charface(2, "C");
            global.msg[3] = "* 对 于 一 个 美 术 俱 乐 部 来 讲&  ...这 地 方 真 奇 怪 。/";
            scr_cloface(4, 6);
            global.msg[5] = "* 是 啊 .../";
            global.msg[6] = "* 嗯 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 或 许 更 像 他 们 在&  ..^2.练 习 美 术 魔 法 。/";
                global.msg[2] = "\\E2* 而 且 因 为 太 危 险 ，&  那 被 禁 止 了 。/";
                global.msg[3] = "* 所 以 他 们 得 秘 密 练 习 。/";
                scr_charface(4, "E");
                global.msg[5] = "* 那 绝 对 不 合 理 。/";
                scr_cloface(6, 2);
                global.msg[7] = "* 我 说 到 点 子 上 了 ！ ！ ！/%%";
            }
            if (global.flag[281] == 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 可 怜 的 家 伙 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 没 有 任 何 值 钱 的 东 西 丢 失 。/";
                scr_cloface(4, 5);
                global.msg[5] = "* 真 是 粗 鲁 。/%%";
            }
            if (global.flag[281] == 2)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../";
                scr_charface(2, "C");
                global.msg[3] = "* .../";
                scr_cloface(4, 7);
                global.msg[5] = "* 真 抱 歉 ^1， Frisk^2.&* 看 起 来 我 们 &  没 东 西 能 加 了 。/%%";
            }
        }
        break;
    case room_fire_apron:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 嘿 ^1， 去 把 它 捡 起 来 ！/%%";
            if (global.flag[111] > 0)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 这 是 一 条 围 裙 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 我 谢 谢 你 啊 ，福 尔 摩 斯 。/";
                scr_cloface(4, "D");
                global.msg[5] = "* 哈 哈 ^1， 真 有 趣 。/";
                global.msg[6] = "* 但 是 ... 它 为 什 么 &  被 丢 弃 在 这 里 了 ？/";
                scr_charface(7, 7);
                global.msg[8] = "* 它 已 经 破 旧 不 堪 了 ^1。&* 它 的 主 人 不 想 要 它 了 ， &  那 就 是 为 什 么 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 不 。/";
                    scr_charface(2, "L");
                    global.msg[3] = "\\E1* 什 么 ？ /";
                    scr_cloface(4, 9);
                    global.msg[5] = "* 它 的 主 人 很 爱 惜 它 。/";
                    global.msg[6] = "\\E6* 它 的 主 人 经 常 穿 戴 它 。&  就 像 把 一 顶 帽 子 &  戴 到 又 脏 又 旧 一 样 。/";
                    global.msg[7] = "\\E7* 其 实 它 的 主 人 &  并 不 想 把 它 丢 下 。/";
                    scr_charface(8, "G");
                    global.msg[9] = "* 跟 帽 子 有 什 么 关 系 ？/";
                    global.msg[10] = "\\E7* ...我 觉 得 你&  过 分 解 读 了 。/";
                    scr_cloface(11, 5);
                    global.msg[12] = "* 可 能 吧 。/";
                    global.msg[13] = "\\E6* .../";
                    global.msg[14] = "\\E3* 但 我 不 觉 得 &  是 我 有 问 题 。/%%";
                }
            }
        }
        break;
    case room_fire10:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 一 个 简 单 的 限 时 挑 战 。/";
            global.msg[2] = "\\E9* 如 果 你 连 这 都 做 不 到 ，&  我 会 很 失 望 的 。/";
            scr_cloface(3, 1);
            global.msg[4] = "* 我 相 信 你 能 做 到 的 ！/%%";
            if (global.plot == 140)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 我 知 道 被 打 电 话 可 能 会&  打 乱 你 的 时 间 安 排 。/";
                global.msg[2] = "\\ED* 但 你 就 非 要 接 那 个 电 话 吗 ？ ？ ？/";
                scr_cloface(3, 7);
                global.msg[4] = "* 只 是 出 于 礼 貌 ！/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 但 那 可 可 可 可 可 能&  确 实 不 是 最 好 的 选 择 。/";
                    scr_charface(2, "H");
                    global.msg[3] = "* 是 啊 我 就 是 那 么 想 的 。/%%";
                }
            }
            if (global.flag[404] == 1)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 很 好 ^2。&* 真 令 人 印 象 深 刻 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* 你 成 功 了 ！/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 我 只 是 不 懂&  你 是 怎 么 做 到 的 。/%%";
                }
            }
            if (global.plot > 140)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 我 很 高 兴 它 已 经 被 解 决 了 。/";
                global.msg[2] = "* 如 果 这 些 谜 题&  一 直 阻 碍 我 们 ，&  那 可 就 太 麻 烦 了 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 0);
                    global.msg[1] = "* 我 以 为 你 很 喜 欢 谜 题 呢 ！/";
                    scr_charface(2, 8);
                    global.msg[3] = "* 我 喜 欢 新 的 谜 题 ，&  不 是 那 些 已 经 解 决 了 的 。/";
                    global.msg[4] = "* 一 开 始 就 知 道 答 案 &  可 没 乐 趣 。/";
                    global.msg[5] = "\\EH* 还 有 ^1， 这 不 是 个 谜 题 ^2。&  这 是 一 个 计 时 挑 战 。/%%";
                }
            }
        }
        break;
    case room_fire_rpuzzle:
        if (clover == 1)
        {
            scr_cloface(0, "J");
            global.msg[1] = "* 这 些 排 汽 口 又 回 来 了 ！/";
            global.msg[2] = "* 而 且 现 在 它 们&  玷 污 上 了 谜 题 ！/";
            scr_charface(3, "L");
            global.msg[4] = "* .^2..在 原 则 上 ^1，&  这 是 个 很 好 的 谜 题 。/";
            scr_cloface(5, "E");
            global.msg[6] = "* 但 不 适 用 于 你 旋 转 得 快 到&  天 旋 地 转 啥 都&  看 不 见 的 时 候 ！/";
            scr_charface(7, "C");
            global.msg[8] = "* 好 吧 ^1， 也 许 你 对 排 汽 口&  的 看 法 还 是 &  有 一 点 正 确 的 。/";
            global.msg[9] = "\\EH* 但 只 有 一 点 。/%%";
            if (global.flag[213] == 1)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 干 得 好 ^2。&* 现 在 我 们 继 续 吧 。/%%";
                if (global.flag[427] == 1)
                {
                    scr_charface(0, "H");
                    global.msg[1] = "* 你 还 想 让 我 再 夸 夸 你 ^2？&  没 有 更 多 了 。/";
                    scr_cloface(2, 7);
                    global.msg[3] = "* 没 事 的 Frisk^1，&  让 我 来 夸 你 ！/";
                    global.msg[4] = "\\E1* 我 真 为 你 以 正 确 的 顺 序 &  按 下 了 这 些 按 钮 &  而 感 到 很 骄 傲 ！/";
                    scr_charface(5, 0);
                    global.msg[6] = "* 真 浪 费 时 间 。/%%";
                }
                if (global.flag[427] == 2)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 好 了 ^1， 就 先 到 这 吧 ！/%%";
                }
                if (global.flag[427] > 2)
                {
                    scr_cloface(0, 5);
                    global.msg[1] = "* 我 们 现 在 真 的 该 走 了 .../";
                    scr_charface(2, "H");
                    global.msg[3] = "* 如 果 你 不 介 意 的 话 .../%%";
                }
            }
            if (global.flag[213] == 2)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 我 真 的 以 为 你 会 因 为&  他 跳 过 谜 题 而 生 他 的 气 。/";
                scr_charface(2, "I");
                global.msg[3] = "* 嗯 ^1， 我 刚 刚 还 这 么 想 呢 。/";
                scr_cloface(4, 7);
                global.msg[5] = "* 然 后 呢 ？/";
                scr_charface(6, "C");
                global.msg[7] = "* 我 才 意 识 到 没 有 被 排 汽 口&  像 螺 旋 桨 一 样 吹 动 &  简 直 太 好 了 。/";
                scr_cloface(8, 5);
                global.msg[9] = "* 你 现 在 知 道 我 为 什 么&  恨 它 们 了 吧 ？/%%";
            }
            if (global.plot > 145)
            {
                scr_cloface(0, "P");
                global.msg[1] = "* 我 的 老 敌 人 ^2。 排 汽 口 。/";
                scr_charface(2, "C");
                global.msg[3] = "* 请 在 Clover开 始 喊 着&  让 它 们 别 挡 路 之 前 &  就 走 吧 。/";
                scr_cloface(4, "J");
                global.msg[5] = "* 我 可 不 会 被 它 们 阻 拦 ！/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "L");
                    global.msg[1] = "* 可 以 走 了 吗 ^1， Frisk？/";
                    scr_cloface(2, "J");
                    global.msg[3] = "* 那 些 该 死 的 排 汽 口 ^2！&* 它 们 以 为 它 们 是 谁 ？/";
                    scr_charface(4, "C");
                    global.msg[5] = "* 可 以 吗 ？/%%";
                }
            }
        }
        break;
    case room_fire_mewmew2:
        if (clover == 1)
        {
            if (global.flag[369] > 20)
            {
                scr_charface(0, "D");
                global.msg[1] = "* 从 未 有 人 错 的 这 么 离 谱 。/";
                scr_cloface(2, 8);
                global.msg[3] = "* 这 只 是 一 种 观 点 而 已 。/";
                scr_charface(4, 0);
                global.msg[5] = "* 你 确 实 可 以 有 一 个&  错 误 的 观 点 。/";
                scr_cloface(6, 6);
                global.msg[7] = "* 她 的 观 点 也 不 过 就 是 ...&* 你 知 道 的 .../";
                global.msg[8] = "\\E7* 很 主 观 ？/";
                scr_charface(9, "E");
                global.msg[10] = "* 然 而 ， 她 的 观 点&  客 观 来 看 就 是 错 误 的 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 但 我 同 意 ^2。&* 原 版 比 不 上 续 作 。 /";
                    scr_charface(2, 8);
                    global.msg[3] = "* 谢 谢 你 。 /";
                    scr_cloface(4, "I");
                    global.msg[5] = "* 不 过 ^1， 真 人 版 翻 拍&  是 最 好 的 。/";
                    scr_charface(6, "J");
                    global.msg[7] = "* 你 个 小 B -/%%";
                }
            }
            if (global.flag[368] == 1)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 我 感 觉 ...有 人 有 个&  糟 糕 的 主 意 。/";
                scr_cloface(2, 0);
                global.msg[3] = "* 嘿 你 什 么 意 思 ？/";
                scr_charface(4, "I");
                global.msg[5] = "* 我 不 到 啊 。/";
                global.msg[6] = "\\E0* 不 过 ， 手 机 关 闭 了 通 知&  的 确 让 我 松 了 口 气 。/%%";
            }
        }
        break;
    case room_fire_boysnightout:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 他 们 在 地 下 用 了&  很 多 蒸 汽 ^1， 不 是 吗 。/";
            global.msg[2] = "\\EA* 先 是 蒸 汽 工 厂 ^1，&  然 后 又 是 这 些 排 汽 口 .../";
            global.msg[3] = "\\E6* 现 在 这 边 又 是 ^1，&  蒸 汽 ..^2.管 道 ？/";
            scr_charface(4, 0);
            global.msg[5] = "* 它 们 被 称 为 烟 囱 -/";
            scr_cloface(6, 7);
            global.msg[7] = "* 蒸 汽 管 道 ^2。&  蒸 汽 的 主 要 特 点 &  都 有 些 什 么 ？/";
            scr_charface(8, 0);
            global.msg[9] = "* 不 会 对 地 下 产 生 &  永 久 性 污 染 &  的 可 再 生 资 源 。/";
            scr_cloface(10, 5);
            global.msg[11] = "* ...有 点 道 理 。/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 我 想 那 “ 蒸 ” 是 个 &  好 方 法 。/";
                scr_charface(2, 8);
                global.msg[3] = "* 那 当 然 ^1 ， 这 就 是 &  为 什 么 它 们 -/";
                global.msg[4] = "\\E3* .../";
                scr_cloface(5, "I");
                global.msg[6] = "* 怎 么 了 ^1， " + scr_gettext("obj_chara_5") + "^1?&* 我 说 什 么 了 吗 ？/";
                scr_charface(7, "D");
                global.msg[8] = "* 我 发 誓 ^1， 再 听 到 一 个&  双 关 语 ^1，我 就 会&  开 始 崩 .../";
                global.msg[9] = "\\EE* “ 蒸 ” 的 。/";
                scr_cloface(10, "B");
                global.msg[11] = "* ！ ！ ！ /%%";
            }
            if (global.flag[427] > 1)
            {
                scr_charface(0, "A");
                global.msg[1] = "* 你 又 不 是 这 里 唯 一 一 个&  可 以 说 双 关 的 人 。 /";
                scr_cloface(2, 7);
                global.msg[3] = "* 我 是 说 ^1， 我 能 理 解 ^1， &  但 是 .../";
                global.msg[4] = "\\E1* 我 从 没 想 过 &  你 也 会 说 双 关 ！/";
                scr_charface(5, "M");
                global.msg[6] = "* 而 我 打 算 确 保 你 &  永 远 别 再 说 双 关 。 /%%";
            }
            if (global.plot == 146)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 哇 ^1， 他 们 真 是 &  好 朋 友 啊 ！/";
                scr_charface(2, 8);
                global.msg[3] = "* 确 实 是 关 系 很 好 的 朋 友 。/";
                scr_cloface(4, 1);
                global.msg[5] = "* 他 们 其 实 是 兄 弟 ^2。&* 伙 计 。/";
                scr_charface(6, 8);
                global.msg[7] = "* 确 实 ^1， 你 说 得 对 。/";
                scr_cloface(8, 8);
                global.msg[9] = "* 说 真 的 ^1，&  我 为 他 们 感 到 高 兴 。/";
                scr_charface(10, "F");
                global.msg[11] = "* 我 同 意 。/%%";
                if (global.flag[427] >= 1)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 我 们 也 很 合 拍 ^1，&  不 是 吗 ？/";
                    global.msg[2] = "* 上 下 浮 动 ..^2.&* 相 互 碰 撞 .../";
                    scr_charface(3, "G");
                    global.msg[4] = "* 这 暗 示 着 .../";
                    scr_cloface(5, 6);
                    global.msg[6] = "* 没 什 么 ^4。&\\E7* 只 是 一 次 观 察 。/%%";
                    if (global.kills == 0)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* ^2.^2.^2./";
                        global.msg[2] = "\\E7* 说 句 题 外 话 ^1， &  你 喜 欢 吃 冰 淇 淋 吗 ^1，&  " + scr_gettext("obj_chara_5") + "?/";
                        scr_charface(3, 8);
                        global.msg[4] = "* 谁 会 不 喜 欢 呢 ？/";
                        scr_cloface(5, 1);
                        global.msg[6] = "* 是 的 ^2！&* 你 说 的 太 对 了 .../%%";
                    }
                }
            }
            if (global.flag[402] == 1)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../";
                scr_charface(2, 1);
                global.msg[3] = "* .../%%";
            }
        }
        break;
    case room_fire_newsreport:
        if (clover == 1)
        {
            if (instance_exists(obj_mettnewsevent))
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 现 在 我 们 来 打 个 赌 吧 ^2！&* 为 什 么 这 个 房 间 会 这 么 暗 ？/";
                global.msg[2] = "\\EA* A 选 项 ^1) &  因 为 Mettaton 在 这 ，/";
                global.msg[3] = "\\EB* B 选 项 ^1) &  因 为 Mettaton 在 这 ，/";
                global.msg[4] = "\\E1* 还 是 说 C 选 项 ^1) &  因 为 Mettaton 在 这 ！/";
                scr_charface(5, 8);
                global.msg[6] = "* 我 肯 定 会 选 D 选 项 ^1)&  因 为 Mettaton 在 这 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "C");
                    global.msg[1] = "* 你 ^1- 只 需 要 往 前 走 &  然 后 自 己 亲 眼 看 看 &  就 知 道 了 。/%%";
                }
                if (obj_mettnewsevent.con == 8)
                {
                    scr_cloface(0, "A");
                    global.msg[1] = "* 有 这 么 多 的 选 择 ..^1. &  但 你 只 能 选 一 个 。/";
                    global.msg[2] = "* 你 打 算 选 哪 一 个 呢 ？/";
                    scr_charface(3, 0);
                    global.msg[4] = "* 我 会 选 最 近 的 那 个 。/";
                    global.msg[5] = "\\EI* 但 是 我 ..^1.&  我 还 是 很 好 奇 &  都 有 些 什 么 的 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 0);
                        global.msg[1] = "* 我 不 好 奇 了 ^2。&* 别 浪 费 时 间 了 ，&  赶 紧 选 一 个 吧 。/";
                        scr_cloface(2, 7);
                        global.msg[3] = "* “ 我 是 整 个 西 部 &  最 有 耐 心 的 鬼 魂 。”/%%";
                    }
                }
                if (obj_mettnewsevent.con == 132)
                {
                    scr_cloface(0, "J");
                    global.msg[1] = "* 你 为 什 么 还 有 功 夫 &  跟 我 们 聊 天 ？ ！ ？/";
                    scr_charface(2, "J");
                    global.msg[3] = "* 快 把 炸 弹 拆 了 ，&  你 个 蠢 货 ！/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, "J");
                        global.msg[1] = "* 我 们 要 被 炸 死 了 ！/";
                        scr_charface(2, "J");
                        global.msg[3] = "* 别 浪 费 时 间 了 ！ ！ ！ ！/%%";
                    }
                }
            }
            if (global.plot > 160)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 我 得 提 一 嘴 ^1，&  关 于 我 们 以 为&  会 被 炸 死 的 那 段 ？/";
                global.msg[2] = "\\EH* 我 刚 才 确 实 被 吓 坏 了 。/";
                scr_charface(3, 0);
                global.msg[4] = "* 我 们 不 会 被 炸 死 的 。/";
                global.msg[5] = "\\E8* 毕 竟 我 们 可 是 鬼 魂 。/";
                scr_cloface(6, 7);
                global.msg[7] = "* 我 觉 得 确 实 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 不 过 ^1， 这 并 没 有 阻 止&  你 和 我 一 样 大 喊 大 叫 。/";
                    scr_charface(2, "C");
                    global.msg[3] = "* ...我 承 认 我 也 被 吓 到 了 。/%%";
                }
            }
        }
        break;
    case room_fire_spidershop:
        if (clover == 1)
        {
            scr_charface(0, "L");
            global.msg[1] = "* 不 是 说 东 西 卖 的 越 贵 &  它 的 质 量 就 越 好 .../";
            scr_cloface(2, 6);
            global.msg[3] = "* ...布 丁 就 是 个 &  很 好 的 例 子 。/";
            scr_charface(4, 0);
            global.msg[5] = "* 我 还 以 为 你 会 说&  \\EA“ 我 们 把 所 有 的 钱&  都 给 他 们 吧 ！ ”/";
            scr_cloface(6, 7);
            global.msg[7] = "* 至 少 这 次 不 会 的 。/";
            global.msg[8] = "\\E6* 我 能 意 识 到 自 己 被 骗 了 。&  至 于 她 ？/";
            global.msg[9] = "\\E9* 我 并 不 信 任 她 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "L");
                global.msg[1] = "* 我 很 好 奇 ^2。&* 你 是 怎 么 知 道 的 ？/";
                scr_cloface(2, 5);
                global.msg[3] = "* 看 看 那 个 家 伙 。/";
                global.msg[4] = "\\E6* 他 拿 着 那 个 甜 甜 圈 &  腿 都 在 哆 嗦 着 。/";
                global.msg[5] = "\\EP* 而 那 些 蜘 蛛 的 眼 睛 里&  没 有 一 丝 说 抱 歉 的 意 思 。/";
                scr_cloface(6, "A");
                global.msg[7] = "* 侦 探 Clover正 在 调 查 此 案 。/%%";
            }
            if (global.plot > 164)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 不 能 因 为 她 这 么 做 &  是 出 于 好 心 .../";
                global.msg[2] = "\\E6* 就 原 谅 她 的 做 法 。/";
                scr_charface(3, "I");
                global.msg[4] = "* 你 是 不 喜 欢 &  赚 更 多 的 钱 吗 ？/";
                scr_cloface(5, 5);
                global.msg[6] = "* .../";
                global.msg[7] = "\\E7* 我 不 会 那 样 做 的 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 5);
                    global.msg[1] = "* 强 迫 别 人 做 某 事 &  是 不 对 的 .../";
                    global.msg[2] = "\\E6* 仅 仅 是 因 为 &  你 想 让 他 们 去 做 。/";
                    scr_charface(3, 5);
                    global.msg[4] = "* .../";
                    global.msg[5] = "\\E7* 好 了 ， ‘ 大 善 人 ’ ^1，&  把 你 的 口 音 去 掉 。/";
                    scr_cloface(6, "J");
                    global.msg[7] = "* 我 可 没 有 什 么 口 音 ！/%%";
                }
            }
        }
        break;
    case room_fire_walkandbranch2:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 现 在 ^1， 我 已 经 见 过 了 &  很 多 奇 怪 的 交 通 工 具 。/";
            global.msg[2] = "* 走 路 的 船 ^1，&  会 飞 的 鲸 ^1，&  还 有 传 送 带 .../";
            global.msg[3] = "* 还 有 一 只 在 熔 岩 中&  游 泳 的 机 器 鳐 鱼 .../";
            scr_charface(4, "C");
            global.msg[5] = "* 什 么 ？ 没 听 清 。/";
            scr_cloface(6, 9);
            global.msg[7] = "* 但 是 这 里 的 排 汽 口 。/";
            global.msg[8] = "\\EE* 肯 定 是 最 不 实 用 的 方 式 。/";
            scr_charface(9, "C");
            global.msg[10] = "* ... 抛 开 什 么 鳐 鱼 不 谈 ^1，&  人 们 一 定 很 讨 厌 &  被 抛 在 空 中 旋 转 。/";
            global.msg[11] = "* 这 可 太 不 合 适 了 ^1，&  这 让 我 犯 恶 心 ^2。 &  而 我 又 是 个 鬼 魂 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 更 不 用 说 这 是 一 个&  名 副 其 实 的 排 汽 口 迷 宫 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* 起 初 我 虽 然 对 &  那 些 排 汽 口 很 恼 火 ，&  但 我 还 能 忍 受 得 了 。/";
                global.msg[4] = "\\E9* 现 在 ^1， 我 每 看 到 一 个 ^1，&  都 会 觉 得 很 反 胃 。/";
                global.msg[5] = "\\EJ* 而 我 甚 至 没 有 一 个 胃 ！/";
                scr_charface(6, 0);
                global.msg[7] = "* 好 了 好 了 ^1， Clover.../";
                global.msg[8] = "* 会 ..^1.有 ..^1.的 .../";
                global.msg[9] = "\\EC* ...我 有 点 害 怕 。/%%";
            }
        }
        break;
    case room_fire_conveyorlaser:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 我 们 穿 过 的 &  传 送 带 越 多 .../";
            global.msg[2] = "\\EC* 当 他 们 决 定 取 消 &  传 送 带 税 的 时 候 ，&  我 就 会 越 高 兴 。/";
            scr_cloface(3, 6);
            global.msg[4] = "* 还 有 传 送 带 税 ？/";
            scr_charface(5, "L");
            global.msg[6] = "* 哦 你 这 个 天 真 无 邪 的 &  小 朋 友 啊 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 等 等 ^1， 你 认 真 的 ？/";
                scr_charface(2, "B");
                global.msg[3] = "* 别 让 我 提 雪 球 税 了 。/";
                if (global.flag[469] > 0)
                {
                    scr_cloface(4, 5);
                    global.msg[5] = "*…没 错 ， 那 确 实 有 点 &  离 谱 了 。/%%";
                }
                else
                {
                    scr_cloface(4, 6);
                    global.msg[5] = "* 雪 球 税 ?/";
                    scr_charface(6, "J");
                    global.msg[7] = "* 我 刚 说 了 别 让 我 提 ！/%%";
                }
            }
        }
        break;
    case room_fire_preshootguy4:
        if (clover == 1)
        {
            scr_charface(0, 3);
            global.msg[1] = "* 怎 么 ^1， 你 想 和 我 们 &  “ 交 谈 ” ？/";
            global.msg[2] = "\\E0* 真 的 没 什 么 可 聊 的 。/";
            scr_cloface(3, 7);
            global.msg[4] = "* 当 然 有 ^2！ 就 比 如 ^1， &  那 里 的 入 口 ！ /";
            scr_charface(5, 0);
            global.msg[6] = "* 哇 ^2。 那 实 在 是 太 酷 了 。 /";
            scr_cloface(7, "D");
            global.msg[8] = "* 你 为 什 么 这 么 着 急 着 &  去 评 判 .../%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 你 知 道 吗 ^1， 我 一 直 想 问 。 /";
                global.msg[2] = "\\E5* 为 什 么 你 每 次 都&  像 那 样 说 “ 交 谈 ” ？/";
                global.msg[3] = "\\E8* 明 明 有 一 种&  更 友 善 的 方 法 来 问 的 。/";
                scr_charface(4, 0);
                global.msg[5] = "* 因 为 他 并 没 有 别 的 选 项 。 /";
                scr_cloface(6, 6);
                global.msg[7] = "* 他 当 然 有 了 。 /";
                scr_charface(8, 8);
                global.msg[9] = "* 菜 单 只 给 了 他 一 个 选 项 。 /";
                scr_cloface(10, 5);
                global.msg[11] = "* 菜 单 ？ /";
                scr_charface(12, "A");
                global.msg[13] = "* 我 已 经 说 的 够 多 了 。 /%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = scr_gettext("obj_chara_0") + "^2？ 你 是 什 么 意 思 ？/";
                scr_charface(2, "H");
                global.msg[3] = "* 你 不 会 懂 的 。/%%";
            }
        }
        break;
    case room_fire_savepoint2:
        if (clover == 1)
        {
            if (global.plot < 165)
            {
                scr_cloface(0, "I");
                global.msg[1] = "* 别 告 诉 我 你 被 吓 ---到 了 。/";
                global.msg[2] = "\\E6* ..^2.你 说 你 从 来&  没 被 吓 到 过 ？/";
                global.msg[3] = "\\E7* 实 话 说 ^1， 我 信 了 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 9);
                    global.msg[1] = "* 他 那 么 勇 敢 &  还 有 什 么 能 阻 碍 得 了 他 呢 ？/%%";
                }
            }
            if (global.flag[19] < 22)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 嘿 ^1！ 我 认 识 这 里 ！/";
                global.msg[2] = "\\E0* 看 来 蜘 蛛 们 的 建 筑 工 程&  已 经 完 成 了 。/";
                scr_charface(3, 9);
                global.msg[4] = "* 你 正 径 直 走 向 野 兽 的 巢 穴 。/";
                scr_cloface(5, 0);
                global.msg[6] = "* 你 会 没 事 的 ^1。&\\E1* 我 相 信 你 ， 伙 伴 ！/";
                scr_charface(7, 9);
                global.msg[8] = "* 祝 你 好 运 。/%%";
                global.flag[19] = 22;
                global.flag[427] -= 1;
                with (obj_cloverchara)
                {
                    instance_destroy();
                }
            }
        }
        break;
    case room_fire_spider:
        if (clover == 1)
        {
            if (global.plot < 165)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 里 ..^2.好 阴 暗 .../";
                scr_charface(2, "L");
                global.msg[3] = "* .../";
                global.msg[4] = "* 你 有 没 有 听 到 什 么 声 音 ？/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 等 等 ^1， 当 我 没 说 。/";
                    global.msg[2] = "* 我 的 确 听 到 了 很 多 东 西 。/";
                    scr_cloface(3, 9);
                    global.msg[4] = "* ...我 觉 得 我 也 听 到 了 。/%%";
                }
                if (obj_spidertalkevent.con > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 看 来 我 们 又 遇 到 &  新 的 敌 人 了 。/";
                    global.msg[2] = "* 你 最 好 小 心 行 事 。/";
                    global.msg[3] = "* 我 不 觉 得 这 一 次 &  我 们 可 以 逃 跑 的 了 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 9);
                        global.msg[1] = "* 除 非 你 有 一 个 击 分 卡 。/";
                        scr_cloface(2, "H");
                        global.msg[3] = "* 击 分 卡 能 有 什 么 用 ？？？/%%";
                    }
                    if (global.flag[220] == 0.1 || global.flag[220] == 1.1)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* 那 个 声 音 .../";
                        global.msg[2] = "\\E7* 我 们 之 前 没 听 到 过 吗 ？/%%";
                        if (global.flag[427] > 0)
                        {
                            scr_cloface(0, 7);
                            global.msg[1] = "* 哦 ^1， 我 真 想 给 那 个 骗 子&  一 点 颜 色 瞧 瞧 。/%%";
                        }
                    }
                }
            }
            if (global.plot >= 165)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 明 白 她 想 要 ^1，&  你 知 道 的 ^2。 吃 了 你 。/";
                global.msg[2] = "\\E7* 但 她 的 宠 物 ...&  也 太 可 爱 了 吧 。/";
                scr_charface(3, 0);
                global.msg[4] = "* 那 就 是 一 只 巨 大 的 &  肉 食 性 松 饼 蜘 蛛 。/";
                scr_cloface(5, 7);
                global.msg[6] = "* 什 么 ？/";
                scr_charface(7, "A");
                global.msg[8] = "* 那 当 然 挺 可 爱 的 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 你 觉 得 你 能 不 能 ..^2. &  再 请 求 看 一 看 那 只 宠 物 ？/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 我 不 得 不 认 同 &  Clover 的 想 法 。/";
                    global.msg[4] = "\\E8* ...我 想 摸 摸 它 。/";
                    scr_cloface(5, 2);
                    global.msg[6] = "* 谁 不 想 呢 ？！/%%";
                }
                if (global.flag[220] == 2 || global.flag[220] == 2.1)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* 这 真 的 奏 效 了 吗 ？/";
                    global.msg[2] = "\\EI* 嗯 ^1， 我 想 这 当 然&  没 什 么 可 抱 怨 的 。/";
                    scr_cloface(3, 7);
                    global.msg[4] = "* 有 付 出 就 会 有 回 报 。/";
                    global.msg[5] = "\\E1* 我 想 这 是 一 个 &  很 好 的 结 果 ！/%%";
                    if (global.flag[220] == 2.1)
                    {
                        global.msg[5] = "\\E1* 我 猜 这 是 好 的 回 报 ！/";
                        global.msg[6] = "\\E5* 尽 管 那 在 遗 迹 中&  可 能 连 “ 一 件 小 事 ” &  都 算 不 上 .../";
                        global.msg[7] = "\\EA* 但 要 多 于 .../";
                        scr_charface(8, 8);
                        global.msg[9] = "* 企 业 垄 断 ？/";
                        scr_cloface(10, "H");
                        global.msg[11] = "* 那 个 。/%%";
                    }
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, "D");
                        global.msg[1] = "* 可 她 要 杀 了 我 们 ，&  这 让 我 很 生 气 。/";
                        scr_charface(2, 8);
                        global.msg[3] = "* 这 点 我 十 分 同 意 。/%%";
                        if (global.flag[220] == 2.1)
                        {
                            scr_cloface(0, 1);
                            global.msg[1] = "* 不 过 ^1， 至 少 这 是 为 了&  支 持 一 项 慈 善 事 业 ！/";
                            scr_charface(2, 0);
                            global.msg[3] = "* 除 非 他 们 在 虚 假 宣 传 。/";
                            scr_cloface(4, "Q");
                            global.msg[5] = "* 不 过 ^1， 至 少 这 是 为 了&  支 持 一 项 慈 善 事 业 ！/";
                            scr_charface(6, "N");
                            global.msg[6] = "* 是 的 ^1， 是 的 ^2！&* 慈 善 事 业 ！/%%";
                        }
                    }
                }
                if (global.flag[59] >= 9000)
                {
                    scr_cloface(0, "G");
                    global.msg[1] = "* .../";
                    scr_charface(2, "C");
                    global.msg[3] = "* .../";
                    scr_cloface(4, "C");
                    global.msg[5] = "* 那 真 是 太 -%";
                    scr_charface(6, "A");
                    global.msg[7] = "* 这 是 我 们 应 得 的 。/%%";
                }
                if (global.flag[397] != 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 她 可 确 实 是 &  想 杀 了 我 们 的 。/";
                    global.msg[2] = "* 那 很 明 显 算 是 自 我 防 卫 。/";
                    global.msg[3] = "* 还 有 ..^2. 就 是 .../";
                    global.msg[4] = "\\E3* .../";
                    global.msg[5] = "* 她 也 有 自 己 的 家 庭 。/";
                    global.msg[6] = "* .../%%";
                    if (global.flag[427] == 1)
                    {
                        scr_charface(0, 0);
                        global.msg[1] = "* 别 把 那 放 在 心 上 ^1， &  Frisk./";
                        global.msg[2] = "* 你 不 必 为 杀 了 她 而 负 责 。/";
                        scr_cloface(3, 9);
                        global.msg[4] = "* 是 啊 .../ " + scr_gettext("obj_chara_5") + "是 对 的 。/";
                        global.msg[5] = "* 我 想 是 的 。/%%";
                    }
                    if (global.flag[427] > 1)
                    {
                        scr_cloface(0, 9);
                        global.msg[1] = "* 我 们 能 走 了 吗 ？/%%";
                    }
                    if (global.kills > 30)
                    {
                        scr_cloface(0, "F");
                        global.msg[1] = "* 我 不 关 心 她 有 &  多 想 杀 了 我 们 。/";
                        global.msg[2] = "* 你 刚 刚 让 这 几 百 只 &  有 感 情 的 生 物 &  失 去 了 它 们 的 领 袖 。/";
                        global.msg[3] = "* 对 它 们 来 说 ，&  她 甚 至 可 能 不 仅 仅 &  是 位 领 袖 那 么 简 单 。/";
                        global.msg[4] = "* 希 望 你 以 后 做 得 更 好 点 。/%%";
                        if (global.flag[427] == 1)
                        {
                            scr_charface(0, 0);
                            global.msg[1] = "* 我 …/";
                            global.msg[2] = "\\EL* 你 应 该 再 努 力 一 点&  去 谈 判 。/";
                            global.msg[3] = "\\E0* 没 有 领 袖 的 群 体 .../";
                            global.msg[4] = "\\EL* 只 会 是 一 潭 死 水 。/%%";
                        }
                        if (global.flag[427] > 1)
                        {
                            scr_cloface(0, "F");
                            global.msg[1] = "* 离 开 这 里 吧 。/";
                            global.msg[2] = "* 我 不 想 再 在 这 里 &  多 待 任 何 一 秒 了 。/%%";
                        }
                    }
                }
            }
        }
        break;
    case room_fire_pacing:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 一 份 Mettaton的 海 报 ？/";
            global.msg[2] = "\\EC* 挺 漂 亮 的 。/";
            scr_charface(3, 0);
            global.msg[4] = "* 看 样 子 我 们 刚 出 了 煎 锅 ^1，&  就 又 得 进 火 坑 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 做 好 准 备 ^2。&  我 们 也 不 知 道&  接 下 来 会 发 生 什 么 。/%%";
            }
            if (global.plot > 166)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 我 想 把 它 撕 下 来 的 想 法 &  是 不 是 不 对 的 ？/";
                scr_charface(2, 8);
                global.msg[3] = "* 嘿 ^1， 我 刚 才 也 是 &  这 么 想 的 ！/%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 但 是 ^1， 那 样 算 是 &  故 意 破 坏 公 物 。/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 那 倒 没 错 。/";
                    scr_cloface(4, 1);
                    global.msg[5] = "* .../";
                    global.msg[6] = "\\EQ* Frisk 求 你 把 它 撕 了 吧 &  我 真 的 求 求 你 了 &  求 你 了 求 你 了 求 你 了 。/%%";
                    if (global.flag[29] < 0.1)
                    {
                        global.flag[29] = 0.1;
                    }
                }
                if (global.flag[427] > 1)
                {
                    scr_cloface(0, "J");
                    global.msg[1] = "* 求 你 撕 了 它 ！！！/%%";
                }
                if (global.flag[29] == 0.2)
                {
                    scr_cloface(0, "J");
                    global.msg[1] = "* 别 那 样 笑 话 我 了 ，&  赶 紧 把 它 撕 了 ！/%%";
                }
                if (global.flag[29] == 1)
                {
                    scr_cloface(0, 2);
                    global.msg[1] = "* 哇 哈 哈 哈 哈 哈 哈 哈 ！/";
                    scr_charface(2, 8);
                    global.msg[3] = "* 很 愉 快 ^1， 又 肆 无 忌 惮 的 &  破 坏 。/";
                    global.msg[4] = "* 我 允 许 你 这 么 做 。/";
                    scr_cloface(5, 6);
                    global.msg[6] = "* ...你 为 什 么 仅 仅 只 是 &  这 么 评 价 它 ？/";
                    scr_charface(7, 0);
                    global.msg[8] = "* 你 ..^1. 说 得 对 ^2。&* 我 道 歉 。/";
                    global.msg[9] = "\\EK* 把 那 海 报 给 我 撕 了 ！！！/";
                    scr_cloface(10, 2);
                    global.msg[11] = "* 把 那 海 报 给 我 撕 了 ！！！/%%";
                }
                if (global.flag[29] == 2)
                {
                    scr_cloface(0, 1);
                    global.msg[1] = "* 真 是 段 有 趣 的 时 光 。/";
                    scr_charface(2, 8);
                    global.msg[3] = "* 真 是 段 有 趣 的 时 光 。/%%";
                }
            }
            if (global.plot > 197)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 之 前 有 点 想 把 它 撕 下 来 。/";
                global.msg[2] = "* 但 ...我 现 在 不 想 了 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 我 猜 当 你 与 某 人 共 情 时 ，&  要 恨 他 们 更 难 。/";
                    global.msg[2] = "\\EE* 我 ^1， 说 实 话 ^1， 还 是 会&  把 它 撕 了 ， &  仅 仅 是 为 了 好 玩 。/";
                    scr_cloface(3, "D");
                    global.msg[4] = "* 我 们 不 撕 它 。/%%";
                }
                if (global.flag[29] == 0.1 || global.flag[29] == 0.2)
                {
                    scr_cloface(0, 0);
                    global.msg[1] = "* 感 谢 你 没 有 听 我 的 话 ^2。&* 关 于 整 个 .../";
                    global.msg[2] = "\\E5* 撕 掉 海 报 什 么 的 。/";
                    global.msg[3] = "\\E8* 我 可 能 会 对 此 &  感 到 很 愧 疚 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 9);
                        global.msg[1] = "* 我 是 肯 定 不 会 &  感 到 愧 疚 的 。/";
                        scr_cloface(2, "C");
                        global.msg[3] = "* 那 就 是 为 什 么 &  我 在 感 谢 他 ^1，&  但 不 感 谢 你 。/%%";
                    }
                }
                if (global.flag[29] == 2)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 我 感 觉 ...这 么 做 &  还 是 不 太 好 。/";
                    scr_charface(2, "H");
                    global.msg[3] = "\\E8* 就 算 你 现 在 感 觉 &  不 一 样 了 ^1， 当 时 也&  挺 有 意 思 的 ， 不 是 吗 ？/";
                    scr_cloface(4, 0);
                    global.msg[5] = "* 是 啊 ^2。 确 实 如 此 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 9);
                        global.msg[1] = "* 你 不 后 悔 吗 ？/";
                        scr_cloface(2, 6);
                        global.msg[3] = "* 是 有 点 后 悔 。/";
                        global.msg[4] = "\\E7* 但 那 还 是 很 有 趣 。/";
                        scr_charface(5, 8);
                        global.msg[6] = "* 这 才 对 嘛 。/%%";
                    }
                }
            }
        }
        break;
    case room_fire_operatest:
        if (clover == 1)
        {
            scr_charface(0, "C");
            global.msg[1] = "* 我 感 觉 ...&  有 一 场 表 演 即 将 到 来 。/";
            scr_cloface(2, 5);
            global.msg[3] = "* 太 棒 了 ^2。 &  我 真 的 很 期 待 。/%%";
            if (global.plot > 166)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 多 么 好 的 一 个 地 方 。/";
                global.msg[2] = "\\E3* 我 觉 得 这 是 临 时 弄 出 来 &  纯 粹 为 了 应 付 我 们 的 。/";
                scr_cloface(3, 5);
                global.msg[4] = "* “ 应 付 ？ ”/";
                scr_charface(5, 7);
                global.msg[6] = "* 你 知 道 我 什 么 意 思 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 但 并 不 ， 我 想 Mettaton&  早 在 我 们 到 达 之 前&  就 准 备 好 了 这 个 地 方 。/";
                    global.msg[2] = "* 如 果 他 临 时 再 换 的 话 ^1， &  那 样 就 会 /";
                    global.msg[3] = "* 太 贵 了 。/";
                    scr_charface(4, 0);
                    global.msg[5] = "* 你 的 文 本 框 管 理 真 糟 糕 ^1，&  Clover 。/";
                    scr_cloface(6, 6);
                    global.msg[7] = "\\E1* 什 么 ？ /";
                    scr_charface(8, 8);
                    global.msg[9] = "* 怎 么 了 ？ /%%";
                }
            }
        }
        break;
    case room_fire_multitile:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 他 没 指 望 我 们 能&  解 决 这 个 谜 题 ^1，对 吧 ？/";
            scr_charface(2, 0);
            global.msg[3] = "* 我 怀 疑 他 的 确 没 指 望 过 。/";
            global.msg[4] = "\\EA* 但 如 果 让 我 来 的 话 &  我 肯 定 能 解 决 的 。/";
            scr_cloface(5, "C");
            global.msg[6] = "* 是 的 ^1， 没 错 ^2。&* 你 别 逗 我 了 。/";
            scr_charface(7, "E");
            global.msg[8] = "* 我 可 以 重 述 所 有 的 &  谜 题 规 则 来 证 明 &  我 说 的 话 。/%%";
            if (global.flag[471] == 1)
            {
                global.msg[8] = "* 我 可 以 重 述 所 有 的 &  谜 题 规 则 来 证 明 &  我 说 的 话 。/";
                scr_cloface(9, "P");
                global.msg[10] = "* 你 不 是 说 你 后 面 没 听 吗 ？/";
                scr_charface(11, "A");
                global.msg[12] = "* 我 使 用 了 一 种 古 老 的 技 术 。/";
                scr_cloface(13, 1);
                global.msg[14] = "* 哦 ！ 哦 ^1 ！ 我 知 道 &  你 说 的 是 什 么 ！/";
                global.msg[15] = "\\EA* 那 是 不 是 叫 ^1，&  心 灵 宫 殿 ？/";
                scr_charface(16, "E");
                global.msg[17] = "* 撒 谎 ^1， Clover^2。&* 这 叫 撒 谎 。/%%";
            }
            if (global.flag[219] == 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 说 实 话 ，&  我 到 现 在 都 很 难 相 信 &  你 居 然 还 都 记 得 。/";
                scr_charface(2, "E");
                global.msg[3] = "* 如 果 一 块 蓝 色 的 砖 块 &  紧 挨 着 一 块 黄 色 的 砖 块 ^1， &  你 就 会 触 电 。/";
                scr_cloface(4, "P");
                global.msg[5] = "* 你 居 然 还 在 说 。/";
                scr_charface(6, 8);
                global.msg[7] = "* 紫 色 的 地 砖 很 滑 。/%%";
                if (global.flag[471] == 1)
                {
                    global.msg[7] = "* 紫 色 的 地 砖 很 滑 。/";
                    scr_cloface(8, "P");
                    global.msg[9] = "* 你 不 是 说 你 后 面 没 听 吗 ？/";
                    scr_charface(10, "A");
                    global.msg[11] = "* 我 使 用 了 一 种 古 老 的 技 术 。/";
                    scr_cloface(12, 1);
                    global.msg[13] = "* 哦 ！ 哦 ^1 ！ 我 知 道 &  你 说 的 是 什 么 ！/";
                    global.msg[14] = "\\EA* 那 是 不 是 叫 ^1，&  心 灵 宫 殿 ？/";
                    scr_charface(15, "E");
                    global.msg[16] = "* 撒 谎 ^1， Clover^2。&* 这 叫 撒 谎 。/%%";
                }
                if (global.flag[477] > 0)
                {
                    global.msg[7] = "* 紫 色 的 地 砖 很 光 ^2-&\\EJ  湿 滑 ！/";
                    scr_cloface(8, "I");
                    global.msg[9] = "* 呵 。/%%";
                }
            }
            if (global.flag[278] == 1)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 好 吧 ^1， 你 到 底 是 怎 么 &  记 得 住 这 所 有 的 规 则 的 ？/";
                global.msg[2] = "* 那 也 太 多 了 ^1， 而 且 &  都 过 这 么 久 了 ^1，&  还 有 。/";
                global.msg[3] = "* 你 到 底 是 怎 么 做 到 的 ？ ？ ？/";
                scr_charface(4, 8);
                global.msg[5] = "* 这 没 有 那 么 难 。/";
                global.msg[6] = "\\EL* 这 确 实 是 有 可 能 &  能 通 过 的 .../";
                global.msg[7] = "\\E0* 嗯 。/";
                global.msg[8] = "\\E3* 或 许 我 们 的 搭 档&  有 自 己 的 秘 密 。/";
                scr_cloface(9, 9);
                global.msg[10] = "* 你 是 什 么 意 思 ？/";
                scr_charface(11, "L");
                global.msg[12] = "* ...对 不 起 ^2。&  别 理 我 的 胡 思 乱 想 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 嘿 ^1， 等 等 .../";
                global.msg[2] = "* 这 个 地 方 以 前 是 个 舞 池 ^1，&  对 吧 ？/";
                scr_charface(3, 1);
                global.msg[4] = "* 你 看 我 干 什 么 ^2？ &  我 不 知 道 你 在 说 什 么 。/";
                scr_cloface(5, 6);
                global.msg[6] = "* 哈 ^2。 我 猜 ..^2. &  这 里 早 就 变 了 。/";
                scr_charface(7, 1);
                global.msg[8] = "* ..^2.确 实 如 此 。/%%";
                if (global.flag[219] == 1)
                {
                    scr_charface(0, "A");
                    global.msg[1] = "* 紫 色 的 砖 块 闻 起 来 &  也 挺 像 柠 檬 的 。/";
                    scr_cloface(2, "J");
                    global.msg[3] = "* 这 个 谜 题 已 经 结 束 了 ！/%%";
                }
            }
            if (instance_exists(obj_multitileevent))
            {
                scr_cloface(0, "J");
                global.msg[1] = "* 怎 么 可 能 有 人 &  能 记 得 住 这 个 呢 ？/";
                global.msg[2] = "* 我 一 想 到 那 些 东 西 &  就 头 疼 的 不 行 ！/";
                scr_charface(3, "H");
                global.msg[4] = "* 红 色 的 砖 块 不 能 通 过 。/";
                global.msg[5] = "* 黄 色 的 砖 块 会 让 你 触 电 。/";
                scr_cloface(6, "B");
                global.msg[7] = "* !/";
                scr_charface(8, 9);
                global.msg[9] = "* 如 果 你 踩 上 绿 色 的 砖 块 ^1， &  你 会 ^2-%";
                scr_cloface(10, "J");
                global.msg[11] = "* 我 们 可 没 时 间 &  说 这 些 了 ！/%%";
                global.flag[219] = 1;
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "A");
                    global.msg[1] = "* 橙 色 的 砖 块 是 橘 子 味 的 。/";
                    global.msg[2] = "* 如 果 你 不 是 橘 子 味 的 ，&  你 就 能 滑 过 蓝 色 的 砖 块 。/";
                    global.msg[3] = "* 否 则 食 人 鱼 就 会 阻 止 你 。/";
                    scr_cloface(4, "D");
                    global.msg[5] = "* 别 搁 那 炫 耀 了 。/%%";
                }
            }
        }
        break;
    case room_fire_hotelfront_1:
        if (clover == 1)
        {
            if (global.flag[19] == 25)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 还 好 我 们 中 有 个 人&  将 它 探 索 完 了 。/%%";
            }
            if (global.flag[19] < 25)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 我 真 怀 念 这 里 。/";
                global.msg[2] = "\\E8* 那 你 呢 ？/";
                scr_charface(3, 0);
                global.msg[4] = "* 我 在 热 域&  待 的 时 间 不 长 ^1。&  \\E1我 对 它 也 没 什 么 感 情 。/";
                scr_cloface(5, 0);
                global.msg[6] = "* 是 的 ， 我 几 乎 跳 过 了&  瀑 布 和 热 域 。/";
                scr_charface(7, 0);
                global.msg[8] = "* 对 ^1， &  你 走 过 的 那 条 路 很 曲 折 。/";
                scr_cloface(9, 7);
                global.msg[10] = "* 你 可 以 说 我 走 了 一 条&  风 景 优 美 的 路 线 。/";
                scr_charface(11, "E");
                global.msg[12] = "* 令 人 难 以 置 信 的&  不 必 要 的 复 杂 的 路 线 。/%%";
                global.flag[19] = 25;
                global.flag[427] -= 1;
                with (obj_cloverchara)
                {
                    instance_destroy();
                }
            }
        }
        break;
    case room_fire_hotelfront_2:
        if (clover == 1)
        {
            if (global.flag[19] == 26)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 只 揍 一 次 就 够 了 。/";
                global.msg[2] = "\\EK* 作 为 对 他 的 招 待 。/";
                scr_charface(3, 8);
                global.msg[4] = "* 你 花 在 那 朵 花 上&  的 时 间 太 长 了 。/%%";
                if (global.lv > 7)
                {
                    scr_charface(0, 3);
                    global.msg[1] = "* 他 似 乎 有 个 诀 窍 ，&  能 把 他 的 脸 全 涂 满 。/";
                    global.msg[2] = "* 真 悲 伤 。/%%";
                }
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 我 不 明 白 你 为 什 么 &  还 停 留 在 这 里 。/";
                    global.msg[2] = "* 这 里 没 什 么 东 西 。/";
                    scr_cloface(3, 6);
                    global.msg[4] = "* 除 了 那 条 向 右 边 的&  小 巷 子 ^1。/%%";
                    if (instance_exists(obj_sans_prefinaldate))
                    {
                        scr_cloface(3, 7);
                        global.msg[4] = "* ...对 吗 ？/";
                        scr_charface(5, 3);
                        global.msg[6] = "* 是 啊 。/%%";
                    }
                }
            }
            else if (instance_exists(obj_sans_prefinaldate))
            {
                scr_charface(0, 3);
                global.msg[1] = "* (如 果 你 忽 略 他 ^1，&  他 就 不 存 在 。 )/";
                scr_cloface(2, "I");
                global.msg[3] = "* 谁 ^1， Sans^1？ 那 个 骷 髅 ^1？&* 站 在 那 的 那 个 ？/";
                scr_charface(4, "D");
                global.msg[5] = "* ...我 讨 厌 你 。/%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 0);
                    global.msg[1] = "* 你 应 该 在 他 问 你&  你 在 干 啥 前 停 下 来 。/";
                    scr_sansface(2, 1);
                    global.msg[3] = "* 你 额 ^1， 在 那 干 什 么 呢 ^1，&  孩 子 ？/";
                    scr_cloface(4, "G");
                    global.msg[5] = "* .../";
                    scr_charface(6, "E");
                    global.msg[7] = "* 他 永 远 也 不 知 道&  为 什 么 这 很 有 趣 。/%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 不 但 认 真 的 ^1，&  停 下 来 。/%%";
                }
            }
            if (global.flag[19] < 26)
            {
                scr_cloface(0, "E");
                global.msg[1] = "* 什 么 ？/";
                global.msg[2] = "\\EF* 嘿 .../";
                global.msg[3] = "* 你 要 是 找 到 了 Mettaton.../";
                global.msg[4] = "\\E1* 替 我 把 他 揍 一 顿 。/%%";
                if (global.lv > 7)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 呃 。/";
                    global.msg[2] = "\\E6* Mettaton的 确 ..^1.&  “ 重 新 装 修 ” 了 这 个 地 方 ^1，&  不 是 吗 ？/%%";
                }
                with (obj_cloverchara)
                {
                    instance_destroy();
                }
                global.flag[19] = 26;
                global.flag[427] -= 1;
            }
        }
        break;
    case room_fire_hotellobby:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 和 我 上 次 来 的 时 候 相 比 ^1，&  这 地 方 没 有 太 大 的 变 化 。/";
            global.msg[2] = "\\EP* 如 果 你 忽 略 房 间 里 那 只&  Mettaton形 状 的 大 象 的 话 。/";
            scr_charface(3, 8);
            global.msg[4] = "* .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 商 店 也 上 新 了 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 我 想 ^1， 这 是 他 们 在 进 行 &  品 牌 重 塑 。/";
                scr_cloface(4, "H");
                global.msg[5] = "* 是 啊 。/%%";
            }
        }
        break;
    case room_fire_restaurant:
        if (clover == 1)
        {
            if (instance_exists(obj_ghostint))
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 我 们 在 这 边 ！/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "G");
                    global.msg[1] = "* 我 们 在 桌 子 这 边 ^1，&  你 应 该 知 道 吧 ？/%%";
                }
            }
            else
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 里 所 有 的 桌 子 &  都 没 有 配 椅 子 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 你 知 道 怪 物 是&  多 种 多 样 、 形 态 各 异 的 ^1，&  对 吧 ？/";
                scr_cloface(4, 0);
                global.msg[5] = "* 有 的 怪 物 的 形 状 和 大 小 &  也 需 要 坐 椅 子 。/";
                scr_charface(6, 8);
                global.msg[7] = "* 你 说 到 点 子 上 了 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 为 了 完 全 了 解 你 .../";
                    global.msg[2] = "\\E8* 我 刚 才 是 故 意 在 唱 反 调 ，&  想 要 惹 你 生 气 。/";
                    global.msg[3] = "* 椅 子 的 缺 失 ^1， 还 有 &  商 业 的 常 识 开 始 让 我 &  有 点 头 晕 了 。/";
                    scr_cloface(4, "J");
                    global.msg[5] = "* 我 知 道 ^1！ 我 真 的 &  不 知 道 这 是 出 于 &  什 么 原 因 ！/%%";
                }
                if (global.flag[219] > 0.5)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* .../";
                    scr_cloface(2, "B");
                    global.msg[3] = "* .../";
                    global.msg[4] = "\\EJ* 难 怪 椅 子 都 不 见 了 。/";
                    scr_charface(5, 8);
                    global.msg[6] = "* 突 然 间 一 切 都 说 得 通 了 。/";
                    scr_cloface(7, "J");
                    global.msg[8] = "* 那 个 贪 婪 ^1， 爱 财 ^1， &  粘 滑 ^1-%";
                    scr_charface(9, "C");
                    global.msg[10] = "* (我 们 快 走 吧 ^1， Frisk 。)/";
                    scr_cloface(11, "E");
                    global.msg[12] = "* 愚 蠢 ^1， 缺 乏 同 情 心 的 -/%%";
                    global.flag[219] = 2;
                    if (global.flag[427] == 1)
                    {
                        scr_cloface(0, "J");
                        global.msg[1] = "* 如 果 他 认 为 他 能 &  侥 幸 的 逃 脱 ， 那 他 就 &  大 错 特 错 了 。/";
                        scr_charface(2, "D");
                        global.msg[3] = "* 你 能 安 静 点 吗 ？/";
                        scr_cloface(4, "J");
                        global.msg[5] = "* 简 直 是 废 物 ^1，垃 圾 ^1， &  我 要 让 他 接 受 惩 罚 ！/%%";
                    }
                    if (global.flag[427] > 1)
                    {
                        scr_charface(0, "D");
                        global.msg[1] = "* 我 说 的 &  “ 我 们 快 走 吧 ”&  你 是 听 不 懂 吗 ？！/";
                        scr_cloface(2, "J");
                        global.msg[3] = "* 他 不 可 能 就 这 样 逃 走 ！ ！ ！ /%%";
                    }
                }
                if (global.flag[219] == 0.5)
                {
                    scr_cloface(0, "B");
                    global.msg[1] = "* 那 ..^2. 太 贪 婪 了 ^2。&  自 己 预 约 椅 子 ？！？/";
                    scr_charface(2, "H");
                    global.msg[3] = "* 又 一 次 。/";
                    scr_cloface(4, "J");
                    global.msg[5] = "* 他 对 普 通 人&  就 没 有 同 情 心 吗 ？/";
                    scr_charface(6, 8);
                    global.msg[7] = "* 这 像 是 一 家 高 档 餐 厅 。/";
                    scr_cloface(8, "P");
                    global.msg[9] = "* 你 见 过 一 家 餐 厅 需 要 &  你 自 己 预 约 椅 子 的 吗 ？！？/";
                    scr_charface(10, 0);
                    global.msg[11] = "* ..^2.\\EC没 有 回 应 。/";
                    scr_cloface(12, "J");
                    global.msg[13] = "* 你 当 然 没 有 ！/";
                    global.msg[14] = "* 这 太 离 谱 了 ^1， &  如 果 有 人 试 过 的 话 .../";
                    global.msg[15] = "* 我 说 ^2。&* 他 会 被 嘲 笑 的 ！！！/";
                    scr_charface(16, "C");
                    global.msg[17] = "* (我 们 快 走 吧 ^1， Frisk 。)/";
                    global.flag[219] = 2;
                }
            }
        }
        break;
    case room_fire_hoteldoors:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 虽 然 我 ...并 不 算 是 &  Mettaton 的 头 号 粉 丝 .../";
            scr_charface(2, 8);
            global.msg[3] = "* (轻 哼 。 )/";
            scr_cloface(4, 7);
            global.msg[5] = "* 我 必 须 承 认 ^1， 这 个 地 方 &  被 打 理 的 一 尘 不 染 。/";
            global.msg[6] = "* 这 地 板 也 太 干 净 了 吧 ！/";
            global.msg[7] = "* 当 然 ， 我 没 有 一 个&  很 好 的 参 考 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 你 是 没 去 过 酒 店 ？/";
                scr_cloface(2, 6);
                global.msg[3] = "* 我 就 来 过 这 一 个 。/";
                global.msg[4] = "\\E5* 我 从 来 没 有 钱 去 度 假 。/";
                scr_charface(5, "L");
                global.msg[6] = "* 我 明 白 了 。 /%%";
            }
        }
        break;
    case room_fire_hotelbed:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 多 大 的 一 张 床 啊 ！/";
            global.msg[2] = "\\E2* 我 们 在 这 里 睡 一 晚 吧 ！/";
            scr_charface(3, "C");
            global.msg[4] = "* 我 们 还 是 别 了 。/";
            global.msg[5] = "\\EG* .^1.^1.别 那 样 看 着 我 ^1, &  我 们 还 有 事 情 要 做 的 。/";
            scr_cloface(6, "D");
            global.msg[7] = "* 总 会 有 时 间 &  能 来 睡 一 晚 的 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "L");
                global.msg[1] = "* ...你 曾 经 有 在 外 面 &  过 夜 过 吗 ？/";
                scr_cloface(2, "A");
                global.msg[3] = "* 你 可 以 这 么 说 。/";
                global.msg[4] = "\\EH* 虽 然 我 很 少 在 床 上 睡 觉 ，&  但 既 然 你 提 到 了 。/";
                scr_charface(5, 3);
                global.msg[6] = "* .../";
                scr_cloface(7, 6);
                global.msg[8] = "* 算 了 ^1。&* 我 还 是 更 喜 欢 睡 沙 发 。/%%";
            }
        }
        break;
    case room_fire_precore:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* .../";
            scr_charface(2, 0);
            global.msg[3] = "* 核 心 这 么 容 易 就 能 进 入 ..^2.&  这 设 计 真 有 趣 。/";
            scr_cloface(4, 7);
            global.msg[5] = "* 你 在 担 心 安 全 问 题 ？/";
            scr_charface(6, "C");
            global.msg[7] = "* 当 然 ^2。 如 果 有 人&  闯 入 了 该 怎 么 办 ？/";
            global.msg[8] = "\\E3* 要 么 他 们 受 伤 ， 要 么&  一 些 敏 感 设 备 可 能 会 损 坏 。/";
            scr_cloface(9, 6);
            global.msg[10] = "* 确 实 .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 8);
                global.msg[1] = "* 我 的 意 思 是 ^1， 我 确 定&  还 没 有 发 生 过 什 么 意 外 。/";
                global.msg[2] = "\\E6* 如 果 发 生 过 的 话 ^1，&  就 会 有 更 多 的 安 全 措 施 。/";
                scr_charface(3, 3);
                global.msg[4] = "* 啊 ^1， 对 ^1， 这 是&  “ 只 有 当 出 问 题 时 才 去&  解 决 问 题 ” 的 方 法 。/";
                scr_cloface(5, 6);
                global.msg[6] = "* ...有 这 些 扶 手 在 ，&  不 会 有 人 受 伤 的 。/%%";
            }
            if (global.plot == 176)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 来 吧 ^1， 咱 们 继 续 。/%%";
            }
        }
        break;
    case room_fire_core3:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* .../%%";
            if (global.plot == 179)
            {
                scr_charface(0, 9);
                global.msg[1] = "* 干 得 好 ^1， 至 少 没 死 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* 就 这 样 保 持 下 去 吧 ！/%%";
            }
        }
        break;
    case room_fire_core_bottomleft:
        if (clover == 1)
        {
            scr_cloface(0, "B");
            global.msg[1] = "* 这 是 从 雪 镇 来 的 冰 块 ？？/";
            scr_charface(2, "C");
            global.msg[3] = "* 那 真 是 不 错 的 一 趟 旅 行 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 1);
                global.msg[1] = "* 这 真 的 是 最 有 效 的&  降 温 方 式 吗 ？/";
                scr_cloface(2, 5);
                global.msg[3] = "* 既 然 能 降 温 ^1，&  于 是 就 这 么 干 了 。/%%";
            }
            if (scr_murderlv() == 7)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* ...为 什 么 这 里 &  会 有 传 送 带 ？/";
                global.msg[2] = "\\E9*真 奇 怪 。/%%";
                if (global.flag[19] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_fire_core_branch:
        if (clover == 1)
        {
            if (global.plot == 185)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 你 别 无 选 择 ，&  只 能 自 己 找 路 了 。/";
                scr_charface(2, "H");
                global.msg[3] = "* 你 会 没 事 的 ^3。&\\EE* 也 许 吧 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "E");
                    global.msg[1] = "* 我 其 实 压 根 对 你 没 有 信 心 。/";
                    scr_cloface(2, 7);
                    global.msg[3] = "* 呵 。/%%";
                }
            }
        }
        break;
    case room_fire_core_left:
    case room_fire_core_topleft:
    case room_fire_core_top:
    case room_fire_core_topright:
    case room_fire_core_right:
    case room_fire_core_bottomright:
    case room_fire_core_center:
        if (clover == 1)
        {
            if (global.flag[248] == 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 些 房 间 ..^2.真 的&  没 什 么 可 聊 的 。/";
                scr_charface(2, "I");
                global.msg[3] = "* 它 们 都 长 得 一 样 ，&  不 是 吗 ？/";
                scr_cloface(4, 0);
                global.msg[5] = "* 对 - 啊 。/%%";
            }
            if (global.flag[248] == 1)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 我 觉 得 让 一 个 设 计 &  看 起 来 好 看 并 不 是 要 .../";
                global.msg[2] = "\\E6* 在 设 计 时 采 取 优 先 事 项&  或 其 他 什 么 东 西 。/";
                global.msg[3] = "\\ED* 但 是 拜 托 .../";
                scr_charface(4, 7);
                global.msg[5] = "* 他 们 也 太 不 体 贴 了 ^2。/";
                global.msg[6] = "\\E8* 主 要 针 对 那 些 真 正 想&  解 说 一 切 的 鬼 魂 。/%%";
            }
            if (global.flag[248] == 2)
            {
                scr_charface(0, 0);
                global.msg[1] = "* .../";
                scr_cloface(2, 1);
                global.msg[3] = "* 哇 哦 ^1！ 这 墙 ..^2.好 蓝 啊 ！/";
                scr_charface(4, 0);
                global.msg[5] = "* 难 以 置 信 。/%%";
            }
            if (global.flag[248] == 3)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 无 话 可 聊 。/";
                global.msg[2] = "\\E7* 我 理 解 你 想 跟 我 们 聊 天 ^1，&  但 是 .../";
                scr_charface(3, 3);
                global.msg[4] = "* 我 同 意 。/%%";
            }
            if (global.flag[248] == 4)
            {
                scr_charface(0, "G");
                global.msg[1] = "* 这 是 让 你 不 要 再&  跟 我 们 说 话 的 警 告 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* 你 这 样 说 话 也 太 &  没 礼 貌 了 吧 。/";
                scr_charface(4, 0);
                global.msg[5] = "* 我 只 是 在 陈 述 事 实 。/%%";
            }
            if (global.flag[248] == 5)
            {
                scr_cloface(0, "C");
                global.msg[1] = "* 这 条 长 廊 .../";
                scr_charface(2, 3);
                global.msg[3] = "* 它 确 实 存 在 。/%%";
            }
            if (global.flag[248] == 6)
            {
                scr_charface(0, "D");
                global.msg[1] = "* 别/%%";
            }
            if (global.flag[248] > 6)
            {
                scr_cloface(0, "J");
                global.msg[1] = "* FRISK/";
                scr_charface(2, "J");
                global.msg[3] = "* 别 再 跟 我 们 说 话 了/%%";
            }
            global.flag[427] = -99;
        }
        else if (global.flag[248] > 6)
        {
            scr_charface(0, "J");
            global.msg[1] = "* 真 的 吗 ？/";
            global.msg[2] = "* 你 真 的 想 把 时 间 &  花 在 这 上 面 ？/";
            global.msg[3] = "\\ED* 我 真 不 敢 相 信 。/%%";
            global.flag[248] = -1;
        }
        break;
    case room_fire_core_treasureleft:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 哦 哦 哦 ^1， 有 宝 藏 ！/";
            scr_charface(2, 0);
            global.msg[3] = "* 你 不 会 说 那 种 话 的 。/";
            scr_cloface(4, 1);
            global.msg[5] = "* 但 我 就 是 说 了 。/";
            scr_charface(6, "D");
            global.msg[7] = "* Clover ，&  那 可 是 个 垃 圾 桶 啊 。/";
            scr_cloface(8, 1);
            global.msg[9] = "* 那 又 如 何 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "D");
                global.msg[1] = "* ...Frisk^2.&* 别 翻 。/";
                scr_cloface(2, "I");
                global.msg[3] = "* Frisk^2.&* 去 翻 。/%%";
            }
            if (global.flag[113] == 1)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 哦 哦 哦 ^1， 有 宝 藏 ！/";
                scr_charface(2, "D");
                global.msg[3] = "* 别 再 去 翻 了 。/";
                scr_cloface(4, 1);
                global.msg[5] = "* 快 点 再 去 翻 ！/";
                scr_charface(6, 0);
                global.msg[7] = "* 你 俩 快 把 我 折 磨 到 死 了 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "D");
                    global.msg[1] = "* 可 惜 ^1， 现 在 就 是 死 亡 &  也 无 法 让 我 解 脱 了 。/";
                    scr_cloface(2, "G");
                    global.msg[3] = "* 呃 。/";
                    global.msg[4] = "* 以 后 不 翻 垃 圾 桶 了 ^2。&* 我 明 白 了 。/%%";
                }
                if (global.flag[112] == 1)
                {
                    scr_charface(0, "D");
                    global.msg[1] = "*/";
                    scr_cloface(2, 6);
                    global.msg[3] = scr_gettext("obj_chara_0") + "^2?&* 你 还 好 吗 ？/";
                    scr_charface(4, "D");
                    global.msg[5] = "*/%%";
                }
            }
            else if (global.flag[112] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 获 得 宝 藏 ！/";
                scr_charface(2, 4);
                global.msg[3] = "* .../%%";
            }
        }
        break;
    case room_fire_core_treasureright:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 哦 哦 哦 ^1， 有 宝 藏 ！/";
            scr_charface(2, 0);
            global.msg[3] = "* 你 不 会 说 那 种 话 的 。/";
            scr_cloface(4, 1);
            global.msg[5] = "* 但 我 就 是 说 了 。/";
            scr_charface(6, "D");
            global.msg[7] = "* Clover ，&  那 可 是 个 垃 圾 桶 啊 。/";
            scr_cloface(8, 1);
            global.msg[9] = "* 那 又 如 何 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "D");
                global.msg[1] = "* ...Frisk^2.&* 别 翻 。/";
                scr_cloface(2, "I");
                global.msg[3] = "* Frisk^2.&* 去 翻 。/%%";
            }
            if (global.flag[112] == 1)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 哦 哦 哦 ^1， 有 宝 藏 ！/";
                scr_charface(2, "D");
                global.msg[3] = "* 别 再 去 翻 了 。/";
                scr_cloface(4, 1);
                global.msg[5] = "* 快 点 再 去 翻 ！/";
                scr_charface(6, 0);
                global.msg[7] = "* 你 俩 快 把 我 折 磨 到 死 了 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "D");
                    global.msg[1] = "* 可 惜 ^1， 现 在 就 是 死 亡 &  也 无 法 让 我 解 脱 了 。/";
                    scr_cloface(2, "G");
                    global.msg[3] = "* 呃 。/";
                    global.msg[4] = "* 以 后 不 翻 垃 圾 桶 了 ^2。&* 我 明 白 了 。/%%";
                }
                if (global.flag[113] == 1)
                {
                    scr_charface(0, "D");
                    global.msg[1] = "*/";
                    scr_cloface(2, 6);
                    global.msg[3] = scr_gettext("obj_chara_0") + "^2?&* 你 还 好 吗 ？/";
                    scr_charface(4, "D");
                    global.msg[5] = "*/%%";
                }
            }
            else if (global.flag[113] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 获 得 宝 藏 ！/";
                scr_charface(2, 4);
                global.msg[3] = "* .../%%";
            }
        }
        break;
    case room_fire_core_warrior:
        if (clover == 1)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 你 要 把 自 己 当 做 一 个 &  战 士 吗 ^1，Frisk?/";
            scr_charface(2, 6);
            global.msg[3] = "* 如 果 你 执 意 要 这 样 做 ..^2. &  那 我 祝 你 好 运 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 你 想 怎 么 做 就 怎 么 做 吧 ^1，&  Frisk。/";
                global.msg[2] = "\\E8* 你 自 己 来 决 定 。/%%";
            }
            if (global.flag[421] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 精 彩 的 战 斗 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* 你 还 好 吗 ？/%%";
            }
            if (global.flag[421] == 3)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 游 戏 ^1， 准 备 ^1， 然 后 开 始 ！/";
                scr_charface(2, 8);
                global.msg[3] = "* 就 是 为 了 按 下 一 个 开 关 。/%%";
            }
            if (global.flag[419] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 就 到 此 为 止 吧 。/%%";
            }
            if (scr_murderlv() == 7)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 这 看 起 来 像 是 个 挑 战 。/";
                scr_charface(2, 9);
                global.msg[3] = "* ...你 确 定 你 想 做 这 个 ？/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 我 相 信 一 定 有 别 的 方 法 。/";
                    global.msg[2] = "\\E7* 为 什 么 我 们 不 ..^1.&  转 一 转 呢 ？/%%";
                }
                if (global.flag[421] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 精 彩 的 战 斗 。/";
                    scr_cloface(2, 6);
                    global.msg[3] = "* 我 猜 我 们 要 做 这 个 了 .../%%";
                }
                if (global.flag[421] == 3)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 那 是 最 后 一 个 了 。/";
                    scr_cloface(2, 6);
                    global.msg[3] = "* .../%%";
                }
                if (global.flag[419] == 1)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 就 到 此 为 止 吧 。/%%";
                }
            }
        }
        break;
    case room_fire_core_bridge:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 哦 ^1， 谢 天 谢 地 ，&  这 里 有 扶 手 。/";
            scr_charface(2, 1);
            global.msg[3] = "* 当 心 脚 下 ^2。&* 我 不 知 道 会 发 生 什 么 .../%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_fire_core_premett:
        if (clover == 1)
        {
            if (global.plot <= 197)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 你 做 到 了 ！/";
                scr_charface(2, 0);
                global.msg[3] = "* 别 搞 砸 了 ^2。&* 我 们 还 没 脱 离 困 境 呢 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "A");
                    global.msg[1] = "* 但 确 实 ^1， 我 就 知 道 你 能 行 。/%%";
                }
            }
        }
        break;
    case room_fire_core_metttest:
        if (clover == 1)
        {
            if (instance_exists(obj_mettboss_event))
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 的 天 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 一 场 大 战 就 要 到 来 了 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "H");
                    global.msg[1] = "* 你 在 .../%%";
                }
            }
            else if (global.flag[425] == 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 还 在 回 忆 那 场 战 斗 ？/";
                scr_charface(2, 8);
                global.msg[3] = "* 你 似 乎 玩 的 很 开 心 ^1，&  Frisk。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 那 确 实 很 酷 ^2。&* 你 跳 舞 跳 的 真 不 错 。/%%";
                    if (global.flag[268] == 3)
                    {
                        global.msg[1] = "* 那 确 实 很 酷 ^2。&* 你 跳 舞 跳 的 真 不 错 。/";
                        global.msg[2] = "\\E1* 我 没 有 一 刻 怀 疑 过 你 。/";
                        global.msg[3] = "* 你 之 前 已 经 证 明 过 你&  跳 舞 跳 的 真 的 不 错 。/%%";
                    }
                    if (global.flag[268] == 2)
                    {
                        global.msg[1] = "* 那 确 实 很 酷 ^2。&* 你 跳 舞 跳 的 真 不 错 。/";
                        scr_charface(2, 0);
                        global.msg[3] = "* 我 对 你 没 有&  太 大 的 信 心 。/";
                        global.msg[4] = "\\E9* 在 El Bailador被 你 打 败 之 后 。/%%";
                    }
                }
            }
            if (instance_exists(obj_mettdestroyed_event))
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 真 是 精 彩 的 演 出 ！/";
                global.msg[2] = "* 他 没 事 真 是 太 好 了 。/";
                global.msg[3] = "\\E6* 我 知 道 我 明 确 地 表 达 了&  我 对 他 的 不 满 ^1， 但 是 .../";
                global.msg[4] = "\\E8* 地 下 世 界 需 要 &  它 自 己 的 明 星 。/%%";
                scr_charface(5, 8);
                global.msg[6] = "* 干 得 好 ^1，&  Frisk。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 我 们 在 这 待 得 够 久 了 。/";
                    scr_cloface(2, "H");
                    global.msg[3] = "* 我 同 意 。/%%";
                }
            }
            if (global.flag[425] != 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* ...一 定 会 有 &  另 一 种 办 法 的 。/";
                global.msg[2] = "* 一 定 会 有 的 。/";
                scr_charface(3, "L");
                global.msg[4] = "* .../%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "L");
                    global.msg[1] = "* ..^2.最 好 别 再 想 这 件 事 了 。/%%";
                }
            }
        }
        break;
    case room_fire_core_final:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 在 我 们 见 过 的 所 有 长 廊 中 ^1，&  这 当 然 也 算 是 其 中 之 一 。/%%";
            if (instance_exists(obj_alphysfollow_event))
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../%%";
            }
            if (global.plot == 199)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* .../";
                scr_charface(2, 6);
                global.msg[3] = "* .../%%";
            }
        }
        break;
    case room_fire_shootguy_1:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 一 个 有 明 确 &  解 决 方 案 的 谜 题 。/";
            global.msg[2] = "* 当 然 比 Papyrus 给&  我 们 的 谜 题 要 好 。/";
            global.msg[3] = "* 但 这 还 是 相 对 简 单 的 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 或 许 这 就 像 一 个 教 程 一 样 ？/";
                global.msg[2] = "\\E7* 毕 竟 ^1，&  Alphys 确 实 让 我 们 &  先 做 这 个 。/";
                scr_charface(3, 0);
                global.msg[4] = "* 完 全 是 有 可 能 的 。/%%";
            }
        }
        break;
    case room_fire_shootguy_2:
        if (clover == 1)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 现 在 的 这 个 才 算 得 上 &  是 一 个 谜 题 。/";
            global.msg[2] = "* 这 仍 然 不 是 &  我 个 人 喜 欢 的 难 度 。/";
            global.msg[3] = "* 但 无 论 如 何 &  这 确 实 是 一 个 谜 题 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 我 希 望 在 未 来 会 有 &  更 多 更 复 杂 的 谜 题 &  被 迭 代 出 来 。/";
                scr_cloface(2, 2);
                global.msg[3] = "* ...呆 瓜 。/%%";
            }
        }
        break;
    case room_fire_shootguy_3:
        if (clover == 1)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 哦 ，这 个 谜 题 的 设 计 &  更 适 合 我 的 速 度 水 平 了 。/";
            global.msg[2] = "\\EA* 虽 然 它 的 要 求 依 然 &  比 我 的 水 平 稍 低 一 点 ^1，&  但 我 挺 喜 欢 的 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 或 许 我 开 始 理 解 你&  为 什 么 会 喜 欢 这 些 了 ^2。&* 但 只 理 解 了 一 点 点 。/";
                scr_charface(2, "J");
                global.msg[3] = "* 我 就 知 道 ^1-%";
                global.msg[4] = "\\EN* .../";
                global.msg[5] = "\\E7* 没 错 ^2。 像 这 样 的 脑 力 挑 战&  对 锻 炼 智 力 很 有 帮 助 。/";
                scr_cloface(6, 2);
                global.msg[7] = "* 它 们 的 确 是 这 样 的 。/%%";
            }
        }
        break;
    case room_fire_shootguy_4:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 哦 哦 哦 哦 哦 ， 天 哪 。/";
            global.msg[2] = "* 这 东 西 让 我 头 晕 。/";
            scr_charface(3, 9);
            global.msg[4] = "* 终 于 啊 。^2 一 个 值 得 思 考&  的 谜 题 。/";
            scr_cloface(5, "C");
            global.msg[6] = "* 你 当 ~ 然 会 那 么 说 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 是 认 真 的 ^1，&  这 玩 意 看 起 来 挺 疯 狂 的 。/";
                scr_charface(2, 8);
                global.msg[3] = "* 上 吧 ^1， Frisk^2。&* 你 能 解 决 它 的 。/";
                global.msg[4] = "\\EK* 把 它 撕 成 碎 片 ^2。&* 揭 示 答 案 ^1，&  并 将 其 公 之 于 众 ！/";
                scr_cloface(5, 1);
                global.msg[6] = "* 就 是 这 个 意 思 ^2！&* 但 没 那 么 暴 力 ！/%%";
            }
            if (global.flag[400] == 1)
            {
                scr_charface(0, 9);
                global.msg[1] = "* 我 就 知 道 你 能 行 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* 我 可 没 有 这 样 的 本 事 。/%%";
            }
        }
        break;
    case room_fire_shootguy_5:
        if (clover == 1)
        {
            scr_charface(0, 3);
            global.msg[1] = "* 这 难 道 是 ...？/";
            global.msg[2] = "\\E9* Frisk^2。 你 为 了 这 一 刻 &  早 已 付 出 了 刻 苦 的 训 练 。/";
            scr_cloface(3, 7);
            global.msg[4] = "* 最 终 的 谜 题 &  就 在 你 面 前 。/";
            scr_charface(5, 9);
            global.msg[6] = "* 来 吧 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 继 续 ^2。&* 你 能 做 到 的 。/";
                scr_cloface(2, 2);
                global.msg[3] = "* 多 么 鼓 舞 人 心 ^2！&* 多 么 令 人 自 信 ^2！&* 多 么 酷 炫 吊 炸 天 ！/";
                scr_charface(4, "N");
                global.msg[5] = "* 这 ^1- 确 实 。/";
                global.msg[6] = "\\E7* 你 还 是 闭 嘴 吧 。/%%";
                if (global.flag[249] < 90)
                {
                    scr_cloface(2, "I");
                    global.msg[3] = "* 不 ^1， 我 想 三 次 尝 试&  就 足 以 让 他 放 弃 。/";
                    scr_charface(4, 8);
                    global.msg[5] = "* 你 要 让 他 就 那 么 诽 谤 你 吗 ^1，&  Frisk？/%%";
                }
            }
            if (global.flag[418] == 1)
            {
                scr_charface(0, "A");
                global.msg[1] = "* 这 就 对 了 。/";
                global.msg[2] = "* 我 很 满 意 。/";
                global.msg[3] = "* ..^2.\\EC我 的 意 思 是 你 做 得 好 ^1，&  Frisk./";
                scr_cloface(4, 8);
                global.msg[5] = "* .../%%";
            }
        }
        break;
    case room_fire_elevator_r1:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 右 侧 一 层 ^1， 是 吗 ？/";
            global.msg[2] = "* 已 经 有 段 时 间 了 ^1，&  但 我 还 记 得 有 一 个 &  右 侧 三 层 。/";
            global.msg[3] = "\\EA* 我 想 知 道 那 个 电 梯 &  是 否 仍 在 使 用 。/";
            global.msg[4] = "\\E6* 那 在 之 前 就 已 经 &  很 破 旧 了 .../%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "G");
                global.msg[1] = "* 你 到 底 在 说 什 么 ？ /";
                scr_cloface(2, 7);
                global.msg[3] = "* 你 会 见 到 的 ^2。&\\E6* 也 许 会 吧 ^2。&\\E9* 我 想 。/%%";
            }
        }
        break;
    case room_fire_elevator_r2:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 当 然 也 会 有 一 个 右 侧 二 层 。/";
            global.msg[2] = "* 但 是 我 们 为 什 么 不 能&  直 接 进 入 下 一 层 呢 ？/";
            scr_charface(3, "A");
            global.msg[4] = "* 序 列 中 断 是 指&  执 行 动 作 或&  获 取 物 品 的 行 为%";
            global.msg[5] = "* 超 出 预 期 的&  线 性 顺 序 或 跳 过%";
            global.msg[6] = "* 完 全 “ 必 须 ” 的&  行 动 或 项 目 。/%%";
            if (global.plot > 167)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 所 以 现 在 我 们 可 以 去 &  任 何 我 们 想 去 的 电 梯 了 ！/";
                global.msg[2] = "* 我 们 一 定 也 可 以&  去 到 左 边 的 电 梯 了 ！/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "G");
                global.msg[1] = "\\E1* 什 么 ？ /";
                scr_charface(2, 8);
                global.msg[3] = "* 怎 么 了 ？ /%%";
                if (global.plot > 167)
                {
                    scr_charface(0, 9);
                    global.msg[1] = "* 我 们 肯 定 是 触 发 了&  一 个 进 程 标 志 。/";
                    scr_cloface(2, "J");
                    global.msg[3] = "* 你 在 说 些 什 么 ？！？/%%";
                }
            }
        }
        break;
    case room_fire_elevator_r3:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 我 想 我 们 到 了 。/";
            global.msg[2] = "\\E7* 感 觉 就 像 我 昨 天 才 &  刚 穿 过 那 些 门 一 样 。/";
            global.msg[3] = "\\E6* ...又 或 者 已 经 过 了 &  一 百 万 年 。/";
            global.msg[4] = "\\E6* 那 个 时 候 ^1， 我 知 道&  我 的 旅 程 将 要 结 束 了 。/";
            global.msg[5] = "* 在 那 里 等 着 真 是 令 人 紧 张 。/";
            global.msg[6] = "\\E9* 无 论 我 做 什 么 ^1，&  它 都 很 快 就 会 结 束 。/";
            global.msg[7] = "\\E8* 那 可 能 是 我 一 辈 子&  最 紧 张 的 一 次 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 7);
                global.msg[1] = "* 等 待 着 结 局 的 到 来 ^1，&  无 论 你 准 备 得 多 么 充 分 .../";
                global.msg[2] = "\\E1* 也 无 论 这 个 结 局&  意 味 着 什 么 .../";
                global.msg[3] = "\\EL* 这 简 直 太 可 怕 了 。/";
                scr_cloface(4, 9);
                global.msg[5] = "* 是 啊 。/";
                global.msg[6] = "\\E7* 在 你 自 己 的 旅 程 结 束 之 前 ^1，&  你 还 有 一 段 路 要 走 。/";
                global.msg[7] = "* 但 如 果 你 感 到 有 点 紧 张 ^1，&  你 要 知 道 你 并 非 孤 军 奋 战 。/%%";
                if (global.plot >= 200)
                {
                    global.msg[6] = "\\E7* 你 自 己 的 旅 程&  也 快 要 结 束 了 。/";
                    global.msg[7] = "* 但 如 果 你 感 到 有 点 紧 张 ^1，&  你 要 知 道 你 不 是 独 自 一 人 。/%%";
                }
            }
        }
        break;
    case room_fire_elevator_l1:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 可 惜 我 们 来 的 时 候 &  没 能 跳 过 那 个 实 验 室 。/";
            scr_cloface(2, 1);
            global.msg[3] = "* 但 那 样 的 话 我 们 就 &  不 会 遇 见 Alphys 了 ！/";
            scr_charface(4, "I");
            global.msg[5] = "* 确 实 ， 这 倒 是 真 的 。/%%";
            if (global.flag[217] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* .../%%";
            }
            if (global.flag[427] == 1 && global.flag[217] == 0)
            {
                scr_charface(0, 0);
                global.msg[1] = "* 不 过 那 样 的 话 &  我 们 的 效 率 会 高 很 多 。/";
                global.msg[2] = "* 更 少 的 干 扰 ^2。&* 更 多 的 进 步 。/";
                scr_cloface(3, 9);
                global.msg[4] = "* 我 不 这 么 认 为 。/";
                scr_charface(5, 3);
                global.msg[6] = "* 哦 ？/";
                scr_cloface(7, 6);
                global.msg[5] = "* 好 吧 ^1， 如 果 我 们 所 做 的 &  一 切 都 只 是 为 了 &  抵 达 目 的 地 .../";
                global.msg[6] = "* 我 们 会 失 去 很 多 东 西 的 。/%%";
            }
            if (global.flag[427] == 2 && global.kills == 0 && global.flag[217] == 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 那 么 关 于 生 活 呢 ？/";
                global.msg[2] = "* 我 们 最 终 得 到 了 什 么 &  并 不 重 要 。/";
                scr_cloface(3, 9);
                global.msg[4] = "* 那 ^1.^1.^1. \\E6让 我 思 考 一 下 。/";
                global.msg[5] = "\\E9* 我 们 ..^2. 最 终 ^1， 都 会 死 ^1。 &  我 无 法 反 驳 。/";
                global.msg[6] = "\\E8* 但 我 们 活 着 的 时 候 &  会 接 触 到 很 多 人 。/";
                global.msg[7] = "\\E6* 我 已 经 死 了 ^2。&* 而 且 ^1， 确 实 ^1， 我 的 生 命 &  比 大 多 数 人 都 要 短 。/";
                global.msg[8] = "\\E7* 然 而 ^2。 我 遇 到 过 的 人 ..^2. &  我 所 造 成 过 的 影 响 .../";
                global.msg[9] = "\\E6* 我 将 无 法 帮 助 他 们 ， &  如 果 我 ... &  很 早 就 放 弃 的 话 。/";
                global.msg[10] = "\\E8* 而 且 他 们 也 将 &  无 法 帮 助 我 。/";
                scr_charface(11, 0);
                global.msg[12] = "* 是 这 样 吗 。/";
                scr_cloface(13, 0);
                global.msg[14] = "* 是 的 ^2。 就 是 这 样 。/";
                global.msg[15] = "* 你 是 不 是 想 说 &  从 来 就 没 有 人 爱 过 你 ？/";
                global.msg[16] = "* 你 就 没 有 爱 过 任 何 人 吗 ？/";
                scr_charface(17, 7);
                global.msg[18] = "* 我 当 然 有 过 。/";
                global.msg[19] = "* 也 许 他 们 没 有 我 &  会 过 得 更 好 -/";
                scr_cloface(20, 9);
                global.msg[21] = "* 但 他 们 真 的 会 那 么 想 吗 ？/";
                scr_charface(22, 7);
                global.msg[23] = "* .../";
                global.msg[24] = "* 不 。/";
                scr_cloface(25, 0);
                global.msg[26] = "* 那 就 坚 持 下 去 。/";
                global.msg[27] = "* 我 们 将 快 乐 带 给 &  我 们 所 认 识 的 人 .../";
                global.msg[28] = "* 也 许 也 会 将 快 乐 &  带 给 我 们 不 认 识 的 人 .../";
                global.msg[29] = "* 那 就 是 我 们 活 着 的 意 义 。/";
                global.msg[30] = "* 直 接 跳 到 生 命 的 尽 头 ， &  就 意 味 着 我 们 跳 过 了 &  我 们 所 带 来 的 美 好 。/";
                scr_charface(31, "N");
                global.msg[32] = "* .../";
                global.msg[33] = "\\EM* 你 比 你 这 个 年 龄 的 人 &  聪 明 的 多 。/%%";
                global.flag[217] = 1;
            }
        }
        if (clover == 0 && global.flag[217] == 1)
        {
            scr_charface(0, "F");
            global.msg[1] = "* ..^2.最 关 键 的 时 候 ^1， &  他 知 道 该 说 什 么 ^1， 是 吧 ？/%%";
        }
        break;
    case room_fire_elevator_l2:
        if (clover == 1)
        {
            scr_cloface(0, "A");
            global.msg[1] = "* 我 在 想 建 造 电 梯 之 前 ，&  怪 物 们 是 怎 么 去 往 各 地 的 。/";
            global.msg[2] = "* 我 的 意 思 是 ^1， 他 们 总 不 能&  一 直 待 在 这 ^1， 对 吧 ？/";
            scr_charface(3, 8);
            global.msg[4] = "* 哦 ^1， 我 想 起 来 了 。/";
            scr_cloface(5, "B");
            global.msg[6] = "* 哈 ？/%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 在 电 梯 建 造 之 前 ，&  还 曾 经 有 一 个 完 整 的 &  升 降 滑 轮 系 统 。/";
                global.msg[2] = "\\EH* 当 然 ^1， 效 率 并 不 高 。/";
                global.msg[3] = "\\EC* 更 不 用 说 ^1， &  发 生 事 故 的 概 率 是 .../";
                global.msg[4] = "\\EE* 那 么 皇 家 科 学 员 的&  首 要 任 务 是 什 么 呢 ^2？&* 找 到 更 好 的 交 通 方 式 。/";
                global.msg[5] = "\\EA* 所 以 现 在 有 了 这 些 电 梯 ！/";
                scr_cloface(6, 9);
                global.msg[7] = "* 还 有 个 问 题 。/";
                global.msg[8] = "\\EA* 他 们 一 开 始 是 怎 么&  安 装 滑 轮 系 统 的 呢 ？/";
                scr_charface(9, "C");
                global.msg[10] = "* 呃 。/";
                global.msg[11] = "\\EA* 是 会 飞 的 怪 物 安 装 的 ！/";
                scr_cloface(12, "B");
                global.msg[13] = "* 哇 哦 .../%%";
            }
            if (global.flag[427] > 1)
            {
                scr_charface(0, 8);
                global.msg[1] = "* (嘿 ^1， Frisk 。)/";
                global.msg[2] = "\\EA* (刚 才 说 的 那 些 ^1， &  我 完 全 是 瞎 编 的 。)/";
                global.msg[3] = "\\EE* (你 要 问 我 为 什 么 ^1，&  因 为 这 很 有 意 思 。)/%%";
            }
        }
        break;
    case room_fire_elevator_l3:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 第 三 层 ^2。&* 最 高 的 一 层 。/";
            global.msg[2] = "\\E7* ..^2.不 ^1， 听 起 来 怪 怪 的 。/";
            scr_cloface(3, "A");
            global.msg[4] = "* 哪 里 怪 了 ？/";
            scr_charface(5, "B");
            global.msg[6] = "* 就 是 ^1， 呃 ^2。&* 我 该 怎 么 跟 他 解 释 呢 ？/";
            global.msg[7] = "* 编 号 最 高 的 楼 层&  不 应 该 是 “ 第 三 层 ” 。/";
            scr_cloface(8, "A");
            global.msg[9] = "* 对 啊 ^1， 这 说 不 通 。/";
            global.msg[10] = "\\EP* 因 为 ^1， 你 知 道 的 ^1，&  三 层 楼 ？/";
            scr_charface(11, 1);
            global.msg[12] = "* 如 果 最 后 一 层 是 第 九 层 ， &  听 起 来 不 是 更 好 吗 ？/";
            scr_cloface(13, 6);
            global.msg[14] = "* 好 吧 ^1， 可 能 是 这 样 的 。/";
            global.msg[15] = "* 如 果 我 们 忽 略 所 有 的 逻 辑 ^1，&  只 按 照 听 起 来 &  最 好 的 来 选 .../";
            scr_charface(16, 3);
            global.msg[17] = "* 对 对 对 对 对 对 对 对 吗 ？/";
            scr_cloface(18, 1);
            global.msg[19] = "* “ 第 十 层 ” 对 我 来 说&  听 起 来 最 像 “ 最 后 一 层 ” ！/";
            scr_charface(20, "B");
            global.msg[21] = "* 你 和 他 都 有 你 们 的 ‘ 十 ’ 。/";
            scr_cloface(22, 6);
            global.msg[23] = "* ...^2？&* 我 说 错 什 么 了 吗 ？/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 等 等 ^1， ‘ 他 ’ 是 谁 ？/";
                scr_charface(2, 1);
                global.msg[3] = "* 他 是 -/";
                global.msg[4] = "* .../";
                global.msg[5] = "\\E7* 跟 你 没 什 么 关 系 。/%%";
                if (global.flag[101] == 1)
                {
                    global.msg[5] = "\\E7* 他 是 我 的 一 个 朋 友 。/";
                    global.msg[6] = "* 你 们 会 相 处 得 很 好 的 。/";
                    scr_cloface(7, 6);
                    global.msg[8] = "* .../%%";
                }
            }
        }
        break;
    case room_fire_elevator:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 一 部 电 梯 。/";
            global.msg[2] = "* 这 和 它 曾 经 的 样 子 相 比 &  没 什 么 变 化 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 所 以 ^1？ 你 要 ..^1.&* 用 它 ？/%%";
                if (irememberyourneutrals < 2)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* 那 怎 么 样 ^1？&* 你 是 打 算 升 高 还 是 怎 样 ？/%%";
                }
            }
            if (global.flag[249] > 90 && irememberyourneutrals < 1)
            {
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 所 以 ^1？ 你 打 算 ..^1.&* 乘 坐 它 ？/";
                }
                if (global.flag[427] == 2)
                {
                    scr_charface(0, "E");
                    global.msg[1] = "* 也 许 你 不 知 道 &  电 梯 运 作 的 原 理 ？/";
                    scr_cloface(2, 1);
                    global.msg[3] = "* 哈 ^1！&* 是 的 ^1， 总 的 来 说 ^1， &  你 要 先 按 下 按 钮 ^2-%";
                    scr_charface(4, 9);
                    global.msg[5] = "* 你 在 吐 舌 头 吗 ^1， Frisk ^2？&* 真 没 礼 貌 。/";
                    scr_cloface(6, "K");
                    global.msg[7] = "* 嘿 嘿 。/%%";
                }
                if (global.flag[427] == 3)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* 抱 歉 Frisk ^2。&* 也 许 我 们 的 幽 默 感 太 .../";
                    scr_cloface(2, "M");
                    global.msg[3] = "* 什 么 ？？？/";
                    scr_charface(4, "E");
                    global.msg[5] = "* 太 难 让 你 理 解 了 。/";
                    scr_cloface(6, 2);
                    global.msg[7] = "* 哈 哈 哈 ^1！&* 是 的 ！/";
                    global.msg[8] = "\\TS \\F0 \\E0 \\T0%";
                    global.msg[9] = "* (你 也 忍 不 住 笑 了 出 来 。 )/%%";
                }
                if (global.flag[427] == 4)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* 我 们 确 实 该 继 续 走 了 。/";
                    scr_cloface(2, "D");
                    global.msg[3] = "* 哦 ^1， 别 啊 。/";
                    scr_charface(4, "H");
                    global.msg[5] = "* 嘘 。/";
                    global.msg[6] = "\\EF* .../%%";
                }
                if (global.flag[427] > 4)
                {
                    scr_charface(0, "F");
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_fire_finalelevator:
        if (clover == 1)
        {
            if (global.flag[432] == 0)
            {
                global.msg[0] = "* (但 没 有 什 么 可 说 的 。 )/%%";
            }
            else
            {
                scr_charface(0, 7);
                global.msg[0] = "* 继 续 前 进 吧 。/%%";
            }
        }
        break;
    case room_castle_elevatorout:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 结 局 已 经 开 始 了 。/";
            global.msg[2] = "\\E9* 虽 然 你 已 经 去 过 了 &  很 多 不 同 的 地 方 .../";
            global.msg[3] = "* 这 个 地 方 还 是 感 觉 &  更 像 是 终 点 。/";
            global.msg[4] = "\\E7* 你 可 以 成 为 带 领 怪 物 们 &  走 向 自 由 的 救 世 主 。/";
            global.msg[5] = "\\E5* 也 可 以 成 为 独 自 逃 出 &  牢 笼 的 无 情 孤 独 者 。/";
            global.msg[6] = "\\E9* 亦 或 是 成 为 一 个 &  行 尸 走 肉 。/";
            global.msg[7] = "\\EK* ...或 者 别 的 什 么 。/";
            scr_charface(8, "D");
            global.msg[9] = "* 你 不 能 用 “ 或 者 什 么 ” &  来 概 括 所 有 的 话 。/%%";
            if (global.plot > 200)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 啊 ^1， 回 溯 。/";
                global.msg[2] = "\\E1* 你 会 喜 欢 上 它 的 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "J");
                global.msg[1] = "* 该 死 ^1， 我 搞 砸 了 ！/";
                global.msg[2] = "\\ED* 我 在 尝 试 像 你 一 样 说 话 。/";
                global.msg[3] = "* 你 的 演 讲 水 平 太 棒 了 ！/";
                scr_charface(4, "F");
                global.msg[5] = "* .../";
                scr_cloface(6, "H");
                global.msg[7] = "* 你 笑 起 来 也 很 好 看 。%";
                global.msg[8] = "\\E5* 不 管 怎 样 ！/%%";
                if (global.flag[249] < 90 || irememberyourneutrals > 1)
                {
                    scr_charface(4, "A");
                    global.msg[5] = "* 我 还 能 说 什 么 呢 ^2？&* 我 擅 长 做 任 何 事 情 。/%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* (^2.^2.^2.啥 玩 意 。)/%%";
                    if (global.flag[249] < 90)
                    {
                        scr_cloface(0, 7);
                        global.msg[1] = "* .../%%";
                    }
                }
                if (global.plot > 200)
                {
                    scr_charface(0, "D");
                    global.msg[1] = "* 郑 重 声 明 一 下 ^1，&  我 强 烈 反 对 你 这 么 做 。/%%";
                }
            }
            if (global.flag[450] >= 17)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 刚 才 那 是 .../";
                scr_charface(2, 3);
                global.msg[3] = "* ........./%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 这 感 觉 ..^2. 不 对 劲 。/";
                    global.msg[2] = "* 那 声 音 到 底 是 谁 ？/";
                    scr_charface(3, 1);
                    global.msg[4] = "* 听 起 来 ..^2. 如 此 熟 悉 .../%%";
                }
            }
        }
        if (global.flag[19] < 26.75)
        {
            global.flag[19] = 26.75;
            global.flag[427] -= 1;
            with (obj_cloverchara)
            {
                instance_destroy();
            }
            scr_charface(0, 0);
            global.msg[1] = "* 继 续 前 进，&  这 里 已 经 没 什 么 东 西 了 。/%%";
            if (global.kills < 20)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 对 不 起 ^2。让 我 们 继 续&  前 进 吧 。/%%";
                if (global.flag[249] > 90)
                {
                    global.msg[0] = "* ...谢 谢^2 。&" + scr_gettext("obj_chara_0") + "/";
                    scr_charface(1, 8);
                    global.msg[2] = "* ...没 什 么 。/%%";
                }
            }
            if (scr_murderlv() > 7)
            {
                scr_charface(0, 6);
                global.msg[1] = "* .../%%";
            }
            if (global.kills == 0)
            {
                scr_charface(0, 1);
                global.msg[1] = "* 我 们 到 了 。/";
                scr_cloface(2, 6);
                global.msg[3] = "* 最 后 的 冲 刺 。/%%";
                if (ossafe_file_exists("file6"))
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 我 希 望 你 能 做 对 的 事 。/%%";
                }
            }
        }
        break;
    case room_castle_precastle:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 这 座 城 市 真 大 。/";
            scr_cloface(2, 6);
            global.msg[3] = "* 从 这 边 来 看 ^1，&  给 人 的 感 觉 完 全 不 一 样 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 除 此 之 外 ^1，&  这 里 只 是 个 长 廊 。/";
                scr_cloface(2, 7);
                global.msg[3] = "* 在 长 廊 里 喊 几 声 吧 。/%%";
            }
            if (global.flag[450] >= 17)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 无 论 有 没 有 电 梯 ，&  对 我 们 来 说&  都 只 有 一 个 选 择 。/";
                scr_charface(2, "L");
                global.msg[3] = "* Asgore.../%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 无 论 路 径 如 何^1 ，&  最 终 的 目 的 地 &  都 是 一 样 的 。/";
                    scr_charface(2, "L");
                    global.msg[3] = "* 别 花 太 长 时 间 。/%%";
                }
            }
        }
        break;
    case room_castle_hook:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 城 堡 就 在 前 面 了 。/";
            global.msg[2] = "\\E1* .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* Frisk ^1， 你 在 长 廊 里&  只 能 说 这 么 多 话 了 。/%%";
                scr_charface(2, 8);
                global.msg[3] = "* 我 们 应 该 给 他 们 打 分 的 。/";
                scr_cloface(4, "J");
                global.msg[5] = "* 哦 ^1， 该 死 ^2！&* 那 可 太 好 了 ！！！/%%";
            }
        }
        break;
    case room_castle_front:
        if (clover == 1)
        {
            scr_charface(0, 7);
            global.msg[1] = "* .../%%";
            if (global.kills == 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../%%";
            }
            if (global.flag[19] < 27)
            {
                scr_charface(0, 7);
                global.msg[1] = "* 这 里 是 .../";
                scr_cloface(2, 0);
                global.msg[3] = "* 国 王 的 城 堡 ， 是 吗 ？/";
                global.msg[4] = "\\E6* 比 我 想 象 的 要 简 朴 。/";
                if (global.kills == 0)
                {
                    scr_charface(5, 2);
                    global.msg[6] = "* 这 是 我 的 家 。/";
                    scr_cloface(7, 9);
                    global.msg[8] = "* ...？ /%%";
                }
                if (scr_murderlv() < 12 && global.kills > 0)
                {
                    scr_charface(5, 7);
                    global.msg[6] = "* .../%%";
                }
                global.flag[19] = 27;
                with (obj_cloverchara)
                {
                    instance_destroy();
                }
            }
        }
        break;
    case room_asghouse1:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 看 上 去 和 Toriel 的 房 子 &  一 样 。/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = scr_gettext("obj_chara_0") + "？&* 你 还 好 吗 ？/";
                scr_charface(2, "L");
                global.msg[3] = "* 没 什 么 。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_asghouse2:
        if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* 这 当 然 会 引 起 ..^2.回 忆 。 /";
            scr_cloface(2, 6);
            global.msg[3] = "* ...你 是 想 .../";
            global.msg[4] = "\\E9* (不 ， 他 当 然 不 想 ， &  我 真 傻 。)/%%";
        }
        break;
    case room_asghouse3:
        if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* .../%%";
            if (obj_mainchara.x > 615)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 仍 然 是 你 。/";
                scr_charface(2, 8);
                global.msg[3] = "* 还 有 你 心 甘 情 愿 的 同 伴 们 。/";
                scr_cloface(4, 8);
                global.msg[5] = "* .../%%";
            }
        }
        break;
    case room_asgoreroom:
        if (clover == 1)
        {
            scr_charface(0, 8);
            global.msg[1] = "* ..^2. 他 一 点 都 没 变 ^1， &  对 吧 .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* Asgore.../";
                global.msg[2] = "* 根 据 Toriel描 述 他 的 方 式 ^1，&  你 认 为 他 会 更 .../";
                scr_charface(3, 0);
                global.msg[4] = "* 具 有 威 胁 ^2？&\\E9* 得 了 吧 。 /";
                global.msg[5] = "* 他 就 是 个 软 柿 子 。 /";
                global.msg[6] = "\\E8* 那 可 能 就 是 大 家&  都 喜 欢 他 的 原 因 。/";
                scr_cloface(7, 6);
                global.msg[8] = "* .../%%";
            }
            if (global.flag[450] >= 17)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_asrielroom_final:
        if (clover == 1)
        {
            scr_charface(0, 2);
            global.msg[1] = "* 和 我 记 忆 里 的 一 样 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* (那 意 味 着 ...)/%%";
            }
            if (global.flag[450] >= 17)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_kitchen_final:
        if (clover == 1)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 偷 吃 夜 宵 的 完 美 地 方 。 /";
            scr_cloface(2, "B");
            global.msg[3] = scr_gettext("obj_chara_0") + "^2! 你^2 ? 偷 ？/";
            global.msg[4] = "\\E1* 我 从 来 没 想 到 &  你 也 会 那 么 做 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "I");
                global.msg[1] = "* 我 猜 我 们 没 那 么 不 同 ^1，&  你 和 我 。 /";
                scr_charface(2, "E");
                global.msg[3] = "* 你 在 拿 你 自 己 和 我 比 吗 ？ /";
                global.msg[4] = "\\E9* 哈^2 ！ 你 甚 至 都 不 够 格 ^1-%";
                scr_cloface(5, 2);
                global.msg[6] = "* 我 会 让 你 把 那 些 话 吞 回 去 ！ /%%";
            }
            if (global.flag[450] >= 17)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_basement1_final:
    case room_basement2_final:
    case room_basement3_final:
    case room_basement4_final:
        if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* .../%%";
        }
        break;
    case room_lastruins_corridor:
        if (clover == 1)
        {
            scr_charface(0, 2);
            global.msg[1] = "* ...你 都 听 到 了 。/";
            global.msg[2] = "* 那 位 王 子 的 悲 惨 故 事 。/";
            global.msg[3] = "* 即 使 遭 受 来 自 四 面 八 方 &  的 攻 击 .../";
            global.msg[4] = "\\E7* 他 依 然 坚 守 着 自 己 的 &  价 值 观 念 ，直 到 那 &  惨 痛 的 结 局 。/";
            global.msg[5] = "* 他 总 是 那 么 固 执 .../";
            global.msg[6] = "\\EB* .../";
            global.msg[7] = "\\E6* (该 死 。 )/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, "H");
                global.msg[1] = scr_gettext("obj_chara_0") + "^1， 你 知 道&  哭 没 关 系 的 ^1， 对 吧 ？/";
                scr_cloface(2, "B");
                global.msg[3] = "* 我 不 记 得 我 刚 刚 和 你 说 话 了 ^1，&  Clover。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, "H");
                global.msg[1] = "* .../%%";
            }
            if (global.kills == 0)
            {
                scr_charface(0, 2);
                global.msg[1] = "* ...你 都 听 到 了 。/";
                global.msg[2] = "* 那 位 王 子 的 悲 惨 故 事 。/";
                global.msg[3] = "* 即 使 遭 受 来 自 四 面 八 方 &  的 攻 击 .../";
                global.msg[4] = "\\E7* 他 依 然 坚 守 着 自 己 的 &  价 值 观 念 ，直 到 那 &  惨 痛 的 结 局 。/";
                global.msg[5] = "\\E8* 他 总 是 那 么 固 执 .../";
                global.msg[6] = "* 我 想 ..^1.他 即 使 死 了 ， &  人 们 也 都 记 得 他 。/";
                global.msg[7] = "\\EF* 大 家 都 爱 着 他 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, "H");
                    global.msg[1] = "* 现 在 ， 快 出 发 吧 。/";
                    scr_cloface(2, "B");
                    global.msg[3] = scr_gettext("obj_chara_0") + "...?/";
                    scr_charface(4, "J");
                    global.msg[5] = "* 你 没 听 到 我 说 的 吗 ？/";
                    global.msg[6] = "\\E2* 忘 记 你 曾 经 看 到 过 &  我 那 样 。/%%";
                }
            }
            if (global.plot < 201)
            {
                scr_charface(0, 2);
                global.msg[1] = "* .../%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* (Frisk ^1，快 点 走 吧 。)/%%";
                }
            }
            if (global.flag[493] >= 12)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_sanscorridor:
        if (clover == 1)
        {
            scr_cloface(0, "B");
            global.msg[1] = "* (哇 哦 ...)/";
            scr_charface(2, 8);
            global.msg[3] = "* 这 里 真 的 好 华 丽 啊 ^1，&  你 不 觉 得 吗 ？ /%%";
            if (global.plot > 200)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 他 比 我 想 的 要 聪 明 得 多 。/";
                global.msg[2] = "\\E8* 你 得 把 他 的 话 牢 记 于 心 。/%%";
                if (global.flag[67] == 1)
                {
                    scr_cloface(0, "E");
                    global.msg[1] = "* .../%%";
                }
            }
            if (global.flag[427] > 0)
            {
                scr_charface(0, "L");
                global.msg[1] = "* .../%%";
            }
            if (global.flag[493] >= 12)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_castle_finalshoehorn:
        if (clover == 1)
        {
            if (global.flag[493] >= 12)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
            else
            {
                ossafe_ini_open("undertale.ini");
                time = ini_read_real("总 体 设 置", "Time", 0);
                ossafe_ini_close();
                hours = 0;
                minutes = floor(time / 1800);
                while (minutes >= 60)
                {
                    hours += 1;
                    minutes -= 60;
                }
                scr_cloface(0, 6);
                global.msg[1] = "* 我 们 真 的 到 了 .../";
                global.msg[2] = "* 这 是 一 趟 漫 长 的 旅 程 ^1，&  但 你 做 到 了 。/";
                if (hours > 23)
                {
                    scr_charface(3, "D");
                    global.msg[4] = "* 是 的 ^1， &  你 用 了 超 过 24 小 时 。/";
                    global.msg[5] = "* 你 都 干 了 些 什 么 ，&  用 了 这 么 长 时 间 ？/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, "D");
                        global.msg[1] = "* .../%%";
                    }
                }
                if (hours <= 23)
                {
                    scr_charface(3, 0);
                    global.msg[4] = "* " + string(hours) + " 小 时 ^1。&* 浪 费 了 这 么 多 时 间 .../";
                    scr_cloface(5, 7);
                    global.msg[6] = "* 嘿^1 ， 他 用 这 么 长 时 间 &  一 定 有 他 自 己 的 理 由 ！/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, "H");
                        global.msg[1] = "* 呵 。/%%";
                    }
                }
                if (hours <= 6)
                {
                    scr_charface(3, "H");
                    global.msg[4] = "* " + string(hours) + " 小 时 ^1，&  还 不 错 。/";
                    scr_cloface(5, 1);
                    global.msg[6] = "* 干 得 漂 亮 ！/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_charface(0, 9);
                        global.msg[1] = "* 我 们 下 次 争 取 " + string(hours - 1) + "&  小 时 完 成 ^1， 行 吗 ？/";
                        scr_cloface(2, "G");
                        global.msg[3] = "* 等 一 下 -/%%";
                    }
                }
                if (hours < 2)
                {
                    scr_charface(3, "D");
                    global.msg[4] = "* 比 一 小 时 稍 多 一 点 。/";
                    scr_cloface(5, "B");
                    global.msg[6] = "* 真 的 吗 ？ ？/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, "B");
                        global.msg[1] = "* 真 快 ！/";
                        scr_charface(2, 8);
                        global.msg[3] = "* 干 得 好 。/%%";
                    }
                }
                if (hours < 1)
                {
                    scr_charface(3, "D");
                    global.msg[4] = "* 时 间 甚 至 没 到 一 个 小 时 。/";
                    scr_cloface(5, "G");
                    global.msg[6] = "* 什 么 。/%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, "B");
                        global.msg[1] = "* 你 疯 了 。/";
                        scr_charface(2, 8);
                        global.msg[3] = "* 他 效 率 真 高 ^1。&\\EC* 真 是 疯 了 。 /%%";
                    }
                }
            }
        }
        if (clover == 0)
        {
            ossafe_ini_open("undertale.ini");
            time = ini_read_real("总 体 设 置", "Time", 0);
            ossafe_ini_close();
            hours = 0;
            minutes = floor(time / 1800);
            while (minutes >= 60)
            {
                hours += 1;
                minutes -= 60;
            }
            if (hours < 3)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 你 在 三 小 时 内 &  使 地 下 世 界 重 获 自 由 。/";
                global.msg[2] = "\\E9* 真 了 不 起 ^2。 &  把 那 写 进 你 的 简 历 吧 。/%%";
            }
        }
        break;
    case room_castle_throneroom:
        if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* ...这 里 太 宁 静 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_castle_coffins1:
    case room_castle_coffins2:
        if (clover == 1)
        {
            scr_cloface(0, 3);
            global.msg[1] = "* .../%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 4);
                global.msg[1] = "* (Frisk.^1)&* (现 在 不 是 闲 聊 的 时 候 。 )/%%";
            }
        }
        if (clover == 0)
        {
            scr_charface(0, 1);
            global.msg[1] = "* ...？ /%%";
        }
        break;
    case room_castle_prebarrier:
        if (clover == 1)
        {
            scr_cloface(0, 8);
            global.msg[1] = "* 我 知 道 这 很 可 怕 。/";
            global.msg[2] = "\\E9* 你 开 始 怀 疑 自 己 到 目 前 为 止&  所 做 的 所 有 决 定 。/";
            scr_charface(3, 1);
            global.msg[4] = "* 你 开 始 想 知 道 ^1，&  “ 我 能 不 能 回 去 ... ”/";
            scr_cloface(5, 9);
            global.msg[6] = "* “ 我 的 朋 友 们 ^1， &  我 还 能 不 能 ... ”/";
            global.msg[7] = "* 但 你 必 须 认 清 现 实 。/";
            scr_charface(8, 8);
            global.msg[9] = "* 你 已 经 没 有 回 头 路 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 8);
                global.msg[1] = "* 弗 里 斯 克 .../";
                global.msg[2] = "* ...请 你 时 刻 准 备 好 ，&  好 吗 ？/%%";
            }
            if (global.flag[493] >= 12)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 你 认 为 ... 这 一 次 会 有 什 么 &  不 一 样 的 地 方 吗 ？/";
                scr_charface(2, "L");
                global.msg[3] = "* ...只 有 一 个 办 法 &  能 找 出 答 案 。/%%";
            }
        }
        if (clover == 0)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 你 所 有 的 朋 友&  都 在 这 里^1 。 真 感 人 。/";
            global.msg[2] = "\\EL* 好 吧^1 ，除 了 .../%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 回 去 和 所 有 人 都 聊 聊 吧 ^2。&  这 是 你 应 得 的 。/%%";
            }
            if (global.flag[48] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 从 地 下 世 界 的 一 头 &  走 到 另 一 头 .../";
                global.msg[2] = "* 然 后 再 一 路 走 回 来 .../";
                global.msg[3] = "\\E9* 这 使 你 感 到 精 疲 力 竭 。/%%";
                if (global.flag[427] == 1)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* ..^1.你 说“ 这 不 是 台 词 ”&  是 什 么 意 思 ？/";
                    scr_torface(2, 1);
                    global.msg[3] = "* 你 在 和 谁 说 话 吗 ^1， &  我 的 孩 子 ？/";
                    scr_sansface(4, 1);
                    global.msg[5] = "* 是 的 ， 他 有 时 候 &  就 会 这 样 。/";
                    global.msg[6] = "\\E2* 不 用 担 心 。/";
                    scr_charface(7, "C");
                    global.msg[8] = "* (..^1.他 知 道 &  我 的 存 在 吗 ？ )/%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* 我 觉 得 我 们 不 该 &  再 在 这 个 房 间 里 聊 天 了 。/%%";
                }
            }
        }
        break;
    case room_castle_exit:
        ossafe_ini_open("undertale.ini");
        won = ini_read_real("总 体 设 置", "Won", 0);
        kill = ini_read_real("小 花", "K", 0);
        ossafe_ini_close();
        if (instance_exists(obj_npc_room))
        {
            scr_charface(0, "C");
            global.msg[1] = "* 我 们 .^1.^1.我 们 做 到 了 。/";
            global.msg[2] = "\\EL* 所 以 .../%%";
            global.msg[3] = "\\E2* 但 为 什 么 我 感 觉 输 了 呢 ？/";
            global.msg[4] = "\\EB* 他 死 了 ^1。 我 们 赢 了 ^1。&* 他 再 也 伤 害 不 了 任 何 人 了 。/";
            global.msg[5] = "* 他 没 赢 。/";
            global.msg[6] = "\\E1* .^1.^1. 他 没 有 。/";
            global.msg[7] = "* .../";
            global.msg[8] = "\\EL* 等 等 ^2。&* Frisk^1， 你 看 到 Clover了 吗 ？/";
            global.msg[9] = "\\EJ* 天 哪 ^1， 你 一 定 在 这 ，&  对 吧 ？/";
            global.msg[10] = "\\TS \\F0 \\E0 \\T0%";
            global.msg[11] = "* (你 在 房 间 里 &  寻 找 你 朋 友 的 踪 迹 ...)/";
            global.msg[12] = "* (但 谁 也 不 在 。 )/";
            scr_charface(13, 1);
            global.msg[14] = "* 所 以 他 仍 然 .../";
            global.msg[15] = "\\E2* .../";
            global.msg[16] = "\\EL* 他 走 了 ^2。&* 没 有 告 别 ^1， 没 有 遗 言 .../";
            global.msg[17] = "\\E5* 就 算 死 了 ， 他 还 是 从&  我 们 这 夺 走 了 些 东 西 。/";
            global.msg[18] = "\\E6* 我 真 希 望 他 还 活 着 ^1，&  这 样 我 就 能&  把 他 撕 成 碎 片 。/";
            global.msg[19] = "* 花 瓣 ..^1. 和 ..^1. 花 瓣 .../";
            global.msg[20] = "\\E7* 但 他 死 了 ^2。&* Clover也 是 。/";
            global.msg[21] = "\\E1* 我 们 能 做 的 只 有 离 开 。/";
            global.msg[22] = "\\EB* 希 望 你 永 世 不 得 安 宁 ^1，&  Flowey。/";
            global.msg[23] = "\\E2* 还 有 ..^2.&* 愿 你 安 息 ^1， Clover。/%%";
            if (scr_murderlv() > 7)
            {
                global.msg[1] = "\\E0* 无 论 他 认 为 他 有 多 强 .../";
                global.msg[2] = "* 他 打 不 赢 我 们 的 。/";
                global.msg[3] = "\\E7* 他 应 该 知 道 的 。/";
                global.msg[4] = "\\EL* ...";
                global.msg[5] = "\\E0* 看 起 来 我 们 的 “ 朋 友 ”&  彻 底 消 失 了 。/";
                global.msg[6] = "\\EB* 我 不 想 承 认&  我 对 这 损 失 感 到 很 遗 憾 。/";
                global.msg[7] = "\\E0* 我 们 走 。/%%";
            }
        }
        else
        {
            scr_charface(0, "C");
            global.msg[1] = "* 我 们 .^1.^1.&* 我 们 做 到 了 。/";
            global.msg[2] = "\\EL* 还 有 .../";
            global.msg[3] = "\\E4* 你 放 他 走 了 。/";
            global.msg[4] = "\\EB* 他 就 这 么 逃 跑 了 ^1，&  等 待 着 来 日 再 战 .../";
            global.msg[5] = "* 他 不 需 要 为 他 的 行 为&  承 担 任 何 后 果 吗 ？！/";
            global.msg[6] = "\\E3* 实 话 讲 .../";
            global.msg[7] = "\\E5* 我 不 知 道 那 个 选 择&  表 现 了 你 的 强 大 .../";
            global.msg[8] = "\\E6* 还 是 揭 露 了 你 的 懦 弱 。/";
            global.msg[9] = "* 我 倾 向 于 相 信 后 者 。/";
            global.msg[10] = "\\E1* 但 木 已 成 舟 。/";
            global.msg[11] = "* .../";
            global.msg[12] = "\\EL* 等 等 ^2。&* Frisk^1， 你 看 到 Clover了 吗 ？/";
            global.msg[13] = "\\EJ* 天 哪 ^1， 你 一 定 在 这 ，&  对 吧 ？/";
            global.msg[14] = "\\TS \\F0 \\E0 \\T0%";
            global.msg[15] = "* (你 在 房 间 里 &  寻 找 你 朋 友 的 踪 迹 ...)/";
            global.msg[16] = "* (但 谁 也 不 在 。 )/";
            scr_charface(17, 1);
            global.msg[18] = "* 所 以 他 仍 然 .../";
            global.msg[19] = "\\E2* .../";
            global.msg[20] = "* 他 走 了 ^2。&* 没 有 说 再 见 ^1， &  没 有 说 告 别 的 话 .../";
            global.msg[21] = "\\E6* 但 罪 魁 祸 首 逃 避 了 &  他 应 得 的 惩 罚 。/";
            global.msg[22] = "\\E5* 就 像 是 你 用 Clover的 生 命&  交 换 了 Flowey的 生 命 。/";
            global.msg[23] = "*我 不 觉 得 我 能 原 谅 &  你 这 么 做 ^1，&  Frisk./";
            global.msg[24] = "\\E4* 但 事 实 上 ^1，&  我 知 道 我 做 不 到 。/";
            global.msg[25] = "\\EL* 我 们 别 无 选 择 ，&  只 能 离 开 。/";
            global.msg[26] = "\\E2* ...对 不 起 ^1， Clover./";
            global.msg[27] = "* 我 为 一 切 事 情 向 你 道 歉 。/%%";
            if (scr_murderlv() > 7)
            {
                global.msg[1] = "* 我 ..^2. 真 的 不 明 白&  你 为 什 么 那 么 做 。/";
                global.msg[2] = "\\EC* 因 为 他 此 前 是 &  我 们 的 挚 友 吗 ？/";
                global.msg[3] = "\\E3* 还 是 说 你 很 讨 厌&  地 下 的 居 民 们 .../";
                global.msg[4] = "\\E4* 于 是 你 放 走 这 样 一 个 &  卑 鄙 的 家 伙 去 对 付 他 们 ？/";
                global.msg[5] = "\\E7* ..^2.这 个 问 题 的 答 案 &  对 我 来 说 并 不 重 要 。/";
                global.msg[6] = "* 最 终 的 结 果 是 一 样 的 。/";
                global.msg[7] = "\\EL* ^1.^1.^1./";
                global.msg[8] = "\\E0* 又 或 者 你 以 为 这 能 &  拯 救 我 们 的 “ 朋 友 ” ？/";
                global.msg[9] = "\\E3* 如 果 那 就 是 你 所 想 的 ^1，&  我 只 能 说 你 大 错 特 错 了 。/";
                global.msg[10] = "\\E7* 他 已 经 死 了 。/";
                global.msg[11] = "* 他 不 会 回 来 了 。/";
                global.msg[12] = "\\E0* 现 在 ^1， 我 们 走 吧 。/%%";
            }
        }
        if (won == 1)
        {
            scr_charface(0, "L");
            global.msg[1] = "* 所 以 ^1， 尽 管 经 历 了 这 一 切 .../";
            global.msg[2] = "* 结 果 还 是 一 样 的 。 /";
            global.msg[3] = "* .../";
            global.msg[4] = "\\E7* 没 必 要 再 在 这 里 待 了 。/";
            global.msg[5] = "* 快 走 吧 。 /%%";
            if (kill)
            {
                scr_charface(0, "B");
                global.msg[1] = "* 你 个 白 痴 。 /";
                global.msg[2] = "* 你 应 该 预 料 到 &  他 会 这 么 做 的 。 /";
                global.msg[3] = "\\E7* 他 真 是 个 讨 厌 鬼 ^1，&  不 是 吗 ？/";
                global.msg[4] = "\\E0* 没 必 要 再 在 这 里 待 了 。/";
                global.msg[5] = "* 快 走 吧 。 /%%";
            }
        }
        if (won == 2)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 所 以 我 们 又 一 次 &  得 到 了 这 个 结 局 。 /";
            global.msg[2] = "\\E3* 这 有 什 么 意 义 吗 ？/";
            global.msg[3] = "* .../";
            global.msg[4] = "\\E7* 随 你 便 吧 。/%%";
        }
        if (won == 3)
        {
            scr_charface(0, "B");
            global.msg[1] = "* 又 一 次 ？ /";
            global.msg[2] = "\\E3* 我 真 是 不 明 白 了 。/";
            global.msg[3] = "* 你 在 期 待 一 个 &  不 同 的 结 局 吗 ？ /";
            global.msg[4] = "* 但 很 明 显 &  你 并 没 有 得 到 一 个 。 /%%";
        }
        if (won == 4)
        {
            scr_charface(0, 3);
            global.msg[1] = "* 你 一 直 回 来 的 原 因 .../";
            global.msg[2] = "* 是 不 是 为 了 看 看 我 的 反 应 ？ /";
            global.msg[3] = "* 如 果 是 这 样 的 话 ..^2.&* 为 什 么 呢 ？ /";
            global.msg[4] = "* 你 就 那 么 急 切 地&  想 找 到 点 新 东 西 吗 ？ /%%";
            if (!kill)
            {
                global.msg[3] = "* 又 或 者 那 朵 花 会 。 /";
            }
        }
        if (won == 5)
        {
            scr_charface(0, 7);
            global.msg[1] = "* 嗯 。/";
            global.msg[2] = "* 如 果 没 有 别 的 东 西 了 ^1， &  你 和 那 朵 花 一 定 能 分 享&  那 种 对 更 多 可 能 性 的 渴 望 。 /";
            global.msg[3] = "\\E0* 说 实 话 ^1， 我 看 不 出&  这 有 什 么 吸 引 力 。/";
            global.msg[4] = "* .../";
            global.msg[5] = "\\E3* 下 次 你 再 回 来 的 时 候 .../";
            global.msg[6] = "* 我 会 什 么 都 不 给 你 说 。 /%%";
        }
        if (won >= 6)
        {
            scr_charface(0, 7);
            global.msg[1] = "* 没 别 的 事 可 做 了 吗 ？/%%";
        }
        if (global.flag[427] > 0)
        {
            scr_charface(0, 3);
            global.msg[0] = "* .../%%";
        }
        break;
    case room_icecave1:
        if (clover == 1)
        {
            if (obj_mysterydoor.image_index == 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 地 方 真 奇 怪 .../";
                global.msg[2] = "\\E9* 那 扇 门 后 面 有 什 么 ？/%%";
            }
            else
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 哇 ， 这 地 方 和 外 面 &  完 全 不 一 样 ！/";
                global.msg[2] = "\\E0* 这 里 的 环 境 真 独 特 ！/";
                scr_charface(3, "I");
                global.msg[4] = "* 有 意 思 ^1。 我 在 想 &  这 里 是 怎 么 变 成 这 样 的 。/";
                global.msg[5] = "\\E1* 我 感 觉 在 这 里&  好 像 有 什 么 ^1.^1..&  不 寻 常 的 东 西 。/";
                scr_cloface(6, 6);
                global.msg[7] = "* 是 的 ...我 也 感 觉 到 了 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 也 许 和 那 扇 门 有 关 系 。/";
                    scr_cloface(2, 6);
                    global.msg[3] = "* 很 奇 怪 ， 但 是 .../";
                    global.msg[4] = "* 在 你 做 完 某 一 件 事 之 前 ，&  我 想 它 是 不 会 打 开 的 .../";
                    global.msg[5] = "\\EA* ...一 件 非 常 特 别 的 事 。/";
                    scr_charface(6, 3);
                    global.msg[7] = "* 在 你 的 旅 途 已 经 到 了 &  终 点 之 后 的 事 。/";
                    scr_cloface(8, "D");
                    global.msg[9] = "* 但 那 时 候 打 开 了 它 &  还 有 什 么 意 义 呢 ？/";
                    scr_charface(10, 1);
                    global.msg[11] = "* ...确 实 搞 不 懂 。/%%";
                }
            }
            if (clover == 0)
            {
                scr_charface(0, 8);
                if (obj_mysterydoor.image_index == 1)
                {
                    global.msg[1] = "* 嗯 ^1？ 那 扇 门 自 己 打 开 了 ？/";
                    global.msg[2] = "\\E2* 奇 怪 。/%%";
                }
                else
                {
                    global.msg[1] = "* 我 们 可 从 来 没 &  打 开 过 那 扇 门 。/";
                    global.msg[2] = "\\E8* 也 许 这 是 一 个 最 容 易 &  忘 记 的 秘 密 。/%%";
                }
            }
        }
        break;
    case room_fire_labelevator:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 就 是 这 里 了 。/";
            scr_charface(2, "L");
            global.msg[3] = "* 见 证 真 相 的 时 刻 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_truelab_elevator:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 好^2 。&* 我 们 到 了 。/";
            scr_charface(2, 1);
            global.msg[3] = "* 是 时 候 探 寻 这 个 地 方 &  埋 藏 的 真 相 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 你 准 备 好 了 吗 ^1 ？&\\E6* 我 还 没 有 。/%%";
            }
        }
        break;
    case room_truelab_elevatorinside:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 你 已 经 没 有 回 头 路 了 。/";
            scr_charface(2, 9);
            global.msg[3] = "* 所 以 ， 向 前 冲 吧 。&* 就 像 你 一 直 以 来 的 那 样 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 你 是 无 懈 可 击 的 ，&  对 吧 ，Frisk ？/%%";
            }
        }
        break;
    case room_truelab_hall1:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* .../%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "L");
                global.msg[1] = "* 确 实 有 点 可 怕 ，不 是 吗 ？/%%";
            }
        }
        break;
    case room_truelab_hub:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 该 怎 么 办 .../";
            scr_charface(2, 0);
            global.msg[3] = "* 那 扇 门 看 起 来 &  是 解 决 问 题 的 关 键 。/";
            scr_cloface(4, 6);
            global.msg[5] = "* 我 猜 你 需 要 用 某 种 方 法 &  来 打 开 它 ？/";
            scr_charface(6, "L");
            global.msg[7] = "* 看 看 你 能 找 到 什 么 。/%%";
            if (global.flag[481] == 3)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 嘿 ^1， 其 中 一 个 灯 亮 了 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 右 边 的 那 扇 门 也 开 了 。/";
                scr_cloface(4, 7);
                global.msg[5] = "* 好 吧 ^1， 我 们 有 个 &  玩 游 戏 的 计 划 。/";
                scr_charface(6, 8);
                global.msg[7] = "* 找 到 那 些 钥 匙 ^1，&  以 解 锁 那 扇 门 。/%%";
                if (global.flag[482] == 3 || global.flag[483] == 3 || global.flag[484] == 4)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 又 一 把 钥 匙 ^1，&  又 开 了 一 扇 门 。/";
                    scr_charface(2, 8);
                    global.msg[3] = "* 继 续 加 油 。/%%";
                }
                if (global.flag[482] == 3 && global.flag[483] == 3 && global.flag[484] == 4)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 这 扇 门 已 经 打 开 了 。/";
                    scr_charface(2, 0);
                    global.msg[3] = "* 我 们 把 这 一 切 了 结 吧 。/%%";
                }
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 如 果 你 迫 切 需 要 一 些 药 品 ，&  这 里 有 一 台 自 动 售 货 机 。/";
                global.msg[2] = "* ..^2.希 望 你 不 需 要 它 们 。/%%";
                if (global.flag[481] == 3)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 我 们 已 经 完 成 一 个 了 ^1， &  还 差 三 个 。/%%";
                    if (global.flag[482] == 3 || global.flag[483] == 3 || global.flag[484] == 4)
                    {
                        scr_charface(0, 0);
                        global.msg[1] = "* 多 么 复 杂 的 系 统 啊 。/";
                        scr_cloface(2, "C");
                        global.msg[3] = "* 我 现 在 已 经 习 惯 了 。/%%";
                    }
                    if (global.flag[482] == 3 && global.flag[483] == 3 && global.flag[484] == 4)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* ...嗯 ？/%%";
                    }
                }
            }
            if (instance_exists(obj_cloverchara))
            {
                scr_cloface(0, 5);
                global.msg[1] = "* 这 地 方 有 点 恐 怖 。/";
                global.msg[2] = "\\E9* 为 什 么 每 一 个 科 学 家 &  都 有 一 个 秘 密 的 地 下 室 ？/";
                global.msg[3] = "\\E6* 不 管 怎 样 ^1， 你 都 应 该&  小 心 行 事 。/";
                scr_charface(4, "C");
                global.msg[5] = "* 我 同 意 最 后 一 句 话^2 。&\\E1  小 心 行 事 。/%%";
                global.flag[19] = 31;
                with (obj_cloverchara)
                {
                    instance_destroy();
                }
            }
        }
        break;
    case room_truelab_hall2:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* .../";
            scr_charface(2, 1);
            global.msg[3] = "* 深 呼 吸 ^2。&* 没 什 么 可 害 怕 的 .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 搞 得 像 你 没 有 被 吓 到 一 样 。 /";
                global.msg[2] = "\\E7* 你 只 是 更 善 于 把 那 &  隐 藏 起 来 。/";
                scr_charface(3, "H");
                global.msg[4] = "* 我 完 全 不 懂 你 什 么 意 思 。 /%%";
            }
        }
        break;
    case room_truelab_operatingroom:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 嗯 ， 是 的 ， 我 明 白 了&  我 明 白 了 .../";
            global.msg[2] = "\\E6* 我 讨 厌 这 个 地 方 的 一 切 。/%%";
            if (global.flag[481] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "\\EJ* 那 到 底 是 什 么 ？！？/";
                scr_charface(2, "L");
                global.msg[3] = "* 我 ..^2.&* 我 也 不 知 道 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_truelab_redlever:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 如 果 让 我 猜^1 ，我 会 说 &  那 里 需 要 一 把 红 色 钥 匙 &  来 打 开 。/";
            scr_charface(2, 8);
            global.msg[3] = "* 什 么 ^1？&* 你 已 经 失 了 智 了 。 /%%";
            if (global.flag[481] == 3)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 干 得 好 。/";
                scr_charface(2, 8);
                global.msg[3] = "* 是 时 候 看 看 结 果 如 何 了 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 嗯 ？/%%";
            }
            if (global.flag[482] == 3 || global.flag[483] == 3 || global.flag[484] == 4)
            {
                scr_charface(0, "C");
                global.msg[1] = "* 你 在 这 后 面 干 什 么 ？/%%";
            }
        }
        break;
    case room_truelab_prebed:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 这 些 显 示 器 &  真 的 吓 死 我 了 。/";
            scr_charface(2, "C");
            global.msg[3] = "* 它 们 ..^2. 很 奇 怪^1 ，&  至 少 可 以 这 么 说 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 就 让 我 们 快 点 了 结 &  这 一 切 吧 。/%%";
            }
        }
        break;
    case room_truelab_bedroom:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* .../%%";
            if (global.flag[484] > 1)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../";
                global.msg[2] = "* 我 该 说 什 么 呢 ？/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* 我 有 种 ..^2. &  不 好 的 预 感 。/%%";
                if (global.flag[484] > 1)
                {
                    scr_cloface(0, 4);
                    global.msg[1] = "* .../";
                    global.msg[2] = "\\E3* Kanako^1 ， 她 是 .../";
                    global.msg[3] = "* 她 是 我 认 识 的&  一 个 人 的 女 儿 。/";
                    if (global.flag[498] > 0)
                    {
                        global.msg[3] = "* 她 是 Ceroba 的 女 儿 。/";
                    }
                    global.msg[4] = "\\E4* 看 到 她 那 样 .../";
                    global.msg[5] = "\\E3* 我 ..^2. 很 高 兴&  看 到 她 还 活 着 。/";
                    scr_charface(6, "L");
                    global.msg[7] = "* .../%%";
                    if (global.flag[427] > 1)
                    {
                        scr_charface(0, "L");
                        global.msg[1] = "* (Frisk 。)/";
                        global.msg[2] = "* (现 在 不 是 闲 聊 的 时 候 。 )/%%";
                    }
                }
            }
        }
        break;
    case room_truelab_mirror:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 这 是 ..^2. 你 ？/";
            scr_charface(2, "C");
            global.msg[3] = "* 还 有 你 苦 恼 的 同 伴 们 。/%%";
            rand = random(ceil(666));
            if (global.debug == 1)
            {
                rand = 666;
            }
            if (global.flag[488] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* ......./";
                global.msg[2] = "* 这 感 觉 ..^1. 好 熟 悉^1 ，&  不 知 为 何 ？/";
                global.msg[3] = "* ..^2. 我 只 是 庆 幸&  事 情 解 决 了 。/%%";
            }
            if (rand == 666)
            {
                scr_cloface(0, "O");
                global.msg[1] = "\\Tj* 头 部 未 连 接 。&* 身 体 未 连 接 。&* 手 臂 未 连 接 。&* 腿 部 未 连 接 。&* 皮 肤 未 连 接 。&* 耳 朵 未 连 接 。&* 脸 部 未 连 接 。&* 嘴 巴 未 连 接 。&* 心 脏 未 连 接 。&* 牙 齿 未 连 接 。&* 心 脏 未 连 接 。%%";
                global.flag[427] -= 1;
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "H");
                global.msg[1] = "* 你 还 撑 得 住 吗^1 ，&  Frisk?/%%";
            }
        }
        break;
    case room_truelab_bluelever:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 蓝 色 钥 匙^1 ， 哈 .../";
            scr_charface(2, "I");
            global.msg[3] = "* 你 有 那 个 吗 ？/%%";
            if (global.flag[482] > 1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 蓝 色 钥 匙^1 ， 哈 .../";
                scr_charface(2, "I");
                global.msg[3] = "* 你 有 那 个 ^1， 对 吧 ？/%%";
            }
            if (global.flag[482] == 3)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 又 搞 定 一 个 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 做 得 不 错 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 觉 得 他 没 有 。/";
                scr_charface(2, "C");
                global.msg[3] = "* 那 就 快 点 找 到 它 。/%%";
                if (global.flag[482] > 1)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 你 还 在 等 什 么 ？/%%";
                }
                if (global.flag[482] == 3)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 这 儿 没 别 的 事 可 做 。/%%";
                }
            }
        }
        break;
    case room_truelab_hall3:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 这 些 显 示 器 .../";
            scr_charface(2, 1);
            global.msg[3] = "* 它 们 描 绘 的 画 面 令 人 不 安 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_truelab_shower:
        if (clover == 1)
        {
            scr_cloface(0, "B");
            global.msg[1] = "* 千 万 别 过 去 。/";
            scr_charface(2, "N");
            global.msg[3] = "* .../%%";
            if (global.flag[483] > 0)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 谢 天 谢 地 ，还 好 没 事 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 我 自 己 其 实 百 分 百 确 定 &  结 果 会 是 这 样 。/%%";
            }
            if (global.flag[483] == 3)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 为 什 么 房 间 会 被 建 成 这 样 ？ ？ ？/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "B");
                if (global.flag[483] > 0)
                {
                    scr_cloface(0, "D");
                    global.msg[1] = "* 当 — — 然 。/";
                    scr_charface(2, 9);
                    global.msg[3] = "* 你 不 愿 意 相 信 我 吗 ？/";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 不 。/";
                    scr_charface(6, "C");
                    global.msg[7] = " 好 吧 。/%%";
                }
                if (global.flag[483] == 3)
                {
                    scr_charface(0, "C");
                    global.msg[1] = "* 我 们 可 以 走 了 吗 ？/%%";
                }
            }
        }
        break;
    case room_truelab_determination:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 它 怎 么 知 道&  存 档 点 长 什 么 样 的 ？/";
            scr_charface(2, "L");
            global.msg[3] = "* 如 果 它 有 足 够 的 决 心 ...&  就 可 以 知 道 。/%%";
            if (instance_exists(obj_amalgam_save))
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 一 个 存 档 ..^2.\\E6 点 ...？/";
                scr_charface(2, 1);
                global.msg[3] = "* ...？ /%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
                if (instance_exists(obj_amalgam_save))
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 别 存 档 ， &  从 它 边 上 挤 过 去 。/";
                    scr_charface(2, 1);
                    global.msg[3] = "* 你 为 什 么 要 那 样 做 ？ /";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 我 也 不 知 道 ^2 。&* 我 就 是 感 觉 这 很 奇 怪 。/";
                    global.msg[6] = "\\EC* 也 许 是 这 个 地 方 &  让 我 疑 心 太 重 了 。/%%";
                }
            }
        }
        break;
    case room_truelab_tv:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 一 台 电 视 ？/";
            scr_charface(2, 0);
            global.msg[3] = "* 还 有 一 个 黄 色 钥 匙 插 槽 。/";
            global.msg[4] = "* 以 及 一 些 .../";
            global.msg[5] = "\\EN* 录 像 带 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "L");
                global.msg[1] = "* 我 们 不 应 该 再 逗 留 了 。/%%";
            }
            if (global.flag[484] == 4)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 钥 匙 已 归 位 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 干 得 不 错 。/";
                global.msg[4] = "\\E1* ..^2.我 们 赶 快 离 开 &  这 个 房 间 吧 。/%%";
            }
            if (global.flag[49] == 0.1)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* ..^2.\\E2噗 。/";
                scr_charface(2, "D");
                global.msg[3] = "* 好 恶 心 。/%%";
                global.flag[427] -= 1;
            }
            if (global.flag[49] == 0.2 || global.flag[49] == 0.3)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../";
                scr_charface(2, 6);
                global.msg[3] = "* .../%%";
                global.flag[427] -= 1;
            }
            if (global.flag[49] == 0.4)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 别 看 了^2 。&\\EL* 拜 托 。/%%";
                global.flag[427] -= 1;
            }
            if (global.flag[49] == 1)
            {
                scr_cloface(0, 5);
                global.msg[1] = "* ..^1. 那 是 你 ^1 ， 对 吗 ？/";
                scr_charface(2, 6);
                global.msg[3] = "* 你 的 推 理 能 力 很 强 ^1。&* 请 ^1解 释 一 下&  你 是 怎 么 发 现 的 。/";
                scr_cloface(4, 9);
                global.msg[5] = "* 好 吧 ，&  我 想 这 是 个 敏 感 话 题 。/";
                scr_charface(6, 7);
                global.msg[7] = "* .^1.^1.不 ^1， 应 该 我 道 歉 ^1。&\\E1* 我 刚 才 太 没 礼 貌 了 。/";
                global.msg[8] = "* 我 .../";
                scr_cloface(9, 8);
                global.msg[10] = "* 如 果 你 不 想 说 ，&  就 别 说 了 ！/";
                scr_charface(11, "B");
                global.msg[12] = "* 我 害 死 了 Asriel^1 ，&  Clover^2 。&  他 是 因 为 我 才 死 的 ！/";
                scr_cloface(13, 9);
                global.msg[14] = "* 但 你 不 是 故 意 的 啊 ！/";
                global.msg[15] = "\\E8* 你 想 让 怪 物 们 &  能 够 重 获 自 由 ^1， 对 吧 ？/";
                global.msg[16] = "\\E0* 这 也 正 是 我 想 要 的 。/";
                scr_charface(17, 2);
                global.msg[18] = "* .../%%";
                global.flag[49] = 2;
                global.flag[427] -= 1;
            }
        }
        break;
    case room_truelab_cooler:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* ...冰 箱 ？/";
            scr_charface(2, 1);
            global.msg[3] = "* 看 来 ..^2. 你 说 得 对 。/";
            scr_cloface(4, 9);
            global.msg[5] = "* ..^2.真 奇 怪 。/%%";
            if (global.flag[482] > 0)
            {
                scr_cloface(0, 3);
                global.msg[1] = "* .../%%";
            }
            if (global.flag[427] > 0)
            {
                scr_charface(0, "L");
                global.msg[3] = "* 小 心 些 。/%%";
                if (global.flag[482] > 0)
                {
                    scr_charface(0, "L");
                    global.msg[1] = "* .../";
                    global.msg[2] = "* 我 们 去 别 的 地 方 吧 。/%%";
                }
            }
            if (global.flag[490] == 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 里 的 阴 霾 &  怎 么 这 么 重 ？？/";
                scr_charface(2, "C");
                global.msg[3] = "* 我 想 你 暂 时 还 不 能&  在 这 里 做 什 么 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 0);
                    global.msg[1] = "* 让 我 们 试 试 另 一 个 房 间 。/%%";
                }
            }
        }
        break;
    case room_truelab_greenlever:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 这 个 插 槽 是 绿 色 的 。/";
            global.msg[2] = "\\EA* 绿 色 钥 匙 会 在 哪 里 呢 .../%%";
            if (global.flag[483] > 0)
            {
                scr_cloface(0, "H");
                global.msg[1] = "* 这 一 个 在 那 个 吓 人 的 &  帘 子 后 面 ^1， 对 吗 ？/%%";
            }
            if (global.flag[483] == 3)
            {
                scr_cloface(0, 7);
                global.msg[1] = "* 干 得 好 。/";
                global.msg[2] = "* 现 在 去 找 到 &  其 余 的 钥 匙 吧 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 嗯 .../%%";
                if (global.flag[483] > 0)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 你 在 等 什 么 ？/%%";
                }
                if (global.flag[483] == 3)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 我 们 赶 快 走 吧 。/%%";
                }
            }
        }
        break;
    case room_truelab_fan:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 我 们 必 须 打 开 那 些 风 扇 。/";
            scr_cloface(2, 1);
            global.msg[3] = "* 我 强 推 这 个 想 法 。/%%";
            if (instance_exists(obj_amalgam_dogevent))
            {
                if (obj_amalgam_dogevent.con >= 9)
                {
                    scr_cloface(0, "B");
                    global.msg[1] = "* 啊 啊 啊 啊 啊 。/";
                    scr_charface(2, "J");
                    global.msg[3] = "* 你 必 须 直 面 它 。/%%";
                }
            }
            if (global.flag[490] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 狗 狗 。/";
                global.msg[2] = "\\E7* 这 些 狗 稍 微 有 些 吓 人 ^1 ，&  但 它 们 还 算 是 狗 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 这 可 能 是 我 听 过 的&  最 糟 糕 的 双 关 。/";
                scr_cloface(2, 1);
                global.msg[3] = "* 但 你 明 明 在 笑 啊 !/";
                scr_charface(4, "H");
                global.msg[5] = "* 我 是 在 嘲 笑 你 。/";
                scr_cloface(6, "I");
                global.msg[7] = "* 当 然^1 ，当 然 。/%%";
                if (instance_exists(obj_amalgam_dogevent))
                {
                    if (obj_amalgam_dogevent.con >= 9)
                    {
                        scr_cloface(0, "H");
                        global.msg[1] = "* 你 ..^1. 能 行 的 ！/";
                        scr_charface(2, 1);
                        global.msg[3] = "* 祝 你 好 运 。/%%";
                    }
                }
                if (global.flag[490] > 0)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* 它 们 似 乎 很 满 足 ^1 ，&  至 少 看 起 来 是 。/%%";
                }
            }
        }
        break;
    case room_truelab_castle_elevator:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 唷 ^1， 又 一 部 电 梯 。/";
            scr_charface(2, 8);
            global.msg[3] = "* 看 来 我 们 可 以 &  离 开 这 里 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 当 然 ^1， &  要 先 等 到 电 源 接 通 。/%%";
            }
            if (global.flag[493] >= 12)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* .../%%";
            }
        }
        break;
    case room_truelab_prepower:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* .../%%";
        }
        break;
    case room_truelab_power:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 那 就 是 电 源 开 关 了 。/";
            global.msg[2] = "* 准 备 好 了 吗 ？/%%";
            if (global.flag[493] >= 12)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 真 是 皆 大 欢 喜 ^1，不 是 吗 ？/";
                scr_charface(2, "C");
                global.msg[3] = "* 你 ..^2. 可 以 这 么 说 。/";
                scr_cloface(4, 9);
                global.msg[5] = "* 是 ^1，我 知 道 。/";
                global.msg[6] = "\\E6* 但 我 觉 得 ..^2. 这 已 经 是&  你 能 得 到 的 最 好 结 局 了 。/";
                scr_charface(7, 0);
                global.msg[8] = "* 嗯 ^2。&* 也 许 是 这 样 的 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 8);
                    global.msg[1] = "* 我 们 走 吧^1 ，Frisk 。/%%";
                }
            }
        }
        break;
    case room_ice_dog:
        scr_charface(0, 9);
        global.msg[1] = "\\W* 这 真 的 是 一 个 &  Undertale \\RRed \\Oand \\YYellow\\W/%%";
        break;
    case room_water_fakehallway:
        if (clover == 1)
        {
            scr_cloface(0, 9);
            global.msg[1] = "* 嗯 ^1？ 是 我 分 心 了 ^1，&  还 是 这 条 长 廊 不 知 道 &  从 哪 冒 出 来 了 ？/";
            scr_charface(2, 1);
            global.msg[3] = "* 真 .^1.^1. 奇 怪 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 真 吓 人 。/%%";
            }
        }
        break;
    case room_dogshrine_ruined:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 这 里 到 底 发 生 了 什 么 ？/";
            scr_charface(2, 1);
            global.msg[3] = "* 这 里 曾 经 也 很 辉 煌 。/";
            scr_cloface(4, 6);
            global.msg[5] = "* 这 里 也 .^1.^1.&\\E7* 太 乱 了 。/";
            scr_charface(6, "G");
            global.msg[7] = "* 这 太 糟 糕 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 里 像 是 &  被 龙 卷 风 刮 过 .../";
                scr_charface(2, 1);
                global.msg[3] = "* 这 太 遗 憾 了 .../";
                global.msg[4] = "* ...我 们 可 能 只 能 看 到 &  这 里 昔 日 的 辉 煌 了 。/";
                global.msg[5] = "* 即 使 破 败 成 这 样 ， &  这 里 也 相 当 震 撼 人 心 。/";
                scr_cloface(6, 9);
                global.msg[7] = "* 那 个 充 气 娃 娃 &  看 起 来 也 很 伤 心 。/";
                scr_charface(8, "D");
                global.msg[9] = "* .../";
                scr_cloface(10, 1);
                global.msg[11] = "* ...那 是 我 说 过 的 吗 ？/%%";
                if (irememberyourneutrals > 0 || global.flag[249] < 20)
                {
                    scr_charface(8, 0);
                    scr_cloface(10, 6);
                }
            }
        }
        break;
    case room_dogshrine_mewmew:
        if (clover == 1)
        {
            if (global.flag[157] == 3)
            {
                scr_cloface(0, "J");
                global.msg[1] = "* 你 为 什 么 &  要 那 么 做 ？ ？ ？ ？ /";
                global.msg[2] = "\\E9* 你 这 样 一 点 都 不 酷 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, "J");
                    global.msg[1] = "* 快 离 开 这 ！ /%%";
                }
            }
            else if (instance_exists(obj_mewmew_npc))
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 这 是 ..^2.一 个 玩 偶 ？ /";
                scr_charface(2, 0);
                global.msg[3] = "* 我 有 种 预 感 ..^2.&  肯 定 没 那 么 简 单 。 /%%";
                if (global.flag[427] > 0)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* 只 有 一 种 方 法 可 以 知 道 ^1，&  对 吗 ？ /%%";
                }
            }
            else
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 挺 精 彩 的 表 演 ！ /";
                scr_charface(2, 8);
                global.msg[3] = "* 干 杯 ^1， 为 你 完 美 地 &  解 决 了 事 情 。 /";
                scr_cloface(4, 1);
                global.msg[5] = "* 干 杯 ！ /";
                global.msg[6] = "\\EA* 但 我 还 是 想 不 明 白 &  一 件 事 。/";
                global.msg[7] = "* Papyrus 的 水 槽 下&  怎 么 会 有 这 么 大 的 空 间 ！ ？ /";
                scr_charface(8, "H");
                global.msg[9] = "* 哦 ^1， 你 知 道 的 。 /%%";
                if (global.flag[427] == 1)
                {
                    scr_cloface(0, 6);
                    global.msg[1] = "* 但 我 真 的 不 知 道 。 /";
                    scr_charface(2, "N");
                    global.msg[3] = "* 真 的 吗 ^2？&\\E8* Frisk ^1 ， 你 知 道 吗 ？ /";
                    global.msg[4] = "\\TS \\F0 \\E0 \\T0%";
                    global.msg[5] = "* (你 自 信 地 点 了 点 头 。 )/";
                    scr_charface(6, "E");
                    global.msg[7] = "* 看 到 了 吗 ^2？ Frisk 也 知 道 ^2。&* 这 就 是 你 的 问 题 。 /%%";
                }
                if (global.flag[427] > 1)
                {
                    scr_cloface(0, "D");
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_fire_elevator_s:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 我 好 兴 奋 啊 ！ ！/";
            scr_charface(2, 0);
            global.msg[3] = "* 别 抱 太 大 希 望 ^2。&* 这 地 方 看 起 来 被 遗 弃 了 。/";
            scr_cloface(4, 7);
            global.msg[5] = "* 别 这 么 沮 丧 ^1！&* 这 里 还 是 有 很 多 &  值 得 一 看 的 东 西 的 ！/%%";
            if (global.flag[215] > 0)
            {
                scr_cloface(0, "D");
                global.msg[1] = "* 好 吧 ，那 太 令 人 失 望 了 。/";
                global.msg[2] = "\\EC* 真 抱 歉 ^1， Frisk 。/";
                scr_charface(3, "H");
                global.msg[4] = "* 我 敢 肯 定 你 完 全 &  没 错 过 任 何 有 趣 的 东 西 。/";
                scr_cloface(5, "J");
                global.msg[6] = "* 那 边 还 有 一 个 机 器 鳐 鱼 。/";
                global.msg[7] = "* 能 够 带 你 穿 越 &  粉 色 的 酸 湖 。/";
                scr_charface(8, "N");
                global.msg[9] = "* ？？？？？/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 我 们 走 吧 ！/%%";
                if (global.flag[215] > 0)
                {
                    scr_cloface(0, "C");
                    global.msg[1] = "* 我 们 还 是 走 吧 .../%%";
                }
            }
            if (global.flag[38] < 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 嘿 ^1！&* 我 都 没 想 到 这 电 梯 还 能 用 ！/";
                scr_charface(2, "G");
                global.msg[3] = "* 你 要 去 哪 ^1？&\\E0* 这 不 是 前 往 城 堡 的 路 。/";
                scr_cloface(4, 2);
                global.msg[5] = "* 拜 托 ^1！&  绕 远 路 没 什 么 不 好 的 ！/";
                scr_charface(6, 7);
                global.msg[7] = "* ^1.^1.^1.\\E8随 你 怎 么 说 吧 。/%%";
                global.flag[38] = 1;
                if (instance_exists(obj_cloverchara))
                {
                    with (obj_cloverchara)
                    {
                        instance_destroy();
                    }
                }
            }
        }
        break;
    case room_steamworks_36:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 哦 ^1， 那 个 溜 道 应 该 能 把 你&  带 到 蒸 汽 工 厂 的 另 一 侧 ！/";
            scr_charface(2, 0);
            global.msg[3] = "* 卡 住 的 那 个 ？/";
            scr_cloface(4, 1);
            global.msg[5] = "* 就 是 那 ^1-&\\E9* 等 等 你 说 它 卡 住 了&  是 什 么 意 思 ？/%%";
            if (global.flag[215] > 0)
            {
                scr_cloface(0, "D");
                global.msg[1] = "* 你 就 不 能 强 行 把 &  那 个 投 递 槽 打 开 吗 .../";
                scr_charface(2, "H");
                global.msg[3] = "* 他 肯 定 打 不 开 的 ^1，&  Clover 。/";
                scr_cloface(4, "C");
                global.msg[5] = "* 我 知 道 .../%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 的 意 思 是 ^1，&  没 事 的 对 吧 ？/";
                global.msg[2] = "* 你 只 是 要 走 很 长 的 路 ！/";
                scr_charface(3, 0);
                global.msg[4] = "* 绕 一 大 圈 。/";
                scr_cloface(5, 6);
                global.msg[6] = "\\E1* 什 么 ？ /";
                scr_charface(7, 0);
                global.msg[8] = "* 确 实 “ 有 很 长 的 路 要 走 ” 。/";
                scr_cloface(9, "B");
                global.msg[10] = "* 什 么 。/%%";
                if (global.flag[215] > 0)
                {
                    scr_charface(0, 8);
                    global.msg[1] = "* 这 又 不 是 世 界 未 日 ^1， &  你 至 于 这 么 夸 张 吗 。/";
                    scr_cloface(2, "G");
                    global.msg[3] = "* 世 界 未 日 是 什 么 ？/%%";
                }
            }
        }
        break;
    case room_steamworks_35:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 这 个 房 间 ..^2.很 难 通 过 。/";
            scr_charface(2, "I");
            global.msg[3] = "* 为 什 么 呢 ？/";
            scr_cloface(4, 1);
            global.msg[5] = "* 我 也 曾 被 一 个 &  杀 手 机 器 人 追 杀 过 。/";
            scr_charface(6, "E");
            global.msg[7] = "* 你 认 真 的 ？ ？/";
            scr_cloface(8, 0);
            global.msg[9] = "* 嗯 。/";
            global.msg[10] = "\\EP* 但 那 个 机 器 人 很 酷 ^1，&  很 有 趣 ^1，&  而 且 一 点 也 不 差 劲 。/";
            scr_charface(11, "E");
            global.msg[12] = "* 当 然 ^1， 你 可 完 全 没 有 偏 见 。/";
            scr_cloface(13, 1);
            global.msg[14] = "* 你 说 的 太 对 了 ！/%%";
            if (global.flag[215] > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 要 是 能 再 见 到 他 就 好 了 ^1，&  但 是 。/";
                global.msg[2] = "* 我 很 确 定 他 &  现 在 一 切 都 好 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "A");
                global.msg[1] = "* 我 想 知 道 他 怎 么 样 了 .../";
                scr_charface(2, 8);
                global.msg[3] = "* 他 叫 什 么 ？/";
                scr_cloface(4, 1);
                global.msg[5] = "* Axis 014!/";
                scr_charface(6, 0);
                global.msg[7] = "* .../";
                global.msg[8] = "\\EC* 那 其 他 13 个 怎 么 样 了 。/";
                scr_cloface(9, 6);
                global.msg[10] = "* 我 觉 得 他 们 ..^2.死 了 ？/%%";
                if (global.flag[427] > 1)
                {
                    scr_cloface(0, "H");
                    global.msg[1] = "* 现 在 想 起 这 些&  有 点 让 人 伤 心 。/%%";
                }
                if (global.flag[215] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 我 很 确 定 你 会 喜 欢 他 的 ^1，&  Frisk 。/";
                    scr_charface(2, 8);
                    global.msg[3] = "* 为 什 么 呢 ？/";
                    scr_cloface(4, 1);
                    global.msg[5] = "* 他 俩 都 看 似 是 个 呆 瓜 &  但 实 则 都 很 强 大 。/%%";
                }
                if (global.flag[215] > 0 && global.flag[215] < 4 && global.flag[498] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* Ceroba 可 能 经 常 会&  来 看 望 他 ^1， 对 吗 ？/";
                    global.msg[2] = "\\Y\\E6* ..^2. 等 等 ^1， 你 就 不 能&   \\G问 问 她 吗 ？/%%";
                    if (global.ghostcolor == 1)
                    {
                        global.msg[2] = "\\W* ..^2. 等 等 ^1， 你 就 不 能&   \\Y问 问 她 吗 ？/%%";
                    }
                }
            }
        }
        break;
    case room_steamworks_34:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 真 美 丽 .../";
            scr_charface(2, 3);
            global.msg[3] = "* (真 迷 人 ...)/%%";
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 看 ^1！&* 扶 手 。/";
                scr_charface(2, 8);
                global.msg[3] = "* 真 神 奇 ^2。&* 这 是 真 正 的 工 程 壮 举 。/";
                scr_cloface(4, 6);
                global.msg[5] = "* 目 前 再 来 看 ^1， &  我 不 太 相 信 这 些 扶 手 &  还 能 撑 得 住 。/%%";
            }
            if (global.flag[427] > 1)
            {
                scr_cloface(0, 8);
                global.msg[1] = "* 我 猜 这 就 是 &  废 弃 设 施 的 缺 点 。/";
                scr_charface(2, 1);
                global.msg[3] = "* (..^2.那 优 点 是 什 么 ？ )/%%";
            }
        }
        break;
    case room_steamworks_33:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 我 们 找 到 了 电 脑 房 ！ /";
            scr_charface(2, 0);
            global.msg[3] = "* 这 玩 意 是 干 啥 的 ？ /";
            scr_cloface(4, 1);
            global.msg[5] = "* 我 不 记 得 了 ！ /%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 别 碰 它 。 /";
                global.msg[2] = "\\EQ* 只 是 以 防 万 一 。/%%";
            }
            if (global.flag[215] > 0)
            {
                scr_cloface(0, 6);
                global.msg[1] = "* 我 是 认 真 的 ^1，&  别 碰 任 何 按 键 。/";
                global.msg[2] = "\\E5* 这 其 中 有 一 个 能 &  关 掉 附 近 所 有 的 机 器 人 ^1？&  我 想 ？/";
                scr_charface(3, 0);
                global.msg[5] = "* 最 好 还 是 顺 其 自 然 吧 。/%%";
            }
        }
        break;
    case room_steamworks_32:
        if (clover == 1)
        {
            scr_cloface(0, 0);
            global.msg[1] = "* 天 哪 ， 你 好 呀 jandroidd 。/";
            scr_charface(2, "C");
            global.msg[3] = "* (他 没 发 神 经 吧 。 )/%%";
            if (global.flag[215] > 0)
            {
                scr_cloface(0, "C");
                global.msg[1] = "* 叹 气 .../";
                scr_charface(2, "C");
                global.msg[3] = "* (他 为 什 么 要 喊 这 么 大 声 。)/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 这 个 地 方 一 点 也 没 有 变 。 /";
                global.msg[2] = "\\E7* 我 ..^2.很 高 兴 。/%%";
                scr_charface(3, 1);
                global.msg[4] = "* 我 很 ..^2. 熟 悉 那 种 感 觉 。 /%%";
                if (global.flag[215] > 0)
                {
                    scr_cloface(0, 0);
                    global.msg[1] = "* 好 吧 ，我 已 经 缓 过 来 了 。/";
                    scr_charface(2, "C");
                    global.msg[3] = "* 还 挺 快 的 。/";
                    scr_cloface(4, 1);
                    global.msg[5] = "* 哈 哈 ^1，我 还 能 说 什 么 呢 ^1！&* 世 事 难 料 啊 ！/";
                    scr_charface(6, 8);
                    global.msg[7] = "* ..^2.你 还 是 没 缓 过 来 。/";
                    scr_cloface(8, 1);
                    global.msg[9] = "*/";
                    scr_charface(10, 8);
                    global.msg[11] = "* 我 就 当 你 &  说 的 是 “ 不 ” 了 。/%%";
                }
            }
        }
        break;
    case room_steamworks_factory_elevator:
        if (clover == 1)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 好 的 ^1，让 我 们 启 动 电 梯 吧 。 /";
            scr_charface(2, "C");
            global.msg[3] = "* 别 抱 太 大 的 希 望 。 /%%";
            if (global.flag[215] == 1)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 我 们 开 始 吧 。 /";
                scr_charface(2, "C");
                global.msg[3] = "* .../%%";
            }
            if (global.flag[215] == 2)
            {
                scr_cloface(0, "Q");
                global.msg[1] = "* 求 你 了 。 /";
                scr_charface(2, "C");
                global.msg[3] = "* .../%%";
            }
            if (global.flag[215] == 3)
            {
                scr_cloface(0, 1);
                global.msg[1] = "* 我 现 在 失 望 透 顶 了 。&  我 这 一 天 都 被 毁 了 。/";
                scr_charface(2, 8);
                global.msg[3] = "* 好 了 好 了 ^1， 你 个 巨 婴 。 /";
                scr_cloface(4, "D");
                global.msg[5] = "* 哼 。/%%";
            }
        }
        if (clover == 0 && global.flag[215] == 3)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 也 许 有 一 天 ^1， 对 吧 ？ /%%";
        }
        break;
    case room_newhome_elevator:
        if (clover == 1)
        {
            scr_cloface(0, 7);
            global.msg[1] = "* 每 一 天 都 好 比 一 部 电 梯 。/%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, 1);
                global.msg[1] = "* 不 是 上 升 就 是 下 降 。/";
                global.msg[2] = "\\E0* 但 你 不 可 能 永 远 待 在 &  同 一 个 地 方 。/%%";
            }
        }
        break;
    case room_newhome_01:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 这 里 就 是 首 都 了 .../";
            scr_cloface(2, 0);
            global.msg[3] = "* 这 里 美 得 难 以 置 信 。/";
            global.msg[4] = "* 真 可 惜 我 没 能 在 这 里 &  多 待 一 会 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 在 这 里 随 便 转 转 吧 ！/";
                scr_charface(2, 0);
                global.msg[3] = "* 我 确 定 你 能 找 得 到 &  你 感 兴 趣 的 东 西 。/%%";
            }
        }
        break;
    case room_newhome_02:
        if (clover == 1)
        {
            scr_charface(0, 8);
            global.msg[1] = "* 这 些 建 筑 真 是 &  令 人 印 象 深 刻 。/";
            scr_cloface(2, 1);
            global.msg[3] = "* 真 的 吗 ？？/";
            global.msg[4] = "\\E6* 我 还 以 为 会 有 &  很 多 行 人 呢 .../";
            scr_charface(5, "I");
            global.msg[6] = "* 嗯 .../%%";
            if (global.flag[427] == 1)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 啊^1 ，Mettaton 的 广 播 。/";
                scr_cloface(2, 0);
                global.msg[3] = "* 哦 ^1！ 大 家 都 进 屋 去 看 &  电 视 上 我 们 的 表 演 了 ！/";
                global.msg[4] = "* 那 就 说 得 通 了 ^1。&* 你 是 最 后 一 个 人 类 ，&  需 要 去 .../";
                global.msg[5] = "\\E9* .../";
                scr_charface(6, 1);
                global.msg[7] = "* 去 解 放 所 有 人 。/%%";
                if (global.flag[425] == 1)
                {
                    scr_charface(0, "L");
                    global.msg[1] = "\\E1* 啊 。 /";
                    scr_cloface(2, 6);
                    global.msg[3] = "* 这 是 什 么 ？/";
                    scr_charface(4, 1);
                    global.msg[5] = "* Mettaton 的 广 播 。/";
                    scr_cloface(6, 9);
                    global.msg[7] = "* ...是 的 。/%%";
                }
            }
            if (global.flag[427] > 1)
            {
                scr_charface(0, 1);
                global.msg[1] = "* .../%%";
                if (global.flag[425] == 1)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case room_newhome_03:
        if (instance_exists(obj_cloverchara))
        {
            scr_cloface(0, 9);
            global.msg[1] = "* .../%%";
        }
        else if (clover == 1)
        {
            scr_charface(0, 1);
            global.msg[1] = "* Clover^1 ， 你 .../";
            scr_cloface(2, 8);
            global.msg[3] = "* .../%%";
            if (global.lv > 10 || scr_murderlv() > 2)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../";
                global.msg[2] = "* 最 终 ^1， 你 所 有 的 行 为&  相 加 产 生 了 结 果 。/";
                global.msg[3] = "* 无 论 那 结 果 是 好 还 是 坏 .../";
                global.msg[4] = "\\E6* 那 取 决 于 你 是 怎 样 的 人 。/";
                global.msg[5] = "* 你 选 择 去 做 的 事 情 .../";
                global.msg[6] = "* 结 合 你 的 情 况 ^1，&  还 有 回 档 。/";
                scr_charface(7, 0);
                global.msg[8] = "* 显 然 ^2。&* 你 是 想 说 什 么 ？/";
                scr_cloface(9, 9);
                global.msg[10] = "* ... 没 什 么 。/%%";
            }
            if (global.flag[427] == 1)
            {
                scr_cloface(0, 8);
                global.msg[1] = "* 这 里 真 的 太 美 丽 了 。/";
                scr_charface(2, "L");
                global.msg[3] = "* Clover 。/";
                scr_cloface(4, 1);
                global.msg[5] = "* 我 们 已 经 离 城 堡 很 近 了 ^2-%";
                scr_charface(6, 0);
                global.msg[7] = "* Clover 。/";
                global.msg[8] = "\\E1* ...你 为 什 么 那 么 做 ？/";
                scr_cloface(9, 9);
                global.msg[10] = "* .^1.^1.因 为 那 是 我 力 所 能 及 的 。/";
                global.msg[11] = "* 即 使 我 要 为 此 &  付 出 生 命 的 代 价 .../";
                global.msg[12] = "* 即 使 那 意 味 着 &  我 将 无 法 看 到 大 家 &  重 获 自 由 .../";
                scr_charface(13, 1);
                global.msg[14] = "* 但 那 是 你 必 须 做 的 。/";
                global.msg[15] = "* 那 是 唯 一 一 个 &  合 理 的 选 择 。/";
                scr_cloface(16, 8);
                global.msg[17] = "* .^1.^1.是 啊 ^1。&* 差 不 多 就 是 那 样 。/%%";
                if (global.lv > 10 || scr_murderlv() > 2)
                {
                    scr_cloface(0, 9);
                    global.msg[1] = "* 只 是 ^1， 别 指 望 别 人&  会 忽 略 你 的 行 为 。/";
                    global.msg[2] = "* 你 可 以 跨 过 它 们 ^1，&  但 它 们 总 会 跟 在 你 身 后 。/%%";
                }
            }
            if (global.flag[427] > 1)
            {
                scr_charface(0, "F");
                global.msg[1] = "* ...谢 谢 你 &  向 我 分 享 了 那 些 。/";
                scr_cloface(2, 8);
                global.msg[3] = "* .../%%";
                if (global.lv > 10 || scr_murderlv() > 2)
                {
                    scr_charface(0, 3);
                    global.msg[1] = "* ..^2. 嗯 。/%%";
                }
            }
        }
        if (clover == 0 && global.flag[38] >= 2 && !ossafe_file_exists("system_information_963"))
        {
            scr_charface(0, 8);
            global.msg[1] = "* ..^2.即 使 到 了 现 在 ，&  你 还 是 那 么 无 私 。/";
            global.msg[2] = "\\EI* 你 知 道 吗 ^1， 你 的 这 趟 旅 程&  非 常 的 精 彩 ，&  途 中 的 一 切 都 是 .../";
            global.msg[3] = "\\E9* 但 我 还 是 有 些 遗 憾 。&  我 自 始 至 终 都 是 个 鬼 魂 ，&  没 能 亲 身 感 受 到 这 一 切 。/%%";
        }
        break;
    case room_newhome_04:
        if (clover == 1)
        {
            scr_charface(0, "I");
            global.msg[1] = "* 我 猜 ^1， 这 部 电 梯 通 往 城 堡 ？/";
            scr_cloface(2, 0);
            global.msg[3] = "* 是 的 ^1！ 我 听 说 过 。/";
            global.msg[4] = "\\EA* 天 哪 ^1， 这 附 近 电 梯 真 多 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 0);
                global.msg[1] = "* 我 们 随 时 准 备 出 发 。/";
                scr_charface(2, 0);
                global.msg[3] = "* 如 果 你 愿 意 ， 你 可 以 再 &  多 转 一 会 。/";
                global.msg[4] = "\\EH* 但 别 花 太 长 时 间 。/%%";
            }
        }
        break;
    case room_water_yellow:
        if (clover == 1)
        {
            scr_charface(0, 0);
            global.msg[1] = "* 多 么 .^1.^1.宁 静 啊 。/";
            scr_cloface(2, 6);
            global.msg[3] = "* 是 啊 .../";
            global.msg[4] = "\\E7* 我 可 以 在 这 里 打 个 盹 。/%%";
            if (global.flag[214] == 1)
            {
                scr_charface(0, 1);
                global.msg[1] = "* .../";
                global.msg[2] = "* Clover^1？&* 你 还 好 吗 ？/%%";
                scr_cloface(3, 9);
                global.msg[4] = "* 我 ..^1. 还 好 。/";
                global.msg[5] = "\\E8* 谢 谢 你 。/%%";
            }
            if (global.flag[427] > 0)
            {
                scr_charface(0, 8);
                global.msg[1] = "* 真 的 很 .../";
                scr_cloface(2, 0);
                global.msg[3] = "* 没 错 。/";
                global.msg[4] = "\\E1* 这 是 个 休 息 的 &  好 地 方 ^1， 不 是 吗 ？/%%";
                if (global.flag[214] == 1)
                {
                    scr_charface(0, 1);
                    global.msg[1] = "* .../%%";
                }
            }
        }
        break;
    case coming_soon:
        if (clover == 1)
        {
            scr_charface(0, "I");
            global.msg[1] = "* 下 部 雪 镇 ^1， 嗯 ^1？&* 不 得 不 说 我 挺 好 奇 的 。/";
            scr_cloface(2, 1);
            global.msg[3] = "* 我 也 早 就 等 不 及 了 。/%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, "D");
                global.msg[1] = "* 那 我 们 还 在 等 什 么 ？/";
                global.msg[2] = "\\E2* 好 了 ^1， 我 们 快 走 吧 ！/%%";
            }
        }
        break;
    case room_fire_alley:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 这 里 现 在 是 ..^2.一 个 商 店 ？ /";
            scr_charface(2, 0);
            global.msg[3] = "* 请 别 买 字 面 意 义 上 的 垃 圾 。 /";
            scr_cloface(4, "I");
            global.msg[5] = "* 哦 哦 哦 哦 你 想 买 垃 圾 &  哦 哦 哦 哦 哦 /%%";
            if (global.flag[427] > 0)
            {
                scr_charface(0, "H");
                global.msg[1] = "* 别 听 那 个 恶 魔 说 的 话 ^1，&  Frisk 。/";
                scr_cloface(2, "D");
                global.msg[3] = "* 哦 ^1 「 我 」 原 来 是 恶 魔 吗 ？/";
                global.msg[4] = "\\EK* 我 觉 得 你 只 是&  讨 厌 有 趣 的 事 情 。/";
                scr_charface(5, "D");
                global.msg[6] = "* 字 面 意 义 上 的 ^2。 垃 圾 。/";
                global.msg[7] = "\\EA* 而 且 ^1， 我 一 直 把 Frisk的&  最 佳 利 益 放 在 心 上 。/";
                scr_cloface(8, 1);
                global.msg[9] = "* 你 真 是 位 仁 慈 的 天 使 啊 ～/%%";
            }
            if (global.flag[443] == 1 || global.flag[442] == 1)
            {
                scr_cloface(0, "B");
                global.msg[1] = "* 那 是 怎 么 回 事 ？ ？ ？ ？/";
                global.msg[2] = "* 是 谁 ？ ？ ^1 &  把 我 的 东 西 ？ ？ ^1&  扔 进 垃 圾 堆 里 了 ？ ？ ？/";
                global.msg[3] = "\\ED* 这 最 好 有 个 合 理 的 解 释 。/%%";
                if (global.flag[427] > 0)
                {
                    scr_cloface(0, 7);
                    global.msg[1] = "* 至 少 它 们 现 在 很 安 全 了 。/";
                    scr_charface(2, "E");
                    global.msg[3] = "* .../";
                    scr_cloface(4, 6);
                    global.msg[5] = "* 它 们 ..^1. 「 现 在 」 很 安 全 ^1，&  对 吧 Frisk ？/";
                    global.msg[6] = "\\TS \\F0 \\E0 \\T0%";
                    global.msg[7] = "*  (...) /";
                    scr_cloface(8, 5);
                    global.msg[9] = "* Frisk ？/";
                    scr_charface(10, "E");
                    global.msg[11] = "* 哦 哦 哦 哦 哦 哦 你 想 把 它 们 &  扔 了 哦 哦 哦 哦 哦 哦 哦 /";
                    scr_cloface(12, "B");
                    global.msg[13] = "* 还 是 别 拿 那 &  开 玩 笑 了 谢 谢 。/%%";
                    if (global.flag[443] == 0)
                    {
                        scr_cloface(0, 8);
                        global.msg[1] = "* 你 能 把 我 的 帽 子 &  拿 回 来 吗 ^1 ？ 求 求 了 ？/";
                        global.msg[2] = "\\E9* 这 ..^2.对 我 来 说 十 分 重 要 。/%%";
                    }
                    if (global.flag[442] == 0)
                    {
                        scr_cloface(0, 6);
                        global.msg[1] = "* 你 不 用 去 买 它 ， 但 .../";
                        global.msg[2] = "\\E7* 那 把 左 轮 手 枪 以 前 &  帮 过 我 很 大 的 忙 。/%%";
                    }
                }
                if (global.flag[117] == 3 || global.flag[116] == 3)
                {
                    scr_cloface(0, "E");
                    global.msg[1] = "* 你 知 道 的 ^1， &  你 不 该 扔 掉 我 的 东 西 的 。/";
                    global.msg[2] = "\\EC* 唉 .../%%";
                    if (global.flag[427] > 0)
                    {
                        scr_cloface(0, "P");
                        global.msg[1] = "* 不 行 ^2。 没 礼 貌 的 人 &  不 配 有 第 二 次 对 话 。/";
                        scr_charface(2, "C");
                        global.msg[3] = "* (...但 现 在 这 确 实 也 &  算 是 第 二 次 对 话 。)/%%";
                    }
                }
            }
        }
        break;
    case room_fire_rooftop:
        if (clover == 1)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 感 觉 我 好 像 已 经 &  来 过 这 个 屋 顶 上 百 次 了 .../%%";
            if (global.flag[427] > 0)
            {
                scr_cloface(0, 9);
                global.msg[1] = "* .../%%";
            }
        }
        break;
}
if (scr_murderlv() == 7 && global.plot >= 101 && room < room_tundra_garage && room != room_tundra_town)
{
    scr_cloface(0, 6);
    global.msg[1] = "* .../%%";
}
if (global.flag[427] > 9 && clover == 1)
{
    if (ghostchoose == 0)
    {
        scr_charface(0, 7);
        global.msg[1] = "* 你 能 别 看 了 吗 ？/%%";
    }
    else
    {
        scr_cloface(0, 6);
        global.msg[1] = "* 我 们 还 不 走 吗 ？/%%";
    }
}
else if (global.flag[427] >= 5 && clover == 0)
{
    scr_charface(0, "E");
    global.msg[1] = "* 没 别 的 事 可 做 了 吗 ？/%%";
}
if (global.flag[427] < 2)
{
    global.flag[249] += 1;
}
global.flag[427] += 1;
if (sweetsilence == 1)
{
    global.msg[0] = "*^1 .^1 .^1 ./";
    global.msg[1] = "* 只 剩 下 了 寂 静 。 /%%";
}
if (!instance_exists(obj_ghostbuds))
{
    instance_create(obj_mainchara.x, obj_mainchara.y, obj_ghostbuds);
}
instance_create(0, 0, obj_dialoguer);
scr_next_talk_check();
