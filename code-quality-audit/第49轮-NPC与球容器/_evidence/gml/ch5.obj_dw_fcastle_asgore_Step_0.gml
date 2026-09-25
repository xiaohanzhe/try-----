if (!init)
{
    init = true;
}
if (subcon == 0 && scr_trigcheck_ext("talk_" + string(con + 1), 1164))
{
    if (con == 0)
    {
        global.currentsong[0] = snd_init("asgore_serious.ogg");
        global.currentsong[1] = snd_loop(global.currentsong[0]);
        snd_volume(global.currentsong[1], 0, 0);
        snd_volume(global.currentsong[1], 1, 60);
    }
    subcon = 1;
    if (npcs[con].text != -4)
    {
        var _flower = npcs[con].flower;
        var _x = mean(_flower.bbox_left, _flower.bbox_right);
        if (_x > 320)
        {
            _x += 60;
        }
        else
        {
            _x -= 60;
        }
        var _y = npcs[con].asgore.bbox_top - 60;
        make_bubble(npcs[con].text, _x, _y, _flower, npcs[con].color);
    }
    with (npcs[con].flower)
    {
        if (other.con == 5)
        {
            scr_shakeobj();
        }
    }
}
if (subcon == 1 && scr_trigcheck_ext("fade_" + string(con + 1), 1164))
{
    subcon = 2;
    scr_delay_var("subcon", 3, 20);
    with (npcs[con].asgore)
    {
        scr_lerpvar("image_alpha", 1, 0, 60);
    }
}
if (subcon == 3)
{
    subcon = 0;
    with (charbubble)
    {
        scr_doom(self, 120);
    }
    var sethdelay = false;
    with (npcs[con].flower)
    {
        if (other.con == 0)
        {
            sprite_index = spr_enemy_aqua_unamused_r;
        }
        if (other.con == 1)
        {
            image_index = 1;
        }
        if (other.con == 5)
        {
            image_index = 1;
            with (other.charbubble)
            {
                instance_destroy();
            }
            var _flower = id;
            var _x = mean(_flower.bbox_left, _flower.bbox_right);
            if (_x > 320)
            {
                _x += 60;
            }
            else
            {
                _x -= 60;
            }
            sethdelay = true;
            var _y = other.npcs[other.con].asgore.bbox_top - 60;
            var _sethtext = stringsetloc("... sorry.", "obj_dw_fcastle_asgore_slash_Step_0_gml_106_0");
            with (other)
            {
                charbubble = make_bubble(_sethtext, _x, _y, _flower, npcs[con].color, true);
                with (charbubble)
                {
                    scr_script_delayed(scr_doom, 60, id, 120);
                }
            }
        }
        if (other.con == 2)
        {
            image_index = 2;
        }
        if (other.con == 4)
        {
            sprite_index = spr_enemy_orange_walk_right_sad;
        }
        if (other.con == 3)
        {
            image_index = 1;
        }
    }
    with (npcs[con].flower)
    {
        scr_script_delayed(scr_lerpvar, 40 + (50 * sethdelay), "image_alpha", 1, 0, 60);
    }
    with (blocker)
    {
        scr_script_delayed(scr_lerpvar, 40 + (50 * sethdelay), "image_alpha", 0, 1, 60);
    }
    con++;
}
