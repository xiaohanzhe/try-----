global.msc = 0;
if (global.darkzone == 1)
{
    global.typer = 6;
}
global.fc = 0;
global.fe = 0;
global.interact = 1;
image_speed = 0.2;
global.flag[20] = 0;
if (global.flag[1372] == 0)
{
    scr_speaker("no_name");
    msgsetloc(0, "* Heh^1. That guy's never going to develop./%", "obj_npc_doubter_slash_Other_10_gml_14_0");
}
else
{
    scr_speaker("no_name");
    msgsetloc(0, "* WH-WHAT!^1? HE DEVELOPED!?/%", "obj_npc_doubter_slash_Other_10_gml_19_0");
}
myinteract = 3;
mydialoguer = instance_create(0, 0, obj_dialoguer);
talked += 1;
