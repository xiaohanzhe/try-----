if (goup)
{
    levitate += 0.1;
}
if (levitate >= maxlevitate && !simplecheck)
{
    alarm[4] = random(5) + 1;
    clovery += random_range(-0.5, 0.5);
    tcharay += random_range(-0.5, 0.5);
    simplecheck = 1;
    maxlevitate = random_range(-3, -2.5);
}
if (!goup)
{
    levitate -= 0.1;
}
if (levitate <= maxlevitate && simplecheck)
{
    alarm[4] = random(5) + 1;
    clovery += random_range(-0.5, 0.5);
    tcharay += random_range(-0.5, 0.5);
    simplecheck = 0;
    maxlevitate = random_range(3, 2.5);
}
if (global.facing == 3)
{
    cloversprite = 3415;
    charasprite = 3416;
}
else if (global.facing == 2)
{
    cloversprite = 3346;
    charasprite = 3344;
}
else
{
    cloversprite = 3345;
    charasprite = 3343;
}
if (instance_exists(obj_face_chara))
{
    charaface = 0;
    if (obj_face_chara.sprite_index == spr_chara_annoy || obj_face_chara.sprite_index == spr_chara_confused)
    {
        charaface = 1;
    }
    if (obj_face_chara.sprite_index == spr_chara_surprised || obj_face_chara.sprite_index == spr_chara_shock)
    {
        charaface = 2;
    }
    if (obj_face_chara.sprite_index == spr_chara_right || obj_face_chara.sprite_index == spr_chara_posh)
    {
        charaface = 3;
    }
    if (obj_face_chara.sprite_index == spr_chara_up || obj_face_chara.sprite_index == spr_chara_left_upset || obj_face_chara.sprite_index == spr_chara_sad)
    {
        charaface = 4;
    }
    if (obj_face_chara.sprite_index == spr_chara_cheer || obj_face_chara.sprite_index == spr_chara_lookside_smile || obj_face_chara.sprite_index == spr_chara_smirk || obj_face_chara.sprite_index == spr_chara_smug || obj_face_chara.sprite_index == spr_chara_cheeky || obj_face_chara.sprite_index == spr_chara_edgeworth)
    {
        charaface = 5;
    }
    if (obj_face_chara.sprite_index == spr_chara_panic || obj_face_chara.sprite_index == spr_chara_squint_upset)
    {
        charaface = 6;
    }
    if (obj_face_chara.sprite_index == spr_chara_creep)
    {
        charaface = 7;
    }
    if (scr_murderlv() < 12)
    {
        juandice = -1;
    }
    car = 1;
}
else if (instance_exists(obj_face_clover))
{
    cloverface = 0;
    if (obj_face_clover.sprite_index == spr_clover_cheer || obj_face_clover.sprite_index == spr_clover_cheer_harder || obj_face_clover.sprite_index == spr_clover_flowey || obj_face_clover.sprite_index == spr_clover_relaxed || obj_face_clover.sprite_index == spr_clover_losingit)
    {
        cloverface = 1;
    }
    if (obj_face_clover.sprite_index == spr_clover_uh || obj_face_clover.sprite_index == spr_clover_sigh)
    {
        cloverface = 2;
    }
    if (obj_face_clover.sprite_index == spr_clover_mad || obj_face_clover.sprite_index == spr_clover_unamused || obj_face_clover.sprite_index == spr_clover_upset_noshadow)
    {
        cloverface = 3;
    }
    if (obj_face_clover.sprite_index == spr_clover_upset || obj_face_clover.sprite_index == spr_clover_sad || obj_face_clover.sprite_index == spr_clover_even_sadder || obj_face_clover.sprite_index == spr_clover_overjoyed)
    {
        cloverface = 4;
    }
    if (obj_face_clover.sprite_index == spr_clover_siffrin)
    {
        cloverface = 5;
    }
    if (obj_face_clover.sprite_index == spr_clover_what || obj_face_clover.sprite_index == spr_clover_shock)
    {
        cloverface = 6;
    }
    juandice = 1;
    car = -1;
}
else if (juandice != 0 && car != 0)
{
    juandice = 1;
    car = 1;
}
if (instance_exists(obj_starker) || instance_exists(obj_backgrounder_pillar) || instance_exists(obj_backgrounder_castle))
{
    if (obj_mainchara.moving == 0)
    {
        if ((juandice > 0 && clover_alpha < 0.5) || (juandice == -1 && clover_alpha < 0.3))
        {
            clover_alpha += 0.05;
        }
        if ((car > 0 && chara_alpha < 0.5) || (car == -1 && chara_alpha < 0.3))
        {
            chara_alpha += 0.05;
        }
    }
    if (juandice == -1 && clover_alpha > 0.3)
    {
        clover_alpha -= 0.05;
    }
    if (car == -1 && chara_alpha > 0.3)
    {
        chara_alpha -= 0.05;
    }
}
else if (obj_mainchara.moving == 0)
{
    if ((clover_alpha < 0.9 && juandice > 0) || (clover_alpha < 0.6 && juandice == -1))
    {
        clover_alpha += 0.05;
    }
    if ((car > 0 && chara_alpha < 0.9) || (car == -1 && chara_alpha < 0.6))
    {
        chara_alpha += 0.05;
    }
    if (juandice == -1 && clover_alpha > 0.6)
    {
        clover_alpha -= 0.05;
    }
    if (car == -1 && chara_alpha > 0.6)
    {
        chara_alpha -= 0.05;
    }
}
if (obj_mainchara.moving == 1)
{
    clover_alpha -= 0.05;
    chara_alpha -= 0.05;
}
if (clover_alpha <= 0 && chara_alpha <= 0)
{
    obj_mainchara.ghosttimer = 0;
    instance_destroy();
}
if (global.kills < 14)
{
    if (room == room_ruins15C)
    {
        clover_angle = 180;
        clovery = 29;
        cloverx = 22;
        if (global.flag[7] == 1 && !ossafe_file_exists("system_information_963"))
        {
            tcharax = 22;
            tcharay = 29;
            tchara_angle = 180;
        }
    }
    if (room == room_ruins15D)
    {
        tchara_angle = 270;
        clover_angle = 270;
        cloverx = 22;
        tcharax = 22;
        tcharay = 29;
        clovery = 29;
    }
    if (room == room_ruins15B)
    {
        clover_angle = 90;
        cloverx = -22;
        clovery = 29;
        if (global.flag[7] == 1 && !ossafe_file_exists("system_information_963"))
        {
            tcharax = -22;
            tcharay = 29;
            tchara_angle = 90;
        }
    }
}
if (car != 0 && !instance_exists(obj_ghostint2))
{
    draw_sprite_ext(charasprite, charaface, (obj_mainchara.x - 20) + tcharax, (obj_mainchara.y - 20 - levitate) + tcharay, 1, 1, tchara_angle, c_white, chara_alpha);
}
if (juandice != 0 && global.flag[7] == 0 && !instance_exists(obj_ghostint) && room != room_castle_exit)
{
    draw_sprite_ext(cloversprite, cloverface, obj_mainchara.x + 20 + cloverx, (obj_mainchara.y - 20) + levitate + clovery, 1, 1, clover_angle, c_white, clover_alpha);
}
