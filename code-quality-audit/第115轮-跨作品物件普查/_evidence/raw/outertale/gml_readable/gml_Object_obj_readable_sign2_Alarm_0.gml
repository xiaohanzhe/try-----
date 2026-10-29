myinteract = 3;
global.msc = 0;
global.msg[0] = scr_gettext("obj_readable_sign2_55");
global.msg[1] = scr_gettext("obj_readable_sign2_56");
if (scr_murderlv() == 0 && global.flag[7] == 0 && global.flag[19] < 665 && global.flag[210] < 1.5)
{
    global.msg[0] = scr_gettext("obj_readable_sign2_55");
    global.msg[1] = "* 来 吃 些 蛛 有 ^1， 蛛 制 ^1， &  蜘 享 的 点 心 吧 ！ /";
    scr_cloface(2, 1);
    global.msg[3] = "* 哦 ^1！ 我 现 在 想 起 来 了 ！/";
    global.msg[4] = "* 我 在 沙 丘 也 遇 到 过 &  这 些 家 伙 们 ！/";
    scr_charface(5, "C");
    global.msg[6] = "* .^1.^1.沙 丘 ？/%%";
    if (global.flag[210] < 1.5)
    {
        global.flag[210] = 1.5;
    }
}
global.typer = 5;
global.facechoice = 0;
global.faceemotion = 0;
mydialoguer = instance_create(0, 0, obj_dialoguer);
