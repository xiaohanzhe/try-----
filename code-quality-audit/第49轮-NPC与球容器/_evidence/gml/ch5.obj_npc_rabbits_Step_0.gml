_timer++;
if (_timer == 1)
{
    with (_qc_npc)
    {
        sprite_index = spr_npc_qc_side_talk;
        image_index = 0;
        image_speed = 0;
    }
    with (_inn_npc)
    {
        sprite_index = spr_npc_innkeep_side_talk;
        image_index = 0;
        image_speed = 0.2;
    }
}
if (_timer == 30)
{
    with (_qc_npc)
    {
        sprite_index = spr_npc_qc_side_talk;
        image_index = 0;
        image_speed = 0.2;
    }
    with (_inn_npc)
    {
        sprite_index = spr_npc_innkeep_side_talk;
        image_index = 1;
        image_speed = 0;
    }
}
if (_timer == 60)
{
    with (_qc_npc)
    {
        sprite_index = spr_npc_qc_side_laugh;
        image_index = 0;
        image_speed = 0.2;
    }
    with (_inn_npc)
    {
        sprite_index = spr_npc_innkeep_side_laugh;
        image_index = 0;
        image_speed = 0.2;
    }
}
if (_timer == 120)
{
    _timer = 0;
}
if (con < 0)
{
    exit;
}
if (con == 1 && global.interact == 0 && !d_ex())
{
    con = 100;
    global.interact = 1;
    scr_speaker("no_name");
    msgsetloc(0, "* ..^1. hmm^1, I do want to get some chamomile^1. And marigolds./", "obj_npc_rabbits_slash_Step_0_gml_69_0");
    msgnextloc("* Well^1, with the Mayor's discount^1, it'd be crazy not to!/", "obj_npc_rabbits_slash_Step_0_gml_70_0");
    msgnextloc("* ..^1. sure^1, but even so^1, I feel bad for him.../%", "obj_npc_rabbits_slash_Step_0_gml_71_0");
    var d = d_make();
    d.side = 0;
}
if (con == 2 && global.interact == 0 && !d_ex())
{
    con = 100;
    global.interact = 1;
    scr_speaker("no_name");
    msgsetloc(0, "* He tries to give me them for free^1, and I have to insist.../", "obj_npc_rabbits_slash_Step_0_gml_82_0");
    msgnextloc("* ..^1. some people are just hopeless^1, QC^1! You can't help them!/%", "obj_npc_rabbits_slash_Step_0_gml_83_0");
    var d = d_make();
    d.side = 0;
}
if (con == 100 && !d_ex())
{
    con = -1;
    global.interact = 0;
}
