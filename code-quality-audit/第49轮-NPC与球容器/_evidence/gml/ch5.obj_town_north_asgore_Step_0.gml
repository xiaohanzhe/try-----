if (con < 0)
{
    exit;
}
if (con == 2 && global.interact == 0)
{
    con = 200;
    global.interact = 1;
    scr_speaker("asgore");
    msgsetloc(0, "\\E4* Come by with your friend later^1, Kris./", "obj_town_north_asgore_slash_Step_0_gml_12_0");
    msgnextloc("\\E6* I'll give you a free rose!/%", "obj_town_north_asgore_slash_Step_0_gml_13_0");
    var d = d_make();
    d.side = 0;
}
if (con == 5 && !d_ex() && global.interact == 0)
{
    con = 100;
    global.interact = 1;
    if (scr_flag_get(1326) == 0)
    {
        scr_flag_set(1326, 1);
    }
    scr_speaker("asgore");
    msgsetloc(0, "\\E4* Oh^1, that little action figure?/", "obj_town_north_asgore_slash_Step_0_gml_33_0");
    msgnextloc("\\E6* Just a gift from a^1, sort of^1, friend of mine./", "obj_town_north_asgore_slash_Step_0_gml_34_0");
    msgnextloc("\\E5* Isn't she cute^1? She's like the store mascot!/%", "obj_town_north_asgore_slash_Step_0_gml_35_0");
    var d = d_make();
    d.side = 0;
}
if (con == 10)
{
    con = 100;
    if (scr_flag_get(1327) == 0)
    {
        scr_flag_set(1327, 1);
    }
    scr_speaker("asgore");
    msgsetloc(0, "\\E4* Oh^1, Kris^1! What a surprise to see you with Noelle!/", "obj_town_north_asgore_slash_Step_0_gml_52_0");
    msgnextloc("\\E6* Need a chaperone for the Ferris Wheel again^1? Oh ho.../", "obj_town_north_asgore_slash_Step_0_gml_53_0");
    scr_anyface_next("noelle", 3);
    msgnextloc("\\E3* Umm^1, no^1, fahaha.../", "obj_town_north_asgore_slash_Step_0_gml_55_0");
    scr_anyface_next("asgore", 5);
    msgnextloc("\\E5* All of you^1, just take any flowers you like!/", "obj_town_north_asgore_slash_Step_0_gml_57_0");
    msgnextloc("\\E6* Any friends of our family get flowers for free!/", "obj_town_north_asgore_slash_Step_0_gml_58_0");
    scr_anyface_next("noelle", "H");
    msgnextloc("\\EH* (..^1. there's no way I'm not paying him money)/%", "obj_town_north_asgore_slash_Step_0_gml_60_0");
    d_make();
}
if (con == 11)
{
    con = 100;
    scr_speaker("asgore");
    msgsetloc(0, "\\E5* Take any flowers you like!/", "obj_town_north_asgore_slash_Step_0_gml_72_0");
    msgnextloc("\\E6* It's all free for you^1, Kris!/%", "obj_town_north_asgore_slash_Step_0_gml_73_0");
    d_make();
}
if (con == 20 && !d_ex())
{
    con = 21;
    cutscene_master = scr_cutscene_make();
    scr_maincharacters_actors();
    as = actor_count + 1;
    as_actor = instance_create(asgore_npc.x, asgore_npc.y, obj_actor);
    scr_actor_setup(as, as_actor, "asgore");
    as_actor.sprite_index = asgore_npc.sprite_index;
    as_actor.image_index = asgore_npc.image_index;
    as_actor.image_speed = asgore_npc.image_speed;
    c_var_instance(asgore_npc, "visible", 0);
    c_wait(1);
    c_sel(as);
    c_sprite(spr_npc_asgore_kneel_flowers_down);
    var kr_x_pos = 687;
    var kr_y_pos = 142;
    var kr_walktime = scr_calculate_move_distance(kr_actor.x, kr_actor.y, kr_x_pos, kr_y_pos, 3);
    c_sel(kr);
    
    var _fixposfunction = function()
    {
        x = round(x);
        y = round(y);
    };
    
    c_set_func(kr_actor, "end_step_func", _fixposfunction);
    c_walkdirect(kr_x_pos, kr_y_pos, kr_walktime);
    c_delayfacing(kr_walktime + 1, "r");
    global.interact = 1;
    global.msc = -99;
    global.choice = -1;
    global.choicemsg[0] = stringsetloc("#You tell me#every year", "obj_town_north_asgore_slash_Step_0_gml_108_0");
    global.choicemsg[1] = stringsetloc("#I didn't#know that", "obj_town_north_asgore_slash_Step_0_gml_109_0");
    global.choicemsg[2] = stringsetloc("I'm good", "obj_town_north_asgore_slash_Step_0_gml_110_0");
    global.choicemsg[3] = stringset("");
    c_msgside("top");
    c_speaker("asgore");
    c_msgsetloc(0, "\\E4* Oh^1, Kris^1! Upsy-daisy^1! Ready for today's Festival?/", "obj_town_north_asgore_slash_Step_0_gml_115_0");
    c_msgnextloc("\\E6* I have a feeling it'll be my biggest sales ever!/%", "obj_town_north_asgore_slash_Step_0_gml_116_0");
    c_talk();
    c_wait_box(1);
    c_sel(as);
    c_facing("d");
    c_wait_talk();
    c_sel(as);
    c_facing("l");
    c_wait(30);
    c_msgside("top");
    c_speaker("asgore");
    c_msgsetloc(0, "\\E2* .../", "obj_town_north_asgore_slash_Step_0_gml_131_0");
    c_msgnextloc("\\E3* Kris^1, did I ever tell you.../", "obj_town_north_asgore_slash_Step_0_gml_132_0");
    c_msgnextloc("\\E0* Back when we were just young buds.../", "obj_town_north_asgore_slash_Step_0_gml_133_0");
    c_msgnextloc("\\E6* Your mother and I were voted Festival King and Queen?/", "obj_town_north_asgore_slash_Step_0_gml_134_0");
    c_msgnext("\\C3 ");
    c_customfunc(function()
    {
        d_make();
    });
    c_waitcustom();
}
if (con == 21 && global.choice != -1 && customcon == 1)
{
    con = -1;
    customcon = 0;
    k_d(3);
    scr_flag_set(1328, global.choice + 1);
    c_waitcustom_end();
    if (global.choice == 0)
    {
        con = 25;
        c_msgside("top");
        c_speaker("asgore");
        c_msgsetloc(0, "\\E2* Oh..^1. is that so?/", "obj_town_north_asgore_slash_Step_0_gml_161_0");
        c_msgnextloc("\\E3* ..^1. well^1, it wouldn't hurt to hear it again^1, would it?/%", "obj_town_north_asgore_slash_Step_0_gml_162_0");
        c_talk_wait();
        c_waitcustom();
    }
    if (global.choice == 1)
    {
        con = 25;
        c_msgside("top");
        c_speaker("asgore");
        c_msgsetloc(0, "\\E4* Oh^1, is that so^1? Well^1, you're going to love this story.../%", "obj_town_north_asgore_slash_Step_0_gml_173_0");
        c_talk_wait();
        c_waitcustom();
    }
    if (global.choice == 2)
    {
        con = 200;
        c_msgside("top");
        c_speaker("asgore");
        c_msgsetloc(0, "\\E3* I see^1. Yes^1, I hope you're having fun!/%", "obj_town_north_asgore_slash_Step_0_gml_184_0");
        c_talk_wait();
        c_sel(as);
        c_autowalk(0);
        c_sprite(asgore_npc.sprite_index);
        c_imageindex(asgore_npc.image_index);
        c_imagespeed(asgore_npc.image_speed);
        c_var_instance(asgore_npc, "visible", 1);
        c_visible(0);
        c_pannable(1);
        c_panobj_fancy(kr_actor, 12);
        c_wait(15);
        c_pannable(0);
        c_sel(kr);
        c_facing("d");
        c_actortokris();
        c_actortocaterpillar();
        c_terminatekillactors();
    }
}
if (con == 25 && !d_ex() && customcon == 1)
{
    con = 26;
    customcon = 0;
    global.interact = 1;
    c_waitcustom_end();
    c_sel(as);
    c_facing("d");
    c_wait(15);
    c_msgside("top");
    c_speaker("asgore");
    c_msgsetloc(0, "\\EI* Oh^1, your mother.../", "obj_town_north_asgore_slash_Step_0_gml_224_0");
    c_msgnextloc("\\E3* Ever since I laid eyes on her crooked smile.../", "obj_town_north_asgore_slash_Step_0_gml_225_0");
    c_msgnextloc("\\EH* It was love at first sight!/", "obj_town_north_asgore_slash_Step_0_gml_226_0");
    c_msgnextloc("\\E5* We became so famous in the annual Nose Nuzzling Contest.../", "obj_town_north_asgore_slash_Step_0_gml_227_0");
    c_msgnextloc("\\E4* ..^1. we were voted Festival King and Queen year after year!/%", "obj_town_north_asgore_slash_Step_0_gml_228_0");
    c_talk();
    c_wait_box(2);
    c_sel(as);
    c_facing("l");
    c_wait_talk();
    c_wait(30);
    c_sel(as);
    c_facing("r");
    c_speaker("asgore");
    c_msgsetloc(0, "\\E1* Actually^1, that's why my store is called \"Flower King!\"/%", "obj_town_north_asgore_slash_Step_0_gml_243_0");
    c_talk_wait();
    c_wait(30);
    c_sel(as);
    c_facing("l");
    c_speaker("asgore");
    c_msgsetloc(0, "\\E6* ..^1. Kris^1, you and little Prince Asriel are royalty too!/%", "obj_town_north_asgore_slash_Step_0_gml_252_0");
    c_talk_wait();
    c_sel(as);
    c_facing("d");
    c_wait(30);
    c_speaker("asgore");
    c_msgsetloc(0, "\\E2* .../%", "obj_town_north_asgore_slash_Step_0_gml_261_0");
    c_talk_wait();
    c_facing("l");
    c_wait(15);
    global.msc = -99;
    global.choice = -1;
    global.choicemsg[0] = stringsetloc("#Maybe later", "obj_town_north_asgore_slash_Step_0_gml_271_0");
    global.choicemsg[1] = stringsetloc("#Yes please", "obj_town_north_asgore_slash_Step_0_gml_272_0");
    global.choicemsg[2] = stringset("");
    global.choicemsg[3] = stringset("");
    c_speaker("asgore");
    c_msgsetloc(0, "\\E7* May I bring up a serious topic for a moment...?/", "obj_town_north_asgore_slash_Step_0_gml_277_0");
    c_msgnext("\\C2 ");
    c_customfunc(function()
    {
        d_make();
    });
    c_waitcustom();
}
if (con == 26 && customcon == 1 && global.choice != -1)
{
    con = 200;
    customcon = 0;
    k_d(3);
    scr_flag_set(1329, global.choice + 1);
    c_waitcustom_end();
    if (global.choice == 0)
    {
        c_msgside("top");
        c_speaker("asgore");
        c_msgsetloc(0, "\\E3* Right..^1. no need for a blue cloud on a sunny day./", "obj_town_north_asgore_slash_Step_0_gml_302_0");
        c_msgnextloc("\\E6* Kris^1. Lots of smiles today^1, okay?/%", "obj_town_north_asgore_slash_Step_0_gml_303_0");
        c_talk_wait();
    }
    if (global.choice == 1)
    {
        c_msgside("top");
        c_speaker("asgore");
        c_msgsetloc(0, "\\E2* ..^1. Kris..^1. your mother./", "obj_town_north_asgore_slash_Step_0_gml_310_0");
        c_msgnextloc("\\E3* ..^1. living on a single teacher's salary.../", "obj_town_north_asgore_slash_Step_0_gml_311_0");
        c_msgnextloc("\\E7* She tries to hide it^1, but..^1. I can't imagine it's not difficult./", "obj_town_north_asgore_slash_Step_0_gml_312_0");
        c_msgnextloc("\\E2* .../", "obj_town_north_asgore_slash_Step_0_gml_313_0");
        c_msgnextloc("\\E7* Kris^1, if things go well with Carol.../", "obj_town_north_asgore_slash_Step_0_gml_314_0");
        c_msgnextloc("\\E2* .../", "obj_town_north_asgore_slash_Step_0_gml_315_0");
        c_msgnextloc("\\EI* ..^1. I think I might be able to get my old job back./", "obj_town_north_asgore_slash_Step_0_gml_316_0");
        c_msgnextloc("\\E6* Promise./%", "obj_town_north_asgore_slash_Step_0_gml_317_0");
        c_talk();
        c_wait_box(2);
        c_sel(as);
        c_facing("u");
        c_wait_box(4);
        c_sel(as);
        c_facing("l");
        c_wait_box(6);
        c_sel(as);
        c_facing("d");
        c_wait_box(7);
        c_sel(as);
        c_facing("l");
        c_wait_talk();
    }
    c_sel(as);
    c_autowalk(0);
    c_sprite(asgore_npc.sprite_index);
    c_imageindex(asgore_npc.image_index);
    c_imagespeed(asgore_npc.image_speed);
    c_var_instance(asgore_npc, "visible", 1);
    c_visible(0);
    c_pannable(1);
    c_panobj_fancy(kr_actor, 12);
    c_wait(15);
    c_pannable(0);
    c_sel(kr);
    c_facing("d");
    c_actortokris();
    c_actortocaterpillar();
    c_terminatekillactors();
}
if (con == 30 && !d_ex() && global.interact == 0)
{
    con = 100;
    global.interact = 1;
    scr_speaker("no_name");
    msgsetloc(0, "* (It's a flower crown^1. You can almost still feel its soft petals on your head.)/%", "obj_town_north_asgore_slash_Step_0_gml_370_0");
    d_make();
}
if (con == 40 && !d_ex() && global.interact == 0)
{
    con = 100;
    global.interact = 1;
    cutscene_master = scr_cutscene_make();
    scr_maincharacters_actors();
    var kr_x_pos = 1331;
    var kr_y_pos = 110;
    var kr_walktime = scr_calculate_move_distance(kr_actor.x, kr_actor.y, kr_x_pos, kr_y_pos, 3);
    c_sel(kr);
    c_walkdirect(kr_x_pos, kr_y_pos, kr_walktime);
    c_delayfacing(kr_walktime + 1, "l");
    var su_x_pos = 1304;
    var su_y_pos = 104;
    var su_walktime = scr_calculate_move_distance(su_actor.x, su_actor.y, su_x_pos, su_y_pos, 3);
    c_sel(su);
    c_walkdirect(su_x_pos, su_y_pos, su_walktime);
    c_delayfacing(su_walktime + 1, "r");
    c_wait(su_walktime + 1);
    c_speaker("susie");
    c_msgsetloc(0, "\\E7* Hey^1, check this out!/%", "obj_town_north_asgore_slash_Step_0_gml_406_0");
    c_talk_wait();
    c_sel(kr);
    c_facing("u");
    c_sel(su);
    c_autowalk(0);
    c_sprite(spr_susie_walk_up_lw);
    c_imagespeed(0.2);
    c_walkdirect_wait(1320, 95, 12);
    c_halt();
    c_speaker("susie");
    c_msgsetloc(0, "\\EK* Ralsei showed me how to^1, uh.../%", "obj_town_north_asgore_slash_Step_0_gml_421_0");
    c_talk_wait();
    c_sel(su);
    c_autowalk(0);
    c_sprite(spr_susie_paper_grab);
    c_imageindex(1);
    c_wait(15);
    c_sprite(spr_susie_walk_up_lw);
    c_halt();
    c_wait(15);
    c_sel(su);
    c_sprite(spr_susie_walk_down_lw);
    c_imagespeed(0.2);
    c_walkdirect(su_x_pos, su_y_pos, 12);
    c_delaycmd(13, "imagespeed", 0);
    c_delaycmd(13, "imageindex", 0);
    c_delayfacing(13, "r");
    c_sel(kr);
    c_delayfacing(13, "l");
    c_wait(13);
    c_sel(su);
    c_sprite(spr_susie_kris_flower_crown);
    c_imageindex(1);
    c_sel(kr);
    c_visible(0);
    c_wait(30);
    c_speaker("susie");
    c_msgsetloc(0, "\\E7* ..^1. how to make this wimpy crap!/%", "obj_town_north_asgore_slash_Step_0_gml_457_0");
    c_talk_wait();
    c_sel(su);
    c_var_lerp("image_index", 2, 4, 8);
    c_wait(8);
    c_sel(kr);
    c_sprite(spr_kris_flower_crown);
    c_visible(1);
    c_sel(su);
    c_facing("r");
    c_wait(30);
    c_snd_play(snd_wing);
    c_sel(kr);
    c_autowalk(0);
    c_var_lerp("image_index", 0, 9, 24);
    c_delaycmd(25, "sprite", spr_krisl);
    c_delaycmd(25, "imageindex", 0);
    c_wait(12);
    c_sel(su);
    c_sprite(spr_susie_surprised_right_lw);
    c_wait(60);
    c_facing("u");
    c_speaker("susie");
    c_msgsetloc(0, "\\EK* Yeah^1, it was stupid anyway./%", "obj_town_north_asgore_slash_Step_0_gml_489_0");
    c_talk_wait();
    c_pannable(1);
    c_panobj_fancy(kr_actor, 12);
    c_wait(15);
    c_pannable(0);
    c_sel(kr);
    c_facing("d");
    c_customfunc(function()
    {
        scr_flag_set(1883, 1);
    });
    c_actortokris();
    c_actortocaterpillar();
    c_terminatekillactors();
}
if (con == 50 && !d_ex() && global.interact == 0)
{
    con = 100;
    global.interact = 1;
    var sentence_end = (scr_flag_get(1331) == 0) ? "/" : "/%";
    scr_speaker("no_name");
    msgsetsubloc(0, "* (You talked to the flowers.)~1", sentence_end, "obj_town_north_asgore_slash_Step_0_gml_521_0");
    if (scr_flag_get(1331) == 0)
    {
        scr_flag_set(1331, 1);
        scr_anyface_next("asgore", "5");
        msgnextloc("\\E5* Good idea^1, Kris^1! A pinch of love really peps them up!/%", "obj_town_north_asgore_slash_Step_0_gml_529_0");
    }
    d_make();
}
if (con == 52 && !d_ex() && global.interact == 0)
{
    con = 100;
    var top_mode = obj_mainchara.y < 110;
    var kr_x_pos = obj_mainchara.x;
    var kr_y_pos = obj_mainchara.y;
    global.interact = 1;
    cutscene_master = scr_cutscene_make();
    scr_maincharacters_actors();
    if (top_mode)
    {
        kr_x_pos = 1196;
        kr_y_pos = 95;
        var kr_walktime = scr_calculate_move_distance(kr_actor.x, kr_actor.y, kr_x_pos, kr_y_pos, 3);
        c_sel(kr);
        c_autodepth(0);
        c_walkdirect(kr_x_pos, kr_y_pos, kr_walktime);
        c_delayfacing(kr_walktime + 1, "u");
        var su_x_pos = 1170;
        var su_y_pos = 90;
        var su_walktime = scr_calculate_move_distance(su_actor.x, su_actor.y, su_x_pos, su_y_pos, 3);
        c_sel(su);
        c_walkdirect(su_x_pos, su_y_pos, su_walktime);
        c_delayfacing(su_walktime + 1, "u");
        c_wait(su_walktime + 1);
    }
    else
    {
        kr_x_pos = 1234;
        kr_y_pos = 154;
        var kr_walktime = scr_calculate_move_distance(kr_actor.x, kr_actor.y, kr_x_pos, kr_y_pos, 3);
        c_sel(kr);
        c_walkdirect(kr_x_pos, kr_y_pos, kr_walktime);
        c_delayfacing(kr_walktime + 1, "d");
        var su_x_pos = 1215;
        var su_y_pos = 144;
        var su_walktime = scr_calculate_move_distance(su_actor.x, su_actor.y, su_x_pos, su_y_pos, 3);
        c_sel(su);
        c_walkdirect(su_x_pos, su_y_pos, su_walktime);
        c_delayfacing(su_walktime + 1, "d");
        c_wait(su_walktime + 1);
    }
    c_speaker("susie");
    c_msgsetloc(0, "\\EN* Everything..^1. smells nice^1, right?/", "obj_town_north_asgore_slash_Step_0_gml_592_0");
    c_msgnextloc("\\EY* C'mon^1. Smell it^1, stinky./%", "obj_town_north_asgore_slash_Step_0_gml_593_0");
    c_talk_wait();
    if (top_mode)
    {
        c_snd_play(snd_wing);
        c_sel(su);
        c_autowalk(0);
        c_sprite(spr_susie_kris_flower_shove_up);
        c_delaycmd(6, "imageindex", 1);
        c_sel(kr);
        c_visible(0);
        c_wait(30);
    }
    else
    {
        c_snd_play(snd_wing);
        c_sel(su);
        c_autowalk(0);
        c_sprite(spr_susie_kris_flower_shove_down);
        c_imageindex(1);
        c_delaycmd(6, "imageindex", 2);
        c_sel(kr);
        c_visible(0);
        c_wait(30);
    }
    c_speaker("susie");
    c_msgsetloc(0, "\\E9* Hehe./%", "obj_town_north_asgore_slash_Step_0_gml_627_0");
    c_talk_wait();
    if (top_mode)
    {
        c_sel(su);
        c_facing("u");
        c_halt();
        c_delayfacing(6, "d");
        c_sel(kr);
        c_visible(1);
        c_autowalk(0);
        c_imagespeed(0.2);
        c_walkdirect(kr_x_pos, kr_y_pos + 20, 12);
        c_delaycmd(13, "imagespeed", 0);
        c_delaycmd(13, "imageindex", 0);
        c_delayfacing(13, "d");
        c_wait(15);
    }
    else
    {
        c_sel(su);
        c_facing("d");
        c_halt();
        c_delayfacing(6, "r");
        c_sel(kr);
        c_visible(1);
        c_autowalk(0);
        c_imagespeed(0.2);
        c_walkdirect(kr_x_pos, kr_y_pos - 20, 12);
        c_delaycmd(13, "imagespeed", 0);
        c_delaycmd(13, "imageindex", 0);
        c_delayfacing(13, "d");
        c_wait(15);
    }
    c_pannable(1);
    c_panobj_fancy(kr_actor, 12);
    c_wait(15);
    c_pannable(0);
    c_sel(kr);
    c_facing("d");
    c_customfunc(function()
    {
        scr_flag_set(1807, 1);
    });
    c_actortokris();
    c_actortocaterpillar();
    c_terminatekillactors();
}
if (con == 54 && !d_ex() && global.interact == 0)
{
    con = 100;
    global.interact = 1;
    scr_speaker("susie");
    msgsetloc(0, "\\E1* Flowers are boring./%", "obj_town_north_asgore_slash_Step_0_gml_691_0");
    d_make();
}
if (con == 60 && !d_ex() && global.interact == 0)
{
    con = 100;
    global.interact = 1;
    var sentence_end = (scr_flag_get(1330) == 0) ? "/" : "/%";
    scr_speaker("no_name");
    msgsetsubloc(0, "* (You looked at the roses.)~1", sentence_end, "obj_town_north_asgore_slash_Step_0_gml_706_0");
    if (scr_flag_get(1330) == 0)
    {
        con = 61;
        global.msc = -99;
        global.choice = -1;
        global.choicemsg[0] = stringsetloc("Yes#absolutely#definitely", "obj_town_north_asgore_slash_Step_0_gml_716_0");
        global.choicemsg[1] = stringsetloc("#No", "obj_town_north_asgore_slash_Step_0_gml_717_0");
        global.choicemsg[2] = stringset("");
        global.choicemsg[3] = stringset("");
        scr_anyface_next("asgore", "6");
        msgnextloc("\\E6* Roses^1! A perfect pick for a romantic moment!/", "obj_town_north_asgore_slash_Step_0_gml_722_0");
        msgnextloc("\\E3* ..^1. does anyone here need a romantic moment?/", "obj_town_north_asgore_slash_Step_0_gml_723_0");
        scr_anyface_next("no_name", 0);
        msgnext("\\C2 ");
    }
    d_make();
}
if (con == 61 && global.choice != -1)
{
    con = 100;
    k_d(3);
    scr_flag_set(1330, global.choice + 1);
    cutscene_master = scr_cutscene_make();
    scr_maincharacters_actors();
    if (global.choice == 0)
    {
        c_speaker("susie");
        c_msgsetloc(0, "\\EM* .../", "obj_town_north_asgore_slash_Step_0_gml_748_0");
        c_facenext("noelle", 25);
        c_msgnextloc("\\EP* .../", "obj_town_north_asgore_slash_Step_0_gml_750_0");
        c_facenext("susie", "M");
        c_msgnextloc("\\EM* We could get them for Kris to use^1, on someone./", "obj_town_north_asgore_slash_Step_0_gml_752_0");
        c_facenext("noelle", "P");
        c_msgnextloc("\\EP* Yeah./", "obj_town_north_asgore_slash_Step_0_gml_754_0");
        c_msgnextloc("\\EJ* I get them^1, for Kris to use^1, and..^1. I could.../", "obj_town_north_asgore_slash_Step_0_gml_755_0");
        c_msgnextloc("\\EO* Give them to you..^1. to hold onto^1. Until then./", "obj_town_north_asgore_slash_Step_0_gml_756_0");
        c_facenext("susie", "M");
        c_msgnextloc("\\EM* Yeah and I do the same thing but^1, uhh^1, reverse./", "obj_town_north_asgore_slash_Step_0_gml_758_0");
        c_msgnextloc("\\ED* .../", "obj_town_north_asgore_slash_Step_0_gml_759_0");
        c_facenext("noelle", "6");
        c_msgnextloc("\\E6* Or..^1. not./", "obj_town_north_asgore_slash_Step_0_gml_761_0");
        c_facenext("susie", "M");
        c_msgnextloc("\\EM* Yeah^1, we could also..^1. not./%", "obj_town_north_asgore_slash_Step_0_gml_763_0");
        c_talk_wait();
    }
    if (global.choice == 1)
    {
        c_speaker("noelle");
        c_msgsetloc(0, "\\EL* (..^1. that was really close.)/%", "obj_town_north_asgore_slash_Step_0_gml_770_0");
        c_talk_wait();
    }
    c_actortokris();
    c_actortocaterpillar();
    c_terminatekillactors();
}
if (con == 90 && !d_ex() && customcon == 1)
{
    con = 100;
    customcon = 0;
    global.facing = 0;
    c_waitcustom_end();
    c_sel(as);
    c_facing("d");
    c_var_instance(asgore_npc, "visible", 1);
    c_pannable(1);
    c_panobj_fancy(kr_actor, 12);
    c_wait(15);
    c_pannable(0);
    c_sel(kr);
    c_facing("d");
    c_actortokris();
    c_actortocaterpillar();
    c_terminatekillactors();
}
if (con == 100 && !d_ex() && !i_ex(obj_cutscene_master))
{
    con = -1;
    global.interact = 0;
}
if (con == 200 && !d_ex() && !i_ex(obj_cutscene_master))
{
    con = -1;
    global.interact = 0;
    asgore_npc.sprite_index = spr_npc_asgore_kneel_flowers;
}
