script_execute(scr_depth, 0, 0, 0, 0, 0);
dist = distance_to_object(obj_mainchara);
if (obj_mainchara.cutscene == 1)
{
    if (instance_exists(obj_face_chara))
    {
        if (image_alpha < 0.9)
        {
            image_alpha += 0.05;
        }
    }
    else if (image_alpha > 0.6)
    {
        image_alpha -= 0.05;
    }
    else if (image_alpha < 0.6)
    {
        image_alpha += 0.05;
    }
}
else if (dist < 100)
{
    disto = 10 / (dist + 1);
    if (disto > 0.9)
    {
        disto = 0.9;
    }
    image_alpha = disto;
}
else if (image_alpha > 0)
{
    image_alpha -= 0.05;
}
else
{
    image_alpha = 0;
}
if (sprite_index == spr_ghost_chara_down || sprite_index == spr_ghost_chara_left || sprite_index == spr_ghost_chara_up)
{
    if (goup == 1)
    {
        y += 0.1;
    }
    if (y >= (starty + 2) && !simplecheck)
    {
        goup = 0;
        simplecheck = 1;
    }
    if (goup == 0)
    {
        y -= 0.1;
    }
    if (y <= (starty - 2) && simplecheck)
    {
        goup = 1;
        simplecheck = 0;
    }
    if (instance_exists(obj_face_chara))
    {
        image_index = 0;
        if (obj_face_chara.sprite_index == spr_chara_annoy || obj_face_chara.sprite_index == spr_chara_confused)
        {
            image_index = 1;
        }
        if (obj_face_chara.sprite_index == spr_chara_surprised || obj_face_chara.sprite_index == spr_chara_shock)
        {
            image_index = 2;
        }
        if (obj_face_chara.sprite_index == spr_chara_right || obj_face_chara.sprite_index == spr_chara_posh)
        {
            image_index = 3;
        }
        if (obj_face_chara.sprite_index == spr_chara_up || obj_face_chara.sprite_index == spr_chara_left_upset || obj_face_chara.sprite_index == spr_chara_sad)
        {
            image_index = 4;
        }
        if (obj_face_chara.sprite_index == spr_chara_cheer || obj_face_chara.sprite_index == spr_chara_lookside_smile || obj_face_chara.sprite_index == spr_chara_smirk || obj_face_chara.sprite_index == spr_chara_smug || obj_face_chara.sprite_index == spr_chara_cheeky || obj_face_chara.sprite_index == spr_chara_edgeworth)
        {
            image_index = 5;
        }
        if (obj_face_chara.sprite_index == spr_chara_panic || obj_face_chara.sprite_index == spr_chara_squint_upset)
        {
            image_index = 6;
        }
        if (obj_face_chara.sprite_index == spr_chara_creep)
        {
            image_index = 7;
        }
    }
}
