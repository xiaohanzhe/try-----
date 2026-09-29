myinteract = 3;
global.msc = 0;
global.typer = 5;
global.facechoice = 0;
global.faceemotion = 0;
scr_cloface(0, 0);
switch (room)
{
    case room_area1:
        global.msg[1] = "* 希 望 那 次 跌 倒 不 是&  太 严 重 。/%%";
        break;
    case room_fire_multitile:
        global.msg[1] = "* 享 受 生 活 真 是 美 好 。/";
        scr_charface(2, "E");
        global.msg[3] = "* 但 你 已 经 死 了 。/";
        scr_cloface(4, 6);
        global.msg[5] = "* .../";
        global.msg[6] = "\\E2* 死 了 也 可 以 过 得 很 好 。/%%";
        if (talkedto == 1)
        {
            global.msg[1] = "* 想 要 一 起 吗 ^1，&  " + scr_gettext("obj_chara_5") + "?/";
            scr_charface(2, 0);
            global.msg[3] = "* 不 。/";
            scr_cloface(4, 1);
            global.msg[5] = "* 你 确 定 ？/";
            scr_charface(6, "D");
            global.msg[7] = "* 是 的 。/%%";
        }
        if (talkedto == 2)
        {
            global.msg[1] = "* 你 真 的 确 定 ？/";
            scr_charface(2, 0);
            global.msg[3] = "* 我 真 的 确 定 。/";
            scr_cloface(4, "I");
            global.msg[5] = "* 你 超 级 深 -%";
            scr_charface(6, "H");
            global.msg[7] = "* 我 超 级 深 刻 究 极 终 极&  无 敌 额 外 炽 热 确 定 。/";
            scr_cloface(8, 2);
            global.msg[9] = "* 啥 ？ ？/%%";
        }
        if (talkedto == 3)
        {
            global.msg[1] = "* 好 吧 ^1， 好 吧 。/";
            scr_charface(2, 0);
            global.msg[3] = "* .../";
            scr_cloface(4, 7);
            global.msg[5] = "* .../";
            scr_charface(6, 3);
            global.msg[7] = "* .../";
            scr_cloface(8, "I");
            global.msg[9] = "* .../";
            scr_charface(10, "G");
            global.msg[11] = "* .../";
            scr_cloface(12, 2);
            global.msg[13] = "* 你 终 极 无 敌 逆 天&  超 级 深 刻 -%";
            scr_charface(14, "E");
            global.msg[15] = "* 够 了 。/%%";
        }
        if (talkedto > 3)
        {
            global.msg[1] = "* 我 想 够 了 吧 。/%%";
        }
        break;
    case room_fire_restaurant:
        global.msg[1] = "* 哈 喽 。/";
        global.msg[2] = "\\E6* 你 和 Sans的 对 话&  看 起 来 很 有 趣 。 /";
        global.msg[3] = "\\E7* 嗯 ^1？ 我 们 刚 刚 在 说 什 么 ？ /";
        global.msg[4] = "\\EK* 秘 密 。 /%%";
        break;
    case room_fire_finalelevator:
        if (global.flag[432] == 0)
        {
            global.msg[1] = "\\E9* ... /%%";
        }
        else
        {
            global.msg[1] = "* 不 用 管 我 。/%%";
        }
        break;
}
mydialoguer = instance_create(0, 0, obj_dialoguer);
talkedto++;
