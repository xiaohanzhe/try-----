if (con < 0)
{
    exit;
}
if (con == 10 && !d_ex())
{
    con = 20;
    global.interact = 1;
    global.msc = -99;
    global.choice = -1;
    global.choicemsg[0] = stringsetloc("#What#happened", "obj_npc_castle_cafe_slash_Step_0_gml_14_0");
    global.choicemsg[1] = stringsetloc("#Recommended#foods", "obj_npc_castle_cafe_slash_Step_0_gml_15_0");
    global.choicemsg[2] = stringsetloc("Recruits", "obj_npc_castle_cafe_slash_Step_0_gml_16_0");
    global.choicemsg[3] = stringsetloc("Nothing", "obj_npc_castle_cafe_slash_Step_0_gml_17_0");
    if (scr_flag_get(1456) == 0)
    {
        scr_flag_set(1456, 1);
        scr_speaker("rouxls");
        msgsetloc(0, "\\E4* I'm in Chargeth nowe./", "obj_npc_castle_cafe_slash_Step_0_gml_24_0");
        msgnextloc("\\E3* It's Goode./", "obj_npc_castle_cafe_slash_Step_0_gml_25_0");
    }
    else
    {
        scr_speaker("rouxls");
        msgsetloc(0, "\\E6* What?/", "obj_npc_castle_cafe_slash_Step_0_gml_29_0");
    }
    msgnext("\\C4 ");
    d_make();
}
if (con == 20 && global.choice != -1)
{
    con = -1;
    k_d(3);
    if (global.choice == 0)
    {
        con = 100;
        if (scr_flag_get(1457) == 0)
        {
            scr_flag_set(1457, 1);
            scr_speaker("rouxls");
            msgsetloc(0, "\\E0* So^1, Sir Swatch steppedeth out for a moment.../", "obj_npc_castle_cafe_slash_Step_0_gml_50_0");
            msgnextloc("\\E3* And^1, so I..^1. perhapseth..^1. as a Favore.../", "obj_npc_castle_cafe_slash_Step_0_gml_51_0");
            msgnextloc("\\E4* Takingeth over for him^1, while he was Gone.../", "obj_npc_castle_cafe_slash_Step_0_gml_52_0");
            msgnextloc("\\E3* And while he was Not Noticinge me doingeth so.../", "obj_npc_castle_cafe_slash_Step_0_gml_53_0");
            msgnextloc("\\E1* .../", "obj_npc_castle_cafe_slash_Step_0_gml_54_0");
            msgnextloc("\\E6* .../", "obj_npc_castle_cafe_slash_Step_0_gml_55_0");
            msgnextloc("\\E1* Okay^1, guyse^1. I will be-eth \"Reale\" withst you Here./", "obj_npc_castle_cafe_slash_Step_0_gml_56_0");
            msgnextloc("\\E6* Any Recruitse you made at yon Churche.../", "obj_npc_castle_cafe_slash_Step_0_gml_57_0");
            msgnextloc("\\E4* They Basicallye haven'tst seen anything besides This before./", "obj_npc_castle_cafe_slash_Step_0_gml_58_0");
            msgnextloc("\\E3* To them^1, this is Normale^1. So it's all coole./", "obj_npc_castle_cafe_slash_Step_0_gml_59_0");
            msgnextloc("\\E6* No one will findeth out^1. No one notices..^1. everyone loveths me.../", "obj_npc_castle_cafe_slash_Step_0_gml_60_0");
            msgnextloc("\\E5* Just..^1. helpeth me cleane up before Swatch gets back./%", "obj_npc_castle_cafe_slash_Step_0_gml_61_0");
        }
        else
        {
            scr_speaker("rouxls");
            msgsetloc(0, "\\E5* Oh^1, something HAPPENEDE^1? No^1, no^1, NOTHINGE happeneds?/", "obj_npc_castle_cafe_slash_Step_0_gml_65_0");
            msgnextloc("\\E3* Righte^1? Winke winke^1, nodge nodge?/", "obj_npc_castle_cafe_slash_Step_0_gml_66_0");
            msgnextloc("\\E2* None of the recruits will suspecteth a thinge...?/%", "obj_npc_castle_cafe_slash_Step_0_gml_67_0");
        }
        d_make();
    }
    else if (global.choice == 1)
    {
        con = 100;
        var party_count = 0;
        var party = [];
        party[party_count] = "kris";
        if (scr_havechar(2))
        {
            party_count++;
            party[party_count] = "susie";
        }
        if (scr_havechar(3))
        {
            party_count++;
            party[party_count] = "ralsei";
        }
        if (scr_havechar(4))
        {
            party_count++;
            party[party_count] = "noelle";
        }
        randomize();
        var response = party[irandom(party_count)];
        if (response == "kris")
        {
            scr_speaker("rouxls");
            msgsetloc(0, "\\E3* For yon blue person^1, I recommendeth..^1. the worm Soupe./%", "obj_npc_castle_cafe_slash_Step_0_gml_105_0");
        }
        else if (response == "susie")
        {
            scr_speaker("rouxls");
            msgsetloc(0, "\\E3* For yon purpleth girl^1, I recommendeth..^1. using Detergente./%", "obj_npc_castle_cafe_slash_Step_0_gml_109_0");
        }
        else if (response == "ralsei")
        {
            scr_speaker("rouxls");
            msgsetloc(0, "\\E6* For yon green bimbitoe^1, I recommendeth..^1. a more than $5 haircut./%", "obj_npc_castle_cafe_slash_Step_0_gml_113_0");
        }
        else if (response == "noelle")
        {
            scr_speaker("rouxls");
            msgsetloc(0, "\\E6* For yon festive ewe^1, I recommendeth..^1. helpingeth me fix the ice cream machine./%", "obj_npc_castle_cafe_slash_Step_0_gml_117_0");
        }
        d_make();
    }
    else if (global.choice == 2)
    {
        con = 30;
        with (instance_create(0, 0, obj_fusionmenu))
        {
            type = 3;
        }
    }
    else
    {
        con = 100;
    }
}
if (con == 30 && !i_ex(obj_fusionmenu))
{
    con = 100;
}
if (con == 50 && !d_ex())
{
    con = 100;
    global.interact = 1;
    scr_speaker("no_name");
    msgsetloc(0, "* (It's an ice cream machine^1. It's broken.)/", "obj_npc_castle_cafe_slash_Step_0_gml_145_0");
    scr_anyface_next("rouxls", "6");
    msgnextloc("\\E6* It camest like that./%", "obj_npc_castle_cafe_slash_Step_0_gml_147_0");
    d_make();
}
if (con == 100 && !d_ex())
{
    con = -1;
    npc_animate = false;
    global.interact = 0;
}
if (npc_animate)
{
    if (i_ex(obj_writer))
    {
        if (obj_writer.halt >= 1)
        {
            with (npc_animate_target)
            {
                image_speed = 0;
                image_index = 0;
            }
        }
        else
        {
            with (npc_animate_target)
            {
                image_speed = 0.2;
            }
        }
    }
}
