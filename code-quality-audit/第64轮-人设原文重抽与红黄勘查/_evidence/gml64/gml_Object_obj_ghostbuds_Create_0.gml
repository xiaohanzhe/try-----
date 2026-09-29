clover_alpha = 0.01;
chara_alpha = 0.01;
levitate = 0;
juandice = 1;
car = 1;
goup = 1;
cloverx = 0;
clovery = 0;
clover_angle = 0;
tcharax = 0;
tcharay = 0;
tchara_angle = 0;
cloverface = 0;
charaface = 0;
simplecheck = 0;
maxlevitate = 3;
yes = 0;
if (instance_exists(obj_ghostint))
{
    yes = obj_ghostint.yes;
}
if (scr_murderlv() >= 12 || global.flag[7] == 1)
{
    juandice = 0;
}
if (room == room_castle_exit || room == room_f_room)
{
    juandice = 0;
}
if (obj_mainchara.kill || scr_murderlv() >= 8)
{
    cloverface = 3;
}
if (global.flag[7] == 1 && !ossafe_file_exists("system_information_963"))
{
    charaface = 5;
}
if (scr_murderlv() >= 13)
{
    car = 0;
}
if (room != room_area1)
{
    if ((instance_exists(obj_ghostint) && instance_exists(obj_ghostint2)) && !yes)
    {
        instance_destroy();
    }
    else if (instance_exists(obj_ghostint) && !yes)
    {
        juandice = 0;
    }
    else if (instance_exists(obj_ghostint2) && !yes)
    {
        car = 0;
    }
    if (instance_exists(obj_ghostint))
    {
        clover_alpha = 0.9;
    }
    if (instance_exists(obj_ghostint2))
    {
        chara_alpha = 0.9;
    }
}
if (room == room_mysteryman)
{
    instance_destroy();
}
depth = obj_mainchara.depth;
