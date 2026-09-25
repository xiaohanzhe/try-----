if (i_ex(platform))
{
    platform.image_xscale = 0.75 * image_xscale;
    platform.image_yscale = 2;
    var _lastx = platform.x;
    platform.x = x - (0.75 * platform.sprite_width);
    if (long > 0)
    {
        platform.image_xscale *= 1 + long;
        platform.x -= 24 * long;
    }
    if (abs(platform.x - _lastx) > 20)
    {
        platform.xprevious += platform.x - _lastx;
    }
    platform.y = y + 4;
    if (is_platform_mode == 3)
    {
        x = platform_mode_target.x + platform_mode_target.hang_xoffset;
        y = platform_mode_target.y + platform_mode_target.hang_yoffset + 60;
        image_xscale = abs(image_xscale);
        image_speed = 0;
        image_index = 0;
        platform.mask_index = platform.sprite_index;
        if (scr_plat_standing_on("kr", platform))
        {
            image_index++;
            player_stood_on_ralsei_recently = true;
        }
        if (scr_plat_standing_on("su", platform))
        {
            image_index++;
        }
        sprite_index = spr_plat_ralsei_hanging_torso;
        if (custom_platform_mode != -4)
        {
            with (platform_mode_target)
            {
                other.custom_platform_mode(other);
            }
        }
    }
    with (platform)
    {
        scr_plat_set_difference();
    }
}
if (instance_exists(obj_cutscene_master) || attacking || forced_anim || (instance_exists(obj_plat_player) && obj_plat_player.targetmode))
{
    important_blend = scr_approach(important_blend, 1, 0.15);
    if (attacking || forced_anim)
    {
        if (!obj_plat_player.targetmode && !is_platform_mode)
        {
            scr_plat_depthcast();
        }
        if (important)
        {
            depth -= 2;
        }
    }
}
else if (!is_platform_mode)
{
    important_blend = scr_approach(important_blend, important, 0.15);
    scr_plat_depthcast();
    if (important)
    {
        depth -= 2;
    }
}
if (paused || custom_paused)
{
    exit;
}
if (!caterpillarmode && !platform_valid && !attacking)
{
    event_inherited();
}
with (back_marker)
{
    other.y += ((other.back_marker_scale - 1) * 20);
    other.platform.y = other.y + 4;
    x = other.x;
    y = other.y;
    image_xscale = other.image_xscale;
    image_yscale = other.image_yscale + other.back_marker_scale;
    image_blend = other.image_blend;
    image_index = other.image_index;
    depth = other.depth + 20;
}
if (kris_throw_state > 0)
{
    speed = 0;
    gravity = 0;
    exit;
}
var _landingsound = false;
var _do_autorun = false;
if (autorun && grounded && !climbing)
{
    _do_autorun = true;
}
if (forced_anim)
{
    exit;
}
if (grounded != groundedprev && grounded && !land_anim && ground != -4)
{
    land_anim = true;
    _landingsound = true;
    sprite_index = spr_land;
    image_index = 0;
    image_speed = 0.25;
}
if (!climbing)
{
    if (key_left)
    {
        if (grounded && !turn_anim && hspeed > 0.1)
        {
            turn_anim = true;
            sprite_index = spr_turn;
            image_speed = 0.5;
        }
        image_xscale = -2 * scale_multiplier;
    }
    if (key_right)
    {
        image_xscale = 2 * scale_multiplier;
        if (grounded && !turn_anim && hspeed < -0.1)
        {
            turn_anim = true;
            sprite_index = spr_turn;
            image_speed = 0.5;
        }
    }
}
if (grounded && !climbing && !_do_autorun)
{
    if (((((!key_left && !key_right) || (key_left && key_right)) && !caterpillarmode) || (caterpillarmode && abs(hspeed) <= 0.5 && sprite_index == spr_run && !turn_anim)) && !runstop_anim && !land_anim && sprite_index == spr_run)
    {
        turn_anim = false;
        runstop_anim = true;
        sprite_index = spr_halt;
        image_index = 0;
        image_speed = 0.3;
    }
}
if (key_left || key_right || sprite_index != spr_halt)
{
    runstop_anim = false;
}
if (!grounded)
{
    land_anim = false;
    turn_anim = false;
    runstop_anim = false;
}
if (sprite_index != spr_land || key_left || key_right)
{
    land_anim = false;
}
if (!hurt && !land_anim && !turn_anim && !runstop_anim && !climbing && !_do_autorun)
{
    if (!turn_anim)
    {
        image_speed = 0.25;
    }
    if (grounded)
    {
        if ((key_left || key_right) || (caterpillarmode && abs(hspeed) > 0))
        {
            if (x != xprevious)
            {
                sprite_index = spr_run;
            }
        }
        if (key_left && hspeed > 0.1 && !turn_anim)
        {
            turn_anim = true;
            sprite_index = spr_turn;
        }
        if (key_right && hspeed < -0.1 && !turn_anim)
        {
            turn_anim = true;
            sprite_index = spr_turn;
        }
        if (hspeed < 0.25 && hspeed > -0.25)
        {
            if (!turn_anim)
            {
                image_speed = 0.25;
                sprite_index = spr_idle;
            }
        }
        else
        {
            if (!turn_anim)
            {
                image_speed = 0.15 + (0.25 * (abs(hspeed) / abs(hspeed_max)));
            }
            if (key_left && key_right)
            {
                turn_anim = false;
                image_speed = 0.25;
                sprite_index = spr_idle;
            }
        }
    }
    else
    {
        image_speed = 0.25;
        if (vspeed < 1)
        {
            sprite_index = spr_jump;
        }
        else
        {
            sprite_index = spr_fall;
        }
    }
}
if (climbing)
{
    sprite_index = spr_climb;
    image_speed = 0;
    if (key_up)
    {
        image_speed = 0.25;
    }
    if (key_down)
    {
        image_speed = -0.25;
    }
}
if (_do_autorun)
{
    sprite_index = spr_run;
    image_speed = 0.25;
    image_xscale = abs(image_xscale);
}
if (jumpsquat > 0)
{
    sprite_index = spr_land;
}
if (autorun)
{
    image_xscale = autorun_xscale;
    if ((t % round(autorun_img_freq)) == 0)
    {
        with (instance_create(x, y, obj_afterimage))
        {
            depth = other.depth + 1;
            hspeed = obj_runner_camera.movespeed / 1.5;
            sprite_index = other.sprite_index;
            image_index = other.image_index;
            image_speed = 0;
            image_xscale = other.image_xscale;
            image_yscale = other.image_yscale;
            image_blend = c_purple;
            image_alpha = 0.6;
            fadeSpeed = 0.1;
        }
    }
}
if (_landingsound && sprite_index == spr_land)
{
}
if (physics && wallcollision && visible)
{
    if (!respawn_leap && !fallen_in_pit && !caterpillarmode)
    {
        scr_collision_failsafe();
    }
    scr_plat_snap_to_ground();
}
