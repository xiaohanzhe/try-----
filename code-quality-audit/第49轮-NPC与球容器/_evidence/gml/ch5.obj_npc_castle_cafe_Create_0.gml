con = -1;
npc_animate = false;
npc_animate_target = -4;
var bg_red = instance_create(0, 0, obj_dw_castle_town_cafe);
for (var i = 0; i < 6; i++)
{
    var _light = scr_dark_marker(178 + (i * 76), 10, spr_dw_castle_cafe_light);
    with (_light)
    {
        image_speed = 0.2;
        scr_depth();
    }
    var _beam = scr_dark_marker(178 + (i * 76), 10, spr_dw_castle_cafe_light_beam);
    with (_beam)
    {
        image_speed = 0.2;
        image_alpha = 0.5;
    }
    _beam.depth = _light.depth + 1;
}
_rouxls_npc = scr_dark_marker(760, 60, spr_rurus_idle_half);
with (_rouxls_npc)
{
    sprite_index = spr_rurus_idle_half;
    scr_depth();
}
_rouxls_readable = instance_create(_rouxls_npc.x + 10, _rouxls_npc.y + 80, obj_readable_room1);
with (_rouxls_readable)
{
    extflag = "cafe_rouxls";
    image_xscale = 3;
    image_yscale = 2;
}
var coody_marker = scr_dark_marker(360, 83, spr_npc_coody);
with (coody_marker)
{
    image_speed = 0.2;
    scr_depth();
}

show_convo = function(arg0, arg1)
{
    npc_animate = false;
    npc_animate_target = -4;
    switch (arg0)
    {
        case "cafe_rouxls":
            con = 10;
            npc_animate = true;
            npc_animate_target = _rouxls_npc;
            break;
        case "cafe_icecream":
            con = 50;
            break;
    }
};

create_worm = function(arg0, arg1, arg2)
{
    var worm = instance_create(arg0, arg1, obj_npc_castle_cafe_worm);
    if (arg2)
    {
        worm._flipped = true;
        worm._marker.image_xscale = -2;
        worm._direction *= -1;
    }
};

create_fire = function(arg0, arg1, arg2 = 98580)
{
    var fire = scr_dark_marker(arg0, arg1, spr_castle_town_cafe_fire);
    with (fire)
    {
        image_speed = 0.2;
        depth = arg2;
    }
};

create_worm(230, 130);
create_worm(210, 150, true);
create_worm(250, 170);
create_worm(320, 160, true);
create_worm(500, 130);
create_worm(540, 160, true);
create_fire(145, 4);
create_fire(222, 73);
create_fire(150, 50);
create_fire(625, 11);
create_fire(640, 67);
create_fire(550, 98);
create_fire(597, 125);
create_fire(305, 92);
create_fire(730, 120, 98440);
create_fire(861, 130, 98440);
