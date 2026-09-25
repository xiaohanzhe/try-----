con = -1;
customcon = 0;
if (scr_flag_get(1324) == 0)
{
    asgore_npc = scr_marker_fancy(710, 118, 6811);
    with (asgore_npc)
    {
        sprite_index = spr_npc_asgore_kneel_flowers;
        image_speed = 0.1;
        scr_addtosunshadows(id, undefined, true);
        scr_depth();
    }
    var asgore_readable = instance_create(asgore_npc.x + 10, asgore_npc.y + 40, obj_readable_room1);
    with (asgore_readable)
    {
        extflag = "asgore_morning";
        image_xscale = 1.2;
        image_yscale = 1;
    }
    var asgore_collision = instance_create(asgore_npc.x + 5, asgore_npc.y + 40, obj_solidblockLight);
    with (asgore_collision)
    {
        image_xscale = 2;
        image_yscale = 1;
    }
}
else if (scr_flag_get(1324) == 1)
{
    asgore_npc = instance_create(1244, 70, obj_npc_room);
    with (asgore_npc)
    {
        extflag = "asgore_day";
        sprite_index = spr_asgored;
        scr_depth();
    }
}
if (scr_flag_get(1324) == 1 || (scr_sideb_active() && scr_flag_get(1324) == 2))
{
    var cart_left = scr_marker(1160, 40, spr_festival_flowerking_cart_flowers_1);
    with (cart_left)
    {
        image_index = (scr_flag_get(1324) == 2) ? 1 : 0;
        scr_depth();
    }
    var cart_left_collider = instance_create(1162, 110, obj_solidblock);
    with (cart_left_collider)
    {
        image_xscale = 2.85;
    }
    var cart_right = scr_marker(1290, 40, spr_festival_flowerking_cart_flowers_2);
    with (cart_right)
    {
        image_index = (scr_flag_get(1324) == 2) ? 1 : 0;
        scr_depth();
    }
    var cart_right_collider = instance_create(1298, 110, obj_solidblock);
    with (cart_right_collider)
    {
        image_xscale = 3.3;
    }
    roses_readable = instance_create(1200, 95, obj_readable_room1);
    with (roses_readable)
    {
        extflag = "asgore_roses";
        if (scr_sideb_active())
        {
            extflag = "asgore_flowers";
        }
    }
    flower_crown = -4;
    crown_readable = -4;
    flower_crown = scr_marker(1300, 100, spr_flowerking_crown);
    flower_crown.depth = cart_right.depth - 10;
    if (scr_flag_get(1324) == 1)
    {
        mewmew_readable = instance_create(1352, 184, obj_readable_room1);
        with (mewmew_readable)
        {
            extflag = "asgore_mewmew";
            image_xscale = 0.5;
            image_yscale = 0.5;
        }
    }
    crown_readable = instance_create(flower_crown.x, flower_crown.y, obj_readable_room1);
    with (crown_readable)
    {
        extflag = "asgore_crown";
    }
    var flower_readables = [[new Vector2(1218, 197), new Vector2(2.55, 1)], [new Vector2(1176, 99), new Vector2(0.75, 0.85)]];
    if (!scr_sideb_active())
    {
        flower_readables[array_length(flower_readables)] = [new Vector2(1334, 105), new Vector2(1.35, 0.85)];
    }
    else
    {
        with (flower_crown)
        {
            instance_destroy();
        }
        with (crown_readable)
        {
            image_xscale = 3;
        }
    }
    for (var i = 0; i < array_length(flower_readables); i++)
    {
        var _readable_data = flower_readables[i];
        var _readable_pos = _readable_data[0];
        var _readable_scale = _readable_data[1];
        var _readable = instance_create(_readable_pos.x, _readable_pos.y, obj_readable_room1);
        with (_readable)
        {
            extflag = "asgore_flowers";
            image_xscale = _readable_scale.x;
            image_yscale = _readable_scale.y;
        }
    }
}

show_convo = function(arg0)
{
    switch (arg0)
    {
        case "asgore_morning":
            con = 20;
            if (scr_flag_get(1328) > 0)
            {
                con = 2;
            }
            break;
        case "asgore_mewmew":
            con = 5;
            break;
        case "asgore_day":
            con = 10;
            if (scr_flag_get(1327) == 1)
            {
                con = 11;
            }
            break;
        case "asgore_crown":
            con = 30;
            if (scr_sideb_active())
            {
                con = 40;
                if (scr_flag_get(1883) == 1)
                {
                    con = 54;
                }
            }
            break;
        case "asgore_flowers":
            con = 50;
            if (scr_sideb_active())
            {
                con = 52;
                if (scr_flag_get(1807) == 1)
                {
                    con = 54;
                }
            }
            break;
        case "asgore_roses":
            con = 60;
            break;
    }
};
