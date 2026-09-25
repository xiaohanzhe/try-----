event_inherited();
t = 0;
depth = 2050;
position_history_length = 36;
entity_gravity = 1.25;
default_gravity = 1.25;
jumpheight = 20;
attacking = false;
attacktimer = 0;
target = -4;
climbing = false;
dashing = false;
land_anim = false;
turn_anim = false;
runstop_anim = false;
hurt = false;
hspeed_max = 9;
autorun = false;
autorun_xscale = image_xscale;
autorun_img_freq = 2;
scale_multiplier = 1;
player_stood_on_ralsei_recently = true;
act_busy = false;
dbg_targets = [];
air_accel = 1.5;
air_decel = 0.85;
ground_accel = 2;
ground_decel = 0.65;
important = false;
important_blend = 1;
jumping = 0;
jump_coyote_time_max = 4;
jump_coyote_time = 0;
jumpsquat = 0;
jumpsquat_max = 2;
fallen_in_pit = false;
respawn_leap = false;
respawn_leap_wait = 15;
respawn_leap_enabled = 0;
mount = -4;
for (var i = position_history_length; i >= 0; i -= 1)
{
    remx[i] = x;
    remy[i] = y;
    remspd[i] = speed;
    remdir[i] = direction;
    remgnd[i] = -4;
}
caterpillarmode = 1;
if (instance_exists(obj_runner_camera))
{
    caterpillarmode = 1;
    respawn_leap_enabled = 0;
}
caterpillardist = 2;
parent = -4;
default_dist = 2;

init_caterpillarmode = function()
{
    if (!i_ex(obj_plat_player))
    {
        exit;
    }
    if (!caterpillarmode)
    {
        offscreen_despawn_cooldown = 10;
        caterpillarmode = 1;
        enable_unstuck_failsafe = 0;
        if (!i_ex(parent))
        {
            parent = obj_plat_player.id;
        }
        var _line = collision_line(x, y, parent.x, parent.y, obj_plat_block, 0, 1);
        if (_line)
        {
            var _jumptime = max(default_dist, 30);
            caterpillardist = _jumptime;
            var _t = _jumptime;
            var _h = 80;
            for (var i = 0; i <= _t; i += 1)
            {
                remx[i] = lerp_ease_inout(parent.x, x, i / _t, 3);
                remy[i] = lerp_ease_inout(parent.bbox_bottom - bbox_bottom_r, y, i / _t, 3) - (sin(i * (pi / _t)) * _h);
                remspd[i] = 0;
                remdir[i] = 0;
                remgnd[i] = -4;
            }
        }
        else
        {
            var _t = caterpillardist;
            for (var i = 0; i <= _t; i += 1)
            {
                remx[i] = lerp_ease_out(parent.x, x, i / _t, 3);
                remy[i] = lerp_ease_out(parent.bbox_bottom - bbox_bottom_r, y, i / _t, 3);
                remspd[i] = 0;
                remdir[i] = 0;
                remgnd[i] = -4;
            }
        }
        x = remx[caterpillardist];
        y = remy[caterpillardist];
    }
};

axethrow = 0;
axe = -4;
can_catch_kris = 0;
kris_throw_state = 0;
kris_throw_wait = 0;
kris_throw_jumptime = 20;
throwzone = -4;
autostop_when_reached = false;

reached_target = function()
{
    if (followtarget == "__nothing")
    {
        exit;
    }
    var _FollowObject = -4;
    if (state == 1)
    {
        if (is_string(followtarget))
        {
            with (obj_plat_movemarker)
            {
                if (extflag == other.followtarget)
                {
                    _FollowObject = self;
                    break;
                }
            }
        }
        else if (instance_exists(followtarget))
        {
            _FollowObject = followtarget;
        }
    }
    reachedtarget = false;
    if (_FollowObject == -4)
    {
        return false;
    }
    var _follow_dist = 10;
    reachedtarget = abs(x - (_FollowObject.x + followxoffset)) < _follow_dist;
    if (reachedtarget && autostop_when_reached)
    {
        followtarget = "__nothing";
    }
    if (reachedtarget)
    {
        followxoffset = 0;
    }
    return reachedtarget;
};

key_left_override = false;
key_right_override = false;

