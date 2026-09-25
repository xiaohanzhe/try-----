con = -1;
_timer = 0;
_qc_npc = scr_marker(604, 97, spr_npc_qc_side_talk);
with (_qc_npc)
{
    depth = 970000;
    sunshadows_exclude = true;
}
_inn_npc = scr_marker(626, 96, spr_npc_innkeep_side_talk);
with (_inn_npc)
{
    depth = 970000;
    sunshadows_exclude = true;
}
var readable = instance_create(683, 130, obj_readable_room1);
with (readable)
{
    extflag = "rabbits_morning";
    image_xscale = 2;
    image_yscale = 2.5;
}

show_convo = function(arg0, arg1)
{
    switch (arg0)
    {
        case "rabbits_morning":
            con = 1;
            if (arg1 > 0)
            {
                con = 2;
            }
            break;
    }
};
