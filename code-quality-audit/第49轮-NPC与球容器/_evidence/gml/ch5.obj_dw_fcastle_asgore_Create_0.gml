timer = 0;
init = false;
con = 0;
subcon = 0;
visible = 0;
turnofflayers("NPC");
npcs = [];
npcs[0] = 
{
    asgore: scr_marker_fromasset(findsprite(spr_asgore_armor_walk_look_away, "NPCs", c_aqua)),
    flower: scr_marker_fromasset(findsprite(spr_enemy_aqua_pose_r)),
    text: stringsetloc("Uuu, that's okay!#We...#can play later.", "obj_dw_fcastle_asgore_slash_Create_0_gml_18_0"),
    color: c_aqua
};
npcs[1] = 
{
    asgore: scr_marker_fromasset(findsprite(spr_asgore_armor_walk_look_away, "NPCs", c_yellow)),
    flower: scr_marker_fromasset(findsprite(spr_yellow_kneelsad)),
    text: stringsetloc("Well, um, more#time to practice...#heh...", "obj_dw_fcastle_asgore_slash_Create_0_gml_25_0"),
    color: c_yellow
};
npcs[5] = 
{
    asgore: scr_marker_fromasset(findsprite(spr_asgore_armor_walk_look_away, "NPCs", c_fuchsia)),
    flower: scr_marker_fromasset(findsprite(spr_seth_pleading)),
    text: stringsetloc("W-wait, what if#I tried...", "obj_dw_fcastle_asgore_slash_Create_0_gml_32_0"),
    color: c_fuchsia
};
npcs[2] = 
{
    asgore: scr_marker_fromasset(findsprite(spr_asgore_armor_walk_look_away, "NPCs", c_blue)),
    flower: scr_marker_fromasset(findsprite(spr_blue_poses_unhappy)),
    text: stringsetloc("Are you sure?#Not even#a pirouette...?", "obj_dw_fcastle_asgore_slash_Create_0_gml_39_0"),
    color: c_blue
};
npcs[4] = 
{
    asgore: scr_marker_fromasset(findsprite(spr_asgore_armor_walk_look_away, "NPCs", c_red)),
    flower: scr_marker_fromasset(findsprite(spr_orange_shock)),
    text: stringsetloc("I... y-yes,#no one will#get in your way!", "obj_dw_fcastle_asgore_slash_Create_0_gml_46_0"),
    color: c_orange
};
npcs[3] = 
{
    asgore: scr_marker_fromasset(findsprite(spr_asgore_armor_walk_look_away, "NPCs", c_lime)),
    flower: scr_marker_fromasset(findsprite(spr_green_hold)),
    text: noone,
    color: c_lime
};
for (var i = 0; i < 6; i++)
{
    npcs[i].asgore.image_blend = c_white;
    npcs[i].asgore.image_index = 0;
    npcs[i].asgore.image_speed = 0;
    npcs[i].flower.image_index = 0;
    npcs[i].flower.image_speed = 0;
}
npcs[1].flower.sprite_index = spr_yellow_kneelsad;
npcs[3].flower.sprite_index = spr_green_hold_sad;
npcs[4].flower.sprite_index = spr_orange_shock;
npcs[5].flower.sprite_index = spr_seth_pleading;
blocker = -4;
charbubble = -4;

make_bubble = function(arg0, arg1, arg2, arg3, arg4, arg5 = false)
{
    charbubble = scr_messagebubble(arg0, arg1, arg2, arg3, -2);
    charbubble.taillength = 0;
    charbubble.tailwidth = 0;
    if (!arg5)
    {
        blocker = instance_create_depth(0, 0, 1500020, obj_marker);
        blocker.x = arg1 - 200;
        blocker.y = arg2 - 200;
        blocker.image_alpha = 1;
        with (blocker)
        {
            image_xscale = 400;
            image_yscale = 400;
            sprite_index = spr_pxwhite;
            image_blend = c_black;
        }
        scr_lerpvar_instance(blocker, "image_alpha", 1, 0, 30);
    }
    charbubble.depth = 1500050;
    charbubble.parallax_depth = 0.1;
    charbubble.dropColor = merge_color(arg4, c_black, 0.25);
    charbubble.textbubbleColor = merge_color(arg4, c_white, 0.75);
};

global.plot = max(global.plot, 435);
with (obj_border_controller)
{
    hide_border(1/30);
}
