if (!grounded)
{
    exit;
}
if (attacking)
{
    exit;
}
if (climbing)
{
    exit;
}
dbg_targets = [];
var candidates_list = ds_list_create();
scr_collision_rectangle_list(x - 300, y - 150, x + 300, y + 150, [321, 1720], candidates_list);
var t = -4;
var best_score = 0;
for (var i = 0; i < ds_list_size(candidates_list); i++)
{
    var tt = ds_list_find_value(candidates_list, i);
    var best_x = x + min(abs(tt.x - x), abs(tt.bbox_left - x), abs(tt.bbox_right - x));
    var best_y = y + min(abs(tt.y - y), abs(tt.bbox_top - y), abs(tt.bbox_bottom - y));
    var dist = abs(best_x - x);
    if (dist < 40)
    {
        continue;
    }
    var angle = point_direction(x, y, best_x, best_y);
    if ((angle % 180) > 35 && (angle % 180) < 145)
    {
        continue;
    }
    var pts = 0;
    if (angle > 90)
    {
        angle -= 180;
    }
    pts += (abs(35 - abs(angle)) / 35);
    pts += sin(degtorad(((dist - 40) / 260) * 180));
    dbg_targets[array_length(dbg_targets)] = [best_x, best_y, 32768, pts];
    if (pts > best_score)
    {
        t = tt;
        best_score = pts;
    }
}
axethrow_cooldown = 10;
if (instance_exists(t))
{
    target = t;
    if (target.x < x)
    {
        image_xscale = -abs(image_xscale);
    }
    else
    {
        image_xscale = abs(image_xscale);
    }
    attacking = true;
    attacktimer = 0;
    hspeed = 0;
    sprite_index = spr_susiep_attackready;
    snd_play_pitch(snd_wallclaw, 1.1);
    axethrow_cooldown = 140;
}
