if (physics)
{
    if (grounded)
    {
        scr_plat_snap_to_ground();
    }
}
if (instance_exists(obj_plat_player) && !obj_plat_player.targetmode)
{
    if (platform_mode_target != -4)
    {
        depth = other.platform_mode_target.depth - 3;
        with (back_marker)
        {
            depth = other.platform_mode_target.depth - 2;
        }
    }
}
else
{
    with (back_marker)
    {
        depth = other.depth + 1;
    }
}
if (forced_anim)
{
    if (instance_exists(obj_plat_player) && !obj_plat_player.targetmode)
    {
        if (is_platform_mode == 3 && image_index > 0)
        {
            depth = obj_plat_player.depth - 1;
        }
    }
}
