_x = x;
_y = y;
_alt = 0;
_direction = -8;
_speed = choose(10, 20, 24, 26, 28, 30);
_flipped = false;
_distance = choose(20, 24, 26, 28);
con = 0;
_marker = scr_dark_marker(_x, _y, spr_rouxls_worm);
with (_marker)
{
    scr_depth();
}
