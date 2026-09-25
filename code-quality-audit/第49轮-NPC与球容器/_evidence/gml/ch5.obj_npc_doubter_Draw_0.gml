blend = c_white;
if (myinteract != 3)
{
    if (image_index == 0)
    {
        siner = 0;
        draw_sprite_ext(spr_doubter_body, image_index, x, y, image_xscale, image_yscale, 0, c_white, 1);
        draw_sprite_ext(spr_doubter_face, image_index, x, y, image_xscale, image_yscale, 0, blend, 1);
    }
    if (image_index == 1)
    {
        siner++;
        draw_sprite_ext(spr_doubter_body, image_index, x, y, image_xscale, image_yscale, 0, c_white, 1);
        draw_sprite_ext(spr_doubter_face, image_index, x + sin(siner), y, image_xscale, image_yscale, 0, c_white, 1);
    }
}
if (myinteract == 3)
{
    siner += 1;
    if (image_index == 0)
    {
        draw_sprite_ext(spr_doubter_body, image_index, x, y - (sin(siner / 4) * 3), image_xscale, image_yscale + (sin(siner / 4) * 0.1), 0, c_white, 1);
        draw_sprite_ext(spr_doubter_face, image_index, x + (sin(siner / 8) * 4), y + (sin(siner / 4) * 2), image_xscale, image_yscale, 0, blend, 1);
    }
    if (image_index == 1)
    {
        draw_sprite_ext(spr_doubter_body, image_index, x, y, image_xscale, image_yscale, 0, c_white, 1);
        draw_sprite_ext(spr_doubter_face, image_index, x + sin(siner), y, image_xscale, image_yscale, 0, c_white, 1);
    }
}