turn = function(arg0)
{
    if (arg0 && image_xscale > 0)
    {
        exit;
    }
    if (!arg0 && image_xscale < 0)
    {
        exit;
    }
    if (arg0)
    {
        key_right_override = true;
    }
    else
    {
        key_left_override = true;
    }
    var _state = state;
    var _caterpillarmode = caterpillarmode;
    state = 0;
    caterpillarmode = 0;
    scr_delay_var("key_left_override", false, 2);
    scr_delay_var("key_right_override", false, 2);
    scr_delay_var("state", _state, 2);
    scr_delay_var("caterpillarmode", _caterpillarmode, 2);
};

force_jump = function()
{
    press_jump = true;
};

force_axe_throw = function()
{
    axethrow_cooldown = 0;
};

buster_explode = true;
is_quick_attack = false;
buster_interim = 0;
__susie_act_cooldown = 120;

force_attack_target = function(arg0, arg1 = true, arg2 = false, arg3 = 0, arg4 = 120)
{
    restore_default_behavior();
    restore_animation();
    target = arg0;
    state = 1;
    caterpillarmode = 0;
    buster_explode = arg1;
    is_quick_attack = arg2;
    buster_interim = arg3;
    attacking = 1;
    attacktimer = 0;
    __susie_act_cooldown = arg4;
    offscreen_despawn_cooldown = 100;
};

force_heal_target = function(arg0, arg1 = false, arg2 = false)
{
    var was_platform = is_platform_mode;
    drop_off_platform_mode(true);
    restore_default_behavior();
    restore_animation();
    target = arg0;
    attacktimer = 0;
    is_quick_attack = arg2;
    if (was_platform)
    {
        attacking = 0.5;
    }
    else
    {
        state = 1;
        restore_animation();
        caterpillarmode = 0;
        attacking = 1;
    }
};

character = 1;
name = "???";
forced_anim = false;
anim_delayer = -4;
sprite_offset_x = 0;
sprite_offset_y = 0;

force_animation = function(arg0, arg1, arg2 = false)
{
    with (anim_delayer)
    {
        instance_destroy();
    }
    forced_anim = true;
    if (arg0 == 7808 || arg0 == 2415 || arg0 == 7396)
    {
        arg2 = true;
    }
    if (arg2)
    {
        sprite_offset_x = 0;
        sprite_offset_y = 0;
    }
    else
    {
        sprite_offset_x = (0.5 * sprite_get_width(arg0)) - sprite_get_xoffset(arg0);
        sprite_offset_y = ((-0.5 * sprite_get_height(spr_idle)) + sprite_get_height(arg0)) - sprite_get_yoffset(arg0);
    }
    sprite_index = arg0;
    paused_spr = arg0;
    if (is_numeric(arg1) || arg1 == undefined)
    {
        if (arg1 > 0)
        {
            anim_delayer = scr_delay_var("forced_anim", false, arg1);
        }
    }
    else
    {
        anim_delayer = scr_delay_var_until("forced_anim", false, arg1);
    }
};

restore_animation = function()
{
    with (anim_delayer)
    {
        instance_destroy();
    }
    sprite_offset_x = 0;
    sprite_offset_y = 0;
    forced_anim = false;
};

custom_state = undefined;
custom_waiter = undefined;
long = false;

custom_behaviour = function(arg0, arg1, arg2)
{
    restore_default_behavior(true);
    caterpillarmode = false;
    custom_state = arg0;
    state = -1;
    if (arg2 == undefined)
    {
        arg2 = restore_default_behavior;
    }
    if (is_numeric(arg1) || arg1 == undefined)
    {
        if (arg1 > 0)
        {
            custom_waiter = scr_script_delayed(arg2, arg1);
        }
    }
    else
    {
        custom_waiter = scr_script_delayed_until(arg2, arg1);
    }
};

restore_default_behavior = function(arg0)
{
    with (custom_waiter)
    {
        instance_destroy();
    }
    long = false;
    wallcollision = true;
    back_marker_scale = 1;
    platform_mode_target = -4;
    attacking = 0;
    is_platform_mode = 0;
    if (image_speed == 0)
    {
        image_speed = 0.25;
    }
    important = false;
    grounded = check_if_above_ground() != -4;
    groundedprev = grounded;
    physics = true;
    if (sprite_index == spr_plat_ralsei_hanging_torso)
    {
        sprite_index = spr_plat_ralsei_hanging;
    }
    platform.mask_index = spr_plat_blankmask;
    entity_gravity = default_gravity;
    if (paused)
    {
        paused_grav = default_gravity;
    }
    else
    {
        gravity = default_gravity;
    }
    scr_plat_depthcast();
    jumpsquat = 0;
    jumping = 0;
    state = 0;
    platform_valid = false;
    if (!arg0)
    {
        init_caterpillarmode();
        restore_animation();
    }
};

