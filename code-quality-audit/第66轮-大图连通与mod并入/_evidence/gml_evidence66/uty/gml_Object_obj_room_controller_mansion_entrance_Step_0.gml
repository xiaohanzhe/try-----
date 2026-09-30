if (live_call())
{
    return global.live_result;
}
switch (scene)
{
    case 0:
        scr_cutscene_start();
        cutscene_follower_into_actor();
        obj_martlet_npc.npc_direction = "up";
        obj_martlet_npc.can_walk = false;
        instance_create(obj_pl.x, obj_pl.y, obj_player_npc);
        obj_player_npc.npc_direction = "up";
        break;
    case 1:
        cutscene_npc_walk(1164, 160, 185, 2, "y", "up");
        if (abs(obj_martlet_npc.y - obj_player_npc.y) > 30)
        {
            scene = 2;
        }
        break;
    case 2:
        cutscene_npc_walk(1168, 160, 220, 2, "x", "up");
        break;
    case 3:
        cutscene_camera_move(160, 160, 2);
        break;
    case 4:
        cutscene_wait(1.5);
        break;
    case 5:
        cutscene_npc_direction(1164, "down");
        break;
    case 6:
        cutscene_dialogue();
        with (msg)
        {
            talker[0] = 1164;
            message[0] = "*  我 当 时 要 是 问 问 那 些#     “ 文 件 和 录 像 带 ” 在 哪#     就 好 了 ，对 吧 ?";
            message[1] = "*  呃 . . . 我 们 可 以 先#     四 处 看 看 。";
            message[2] = "*  在 某 个 地 方 应 该#     会 有 个 办 公 室 的 . . .";
            prt[0] = 311;
            prt[1] = 324;
            prt[2] = 321;
            if (message_current == 2)
            {
                obj_martlet_npc.npc_direction = "up";
            }
        }
        break;
    case 7:
        cutscene_npc_walk(1164, obj_player_npc.x, obj_player_npc.y + 20, 3, "y", "up");
        break;
    case 8:
        cutscene_actor_into_follower();
        break;
    case 9:
        cutscene_camera_move(obj_pl.x, obj_pl.y, 2);
        break;
    case 10:
        cutscene_camera_reset();
        instance_destroy(obj_player_npc);
        scr_cutscene_end();
        global.dunes_flag[41] = 3;
        break;
    case 11:
        if (obj_pl.y >= 260 && global.party_member != -4)
        {
            scr_cutscene_start();
            instance_create(obj_pl.x, obj_pl.y, obj_player_npc);
            cutscene_advance();
        }
        break;
    case 12:
        cutscene_dialogue();
        with (msg)
        {
            message[0] = "*  在 出 发 之 前 ，我 们 需 要 找 到#     艾 德 说 过 的 那 些 东 西 。";
            prt[0] = 321;
            sndfnt = 102;
        }
        break;
    case 13:
        cutscene_npc_walk(1168, obj_pl.x, 250, 3, "y", "up");
        break;
    case 14:
        scr_cutscene_end();
        instance_destroy(obj_player_npc);
        scene = 11;
        break;
}
