myinteract = 3;
global.msc = 0;
global.typer = 5;
global.facechoice = 0;
global.faceemotion = 0;
global.msg[0] = scr_gettext("obj_readable_room4_60");
if (room == room_torhouse3)
{
    global.msg[0] = scr_gettext("obj_readable_room4_63");
    if (global.ghost == 0)
    {
        scr_cloface(0, 1);
        global.msg[1] = "* 这 是 你 ！/";
        scr_charface(2, 0);
        global.msg[3] = "* 还 有 你 不 情 愿 的 同 伴 们 。/";
        scr_cloface(4, 8);
        global.msg[5] = "* 我 是 很 情 愿 的 ！/%%";
        if (scr_murderlv() > 0)
        {
            scr_cloface(0, "E");
            global.msg[1] = "* .../%%";
        }
        if (read > 0)
        {
            scr_cloface(0, 6);
            global.msg[1] = "* 我 看 不 见 自 己 的 镜 像 ，&  真 奇 怪 .../%%";
            if (scr_murderlv() > 0)
            {
                scr_charface(0, 3);
                global.msg[1] = "* 这 就 是 他 们 所 说 的 “ 你 ” 。/%%";
            }
        }
        read++;
    }
    if (global.flag[7] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_64");
    }
}
if (room == room_torhouse3 && murdererlv1() == 1)
{
    global.msg[0] = scr_gettext("obj_readable_room4_66");
}
if (room == room_asghouse2)
{
    global.msg[0] = scr_gettext("obj_readable_room4_67");
}
if (room == room_asghouse3)
{
    global.msg[0] = scr_gettext("obj_readable_room4_70");
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_73");
    }
}
if (room == room_kitchen && x < 130)
{
    global.msg[0] = scr_gettext("obj_readable_room4_76");
}
if (room == room_kitchen && murdererlv1() == 1 && x < 130)
{
    global.msg[0] = scr_gettext("obj_readable_room4_77");
}
if (room == room_kitchen && x > 130)
{
    global.msg[0] = scr_gettext("obj_readable_room4_78");
}
if (room == room_kitchen && x > 130 && global.flag[45] == 4)
{
    global.msg[0] = scr_gettext("obj_readable_room4_79");
}
if (room == room_kitchen_final && x < 130)
{
    global.msg[0] = scr_gettext("obj_readable_room4_83");
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_84");
    }
}
if (room == room_kitchen_final && x > 130)
{
    global.msg[0] = scr_gettext("obj_readable_room4_90");
    if (scr_murderlv() >= 16)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_91");
    }
}
if (room == room_asrielroom_final)
{
    if (x < 160)
    {
        global.msg[0] = "* (好 一 张 舒 服 的 床 。 ) ^1 &* (要 是 你 在 这 里 躺 下 来 ^1， & 你 可 能 就 再 也 不 想 起 来 了 。 ) /";
        scr_charface(1, "B");
        global.msg[2] = "* 想 都 别 想 ^2。 那 是 我 的 床 。 /%%";
        if (global.flag[7] == 1)
        {
            scr_charface(0, "H");
            global.msg[1] = "* 还 是 我 的 床 ^1， Frisk ^2。&\\EE* 别 。 /%%";
        }
        if (ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
        {
            global.msg[0] = "*  (好 一 张 舒 服 的 床 。 ) ^1 &*  (要 是 你 在 这 里 躺 下 来 ^1， &  你 可 能 就 再 也 不 想 起 来 了 。 ) /%%";
        }
        if (scr_murderlv() >= 16)
        {
            global.msg[0] = scr_gettext("obj_readable_room4_99");
        }
    }
    if (x > 160)
    {
        global.msg[0] = "* (这 是 一 张 单 人 床 。 ) /";
        scr_charface(1, 1);
        global.msg[2] = "* (...)/%%";
        if (read > 0)
        {
            scr_charface(0, "L");
            global.msg[1] = "* Asriel 的 床 。/";
            if (global.flag[7] == 1)
            {
                global.msg[2] = "%%";
            }
            else
            {
                scr_cloface(2, 9);
                global.msg[3] = "* .../%%";
            }
        }
        if (global.flag[7] == 1 || ossafe_file_exists("file6") || global.flag[19] > 665 || global.ghost == 1)
        {
            global.msg[0] = "*  (这 是 一 张 单 人 床 。 ) /%%";
        }
        if (scr_murderlv() >= 16)
        {
            global.msg[0] = scr_gettext("obj_readable_room4_105");
        }
    }
}
if (room == room_asgoreroom)
{
    global.msg[0] = scr_gettext("obj_readable_room4_110");
}
if (room == room_tundra_library)
{
    global.msg[0] = scr_gettext("obj_readable_room4_114");
    global.msg[1] = scr_gettext("obj_readable_room4_116");
    global.msg[2] = scr_gettext("obj_readable_room4_117");
    global.msg[3] = scr_gettext("obj_readable_room4_118");
    global.msg[4] = scr_gettext("obj_readable_room4_119");
    global.msg[5] = scr_gettext("obj_readable_room4_120");
}
if (room == room_water_prebird)
{
    global.msg[0] = scr_gettext("obj_readable_room4_126");
    global.msg[1] = scr_gettext("obj_readable_room4_127");
    global.msg[2] = scr_gettext("obj_readable_room4_128");
    if (global.flag[97] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_131");
    }
    global.flag[97] = 1;
}
if (room == room_water7)
{
    global.msg[0] = scr_gettext("obj_readable_room4_139");
    global.msg[1] = scr_gettext("obj_readable_room4_140");
}
if (room == room_fire_lab1)
{
    global.msg[0] = scr_gettext("obj_readable_room4_145");
    if (global.plot < 126)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_146");
    }
    if (scr_murderlv() >= 12)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_147");
    }
}
read += 1;
if (room == room_fire_lab2)
{
    global.msc = 645;
}
if (room == room_fire_cookingshow)
{
    global.msg[0] = scr_gettext("obj_readable_room4_159");
    if (global.plot < 134 && scr_murderlv() < 12)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_161");
    }
    if (instance_exists(obj_mettaton_npc))
    {
        global.typer = 27;
        global.msg[0] = scr_gettext("obj_readable_room4_168");
        global.msg[1] = scr_gettext("obj_readable_room4_169");
        global.msg[2] = scr_gettext("obj_readable_room4_170");
        if (global.plot == 134)
        {
            global.msg[0] = scr_gettext("obj_readable_room4_174");
            global.msg[1] = scr_gettext("obj_readable_room4_175");
        }
    }
}
if (room == room_water_undynehouse)
{
    global.msg[0] = scr_gettext("obj_readable_room4_182");
    if (x > 200)
    {
        global.facechoice = 5;
        global.typer = 37;
        global.msc = 714;
    }
}
if (room == room_truelab_hall1)
{
    global.msg[0] = scr_gettext("obj_readable_room4_193");
    global.msg[1] = scr_gettext("obj_readable_room4_194");
    global.msg[2] = scr_gettext("obj_readable_room4_195");
    global.msg[3] = scr_gettext("obj_readable_room4_196");
    global.msg[4] = scr_gettext("obj_readable_room4_197");
    global.msg[5] = scr_gettext("obj_readable_room4_198");
    global.msg[6] = scr_gettext("obj_readable_room4_199");
    if (global.flag[485] == 1)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_201");
    }
}
if (room == room_truelab_mirror)
{
    global.msg[0] = scr_gettext("obj_readable_room4_206");
}
if (room == room_tundra_sansroom)
{
    if (y < 128)
    {
        global.msc = 845;
    }
    global.msg[0] = scr_gettext("obj_readable_room4_212");
}
if (room == room_tundra_sansbasement)
{
    global.msg[0] = scr_gettext("obj_readable_room4_217");
}
if (room == room_tundra_town)
{
    if (global.flag[497] < 3)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_222");
    }
    if (global.flag[497] >= 3)
    {
        global.msg[0] = scr_gettext("obj_readable_room4_226");
        instance_create(0, 0, obj_sansbasemententer);
        snd_play(snd_item);
    }
}
if (room == room_ice_dog)
{
    global.msg[0] = scr_gettext("obj_readable_room4_234");
}
if (room == room_water3)
{
    global.msg[0] = scr_gettext("obj_readable_room4_237");
}
mydialoguer = instance_create(0, 0, obj_dialoguer);
