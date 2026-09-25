if (con == 0)
{
    con = 10;
    _alt++;
    _marker.image_index = 1;
    scr_lerp_var_instance(_marker, "x", _marker.x, _marker.x + _direction, _speed);
    scr_delay_var("con", 20, _speed + 1);
}
if (con == 20)
{
    con = 21;
    _marker.image_index = 0;
    if (_marker.x < (_marker.xstart - _distance) || _marker.x >= (_marker.xstart + _distance))
    {
        scr_delay_var("con", 30, _speed + 15);
    }
    else
    {
        scr_delay_var("con", 0, _speed + 15);
    }
}
if (con == 30)
{
    con = 31;
    _alt = 0;
    _marker.image_xscale *= -1;
    _direction *= -1;
    scr_delay_var("con", 0, _speed + 15);
}
