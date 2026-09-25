if (parent == -4 && instance_exists(obj_plat_player))
{
    parent = obj_plat_player;
    for (var i = 0; i < (position_history_length + 1); i += 1)
    {
        remx[i] = parent.x;
        remy[i] = parent.bbox_bottom - bbox_bottom_r - 2;
        remspd[i] = parent.speed;
        remdir[i] = parent.direction;
        remgnd[i] = -4;
    }
}
if (paused || custom_paused)
{
    scr_pause_alarms();
    exit;
}
offscreen_despawn_cooldown--;
var pj = press_jump;
key_left = false;
key_right = false;
key_up = false;
key_down = false;
press_left = false;
press_right = false;
press_up = false;
press_down = false;
vinput = 0;
hinput = 0;
press_jump = false;
key_jump = false;
press_attack = false;
key_attack = false;
key_left = key_left_override;
key_right = key_right_override;
press_jump = pj;
onscreen = true;
var _early_cancel = false;
var _FollowObject = -4;
if (state == 0)
{
    _FollowObject = instance_nearest(x, y, obj_plat_player);
}
else if (state == 1)
{
    var _next_marker = -4;
    var _follow = -4;
    if (is_string(followtarget))
    {
        with (obj_plat_movemarker)
        {
            if (extflag == other.followtarget)
            {
                _follow = id;
                _next_marker = next_extflag;
                break;
            }
        }
    }
    else if (instance_exists(followtarget))
    {
        _follow = followtarget;
        if (followtarget.object_index == obj_plat_movemarker)
        {
            _next_marker = followtarget.next_extflag;
        }
    }
    with (_follow)
    {
        var _dist = point_distance(x, y, other.x + other.followxoffset, other.y);
        if (_dist <= 60 && _next_marker != "" && _next_marker != -4)
        {
            other.followtarget = _next_marker;
        }
    }
    _FollowObject = _follow;
}
else if (state == 2)
{
    if (x < (obj_plat_player.x + 80) && x > (obj_plat_player.x - 80))
    {
        var sgn = sign(image_xscale);
        if (x < obj_plat_player.x)
        {
            key_left = true;
            sgn = -1;
        }
        else
        {
            key_right = true;
            sgn = 1;
        }
        var xx = 0;
        if (sgn == -1)
        {
            xx = bbox_left - 4;
        }
        else
        {
            xx = bbox_right + 4;
        }
        if (!collision_line(xx, y, xx, bbox_bottom + 10, obj_plat_floor, 0, 0))
        {
            _early_cancel = true;
        }
        if (wallhitspd != 0)
        {
            _early_cancel = true;
        }
        if (_early_cancel)
        {
            key_left = false;
            key_right = false;
            state = 1;
        }
    }
}
else if (state == -1)
{
    if (custom_state != undefined)
    {
        custom_state();
    }
}
if (i_ex(_FollowObject))
{
    var _followX = _FollowObject.x + followxoffset;
    var _followY = _FollowObject.y;
    var pause_AI = false;
    if (!pause_AI && !caterpillarmode)
    {
        if (vspeed > -3 && !grounded)
        {
            var _goto_last_ground = true;
            var _ground = check_if_above_ground();
            if (instance_exists(_ground))
            {
                _goto_last_ground = false;
            }
            if (_goto_last_ground)
            {
                _followX = grounded_lastX;
                if (_FollowObject == 910)
                {
                    with (obj_plat_player)
                    {
                        if (grounded)
                        {
                            _followX = x;
                        }
                    }
                }
            }
        }
        var _follow_dist = 90;
        if (character == 2)
        {
            _follow_dist += 40;
        }
        if (y > _followY)
        {
            _follow_dist = 60;
        }
        if (!grounded)
        {
            _follow_dist = 20;
        }
        if (state == 1)
        {
            _follow_dist = min(10, _follow_dist);
        }
        if (instance_exists(obj_plat_player))
        {
            if (instance_exists(obj_plat_player.mount))
            {
                _follow_dist = 10;
                _followX = obj_plat_player.x;
                press_jump = true;
            }
        }
        var _keepmoving = 0;
        if (x > (_followX + _follow_dist))
        {
            key_left = true;
        }
        else
        {
            _keepmoving++;
        }
        if (x < (_followX - _follow_dist))
        {
            key_right = true;
        }
        else
        {
            _keepmoving++;
        }
        if (state == 0 && !attacking)
        {
            if (y > (_followY + 120) && press_jump == true)
            {
                if (y > (_followY + 40) && (!variable_instance_exists(_FollowObject.id, "grounded") || _FollowObject.grounded))
                {
                    press_jump = true;
                }
            }
            if (instance_place(x - 4, y - 2, obj_plat_block) && key_left)
            {
                press_jump = true;
            }
            if (instance_place(x + 4, y - 2, obj_plat_block) && key_right)
            {
                press_jump = true;
            }
        }
        if (state == 1)
        {
            if (grounded)
            {
                if (y > (_followY + 40) && abs(_followX - x) <= 80)
                {
                    press_jump = true;
                }
            }
        }
        if (grounded)
        {
            if (hspeed > 0 && !collision_line(x, y, x, bbox_bottom + 10, obj_plat_floor, 0, 0) && !collision_line(x, y, x, bbox_bottom + 10, obj_plat_player.ground, 0, 0))
            {
                press_jump = true;
            }
            if (hspeed < 0 && !collision_line(x, y, x, bbox_bottom + 10, obj_plat_floor, 0, 0) && !collision_line(x, y, x, bbox_bottom + 10, obj_plat_player.ground, 0, 0))
            {
                press_jump = true;
            }
        }
        var _cue = instance_place(x, y, obj_plat_followercue);
        if (!scr_onscreen(id))
        {
            _cue = -4;
        }
        if (_cue != -4)
        {
            switch (_cue.dothing)
            {
                case UnknownEnum.Value_0:
                    press_jump = true;
                    break;
                case UnknownEnum.Value_1:
                    if (grounded)
                    {
                        if (hspeed > 0 && !instance_place(x + 20, y + 2, obj_plat_floor))
                        {
                            press_jump = true;
                        }
                        if (hspeed < 0 && !instance_place(x - 20, y + 2, obj_plat_floor))
                        {
                            press_jump = true;
                        }
                    }
                    break;
            }
        }
        release_jump = 0;
        if (!climbing && y < _FollowObject.y && vspeed < 0)
        {
            release_jump = 1;
        }
        if (scr_onscreen(id) == false && climbing)
        {
            press_jump = true;
            key_up = false;
            key_down = false;
        }
    }
    if (fallen_in_pit)
    {
        scr_get_inputs(false);
    }
}
var _hspeedmax = hspeed_max;
var _dashspeed = 18;
if (abs(hspeed) < abs(hspeed_max) && !hitstop)
{
    dashing = false;
}
var _gate = -4;
if (_gate != -4 && !dashing && !attacking && !climbing && (key_left || key_right))
{
    if (_gate.usable)
    {
        dashing = true;
        if (hspeed < 0)
        {
            hspeed = -_dashspeed;
        }
        if (hspeed > 0)
        {
            hspeed = _dashspeed;
        }
    }
}
if (dashing)
{
    _hspeedmax = _dashspeed;
}
if (dashing)
{
    if (!variable_instance_exists(id, "afterimagetimer"))
    {
        afterimagetimer = 4;
    }
    if (afterimagetimer == 0)
    {
        scr_afterimage();
        afterimagetimer = 4;
    }
    if (afterimagetimer > 0)
    {
        afterimagetimer--;
    }
}
var _haccel = ground_accel;
if (!grounded)
{
    _haccel = air_accel;
}
if (climbing)
{
    _haccel = 0;
}
if (attacking < 2 && !climbing)
{
    if (key_left)
    {
        hspeed -= _haccel;
        if (autorun)
        {
            _hspeedmax = 18;
        }
        if (hspeed <= -_hspeedmax)
        {
            hspeed = -_hspeedmax;
        }
        if (instance_place(x - 1, y, obj_plat_block))
        {
            hspeed = 0;
            x = xprevious;
        }
    }
    if (key_right)
    {
        hspeed += _haccel;
        if (autorun)
        {
            _hspeedmax = 3;
        }
        if (hspeed >= _hspeedmax)
        {
            hspeed = _hspeedmax;
        }
        if (instance_place(x + 1, y, obj_plat_block))
        {
            hspeed = 0;
            x = xprevious;
        }
    }
}
var _hdecel = 1;
if (grounded)
{
    _hdecel = ground_decel;
}
else
{
    _hdecel = air_decel;
}
if (respawn_leap)
{
    _hdecel = 1;
}
if (climbing)
{
    _hdecel = 0;
}
if ((!key_left && !key_right) || (key_left && key_right) || attacking > 2)
{
    hspeed *= _hdecel;
}
if (grounded || climbing)
{
    jump_coyote_time = jump_coyote_time_max;
    jumping = 0;
}
else if (jump_coyote_time > 0)
{
    jump_coyote_time--;
}
if ((press_jump || jumpsquat > 0) && (climbing || grounded || (jump_coyote_time > 0 && vspeed > -1)) && !attacking && !instance_place(x, y - 4, obj_plat_block))
{
    jumpsquat = max(jumpsquat + 1, 1);
    press_jump = false;
    if (jumpsquat > jumpsquat_max)
    {
        jumpsquat = 0;
        climbing = false;
        vspeed = -jumpheight;
        y -= 1;
        jumping = 1;
    }
}
else
{
    jumpsquat = 0;
}
if (vspeed < 0 && release_jump && jumping)
{
    vspeed *= 0.8;
    jumping = 0;
}
if (vspeed > 0)
{
    jumping = 0;
}
scr_get_vxy(0);
if (!fallen_in_pit && y > (vy + vh + (sprite_height * 0.5)) && respawn_leap_enabled)
{
    fallen_in_pit = true;
    snd_play(snd_firework_send);
    respawn_leap = false;
    physics = false;
    vspeed = 0;
    hspeed = 0;
    gravity = 0;
    respawn_leap_wait = 15;
    checkpoint_x = clamp(obj_plat_player.x - (80 * sign(obj_plat_player.image_xscale)), vx + 80, (vx + vw) - 80);
    scr_lerpvar_instance(id, "x", id.x, checkpoint_x, respawn_leap_wait, 2, "out");
}
if (fallen_in_pit)
{
    if (!respawn_leap)
    {
        respawn_leap_wait--;
        vspeed = 0;
        y = vy + vh + (sprite_height * 2);
    }
    if (respawn_leap_wait <= 0 && !respawn_leap)
    {
        x = checkpoint_x;
        snd_play(snd_jump);
        y = vy + vh;
        respawn_leap = true;
        vspeed = -33;
        hspeed = 0;
        gravity = entity_gravity;
        gravity_direction = 270;
    }
    if (respawn_leap)
    {
        if (x != clamp(x, vx + 80, (vx + vw) - 80))
        {
            hspeed = 0;
            x = clamp(x, vx + 80, (vx + vw) - 80);
        }
        if (vspeed > 0 && scr_onscreen(id))
        {
            if (!instance_place(x, y, obj_plat_block) && y < ((vy + vh) - 40) && x == clamp(x, vx + sprite_width, (vx + vw) - sprite_width))
            {
                fallen_in_pit = false;
                respawn_leap = false;
                physics = true;
            }
        }
    }
}
event_inherited();
if (caterpillarmode && instance_exists(parent))
{
    ground = remgnd[caterpillardist];
    var _force_follow = 0;
    var _ground = collision_line(x, bbox_bottom - 2, x, bbox_bottom + 2, obj_plat_floor, 0, 0);
    if (i_ex(_ground))
    {
        ground = _ground;
    }
    else
    {
        _force_follow = 1;
    }
    var _wall = collision_line(x, bbox_top, x, y, obj_plat_block, 0, 0);
    if (i_ex(_wall))
    {
        _force_follow = 1;
    }
    if (offscreen_despawn_cooldown > 0)
    {
        _force_follow = 0;
    }
    remgnd[caterpillardist] = ground;
    apply_ground_difference();
    parent_dist = point_distance(x, y, parent.x, parent.y);
    if (_force_follow || !grounded || !parent.grounded || round(parent.speed) > 2 || parent_dist >= 200)
    {
        for (var i = position_history_length; i > 0; i -= 1)
        {
            remx[i] = remx[i - 1];
            remy[i] = remy[i - 1];
            remspd[i] = remspd[i - 1];
            remdir[i] = remdir[i - 1];
            remgnd[i] = remgnd[i - 1];
        }
        remx[0] = parent.x;
        remy[0] = parent.bbox_bottom - bbox_bottom_r;
        remspd[0] = parent.speed;
        remdir[0] = parent.direction;
        remgnd[0] = parent.ground;
    }
    var _x = remx[caterpillardist];
    var _y = remy[caterpillardist];
    var _dist = point_distance(x, y, _x, _y);
    move_towards_point(_x, _y, _dist * 0.5);
    gravity = 0;
    if (grounded && !turn_anim && sign(hspeed) != sign(image_xscale) && abs(hspeed) > 0)
    {
        turn_anim = true;
        sprite_index = spr_turn;
        image_speed = 0.5;
        image_index = 0;
    }
    if (x < _x)
    {
        image_xscale = 2 * scale_multiplier;
    }
    if (x > _x)
    {
        image_xscale = -2 * scale_multiplier;
    }
    ground = remgnd[caterpillardist];
    if (instance_exists(ground))
    {
        grounded = true;
    }
}
if (axethrow && state == 0 && !attacking)
{
    axethrow_cooldown--;
}
if (axethrow_cooldown <= 0)
{
    event_user(0);
}
if (attacking > 0)
{
    vspeed = max(vspeed, 0);
    apply_ground_difference();
    if (caterpillarmode)
    {
        attacktimer++;
        if (attacktimer >= 30)
        {
            state = 1;
            restore_animation();
            caterpillarmode = 0;
            attacking = 1;
            attacktimer = 0;
        }
    }
    else
    {
        if (is_quick_attack)
        {
            vspeed = lerp(vspeed, -gravity, min(attacktimer / 10, 1));
            hspeed = lerp(hspeed, 0, min(attacktimer / 10, 1));
        }
        if (attacking == 1)
        {
            state = 2;
            caterpillarmode = false;
            if (is_quick_attack)
            {
                attacking = 2;
                forced_anim = true;
                state = 0;
                if (target.x > x)
                {
                    image_xscale = 2 * scale_multiplier;
                }
                else
                {
                    image_xscale = -2 * scale_multiplier;
                }
                image_speed = 0.25;
                attacktimer = 0;
            }
            else if (grounded || is_quick_attack)
            {
                attacktimer++;
                var timer_max = 40;
                if (is_quick_attack)
                {
                    timer_max = 10;
                }
                if (_early_cancel || attacktimer > timer_max || !(x < (obj_plat_player.x + 80) && x > (obj_plat_player.x - 80)))
                {
                    if ((!is_quick_attack && !_early_cancel && point_distance(x, y, obj_plat_player.x, obj_plat_player.y) < 40) || !instance_exists(target))
                    {
                        attacking = 0;
                        if (!d_plat_exists(1))
                        {
                        }
                        state = 0;
                        init_caterpillarmode();
                    }
                    else
                    {
                        if (name == "susie")
                        {
                            snd_play(snd_boost);
                            if (scr_use_unhappy_sprites())
                            {
                                sprite_index = spr_plat_susie_spellready_unhappy;
                            }
                            else
                            {
                                sprite_index = spr_plat_susie_spellready;
                            }
                        }
                        else
                        {
                            snd_play(snd_spellcast);
                            sprite_index = spr_plat_ralsei_spellready;
                        }
                        attacking = 2;
                        forced_anim = true;
                        state = 0;
                        if (target.x > x)
                        {
                            image_xscale = 2 * scale_multiplier;
                        }
                        else
                        {
                            image_xscale = -2 * scale_multiplier;
                        }
                        image_speed = 0.25;
                        if (!is_quick_attack)
                        {
                            hspeed = 0;
                            vspeed = 0;
                        }
                        attacktimer = 0;
                    }
                }
            }
        }
        else if (attacking == 2)
        {
            attacktimer++;
            var t1 = 30;
            var t2 = 40;
            if (is_quick_attack)
            {
                t1 = 2;
                t2 = 6;
            }
            if (attacktimer == t1)
            {
                if (name == "susie")
                {
                    sprite_index = spr_susiep_attackready;
                    image_index = 0;
                    image_speed = 0.25;
                }
                else
                {
                    sprite_index = spr_plat_ralsei_spell;
                    image_index = 0;
                    image_speed = 0.25;
                }
            }
            if (attacktimer < t2 && (attacktimer % 3) == 0)
            {
                var col = 16711935;
                if (name == "ralsei")
                {
                    col = 65280;
                }
                with (scr_afterimage_monochrome(col, false))
                {
                    image_alpha = other.attacktimer / t2;
                    image_xscale = other.image_xscale + ((sign(other.image_xscale) * other.attacktimer) / 100);
                    image_yscale = other.image_yscale + (other.attacktimer / 100);
                    scr_lerpvar("image_xscale", image_xscale, other.image_xscale, 10);
                    scr_lerpvar("image_yscale", image_yscale, other.image_yscale, 10);
                }
            }
            if (attacktimer == t2)
            {
                if (instance_exists(target))
                {
                    if (name == "susie")
                    {
                        sprite_index = spr_susiep_attack;
                        var _dir = point_direction(x, y, target.x, target.y);
                        snd_play(snd_rudebuster_swing);
                        image_index = 0;
                        image_speed = 0.25;
                        blast = instance_create(x + 40, y + 30, obj_rudebuster_bolt_plat);
                        blast.caster = 0;
                        blast.interim_target_reached = buster_interim == 0;
                        blast.interim_target_x = buster_interim;
                        blast.explodes = buster_explode;
                        blast.target = target;
                        blast.owner = self;
                        blast.damage = 2;
                        blast.star = 0;
                    }
                    else if (name == "ralsei")
                    {
                        snd_play(snd_power);
                        with (target)
                        {
                            event_user(7);
                        }
                        var ha = instance_create(target.x, target.y, obj_healanim);
                        ha.target = target;
                    }
                }
                else
                {
                    scr_plat_set_cooldown(_susie_attack_cooldown_text, __susie_act_cooldown);
                    attacking = false;
                    attacktimer = 0;
                }
                attacktimer = 0;
                attacking = 3;
            }
        }
        else if (attacking == 3)
        {
            attacktimer += 1;
            var timermax = 22;
            if (is_quick_attack)
            {
                timermax = 10;
            }
            if (attacktimer > timermax)
            {
                forced_anim = false;
                init_caterpillarmode();
                scr_plat_set_cooldown(_susie_attack_cooldown_text, __susie_act_cooldown);
                attacking = false;
            }
        }
    }
}
if (is_platform_mode)
{
    platform_mode_timer++;
    grounded = false;
    if (is_platform_mode == 1)
    {
        ground = -4;
        image_alpha -= 0.15;
        if (platform_mode_timer == 8 && !i_ex(obj_dog_hanging))
        {
            image_alpha = 0;
            is_platform_mode = 2;
            platform_mode_timer = 0;
            x = platform_mode_target.x + platform_mode_target.hang_xoffset;
            y = (platform_mode_target.y + platform_mode_target.hang_yoffset) - 20;
            vspeed = 2;
        }
    }
    else if (is_platform_mode == 2)
    {
        x = platform_mode_target.x + platform_mode_target.hang_xoffset;
        vspeed += 0.2;
        gravity = 1;
        image_alpha += 0.1;
        if ((y + vspeed) >= (platform_mode_target.y + platform_mode_target.hang_yoffset + 60))
        {
            y = platform_mode_target.y + platform_mode_target.hang_yoffset + 60;
            platform.mask_index = platform.sprite_index;
            image_alpha = 1;
            is_platform_mode = 3;
            forced_anim = true;
            vspeed = 0;
            entity_gravity = 0;
            gravity = 0;
            snd_play(snd_grab);
            back_marker = instance_create(x, y, obj_marker_fancy);
            with (back_marker)
            {
                sprite_index = spr_plat_ralsei_hanging_back;
                scr_darksize();
                draw_func = other.draw_back_marker;
            }
        }
    }
}
if (is_platform_mode < 3)
{
    if (platform_valid)
    {
        platform.mask_index = platform.sprite_index;
    }
    else
    {
        platform.mask_index = spr_plat_blankmask;
    }
    if (i_ex(back_marker))
    {
        with (back_marker)
        {
            instance_destroy();
        }
    }
}
if (visible)
{
    if (state != 1 && offscreen_despawn_cooldown <= 0 && !onscreen_tolerance(120))
    {
        drop_off_platform_mode(true);
    }
    if (is_platform_mode > 1 && offscreen_despawn_cooldown <= 0 && !onscreen_tolerance(120, false))
    {
        drop_off_platform_mode(true);
    }
}
if (is_platform_mode > 1)
{
    physics = false;
}
else
{
    physics = true;
}
if (caterpillardist > default_dist)
{
    caterpillardist = scr_approach(caterpillardist, default_dist, 1);
}
if (free_will && !act_busy && (is_platform_mode % 3) == 0 && attacking == 0)
{
    var act_target = -4;
    var is_gonna_act;
    if (name == "ralsei")
    {
        is_gonna_act = !act_busy && (!is_platform_mode || (is_platform_mode == 3 && player_stood_on_ralsei_recently)) && !obj_plat_player.grounded && obj_plat_player.vspeed < 12;
        with (obj_plat_player)
        {
            var li = ds_list_create();
            collision_circle_list(x, y, 300, obj_plat_targethelper, false, true, li, false);
            var maxdist = 999999;
            var dist = 999999;
            for (var i = 0; i < ds_list_size(li); i++)
            {
                var v = ds_list_find_value(li, i);
                if (v.char == "ra" && variable_instance_exists(v.owner, "ralsei_ready"))
                {
                    var d = point_distance(x, y, v.x, v.y);
                    if (v.active && !v.blocked && !v.owner.ralsei_ready && d < dist && v.activetimer > 60)
                    {
                        act_target = v;
                        dist = d;
                    }
                }
            }
            if (instance_exists(act_target))
            {
                var d = point_distance(x, y, act_target.x, act_target.y);
                other.free_will_target_lerp = 1 - ((d - 200) / 100);
                if (d > 200)
                {
                    is_gonna_act = false;
                }
            }
            ds_list_destroy(li);
        }
    }
    else
    {
        is_gonna_act = !act_busy && attacking == 0 && obj_plat_player.vspeed > -30;
        with (obj_plat_player)
        {
            var vradius = 160;
            var hradius = 260;
            var arrow_margin_h = 100;
            var arrow_margin_v = 40;
            var li = ds_list_create();
            collision_rectangle_list(x - hradius - arrow_margin_h, y - vradius - arrow_margin_v, x + hradius + arrow_margin_h, y + vradius + arrow_margin_v, obj_plat_targethelper, false, true, li, false);
            var maxdist = point_distance(x, y, other.x, other.y);
            act_target = -4;
            for (var i = 0; i < ds_list_size(li); i++)
            {
                var v = ds_list_find_value(li, i);
                if (v.active && !v.blocked && v.char == "su" && v.activetimer > 20)
                {
                    act_target = v;
                }
            }
            ds_list_destroy(li);
            if (instance_exists(act_target))
            {
                other.free_will_target_lerp = 1 - ((point_distance(0, 0, act_target.x - x, (act_target.y - y) * 1.8) - 260) / 200);
                if (act_target.x < (x - hradius) || act_target.x > (x + hradius) || act_target.y < (y - vradius) || act_target.y > (y + vradius))
                {
                    is_gonna_act = false;
                }
            }
        }
    }
    if (free_will_target != act_target)
    {
        free_will_target = act_target;
        if (!is_gonna_act)
        {
            if (!instance_exists(act_target))
            {
            }
            else
            {
                free_will_target_x = act_target.x;
                free_will_target_y = act_target.y;
            }
        }
    }
    if (is_gonna_act && instance_exists(act_target))
    {
        if (scr_onscreen(self))
        {
            snd_play(snd_select);
        }
        act_target.select();
        free_will_target = -4;
    }
    if (!instance_exists(free_will_target))
    {
        free_will_target_x = x;
        free_will_target_y = y;
    }
}
if (free_will)
{
    var can_highlight = true;
    if (instance_exists(obj_dw_fcastle_top_ascent) && instance_exists(obj_plat_player))
    {
        can_highlight = y > 2960 && obj_plat_player.x < 1800;
    }
    highlighted = !act_busy && can_highlight;
    if (!highlighted)
    {
        free_will_target = -4;
    }
    important = true;
}
if (state == 1)
{
    reached_target();
}

enum UnknownEnum
{
    Value_0,
    Value_1
}
