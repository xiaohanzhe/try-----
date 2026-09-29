myinteract = 0;
if (instance_exists(obj_mainchara))
{
    if (obj_mainchara.kill == 1)
    {
        instance_destroy();
    }
}
if (room == room_area1 && global.flag[19] > 0)
{
    instance_destroy();
}
image_speed = 0;
if (room == room_area1 || room == room_fire_restaurant)
{
    sprite_index = spr_ghost_clover_left;
}
if (room == room_fire_restaurant)
{
    if (!instance_exists(obj_sansdate3))
    {
        instance_destroy();
    }
}
if (room == room_fire_multitile)
{
    if (global.kills == 0 && global.flag[19] > 24)
    {
        sprite_index = spr_ghost_clover_dance;
        image_speed = 0.2;
    }
    else
    {
        instance_destroy();
    }
}
if (room == room_fire_finalelevator)
{
    sprite_index = spr_ghost_clover_sit;
}
if (global.flag[7] == 1 || scr_murderlv() >= 12)
{
    instance_destroy();
}
starty = y;
goup = 1;
simplecheck = 0;
yes = 0;
talkedto = 0;
