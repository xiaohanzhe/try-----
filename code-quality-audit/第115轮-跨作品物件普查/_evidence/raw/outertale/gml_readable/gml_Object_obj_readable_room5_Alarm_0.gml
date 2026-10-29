myinteract = 3;
global.msc = 0;
global.typer = 5;
global.facechoice = 0;
global.faceemotion = 0;
global.msg[0] = scr_gettext("obj_readable_room5_64");
if (room == room_asrielroom_final)
{
    global.msg[0] = scr_gettext("obj_readable_room5_68");
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_69");
    }
}
if (room == room_asgoreroom)
{
    global.msg[0] = scr_gettext("obj_readable_room5_74");
    global.msg[1] = scr_gettext("obj_readable_room5_75");
    if (global.flag[7] == 1)
    {
        global.msg[1] = scr_gettext("obj_readable_room5_78");
    }
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_80");
    }
    if (x < 208)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_82");
    }
}
if (room == room_tundra_xoxopuzz)
{
    global.msc = 696;
}
if (room == room_fire_lab1)
{
    global.msg[0] = scr_gettext("obj_readable_room5_92");
    if (global.plot < 126 && scr_murderlv() < 12)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_93");
    }
    if (y >= 125 && x > 800)
    {
        global.msc = 827;
    }
}
if (room == room_fire_lab2)
{
    if (x < 130)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_104");
        global.msg[1] = scr_gettext("obj_readable_room5_105");
    }
    if (x < 204 && x > 144)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_110");
        global.msg[1] = scr_gettext("obj_readable_room5_111");
    }
    if (x < 575 && x > 474)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_116");
    }
    if (x > 575)
    {
        global.msc = 647;
    }
}
if (room == room_water_piano)
{
    global.msg[0] = scr_gettext("obj_readable_room5_126");
    global.msg[1] = scr_gettext("obj_readable_room5_127");
}
if (room == room_water7)
{
    global.msg[0] = scr_gettext("obj_readable_room5_131");
    global.msg[1] = scr_gettext("obj_readable_room5_132");
    read += 1;
}
if (room == room_tundra_library)
{
    global.msg[0] = scr_gettext("obj_readable_room5_138");
    global.msg[1] = scr_gettext("obj_readable_room5_139");
    if (global.ghost == 1 || scr_murderlv() >= 7 || ossafe_file_exists("system_information_963") || ossafe_file_exists("system_information_964"))
    {
        global.msg[2] = scr_gettext("obj_readable_room5_140");
    }
    else
    {
        global.msg[2] = "* 毕 竟 ^1，人 类 已 经 证 明 & 他 们 的 灵 魂 不 需 要 &  这 些 东 西 的 存 在 。/";
    }
    scr_charface(3, 6);
    global.msg[4] = "* (...)/%%";
    global.flag[365] = 1;
}
if (room == room_water_undynehouse)
{
    global.msg[0] = scr_gettext("obj_readable_room5_145");
    global.msg[1] = scr_gettext("obj_readable_room5_146");
}
if (room == room_water_undynehouse && x < 80)
{
    global.facechoice = 5;
    global.faceemotion = 4;
    global.typer = 37;
    global.msg[0] = scr_gettext("obj_readable_room5_154");
    global.msg[1] = scr_gettext("obj_readable_room5_155");
}
if (room == room_fire2)
{
    global.msg[0] = scr_gettext("obj_readable_room5_160");
    if (global.flag[353] > 7)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_163");
    }
    if (global.flag[353] > 15)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_167");
    }
    if (global.flag[353] > 15 && global.flag[7] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_171");
    }
}
if (room == room_fire_lab1 && x > 828 && x < 868 && y < 90)
{
    global.msg[0] = scr_gettext("obj_readable_room5_177");
}
if (room == room_tundra_sansroom)
{
    if (x < 128)
    {
        if (global.flag[497] < 3)
        {
            global.msg[0] = scr_gettext("obj_readable_room5_186");
            global.msg[1] = scr_gettext("obj_readable_room5_187");
            global.flag[497] = 3;
        }
        else
        {
            global.msg[0] = scr_gettext("obj_readable_room5_192");
        }
    }
    else
    {
        global.msg[0] = scr_gettext("obj_readable_room5_197");
    }
}
if (room == room_fire_cookingshow)
{
    global.msg[0] = scr_gettext("obj_readable_room5_203");
}
if (room == room_dogshrine)
{
    global.msc = 0;
    global.msg[0] = scr_gettext("obj_readable_room5_209");
    if (dognumber == 1)
    {
        global.msc = 950;
    }
    if (dognumber == 2)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_216");
        global.msg[1] = scr_gettext("obj_readable_room5_217");
        global.msg[2] = scr_gettext("obj_readable_room5_218");
    }
    if (dognumber == 3)
    {
        global.msc = 955;
    }
    if (dognumber == 4)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_226");
        global.msg[1] = scr_gettext("obj_readable_room5_227");
    }
    if (dognumber == 5)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_231");
        global.msg[1] = scr_gettext("obj_readable_room5_232");
    }
    if (dognumber == 6)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_236");
        global.msg[1] = scr_gettext("obj_readable_room5_237");
    }
    if (dognumber == 7)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_241");
        global.msg[1] = scr_gettext("obj_readable_room5_242");
    }
    if (dognumber == 8)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_246");
        global.msg[1] = scr_gettext("obj_readable_room5_247");
        global.msg[2] = scr_gettext("obj_readable_room5_248");
    }
    if (dognumber == 9)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_252");
        global.msg[1] = scr_gettext("obj_readable_room5_253");
    }
    if (dognumber == 10)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_257");
        global.msg[1] = scr_gettext("obj_readable_room5_258");
        global.msg[2] = scr_gettext("obj_readable_room5_259");
        global.msg[3] = scr_gettext("obj_readable_room5_260");
    }
    if (dognumber == 11)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_264");
        global.msg[1] = scr_gettext("obj_readable_room5_265");
    }
    if (dognumber == 12)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_269");
        global.msg[1] = scr_gettext("obj_readable_room5_270");
        global.msg[2] = scr_gettext("obj_readable_room5_271");
        global.msg[3] = scr_gettext("obj_readable_room5_272");
    }
}
if (room == room_dogshrine_ruined)
{
    if (locked == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room5_ds2_0");
        global.msg[1] = scr_gettext("obj_readable_room5_ds2_1");
        global.msg[2] = scr_gettext("obj_readable_room5_ds2_2");
        snd_stop(mus_sfx_dogseal);
        snd_play(mus_sfx_dogseal);
    }
    else
    {
        global.msg[0] = scr_gettext("obj_readable_room5_ds2_3");
        global.msg[1] = scr_gettext("obj_readable_room5_ds2_4");
        if (read >= 1)
        {
            global.msg[0] = scr_gettext("obj_readable_room5_ds2_5");
            global.msg[1] = scr_gettext("obj_readable_room5_ds2_6");
            global.msg[2] = scr_gettext("obj_readable_room5_ds2_7");
        }
    }
    read += 1;
}
if (room == room_steamworks_36)
{
    global.msg[0] = "* (这 是 个 投 递 槽 。 )/";
    global.msg[1] = "* (它 似 乎 被 堵 住 了 。 )/%%";
}
if (room == room_steamworks_34)
{
    global.msg[0] = "* (一 个 自 动 售 货 机 。 ^1)&* (它 完 全 坏 掉 了 。 )/";
    global.msg[1] = "* (你 感 觉 它 曾 经 卖 过 &  很 美 味 的 食 品 。 )/%%";
    if (read > 0)
    {
        global.msg[0] = "* (尽 管 历 经 险 阻 ^1，&  你 的 头 脑 仍 然 清 晰 如 初 。 )/%%";
        if (global.ghost == 0 && scr_murderlv() < 8)
        {
            global.msg[0] = "* (尽 管 历 经 险 阻 ^1，&  你 的 头 脑 仍 然 清 晰 如 初 。 )/%%";
            scr_cloface(1, 6);
            global.msg[2] = "* 嗯 ^2？ 什 么 叫 “ 历 经 险 阻 ” ？ /%%";
        }
    }
    if (scr_murderlv() > 12)
    {
        global.msg[0] = "* 毫 无 价 值 的 废 品 。 /%%";
    }
    read += 1;
}
if (room == room_steamworks_33)
{
    global.msg[0] = "* (一 个 巨 大 的 电 脑 。 )/";
    global.msg[1] = "* (你 很 想 把 所 有 的 按 钮 都 按 一 遍 ...)/%%";
    if (read > 0 && scr_murderlv() < 12 && global.flag[7] == 0)
    {
        scr_cloface(0, "D");
        global.msg[1] = "* ( 别 。 )/%%";
    }
    if (read > 0 && global.ghost == 1)
    {
        global.msg[0] = "* (你 不 知 怎 地 抑 制 住 了 陷 入&  混 沌 的 冲 动 。)/%%";
    }
    if (global.flag[7] == 1)
    {
        global.msg[0] = "* (你 的 旅 程 将 要 结 束 ^1， 你 当 然 要 &  看 看 这 到 底 是 干 什 么 用 的 ^1，&  对 吧 ？)/";
        global.msg[1] = "* (^1.^1.^1.)/";
        global.msg[2] = "* (什 么 都 没 发 生 。 )/%%";
    }
    if (scr_murderlv() > 12)
    {
        global.msg[0] = "* 一 台 电 子 设 备 。/%%";
    }
    read += 1;
}
if (room == room_steamworks_32)
{
    global.msg[0] = "* (一 个 老 旧 的 屏 幕 。 )/";
    global.msg[1] = "* (无 法 使 用 。 )/";
    scr_charface(2, 7);
    global.msg[3] = "* (这 里 的 一 切 都 坏 了 。)/%%";
    if (read > 0 || global.ghost == 1)
    {
        global.msg[0] = "* (一 个 无 法 使 用 的 显 示 器 。 )/%%";
    }
    if (scr_murderlv() > 12)
    {
        global.msg[0] = "* 垃 圾 。 /%%";
    }
    read += 1;
}
if (room == room_steamworks_factory_elevator)
{
    global.msg[0] = "* (似 乎 没 在 运 作 。 )/%%";
    if (read > 0)
    {
        global.msg[0] = "* (看 来 这 就 是 目 前 你 能 够 &  到 达 的 最 远 的 地 方 了 。 )/%%";
    }
    if (global.ghost == 0 && global.flag[7] == 0 && global.lv < 8)
    {
        if (global.flag[215] == 0)
        {
            global.msg[0] = "* (你 尝 试 打 开 屏 幕 。 )/";
            global.msg[1] = "* ( 似 乎 没 有 生 效 。 )/";
            scr_cloface(2, "J");
            global.msg[3] = "* 什 么 ？ ^1！&* 不 ^1！&* 再 试 一 次 ！/%%";
            global.flag[215] = 1;
        }
        else if (global.flag[215] == 1)
        {
            global.msg[0] = "\\TS \\F0 \\E0 \\T0%";
            global.msg[1] = "* (你 尝 试 摆 弄 那 个 设 备 。 )&* (又 一 次 。 )/";
            global.msg[2] = "* ( ..^1. 没 有 反 应 。 )/";
            scr_cloface(3, 9);
            global.msg[4] = "* 第 三 次 准 有 好 运 气 ，&  没 错 吧 ？？/";
            scr_charface(5, "C");
            global.msg[6] = "* .../%%";
            global.flag[215] = 2;
        }
        else if (global.flag[215] == 2)
        {
            audio_sound_gain(global.currentsong, 0, 3000);
            global.msg[0] = "\\TS \\F0 \\E0 \\T0%";
            global.msg[1] = "* (你 按 下 了 启 动 键 。^1 ）&* (..^1.什 么 也 没 有 发 生 。 )/";
            global.msg[2] = "* (你 敲 了 敲 它 。)/";
            global.msg[3] = "* (你 踢 了 踢 它 。)/";
            global.msg[4] = "*  (...) /";
            global.msg[5] = "* (..^1.没 有 反 应 。 )/";
            scr_charface(6, 1);
            global.msg[7] = "* 这 ^1.^1.真 的 对 你 如 此&  重 要 吗 ^1， Clover ？/";
            scr_cloface(8, 9);
            global.msg[9] = "* 呃 .^1.^1. 我 只 是 &  想 去 见 一 些 熟 人 。/";
            global.msg[10] = "\\EH* 我 很 想 念 他 们 ^1。&* 但 现 在 我 再 也 无 法 &  与 他 们 相 见 了 。/";
            scr_charface(11, "L");
            global.msg[12] = "* .../";
            global.msg[13] = "\\E8* 醒 醒 吧 ^1， 白 痴 。/";
            scr_cloface(14, "B");
            global.msg[15] = "* 什 ^1-%";
            global.msg[16] = "\\E2* 哦 哦 哦 哦 ^1，&  我 都 没 想 到 那 个 ！/";
            scr_charface(17, "A");
            global.msg[18] = "* 不 客 气 ！&  我 真 高 兴 能 点 醒 你 。/";
            global.msg[19] = "\\E1* .../";
            global.msg[20] = "\\TS \\F0 \\E0 \\T0%";
            global.msg[21] = "* .../%%";
            global.flag[215] = 3;
        }
    }
    if (scr_murderlv() > 12)
    {
        global.msg[0] = "* 没 有 反 应 。 /%%";
    }
    read += 1;
}
if (room == room_newhome_01)
{
    global.msg[0] = "* (你 当 前 位 置 的 一 张 地 图 。 )/";
    global.msg[1] = "* (你 从 未 想 象 到 过 你 的 冒 险 途 中 &  会 经 历 多 少 事 情 。 )/";
    scr_cloface(2, "B");
    global.msg[3] = "* 我 知 道 ， 难 道 不 是 吗 ？！/%%";
    if (global.ghost == 1)
    {
        global.msg[1] = "* ( 你 从 未 想 象 过 你 会 在&  冒 险 中 遇 到 如 此 多 的 事 。 )/%%";
    }
    if (scr_murderlv() > 12 || global.kills > 60 || global.flag[7] == 1)
    {
        global.msg[0] = "* (你 当 前 位 置 的 一 张 地 图 。 )/%%";
    }
}
if (room == room_newhome_02)
{
    scr_cloface(0, "B");
    global.msg[1] = "* 为 什 么 这 里 &  有 这 么 多 路 障 ？？/";
    global.msg[2] = "\\TS \\F0 \\E0 \\T0%";
    global.msg[3] = "* (在 你 的 前 方 ^1， 你 看 到 &  有 一 只 狗 正 在 用 叉 车 &  制 造 混 乱 。)/";
    scr_cloface(4, "G");
    global.msg[5] = "* 那 没 事 了 。&  放 这 么 多 路 障 还 是 &  很 合 理 的 。/";
    scr_charface(6, "C");
    global.msg[7] = "* 我 真 为 那 些 稍 后 要 去 &  清 理 残 局 的 人 &  感 到 很 难 过 。/%%";
    if (global.ghost == 1)
    {
        global.msg[0] = "* (这 条 路 被 合 理 数 量 的 &  路 障 堵 住 了 。)/";
        global.msg[1] = "* (在 你 的 前 方 ^1， 你 看 到 &  有 一 只 狗 正 在 用 叉 车 &  制 造 混 乱 。)/";
        global.msg[2] = "* (...也 许 用 这 么 多 路 障 &  也 不 算 多 。)/%%";
    }
    if (read > 0)
    {
        global.msg[0] = "* (这 条 路 被 合 理 数 量 的 &  路 障 堵 住 了 。)/%%";
    }
    if (scr_murderlv() > 7)
    {
        global.msg[0] = "* (这 边 没 什 么 有 用 的 东 西 。 )/%%";
    }
    if (global.flag[7] == 1)
    {
        global.msg[0] = "* (那 只 狗 已 经 不 再 &  制 造 破 坏 了 。 )/";
        global.msg[1] = "* (然 而 ^1， 他 已 经 造 成 的 破 坏 ...)/";
        global.msg[2] = "* (...真 庆 幸 结 界 &  已 经 被 摧 毁 了 。 )/%%";
    }
    read += 1;
}
if (room == room_fire_alley)
{
    global.msg[0] = "* 嘿 ^1， 额 ^1， 别 碰 商 品 ！ ！ /%%";
    if (scr_murderlv() >= 12)
    {
        global.msg[0] = "* (只 有 垃 圾 。 )/%%";
    }
}
mydialoguer = instance_create(0, 0, obj_dialoguer);
