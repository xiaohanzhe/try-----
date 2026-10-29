myinteract = 3;
global.msc = 0;
global.typer = 5;
global.facechoice = 0;
global.faceemotion = 0;
global.msg[0] = scr_gettext("obj_readable_room1_64");
if (room == room_ruins2)
{
    global.msg[0] = scr_gettext("obj_readable_room1_65");
}
if (room == room_ruins3)
{
    global.msg[0] = scr_gettext("obj_readable_room1_66");
}
if (room == room_ruins5)
{
    global.msg[0] = scr_gettext("obj_readable_room1_67");
}
if (room == room_ruins9)
{
    global.msg[0] = scr_gettext("obj_readable_room1_68");
}
if (room == room_ruins13)
{
    if (global.osflavor >= 3 || ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_69_console_1");
        global.msg[1] = scr_gettext("obj_readable_room1_69_console_2");
        global.msg[2] = scr_gettext("obj_readable_room1_69_console_3");
        global.msg[3] = scr_gettext("obj_readable_room1_69_console_4");
    }
    else if (scr_murderlv() == 0)
    {
        global.msg[0] = "*  (在 墙 缝 里 有 一 只 &  蚂 蚁 大 小 的 青 蛙 ...) ^1 &*  (它 在 向 你 招 手 。 ) /";
        scr_cloface(1, 1);
        global.msg[2] = "* 哦 ^1！ 这 里 有 一 只 &  迷 你 Froggit！/%%";
        if (read > 0)
        {
            global.msg[0] = "* (墙 缝 里 有 一 只&  迷 你 Froggit...^1)&* (它 在 对 你 挥 手 。)/%%";
        }
    }
    if (scr_murderlv() >= 1)
    {
        global.msg[0] = "* (这 里 的 墙 上 &  有 一 条 小 裂 缝 。)/%%";
    }
    if (global.flag[7] == 1)
    {
        global.msg[0] = "* (哦 ^1！ 迷 你 Froggit举 了&  一 个 写 了 “ 谢 谢 你 ” 的&  迷 你 牌 子 。)/%%";
    }
}
if (room == room_ruins14)
{
    global.msg[0] = scr_gettext("obj_readable_room1_70");
}
if (room == room_ruins15A)
{
    global.msg[0] = scr_gettext("obj_readable_room1_71");
}
if (room == room_ruins15B)
{
    global.msg[0] = scr_gettext("obj_readable_room1_72");
}
if (room == room_ruins15C)
{
    global.msg[0] = scr_gettext("obj_readable_room1_73");
}
if (room == room_ruins15D)
{
    global.msg[0] = scr_gettext("obj_readable_room1_74");
}
if (room == room_torhouse1)
{
    global.msg[0] = scr_gettext("obj_readable_room1_75");
}
if (room == room_asghouse1)
{
    global.msg[0] = "*  (这 是 一 部 从 201X年 末 开 始 的 &  旧 日 历 。 ) ^1 &*  (一 个 日 期 被 圈 了 起 来 。 ) /";
    scr_charface(1, 1);
    global.msg[2] = "* 我 来 到 这 里 的 日 期 。/";
    scr_cloface(3, 5);
    global.msg[4] = "* 你 .^1.^1./%%";
    if (scr_murderlv() >= 8 || global.kills > 40)
    {
        scr_charface(0, 3);
        global.msg[1] = "* 我 来 到 这 里 的 日 期 。/%%";
    }
    if (global.flag[7] == 1 || ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
    {
        global.msg[0] = "*  (这 是 一 部 从 201X年 末 开 始 的 &  旧 日 历 。 ) ^1 &*  (一 个 日 期 被 圈 了 起 来 。 ) /%%";
    }
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = "* (我 来 这 里 的 日 期 。)/%%";
    }
}
if (room == room_torhouse2)
{
    global.msg[0] = scr_gettext("obj_readable_room1_81");
}
if (room == room_asghouse2)
{
    global.msg[0] = scr_gettext("obj_readable_room1_82");
}
if (room == room_asrielroom)
{
    global.msg[0] = scr_gettext("obj_readable_room1_83");
}
if (room == room_asrielroom_final)
{
    global.msg[0] = scr_gettext("obj_readable_room1_84");
}
if (room == room_castle_finalshoehorn)
{
    global.msg[0] = scr_gettext("obj_readable_room1_86");
}
if (room == room_castle_coffins2)
{
    global.msg[0] = scr_gettext("obj_readable_room1_90");
    global.msg[1] = scr_gettext("obj_readable_room1_91");
    global.msg[2] = "* (是 空 的 。 ) /";
    if (ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
    {
        global.msg[2] = "*  (是 空 的 。 ) /%%";
    }
    scr_charface(3, 1);
    global.msg[4] = "* ...我 们 离 开 这 里 吧 。/";
    scr_cloface(5, 3);
    global.msg[6] = "* .../%%";
    if (global.flag[7] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_96");
        global.msg[1] = scr_gettext("obj_readable_room1_97");
        global.msg[2] = scr_gettext("obj_readable_room1_98");
    }
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = "* (它 就 像 它 看 起 来 那 样 舒 适 。 )/%%";
    }
}
if (room == room_torielroom)
{
    global.msc = 524;
    if (x > 192)
    {
        global.msc = 0;
        global.msg[0] = scr_gettext("obj_readable_room1_112");
        global.msg[1] = scr_gettext("obj_readable_room1_113");
        if (read > 0)
        {
            global.msg[0] = scr_gettext("obj_readable_room1_114");
        }
        if (global.flag[7] == 1)
        {
            global.msg[0] = scr_gettext("obj_readable_room1_118");
            global.msg[1] = scr_gettext("obj_readable_room1_119");
        }
    }
}
if (room == room_asgoreroom)
{
    global.msg[0] = scr_gettext("obj_readable_room1_125");
    global.msg[1] = scr_gettext("obj_readable_room1_126");
    scr_charface(2, "C");
    global.msg[3] = "* 他 竟 然 还 留 着 那 个 ？/%%";
    if (global.ghost == 1)
    {
        global.msg[2] = "%%";
    }
    if (global.flag[7] == 1 && global.ghost == 0)
    {
        scr_charface(0, "E");
        global.msg[1] = "* 噗 ^1， 那 件 毛 衣 。/%%";
    }
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_130");
    }
    if (y > 120)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_134");
    }
}
if (room == room_castle_throneroom)
{
    global.msg[0] = scr_gettext("obj_readable_room1_139");
    if (global.ghost == 0 && scr_murderlv() < 8 && global.flag[7] == 0)
    {
        global.msg[0] = "* (这 是 一 个 王 座 。 ) /%%";
        scr_cloface(1, 7);
        global.msg[2] = "* 你 应 该 坐 上 去 。/";
        scr_charface(3, "D");
        global.msg[4] = "* 啥 ^2？&* 你 不 该 那 样 。/%%";
        if (read > 0)
        {
            global.msg[0] = "* (没 有 时 间 休 息 了 。)/%%";
        }
    }
}
if (room == room_torhouse3)
{
    global.msg[0] = scr_gettext("obj_readable_room1_142");
}
if (room == room_asghouse3)
{
    global.msg[0] = scr_gettext("obj_readable_room1_143");
}
if (room == room_kitchen)
{
    global.msg[0] = "* 不 知 为 何 ^1， &  冰 箱 里 有 块 名 牌 巧 克 力 。 /";
    if (ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
    {
        global.msg[0] = "* 不 知 为 何 ^1， &  冰 箱 里 有 块 名 牌 巧 克 力 。 /%%";
    }
    scr_charface(1, 4);
    global.msg[2] = "* 把 它 给 我 。/";
    scr_cloface(3, 6);
    global.msg[4] = "* 我 ^1.^1.^1.\\E8不 觉 得 他 &  能 够 把 巧 克 力 &  给 一 个 鬼 魂 。/%%";
    if (scr_murderlv() >= 1)
    {
        global.msg[0] = "* 没 什 么 有 用 的 。/%%";
    }
    if (global.flag[7] == 1)
    {
        global.msg[0] = "* 你 不 会 得 到 巧 克 力 的 。/%%";
    }
    if (read == 0)
    {
        global.flag[427] = 0;
    }
}
if (room == room_kitchen_final)
{
    global.msg[0] = "*  (冰 箱 里 放 满 了 &  未 开 封 的 蜗 牛 罐 子 。 ) /%%";
    if (ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
    {
        global.msg[0] = "*  (冰 箱 里 放 满 了 &  未 开 封 的 蜗 牛 罐 子 。 ) /%%";
    }
    scr_charface(1, 7);
    global.msg[2] = "* 没 有 巧 克 力 。/";
    scr_cloface(3, 8);
    global.msg[4] = "* 也 没 有 枪 粉 。/";
    scr_charface(5, 1);
    global.msg[6] = "* .../";
    global.msg[7] = "\\EG* 什 么 ？/%%";
    if (scr_murderlv() >= 8 || global.flag[7] == 1)
    {
        global.msg[0] = "*  (冰 箱 里 放 满 了 &  未 开 封 的 蜗 牛 罐 子 。 ) /%%";
        scr_charface(1, 7);
        global.msg[2] = "* 没 有 巧 克 力 。/%%";
    }
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_151");
    }
}
if (room == room_tundra1)
{
    global.msg[0] = scr_gettext("obj_readable_room1_154");
}
if (room == room_tundra8A)
{
    global.msg[0] = scr_gettext("obj_readable_room1_155");
}
if (room == room_tundra_snowpuzz)
{
    if (global.plot <= 48)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_158");
    }
    if (global.plot > 48)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_159");
    }
    if (global.flag[64] == 0)
    {
        global.flag[64] = 1;
    }
    if (global.plot <= 48)
    {
        global.plot = 49;
    }
    if (scr_murderlv() >= 3)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_162");
    }
}
if (room == room_tundra_lesserdog)
{
    global.msg[0] = scr_gettext("obj_readable_room1_164");
}
if (room == room_tundra_library)
{
    global.msg[0] = scr_gettext("obj_readable_room1_198");
    global.msg[1] = scr_gettext("obj_readable_room1_199");
    global.msg[2] = scr_gettext("obj_readable_room1_200");
    global.msg[3] = scr_gettext("obj_readable_room1_201");
    global.msg[4] = scr_gettext("obj_readable_room1_202");
    global.msg[5] = scr_gettext("obj_readable_room1_203");
}
if (room == room_tundra_inn)
{
    global.msg[0] = scr_gettext("obj_readable_room1_208");
    global.msg[1] = scr_gettext("obj_readable_room1_209");
    if (global.flag[7] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_213");
        global.msg[1] = scr_gettext("obj_readable_room1_214");
    }
    if (scr_murderlv() >= 7)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_219");
    }
}
if (room == room_water12)
{
    global.msg[0] = scr_gettext("obj_readable_room1_228");
    global.msg[1] = scr_gettext("obj_readable_room1_229");
}
if (room == room_water7)
{
    global.msg[0] = scr_gettext("obj_readable_room1_235");
    global.msg[1] = scr_gettext("obj_readable_room1_236");
}
if (room == room_water14)
{
    global.msg[0] = scr_gettext("obj_readable_room1_241");
}
if (room == room_water15)
{
    global.msg[0] = scr_gettext("obj_readable_room1_247");
    global.msg[1] = scr_gettext("obj_readable_room1_248");
    global.msg[2] = scr_gettext("obj_readable_room1_249");
}
if (room == room_water19)
{
    global.msg[0] = scr_gettext("obj_readable_room1_256");
    global.msg[1] = scr_gettext("obj_readable_room1_257");
    global.msg[2] = scr_gettext("obj_readable_room1_258");
}
if (room == room_water_nicecream)
{
    global.msg[0] = scr_gettext("obj_readable_room1_263");
}
if (room == room_water_prebird)
{
    global.msg[0] = scr_gettext("obj_readable_room1_269");
}
if (room == room_water_preundyne)
{
    global.msg[0] = scr_gettext("obj_readable_room1_274");
    global.msg[1] = scr_gettext("obj_readable_room1_275");
}
if (room == room_water17)
{
    global.msg[0] = scr_gettext("obj_readable_room1_280");
}
if (room == room_water20)
{
    if (instance_exists(obj_monsterkidtrigger7))
    {
        obj_monsterkidtrigger7.con = 80;
    }
    cantalk = 0;
}
if (room == room_fire_lab1)
{
    global.msg[0] = scr_gettext("obj_readable_room1_292");
    if (global.plot < 126 && scr_murderlv() < 12)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_293");
    }
}
if (room == room_fire_lab2)
{
    global.msg[0] = scr_gettext("obj_readable_room1_299");
}
if (room == room_fire_cookingshow)
{
    global.msg[0] = scr_gettext("obj_readable_room1_304");
    if (global.plot < 134)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_306");
    }
    if (instance_exists(obj_mettaton_npc))
    {
        global.typer = 27;
        global.msg[0] = scr_gettext("obj_readable_room1_312");
        global.msg[1] = scr_gettext("obj_readable_room1_313");
    }
    if (global.plot == 134)
    {
        snd_play(snd_phone);
        global.typer = 5;
        global.msg[0] = scr_gettext("obj_readable_room1_320");
        global.msg[1] = scr_gettext("obj_readable_room1_321");
        global.msg[2] = scr_gettext("obj_readable_room1_322");
        global.msg[3] = scr_gettext("obj_readable_room1_323");
        global.msg[4] = scr_gettext("obj_readable_room1_324");
        global.msg[5] = scr_gettext("obj_readable_room1_325");
        if (specialread > 0)
        {
            global.msg[0] = scr_gettext("obj_readable_room1_328");
            global.msg[1] = scr_gettext("obj_readable_room1_329");
            global.msg[2] = scr_gettext("obj_readable_room1_330");
        }
        specialread += 1;
    }
}
if (room == room_water_undynehouse)
{
    global.typer = 37;
    global.facechoice = 5;
    global.faceemotion = 4;
    global.msc = 0;
    if (x > 180)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_347");
        global.msg[1] = scr_gettext("obj_readable_room1_349");
        global.msg[2] = scr_gettext("obj_readable_room1_350");
        if (read > 0)
        {
            global.msg[0] = scr_gettext("obj_readable_room1_354");
        }
    }
    else
    {
        global.faceemotion = 0;
        global.msg[0] = scr_gettext("obj_readable_room1_360");
        global.msg[1] = scr_gettext("obj_readable_room1_361");
        global.msg[2] = scr_gettext("obj_readable_room1_362");
    }
}
if (room == room_fire_spidershop)
{
    global.msg[0] = scr_gettext("obj_readable_room1_369");
    global.msg[1] = scr_gettext("obj_readable_room1_370");
}
if (room == room_fire_hotelfront_2)
{
    if (global.flag[7] == 1 || scr_murderlv() >= 12)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_375");
    }
    else
    {
        global.msg[0] = scr_gettext("obj_readable_room1_375");
    }
}
if (room == room_fire_core_branch)
{
    global.msg[0] = scr_gettext("obj_readable_room1_380");
}
if (room == room_fire_core_left)
{
    global.msg[0] = scr_gettext("obj_readable_room1_385");
}
if (room == room_fire_core_top)
{
    global.msg[0] = scr_gettext("obj_readable_room1_390");
}
if (room == room_fire_core_right)
{
    global.msg[0] = scr_gettext("obj_readable_room1_395");
    global.msg[1] = scr_gettext("obj_readable_room1_396");
}
if (room == room_fire_core_center)
{
    global.msg[0] = scr_gettext("obj_readable_room1_401");
}
if (room == room_fire_core_treasureleft)
{
    global.msg[0] = scr_gettext("obj_readable_room1_406");
}
if (room == room_fire_core_metttest)
{
    global.msg[0] = scr_gettext("obj_readable_room1_416");
    if (global.flag[425] == 0)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_419");
    }
}
if (room == room_truelab_hall1)
{
    global.msg[0] = scr_gettext("obj_readable_room1_425");
    global.msg[1] = scr_gettext("obj_readable_room1_426");
    global.msg[2] = scr_gettext("obj_readable_room1_427");
    global.msg[3] = scr_gettext("obj_readable_room1_428");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_430");
    }
}
if (room == room_truelab_hub)
{
    global.msg[0] = scr_gettext("obj_readable_room1_435");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_436");
    }
}
if (room == room_truelab_hall2)
{
    global.msg[0] = scr_gettext("obj_readable_room1_441");
    global.msg[1] = scr_gettext("obj_readable_room1_442");
    global.msg[2] = scr_gettext("obj_readable_room1_443");
    global.msg[3] = scr_gettext("obj_readable_room1_444");
    global.msg[4] = scr_gettext("obj_readable_room1_445");
    global.msg[5] = scr_gettext("obj_readable_room1_446");
    global.msg[6] = scr_gettext("obj_readable_room1_447");
    if (read < 1 && global.ghost == 0)
    {
        global.msg[6] = "* 自 由 或 许 比 我 们&  想 的 要 离 我 们 更 近 。 /";
        scr_cloface(7, 9);
        global.msg[8] = "* 哦 不 。/";
        scr_charface(9, 3);
        global.msg[10] = "* 你 认 为 实 验 出 错 了 ？ /";
        scr_cloface(11, 9);
        global.msg[12] = "* 我 ..^2.真 心 希 望 我 是 错 的 。 /%%";
        if (global.flag[481] == 3)
        {
            global.msg[6] = "* 自 由 或 许 比 我 们&  想 的 要 离 我 们 更 近 。 /";
            scr_cloface(7, 9);
            global.msg[8] = "* .../%%";
        }
    }
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_449");
    }
}
if (room == room_truelab_operatingroom)
{
    global.msg[0] = scr_gettext("obj_readable_room1_454");
    global.msg[1] = scr_gettext("obj_readable_room1_455");
    global.msg[2] = scr_gettext("obj_readable_room1_456");
    global.msg[3] = scr_gettext("obj_readable_room1_457");
    global.msg[4] = scr_gettext("obj_readable_room1_458");
    global.msg[5] = scr_gettext("obj_readable_room1_459");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_462");
    }
}
if (room == room_truelab_prebed)
{
    global.msg[0] = scr_gettext("obj_readable_room1_467");
    global.msg[1] = scr_gettext("obj_readable_room1_468");
    global.msg[2] = scr_gettext("obj_readable_room1_469");
    global.msg[3] = scr_gettext("obj_readable_room1_470");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_471");
    }
}
if (room == room_truelab_bedroom)
{
    global.msg[0] = scr_gettext("obj_readable_room1_476");
    global.msg[1] = scr_gettext("obj_readable_room1_477");
    global.msg[2] = scr_gettext("obj_readable_room1_478");
    global.msg[3] = scr_gettext("obj_readable_room1_479");
    global.msg[4] = scr_gettext("obj_readable_room1_480");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_481");
    }
}
if (room == room_truelab_mirror)
{
    global.msg[0] = scr_gettext("obj_readable_room1_486");
    global.msg[1] = scr_gettext("obj_readable_room1_487");
    global.msg[2] = scr_gettext("obj_readable_room1_488");
    global.msg[3] = scr_gettext("obj_readable_room1_489");
    global.msg[4] = scr_gettext("obj_readable_room1_490");
    global.msg[5] = scr_gettext("obj_readable_room1_491");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_492");
    }
}
if (room == room_truelab_hall3)
{
    global.msg[0] = scr_gettext("obj_readable_room1_497");
    global.msg[1] = scr_gettext("obj_readable_room1_498");
    global.msg[2] = scr_gettext("obj_readable_room1_499");
    global.msg[3] = scr_gettext("obj_readable_room1_500");
    global.msg[4] = scr_gettext("obj_readable_room1_501");
    global.msg[5] = "* 第 二 天 我 会 把 &  所 有 人 送 回 去 。 :) /";
    scr_cloface(6, 9);
    global.msg[7] = "* (...)/%%";
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_503");
    }
}
if (room == room_truelab_determination)
{
    global.msg[0] = scr_gettext("obj_readable_room1_517");
    if (global.ghost == 0)
    {
        scr_cloface(1, 9);
        global.msg[2] = "* ...看 起 来 确 实 有 点 吓 人 。/%%";
    }
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_518");
    }
}
if (room == room_truelab_tv)
{
    global.msg[0] = scr_gettext("obj_readable_room1_523");
    global.msg[1] = scr_gettext("obj_readable_room1_524");
    global.msg[2] = scr_gettext("obj_readable_room1_525");
    global.msg[3] = scr_gettext("obj_readable_room1_526");
    global.msg[4] = scr_gettext("obj_readable_room1_527");
    if (global.ghost == 0)
    {
        global.msg[4] = "* 我 不 认 为 他 应 该 这 么 做 。/";
        scr_charface(5, 1);
        global.msg[6] = "* .../%%";
    }
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_528");
    }
}
if (room == room_truelab_fan)
{
    global.msc = 780;
}
if (room == room_truelab_cooler)
{
    global.msg[0] = scr_gettext("obj_readable_room1_538");
    global.msg[1] = scr_gettext("obj_readable_room1_539");
    global.msg[2] = scr_gettext("obj_readable_room1_540");
    global.msg[3] = scr_gettext("obj_readable_room1_541");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_542");
    }
    if (global.flag[490] == 0)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_543");
    }
}
if (room == room_truelab_prepower)
{
    global.msg[0] = scr_gettext("obj_readable_room1_548");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_551");
        global.msg[1] = scr_gettext("obj_readable_room1_552");
        global.msg[2] = scr_gettext("obj_readable_room1_553");
        global.msg[3] = scr_gettext("obj_readable_room1_554");
        global.msg[4] = scr_gettext("obj_readable_room1_555");
        global.msg[5] = scr_gettext("obj_readable_room1_556");
        global.msg[6] = scr_gettext("obj_readable_room1_557");
        global.msg[7] = scr_gettext("obj_readable_room1_558");
        global.msg[8] = "* 当 没 有 灵 魂 的 东 西 &  产 生 了 意 志 会 发 生 什 么 ？/";
        scr_charface(9, "B");
        global.msg[10] = "* 我 们 已 经 知 道 结 果 如 何 了 。/";
        scr_cloface(11, "A");
        global.msg[12] = "* 我 们 怎 么 就 知 道 了 ？/";
        scr_charface(13, 3);
        global.msg[14] = "* .../";
        global.msg[15] = "\\ED* 你 在 逗 我 ？/";
        scr_cloface(16, "B");
        global.msg[17] = "* 哦^2 ！\\E6 哦^1 。&* 是 Flowey^1 。\\E8 那 没 事 了 。/";
        scr_charface(18, "C");
        global.msg[19] = "* ^1.^1.^1. \\E7有 时 你 的 智 商 &  真 令 人 堪 忧 。/%%";
        if (read > 0)
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 我 就 当 你 这 是 在&  鼓 励 我 了 ？/";
            scr_charface(2, "G");
            global.msg[3] = "* 不 ^1， 你 真 的 不 应 该 &  这 么 想 。 /%%";
        }
    }
}
if (room == room_truelab_elevatorinside)
{
    global.msg[0] = scr_gettext("obj_readable_room1_565");
}
if (room == room_castle_elevatorout)
{
    global.msg[0] = scr_gettext("obj_readable_room1_570");
}
if (room == room_truelab_castle_elevator)
{
    global.msg[0] = scr_gettext("obj_readable_room1_575");
}
if (room == room_tundra_grillby)
{
    global.msg[0] = scr_gettext("obj_readable_room1_580");
}
if (room == room_water_blookyard)
{
    global.msg[0] = scr_gettext("obj_readable_room1_585");
}
if (room == room_tundra_sansroom)
{
    global.msg[0] = scr_gettext("obj_readable_room1_590");
}
if (room == room_tundra_sansbasement)
{
    global.msg[0] = scr_gettext("obj_readable_room1_595");
    global.msg[1] = scr_gettext("obj_readable_room1_596");
    global.msg[2] = scr_gettext("obj_readable_room1_597");
    if (global.flag[7] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_602");
        global.msg[1] = scr_gettext("obj_readable_room1_603");
        global.msg[2] = scr_gettext("obj_readable_room1_604");
        global.msg[3] = scr_gettext("obj_readable_room1_605");
    }
    if (global.flag[279] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_610");
        global.msg[1] = scr_gettext("obj_readable_room1_611");
        global.msg[2] = scr_gettext("obj_readable_room1_612");
        global.msg[3] = scr_gettext("obj_readable_room1_613");
        global.msg[4] = scr_gettext("obj_readable_room1_614");
    }
}
if (room == room_fire_pacing)
{
    global.msg[0] = scr_gettext("obj_readable_room1_621");
    global.msg[1] = scr_gettext("obj_readable_room1_622");
    global.msg[2] = scr_gettext("obj_readable_room1_623");
}
if (room == room_fire_hoteldoors)
{
    global.msg[0] = scr_gettext("obj_readable_room1_628");
}
if (room == room_fire_hotellobby)
{
    global.msg[0] = scr_gettext("obj_readable_room1_633");
    global.msg[1] = "* 皇 家 纪 念 喷 泉 &* 建 成 于 201X年 &* (Mettaton 是 上 周 加 的 ) /";
    scr_cloface(2, "J");
    global.msg[3] = "* 这 家 伙 到 底 还 能 有 &  多 自 恋 ？/";
    scr_charface(4, "C");
    global.msg[5] = "* 这 是 相 当 傲 慢 的 表 现 。/%%";
    if (scr_murderlv() >= 11 || global.plot >= 198 || global.flag[7] == 1 || ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_633");
        global.msg[1] = scr_gettext("obj_readable_room1_634");
    }
}
if (room == room_fire_restaurant)
{
    global.msg[0] = scr_gettext("obj_readable_room1_639");
    global.msg[1] = scr_gettext("obj_readable_room1_640");
    global.msg[2] = "* (...这 些 都 是 Mettaton 写 的 。)/";
    scr_cloface(3, "C");
    global.msg[4] = "* 真 的 假 的 ？/%%";
    if (scr_murderlv() >= 11 || global.plot >= 198 || global.flag[7] == 1 || ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room1_639");
        global.msg[1] = scr_gettext("obj_readable_room1_640");
        global.msg[2] = scr_gettext("obj_readable_room1_641");
    }
}
if (room == room_fire_hotelbed)
{
    global.msg[0] = scr_gettext("obj_readable_room1_646");
    global.msg[1] = scr_gettext("obj_readable_room1_647");
}
if (room == room_water_temvillage)
{
    global.msg[0] = scr_gettext("obj_readable_room1_652");
}
read += 1;
if (cantalk == 1)
{
    mydialoguer = instance_create(0, 0, obj_dialoguer);
}