axethrow_cooldown = 45;
outlinecolor = 16711935;

get_preset = function(arg0)
{
    character = arg0;
    switch (arg0)
    {
        case 1:
            caterpillardist = 6;
            default_dist = caterpillardist;
            name = "susie";
            spr_idle = 8042;
            spr_run = 1190;
            spr_halt = 8242;
            spr_turn = 1607;
            spr_jump = 7013;
            spr_fall = 6004;
            spr_land = 1185;
            spr_climb = 3152;
            if (scr_use_unhappy_sprites())
            {
                spr_idle = 4946;
                spr_run = 2119;
                spr_halt = 7637;
            }
            mask_index = spr_idle;
            sprite_index = spr_idle;
            set_bbox_relative();
            can_catch_kris = 1;
            jumpheight = 21;
            scr_plat_set_group(UnknownEnum.Value_11, false);
            break;
        case 2:
            caterpillardist = 12;
            default_dist = caterpillardist;
            axethrow = 0;
            name = "ralsei";
            outlinecolor = 65280;
            spr_idle = 4371;
            spr_run = 3895;
            spr_halt = 4781;
            spr_turn = 8354;
            spr_jump = 7433;
            spr_fall = 6461;
            spr_land = 6347;
            spr_climb = 5760;
            if (scr_use_unhappy_sprites())
            {
                spr_idle = 6144;
            }
            mask_index = spr_idle;
            sprite_index = spr_idle;
            if (scr_flag_get(1311) == 1)
            {
                spr_run = 6954;
                spr_halt = 5542;
                spr_turn = 7549;
                spr_jump = 316;
                spr_fall = 5569;
                spr_land = 1575;
                spr_climb = 5162;
            }
            set_bbox_relative();
            can_catch_kris = 0;
            jumpheight = 20.5;
            entity_gravity = 1.1;
            default_gravity = entity_gravity;
            hspeed_max = 8;
            depth += 50;
            scr_plat_set_group(UnknownEnum.Value_10, false);
            break;
    }
};

get_preset(1);
scr_get_inputs(false);
release_jump = false;
state = 0;
followtarget = "__nothing";
followxoffset = 0;
followyoffset = 0;
is_platform_mode = false;
platform = instance_create(-999, 0, obj_plat_movingplat);
platform.image_xscale = 2;
platform.movetype = -1;
platform.visible = false;
platform.image_yscale = 2;
platform_mode_target = -4;
platform_mode_offset = [0, 0];
platform_mode_timer = 0;
reachedtarget = false;
custom_platform_mode = -4;

turn_into_platform = function(arg0, arg1, arg2, arg3 = -4)
{
    restore_default_behavior();
    wallcollision = 0;
    offscreen_despawn_cooldown = 100;
    is_platform_mode = 1;
    platform_valid = false;
    long = instance_exists(obj_dw_fcastle_top_ascent) && global.flag[1903];
    player_stood_on_ralsei_recently = false;
    custom_platform_mode = arg3;
    hspeed = 0;
    image_alpha = 1;
    state = 1;
    gravity = entity_gravity;
    caterpillarmode = 0;
    forced_anim = false;
    caterpillarmode = false;
    platform_mode_timer = 0;
    platform_mode_target = arg0;
    platform_mode_offset[0] = arg1;
    platform_mode_offset[1] = arg2;
    force_jump();
    physics = false;
    land_anim = false;
    vspeed = 1;
    jump_coyote_time = 5;
};

onscreen_tolerance = function(arg0, arg1 = true)
{
    with (obj_plat_camera)
    {
        if ((other.x + arg0) <= (x - 320))
        {
            return false;
        }
        if ((other.x - arg0) >= (x + 320))
        {
            return false;
        }
        if (arg1)
        {
            if ((other.y + arg0) <= (y - 240))
            {
                return false;
            }
            if ((other.y - arg0) >= (y + 240))
            {
                return false;
            }
        }
    }
    return true;
};

