if (obj_time.left == 0)
{
    if (obj_time.right == 0)
    {
        if (obj_time.down == 0)
        {
            if (obj_time.up == 0)
            {
                moving = 0;
            }
        }
    }
}
if (global.interact > 0)
{
    moving = 0;
    movement = 0;
}
else
{
    movement = 1;
}
if (abs(xprevious - x) > 0.01 || abs(yprevious - y) > 0.01)
{
    moving = 1;
}
if (moving == 0)
{
    image_speed = 0;
    image_index = 0;
}
if (global.interact == 0)
{
    if (moving == 1)
    {
        global.encounter += 1;
    }
}
if (cutscene == 0)
{
    if (instance_exists(obj_shaker) == 0)
    {
        __view_set(0, 0, round((x - (__view_get(2, 0) / 2)) + 10));
        __view_set(1, 0, round((y - (__view_get(3, 0) / 2)) + 10));
    }
}
with (obj_backgrounder_parent)
{
    event_user(0);
}
