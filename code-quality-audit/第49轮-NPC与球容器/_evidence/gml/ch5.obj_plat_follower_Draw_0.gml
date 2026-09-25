image_blend = merge_color(#8F8F8F, c_white, important_blend);
if (is_platform_mode == 3)
{
    if (long > 0.05)
    {
        var spr = 5675;
        if (image_index == 1)
        {
            spr = 345;
        }
        if (image_index == 2)
        {
            spr = 3123;
        }
        var xoffset = -10 + (-32 * long);
        var yy = (((y - 16) + (2 * image_index)) - 4) + (2 * image_index);
        if (highlighted)
        {
            for (var i = 0; i < 5; i++)
            {
                var xs = image_xscale;
                var xx = ((x + xoffset) - 40) + 10;
                if (i == 1 || i == 3)
                {
                    xs *= ((1 + long) * 0.85);
                    if (i == 1)
                    {
                        xx -= (0.1 * sprite_get_width(spr) * xs);
                    }
                    if (i == 3)
                    {
                        xx += (0.2 * sprite_get_width(spr) * xs);
                    }
                }
                if (i == 2)
                {
                    xx = (x - 60) + 10;
                }
                if (i == 4)
                {
                    xx = x - 60 - xoffset;
                    yy = yy + 2;
                }
                if (i == 0)
                {
                    xx = xx - 8;
                }
                var _xs = image_xscale;
                var _i = image_index;
                var _spr = sprite_index;
                var _x = x;
                var _y = y;
                image_xscale = xs;
                sprite_index = spr;
                image_index = i;
                x = xx;
                y = yy;
                scr_draw_outline(2, merge_color(outlinecolor, c_white, 0.8 + (sin(current_time / 100) * 0.2)), 1);
                x = _x;
                y = _y;
                sprite_index = _spr;
                image_index = _i;
                image_xscale = _xs;
            }
            yy = (((y - 16) + (2 * image_index)) - 4) + (2 * image_index);
        }
        for (var i = 0; i < 5; i++)
        {
            var xs = image_xscale;
            var xx = ((x + xoffset) - 40) + 10;
            if (i == 1 || i == 3)
            {
                xs *= ((1 + long) * 0.85);
                if (i == 1)
                {
                    xx -= (0.1 * sprite_get_width(spr) * xs);
                }
                if (i == 3)
                {
                    xx += (0.2 * sprite_get_width(spr) * xs);
                }
            }
            if (i == 2)
            {
                xx = (x - 60) + 10;
            }
            if (i == 4)
            {
                xx = x - 60 - xoffset;
                yy = yy + 2;
            }
            if (i == 0)
            {
                xx = xx - 8;
            }
            draw_sprite_ext(spr, i, xx, yy, xs, image_yscale, 0, image_blend, image_alpha);
        }
    }
    else
    {
        draw_self();
        var frame = 0;
        var yy = (y - (11 * image_yscale)) + (4 * image_index);
        with (obj_plat_player)
        {
            if (x < (other.x - (11 * image_xscale)))
            {
                frame = 1;
            }
        }
        if (image_index > 0)
        {
            frame = 2;
        }
        if (highlighted)
        {
            scr_draw_outline(2, merge_color(outlinecolor, c_white, 0.8 + (sin(current_time / 100) * 0.2)), 1);
            draw_self();
        }
        draw_sprite_ext(spr_plat_ralsei_hanging_head, frame, x - (11 * image_xscale), yy, image_xscale, image_yscale, image_angle, image_blend, image_alpha);
    }
}
else
{
    var restore_x = x;
    var restore_y = y;
    x -= (sprite_offset_x * image_xscale);
    y -= (sprite_offset_y * image_yscale);
    if (highlighted)
    {
        scr_draw_outline(2, merge_color(outlinecolor, c_white, 0.8 + (sin(current_time / 100) * 0.2)), 1);
    }
    draw_self();
    x = restore_x;
    y = restore_y;
}
if (scr_debug())
{
    for (var i = 0; i < array_length(dbg_targets); i++)
    {
        var tt = dbg_targets[i];
        draw_set_color(tt[2]);
        draw_line(x, y, tt[0], tt[1]);
        draw_text(tt[0], tt[1], string(tt[3]));
    }
}
if (global.pause_plat)
{
    exit;
}
if (instance_exists(free_will_target))
{
    var xx = x;
    var yy = y;
    var cx = free_will_target_x;
    var cy = free_will_target_y;
    var dist = point_distance(xx, yy, cx, cy);
    var dir = point_direction(xx, yy, cx, cy);
    var wavefreq = current_time * -0.005;
    var dist_off = (current_time * 0.01) % 20;
    for (var i = 20; i < (dist - 20); i += 20)
    {
        var _idist = i + dist_off;
        var _x = lengthdir_x(_idist, dir);
        var _y = lengthdir_y(_idist, dir);
        var _alpha = 1;
        if (_idist < 40)
        {
            _alpha = inverselerp(20, 40, _idist);
        }
        else if (_idist > (dist - 40))
        {
            _alpha = inverselerp(dist - 20, dist - 40, _idist);
        }
        var size = 1;
        var _alpha2 = clamp01(_alpha - (dist_off / 20)) / 3;
        _idist += (dist_off * 0.75);
        var _x2 = lengthdir_x(_idist, dir);
        var _y2 = lengthdir_y(_idist, dir);
        size = 1;
        var accent_color = 16777215;
        if (name == "susie")
        {
            accent_color = 16711935;
        }
        else
        {
            accent_color = 65280;
        }
        accent_color = merge_color(accent_color, c_gray, 0.5);
        draw_sprite_ext(spr_plat_targetmode_arrow, 0, xx + _x2, yy + _y2, size, size, dir, accent_color, _alpha2 * free_will_target_lerp);
        draw_sprite_ext(spr_plat_targetmode_arrow, 0, xx + _x, yy + _y, size, size, dir, accent_color, _alpha * free_will_target_lerp);
    }
}