drop_off_platform_mode = function(arg0)
{
    if (is_platform_mode || attacking || !onscreen_tolerance(120))
    {
        back_marker_scale = 1;
        image_alpha = 1;
        attacking = 0;
        player_stood_on_ralsei_recently = true;
        long = false;
        act_busy = false;
        is_platform_mode = 0;
        platform_valid = false;
        important = false;
        physics = true;
        entity_gravity = default_gravity;
        restore_default_behavior();
        gravity = entity_gravity;
        image_xscale = sign(image_xscale) * 2 * scale_multiplier;
        caterpillarmode = true;
        forced_anim = false;
        if (arg0)
        {
            image_alpha = 0;
            scr_lerpvar("image_alpha", -1, 1, 30);
            for (var i = 0; i < (position_history_length + 1); i += 1)
            {
                remx[i] = parent.x;
                remy[i] = parent.y;
                remspd[i] = parent.speed;
                remdir[i] = parent.direction;
                remgnd[i] = parent.ground;
            }
        }
    }
};

set_sprite_simple = function(arg0)
{
    sprite_index = arg0;
};

draw_back_marker = function()
{
    draw_sprite_ext(spr_plat_ralsei_hanging_back_loop, 0, x, y - 20, image_xscale * scale_multiplier, image_yscale * 20, 0, image_blend, image_alpha);
    draw_sprite_ext(spr_plat_ralsei_hanging_back, image_index, x, y, image_xscale * scale_multiplier, 2, 0, image_blend, image_alpha);
};

defaultdepth = depth;
highlighted = false;
back_marker = -4;
back_marker_scale = 1;
image_speed = 0.25;
platform_valid = false;

deactivate = function()
{
    restore_default_behavior();
    restore_animation();
    with (back_marker)
    {
        instance_destroy();
    }
    instance_destroy(self);
};

free_will = false;
free_will_target = -4;
free_will_target_lerp = 0;
free_will_target_x = 0;
free_will_target_y = 0;
offscreen_despawn_cooldown = 0;
__splats = false;
__splat_duration = 60;

ralsei_fall_down = function(arg0)
{
    if (name != "ralsei")
    {
        exit;
    }
    if (is_platform_mode < 3)
    {
        drop_off_platform_mode(true);
        exit;
    }
    back_marker_scale = 1;
    long = false;
    force_animation(8083, undefined, true);
    __splats = arg0 > 0;
    __splat_duration = arg0;
    custom_behaviour(function()
    {
        hspeed = 0;
        vspeed = 0;
        platform_valid = true;
    }, 15, function()
    {
        custom_behaviour(function()
        {
            platform_valid = true;
            vspeed = min(vspeed + 0.5, 15);
        }, function()
        {
            return grounded && instance_exists(ground);
        }, __splats ? function()
        {
            snd_play(snd_splat);
            hspeed = 0;
            vspeed = 0;
            force_animation(4429, undefined, true);
            var _cooldown_text = stringsetloc("SPLAT", "obj_plat_follower_slash_Create_0_gml_579_0");
            scr_plat_set_cooldown(_cooldown_text, __splat_duration);
            custom_behaviour(function()
            {
                platform_valid = false;
                apply_ground_difference();
            }, __splat_duration);
        } : function()
        {
            hspeed = 0;
            vspeed = 0;
            force_animation(1827, undefined, true);
            custom_behaviour(function()
            {
                platform_valid = true;
                act_busy = false;
                apply_ground_difference();
            }, -1);
        });
    });
};

_susie_attack_cooldown_text = stringsetloc("RECHARGE", "obj_plat_follower_slash_Create_0_gml_604_0");

apply_ground_difference = function()
{
    if (instance_exists(ground))
    {
        grounded = 1;
        if (ground.moving_platform || ground.rideable)
        {
            if (!instance_place(x + ground.dif_x, y + ground.dif_y, obj_plat_block))
            {
                x += ground.dif_x;
                y += ground.dif_y;
                for (var i = position_history_length; i >= 0; i -= 1)
                {
                    remx[i] += ground.dif_x;
                    remy[i] += ground.dif_y;
                }
            }
        }
    }
};

hspeedprev = 0;

enum UnknownEnum
{
    Value_10 = 10,
    Value_11
}
