if (forced_anim)
{
    exit;
}
if (turn_anim && sprite_index == spr_turn)
{
    sprite_index = spr_idle;
}
turn_anim = false;
if (runstop_anim && sprite_index == spr_halt)
{
    sprite_index = spr_idle;
}
runstop_anim = false;
if (attacking && sprite_index == spr_susiep_attack)
{
    sprite_index = spr_idle;
}
if (land_anim)
{
    sprite_index = spr_idle;
}
land_anim = false;
if (kris_throw_state >= 4)
{
    kris_throw_state = 0;
    kris_throw_wait = 60;
    throwing_kris = false;
    catch_waiting = false;
    sprite_index = spr_jump;
    vspeed = -17.5;
    snd_play_pitch(snd_smallswing, 1.5);
}
