myinteract = 3;
if (global.plot < 5)
{
    if (instance_exists(obj_torinteractable2))
    {
        obj_torinteractable2.lsprite = spr_toriel_lt;
        global.msc = 0;
        global.typer = 4;
        global.facechoice = 1;
        global.faceemotion = 1;
        global.msg[0] = scr_gettext("obj_readable_switch1_65");
        global.msg[1] = scr_gettext("obj_readable_switch1_66");
        global.msg[2] = scr_gettext("obj_readable_switch1_67");
        if (global.flag[6] == 1)
        {
            global.msg[0] = scr_gettext("obj_readable_switch1_71");
        }
    }
    else
    {
        global.msc = 0;
        global.typer = 5;
        global.facechoice = 0;
        global.faceemotion = 0;
        snd_play(snd_wrongvictory);
        global.msg[0] = scr_gettext("obj_readable_switch1_81");
    }
}
if (global.plot >= 5)
{
    global.msc = 0;
    global.typer = 5;
    global.facechoice = 0;
    global.faceemotion = 0;
    if (global.flag[7] == 1 || scr_murderlv() >= 1 || global.flag[19] > 665 || global.ghost == 1)
    {
        global.msg[0] = "* 这 个 开 关 甚 至 不 能 运 作 .../%%";
    }
    else
    {
        scr_cloface(0, 5);
        global.msg[1] = "* 别 ..^1. 按 那 个 ^2。&\\E8* 只 是 以 防 万 一 。/%%";
        if (ossafe_file_exists("file6"))
        {
            scr_cloface(0, 1);
            global.msg[1] = "* 不 。/";
            global.msg[2] = "\\EQ* 当 然 不 了 。/%%";
        }
    }
}
mydialoguer = instance_create(0, 0, obj_dialoguer);
