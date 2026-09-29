global.entrance = 19;
instance_create(0, 0, obj_persistentfader);
if (room == room_water_yellow)
{
}
room_goto(room_water_prebird);
if (room == room_water_prebird)
{
    room_goto(room_water_yellow);
}
if (room == room_water_bird)
{
    room_goto(room_water_friendlyhub);
}
if (room == room_tundra_sanshouse)
{
    room_goto(room_tundra_town);
}
if (room == room_water_blookyard)
{
    room_goto(room_water_farm);
}
if (room == room_water_farm)
{
    room_goto(room_water_blookyard);
}
if (room == room_water_friendlyhub)
{
    room_goto(room_water_bird);
}
if (room == room_water_bird)
{
    room_goto(room_water_friendlyhub);
}
if (room == room_water14)
{
    room_goto(room_water_statue);
}
if (room == room_water_statue)
{
    room_goto(room_water14);
}
if (room == room_fire_elevator_r1)
{
    room_goto(room_fire_elevator);
}
if (room == room_fire_elevator_r2)
{
    room_goto(room_fire_elevator);
}
if (room == room_fire_elevator_r3)
{
    room_goto(room_fire_elevator);
}
if (room == room_fire_elevator_l1)
{
    room_goto(room_fire_elevator);
}
if (room == room_fire_elevator_l2)
{
    room_goto(room_fire_elevator);
}
if (room == room_fire_elevator_l3)
{
    room_goto(room_fire_elevator);
}
if (room == room_fire_elevator_s)
{
    room_goto(room_fire_elevator);
}
if (room == room_fire_elevator)
{
    if (global.flag[398] == 0)
    {
        room_goto(room_fire_elevator_l1);
    }
    if (global.flag[398] == 1)
    {
        room_goto(room_fire_elevator_r1);
    }
    if (global.flag[398] == 2)
    {
        room_goto(room_fire_elevator_r2);
    }
    if (global.flag[398] == 3)
    {
        room_goto(room_fire_elevator_l2);
    }
    if (global.flag[398] == 4)
    {
        room_goto(room_fire_elevator_l3);
    }
    if (global.flag[398] == 5)
    {
        room_goto(room_fire_elevator_r3);
    }
    if (global.flag[398] == 6)
    {
        room_goto(room_fire_elevator_s);
    }
}
if (room == room_fire_core_final)
{
    global.flag[431] = 0;
    room_goto(room_fire_finalelevator);
}
if (room == room_castle_elevatorout)
{
    global.flag[431] = 1;
    global.flag[429] = 0;
    room_goto(room_fire_finalelevator);
}
if (room == room_fire_finalelevator)
{
    if (global.flag[431] == 0)
    {
        room_goto(room_fire_core_final);
    }
    if (global.flag[431] == 1)
    {
        room_goto(room_castle_elevatorout);
    }
}
if (room == room_castle_finalshoehorn)
{
    room_goto(room_castle_throneroom);
}
if (room == room_castle_throneroom)
{
    room_goto(room_castle_finalshoehorn);
}
if (room == room_fire_lab1)
{
    room_goto(room_fire_labelevator);
}
if (room == room_fire_labelevator)
{
    room_goto(room_fire_lab1);
}
if (room == room_truelab_hub)
{
    room_goto(room_truelab_castle_elevator);
}
if (room == room_truelab_castle_elevator)
{
    room_goto(room_truelab_hub);
}
if (room == room_ruinsexit)
{
    room_goto(room_tundra1);
}
if (room == room_tundra1)
{
    room_goto(room_ruinsexit);
}
if (room == room_fire_hotellobby && x < 300)
{
    room_goto(room_shop4);
}
if (room == room_tundra_sansbasement)
{
    room_goto(room_tundra_town);
}
if (room == room_tundra_town)
{
    room_goto(room_tundra_sansbasement);
}
if (room == room_castle_precastle)
{
    room_goto(room_lastruins_corridor);
}
if (room == room_lastruins_corridor)
{
    global.flag[422] = 0;
    global.flag[429] = 2;
    if (global.plot >= 201)
    {
        room_goto(room_newhome_elevator);
    }
    else
    {
        room_goto(room_castle_precastle);
    }
}
if (room == room_mysteryman)
{
    room_goto(room_water_fakehallway);
}
if (room == room_steamworks_32)
{
    room_goto(room_steamworks_factory_elevator);
}
if (room == room_steamworks_factory_elevator)
{
    room_goto(room_steamworks_32);
}
if (room == room_newhome_01)
{
    global.flag[422] = 0;
    global.flag[429] = 0;
    room_goto(room_newhome_elevator);
}
if (room == room_fire_hotellobby && x > 300)
{
    global.flag[422] = 0;
    global.flag[429] = 1;
    room_goto(room_newhome_elevator);
}
if (room == room_newhome_04)
{
    global.flag[422] = 1;
    global.flag[429] = 3;
    room_goto(room_newhome_elevator);
}
if (room == room_newhome_elevator)
{
    if (global.flag[429] == 1)
    {
        room_goto(room_fire_hotellobby);
    }
    if (global.flag[429] == 0)
    {
        room_goto(room_newhome_01);
    }
    if (global.flag[429] == 2)
    {
        room_goto(room_lastruins_corridor);
    }
    if (global.flag[429] == 3)
    {
        room_goto(room_newhome_04);
    }
    if (global.flag[422] == 2)
    {
        room_goto(room_castle_precastle);
    }
}
