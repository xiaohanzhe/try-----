with (obj_robuild_parent)
{
    if (robot_item_is_carried == true)
    {
        exit;
    }
}
if (global.sworks_flag[6] == 0)
{
    switch (scene)
    {
        case 0:
            if (place_meeting(x, y, obj_pl))
            {
                obj_pl.direction = 180;
                scr_cutscene_start();
                cutscene_advance();
                if (global.route == 2)
                {
                    obj_ceroba_npc.npc_direction = "right";
                }
            }
            break;
        case 1:
            cutscene_dialogue();
            with (msg)
            {
                talker[0] = 1161;
                message[0] = "*  等 一 下 ! #     就 这 样 逃 走 也 太 轻 巧 了 。";
                message[1] = "*  别 冒 冒 失 失 的 ，#     我 们 会 找 到 另 一 条 出 路 的 。";
                prt[0] = 381;
                prt[1] = 377;
            }
            break;
        case 2:
            obj_ceroba_npc.npc_direction = "down";
            cutscene_advance();
            break;
        case 3:
            cutscene_instance_create(obj_pl.x, obj_pl.y, 1168);
            break;
        case 4:
            cutscene_npc_walk_relative(1168, 0, 40, 3, "y", "down");
            break;
        case 5:
            with (obj_player_npc)
            {
                if (!place_free(x, y))
                {
                    other.scene = 4;
                    exit;
                }
            }
            instance_destroy(obj_player_npc);
            scr_cutscene_end();
            cutscene_advance();
            break;
        case 6:
            if (place_meeting(x, y, obj_pl))
            {
                scr_cutscene_start();
                cutscene_change_room(161, 160, 280, 0.1);
            }
            break;
    }
}
if (global.sworks_flag[6] == 1)
{
    switch (scene)
    {
        case 0:
            cutscene_wait(1);
            break;
        case 1:
            if (global.route != 2)
            {
                global.sworks_flag[6] = 2;
                scr_cutscene_end();
                scene = 0;
                exit;
            }
            obj_ceroba_npc.npc_direction_hold = "down";
            obj_ceroba_npc.npc_direction = "right";
            cutscene_dialogue();
            with (msg)
            {
                talker[0] = 1161;
                message[0] = "*  哇 ，他 抓 住 你 了 。#     震 惊 。";
                prt[0] = 384;
            }
            break;
        case 2:
            global.sworks_flag[6] = 2;
            scr_cutscene_end();
            scene = 0;
            break;
    }
}
if (global.sworks_flag[6] == 2)
{
    if (place_meeting(x, y, obj_pl))
    {
        scr_cutscene_start();
        cutscene_change_room(161, 160, 280, 0.1);
    }
}
if (global.sworks_flag[6] == 3)
{
    switch (scene)
    {
        case 0:
            cutscene_wait(1);
            break;
        case 1:
            if (global.route != 2)
            {
                global.sworks_flag[6] = 4;
                scr_cutscene_end();
                scene = 0;
                exit;
            }
            obj_ceroba_npc.npc_direction_hold = "down";
            obj_ceroba_npc.npc_direction = "right";
            cutscene_dialogue();
            with (msg)
            {
                talker[0] = 1161;
                message[0] = "*  你 想 做 什 么 ?";
                message[1] = "*  快 点 ，按 照 计 划 来 !";
                prt[0] = 366;
                prt[1] = 368;
            }
            break;
        case 2:
            global.sworks_flag[6] = 4;
            scr_cutscene_end();
            scene = 0;
            break;
    }
}
if (global.sworks_flag[6] == 4)
{
    switch (scene)
    {
        case 0:
            if (scr_interact() && keyboard_multicheck_pressed(0))
            {
                scr_cutscene_start();
                cutscene_advance();
            }
            break;
        case 1:
            cutscene_sfx_play(364, 1);
            break;
        case 2:
            cutscene_wait(1);
            break;
        case 3:
            cutscene_dialogue();
            with (msg)
            {
                message[0] = "*  （ 门 锁 着 。）";
            }
            break;
        case 4:
            cutscene_advance();
            break;
        case 5:
            if (global.party_member != -4)
            {
                cutscene_advance(7);
                exit;
            }
            cutscene_instance_create(obj_pl.x, obj_pl.y, 1168);
            break;
        case 6:
            cutscene_npc_walk_relative(1168, 0, 40, 3, "y", "down");
            break;
        case 7:
            with (obj_player_npc)
            {
                if (!place_free(x, y))
                {
                    other.scene = 6;
                    exit;
                }
            }
            instance_destroy(obj_player_npc);
            scr_cutscene_end();
            cutscene_advance(0);
            break;
    }
}
