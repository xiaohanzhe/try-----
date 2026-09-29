myinteract = 3;
global.msc = 0;
global.typer = 5;
global.facechoice = 0;
global.faceemotion = 0;
scr_charface(0, 0);
switch (room)
{
    case room_area1:
        global.msg[1] = "* 好 了 ^1？ 我 们 该 走 了 。/%%";
        break;
    case room_fire_restaurant:
        global.msg[1] = "* 你 好 。/";
        global.msg[2] = "\\EL* 虽 然 我 没 有 听 全&  你 们 都 说 了 些 什 么 ^.../";
        global.msg[3] = "\\E3* 但 看 起 来 你 们 的 对 话&  挺 有 趣 的 。 /";
        global.msg[4] = "\\EC* ...你 问 我 们 都 说 了 什 么 ？ /";
        global.msg[5] = "\\E7* 实 话 讲 没 什 么 重 要 的 。 /%%";
        break;
    case room_fire_finalelevator:
        if (global.flag[432] == 0)
        {
            global.msg[1] = "\\E7* ... /%%";
        }
        else if (global.flag[7] == 1)
        {
            global.msg[1] = "\\EL* .../%%";
        }
        else
        {
            global.msg[1] = "* 继 续 前 进 吧 。/%%";
        }
        break;
}
mydialoguer = instance_create(0, 0, obj_dialoguer);
