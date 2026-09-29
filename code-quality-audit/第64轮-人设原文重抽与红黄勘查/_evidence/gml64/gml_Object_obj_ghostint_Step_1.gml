script_execute(scr_depth, 0, 0, 0, 0, 0);
dist = distance_to_object(obj_mainchara);
if (obj_mainchara.cutscene == 1)
{
    if (instance_exists(obj_face_clover))
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
if (sprite_index == spr_ghost_clover_down || sprite_index == spr_ghost_clover_left || sprite_index == spr_ghost_clover_up)
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
    if (instance_exists(obj_face_clover))
    {
        image_index = 0;
        if (obj_face_clover.sprite_index == spr_clover_cheer || obj_face_clover.sprite_index == spr_clover_cheer_harder || obj_face_clover.sprite_index == spr_clover_flowey || obj_face_clover.sprite_index == spr_clover_relaxed || obj_face_clover.sprite_index == spr_clover_losingit)
        {
            image_index = 1;
        }
        if (obj_face_clover.sprite_index == spr_clover_uh || obj_face_clover.sprite_index == spr_clover_sigh)
        {
            image_index = 2;
        }
        if (obj_face_clover.sprite_index == spr_clover_mad || obj_face_clover.sprite_index == spr_clover_unamused || obj_face_clover.sprite_index == spr_clover_upset_noshadow)
        {
            image_index = 3;
        }
        if (obj_face_clover.sprite_index == spr_clover_upset || obj_face_clover.sprite_index == spr_clover_sad || obj_face_clover.sprite_index == spr_clover_even_sadder)
        {
            image_index = 4;
        }
        if (obj_face_clover.sprite_index == spr_clover_siffrin)
        {
            image_index = 5;
        }
        if (obj_face_clover.sprite_index == spr_clover_what || obj_face_clover.sprite_index == spr_clover_shock)
        {
            image_index = 6;
        }
    }
}
