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
if (room == room_area1)
{
    sprite_index = spr_ghost_chara_lean;
    image_xscale = -1;
}
if (room == room_fire_restaurant)
{
    if (!instance_exists(obj_sansdate3))
    {
        instance_destroy();
    }
}
if (room == room_fire_finalelevator)
{
    sprite_index = spr_ghost_chara_lean;
}
starty = y;
goup = 0;
simplecheck = 1;
talkedto = 0;
