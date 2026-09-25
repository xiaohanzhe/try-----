if (!_active)
{
    exit;
}
gpu_set_fog(true, c_black, 0, 0);
draw_sprite_ext(spr_asgored, 0, (camerax() + (view_wport[0] / 2)) - 32, (cameray() + (view_hport[0] / 2)) - 70, 2, 2, 0, c_white, _alpha);
gpu_set_fog(false, c_white, 0, 0);
gpu_set_fog(true, c_red, 0, 0);
draw_sprite_ext(spr_asgored, 0, (camerax() + (view_wport[0] / 2)) - 32, (cameray() + (view_hport[0] / 2)) - 70, 2, 2, 0, c_white, _alpha);
gpu_set_fog(false, c_white, 0, 0);
