if (i_ex(obj_herosusie))
{
    y = obj_herosusie.y;
}
if (throwcon == 1)
{
    timer++;
    if (activatethrow == 1)
    {
        throwready = 1;
        activatethrow = 0;
        angledraw = 0;
        throwcon = 2;
        kris = instance_create(kx, ky, obj_flowery_kristhrown);
        kris.speed = mypower;
        kris.mypower = mypower;
        kris.image_xscale = 2;
        kris.image_yscale = 2;
        kris.direction = angle;
        kris.image_angle = angle;
        kris.gravity = krisgrav;
    }
}
if (throwcon == 2)
{
    if (image_index >= 5)
    {
        image_speed = 0;
    }
}
