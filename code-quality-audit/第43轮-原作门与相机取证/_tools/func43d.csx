using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 探针 F：精确导出（GlobalScript 真实函数体 + 相关对象事件）
// 产出 func43d_codes.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outCodes = Path.Combine(dir, "func43d_codes.txt");
var sd = new StringBuilder();

string GS(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    object v = null;
    try { v = p.GetValue(o); } catch (Exception) { return null; }
    return v == null ? null : v.ToString();
}

object GO(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

string ResName(object res)
{
    if (res == null) return null;
    object nv = GO(res, "Name");
    if (nv == null) return null;
    object cv = GO(nv, "Content");
    return cv == null ? null : cv.ToString();
}

string[] DUMP = new string[] {
    "gml_GlobalScript___view_get","gml_GlobalScript___view_set",
    "gml_GlobalScript___view_set_internal","gml_GlobalScript___init_view",
    "gml_GlobalScript_scr_depth","gml_GlobalScript_scr_dark_marker",
    "gml_GlobalScript_scr_pan_to_obj","gml_GlobalScript_scr_get_id_by_room_index",
    "gml_GlobalScript_scr_get_room_by_id","gml_GlobalScript_scr_get_room_list",
    "gml_GlobalScript_scr_get_valid_room","gml_GlobalScript_scr_outside_camera",
    "gml_GlobalScript_scr_shakeobj","gml_GlobalScript_scr_minishakeobj",
    "gml_GlobalScript_scr_oflash","gml_GlobalScript_scr_darkbox",
    "gml_GlobalScript_scr_darkbox_black","gml_GlobalScript_scr_become_dark",
    "gml_GlobalScript_scr_enable_screen_border","gml_GlobalScript_scr_draw_screen_border",
    "gml_GlobalScript___background_set","gml_GlobalScript___background_set_element",
    "gml_GlobalScript___background_set_internal","gml_GlobalScript___background_get_internal",
    "gml_GlobalScript___init_background","gml_GlobalScript___init_d3d",
    "gml_Object_obj_panner","gml_Object_obj_roomcontroller",
    "gml_Object_obj_backgrounderparent","gml_Object_obj_backgrounder_sprite_Draw_0",
    "gml_Object_obj_event_room_Step_0","gml_Object_obj_shortcut_door"
};

try
{
    var codes = (IList)GO(Data, "Code");
    int dumped = 0;
    for (int i = 0; i < codes.Count; i++)
    {
        object cd = codes[i];
        string cn = ResName(cd);
        if (cn == null) continue;
        bool want = false;
        foreach (string d in DUMP) if (cn.IndexOf(d, StringComparison.OrdinalIgnoreCase) >= 0) { want = true; break; }
        if (!want) continue;
        object instrs = GO(cd, "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        sd.AppendLine("### " + cn + " ins=" + li.Count);
        for (int k = 0; k < li.Count; k++)
        {
            object ins = li[k];
            sd.AppendLine("  " + k + "\t" + GS(ins, "Kind")
                          + "\tT1=" + GS(ins, "Type1") + "\tT2=" + GS(ins, "Type2")
                          + "\tS=" + GS(ins, "ValueShort") + "\tI=" + GS(ins, "ValueInt")
                          + "\tL=" + GS(ins, "ValueLong") + "\tD=" + GS(ins, "ValueDouble")
                          + "\tfn=" + ResName(GO(ins, "ValueFunction"))
                          + "\tvar=" + ResName(GO(ins, "ValueVariable"))
                          + "\tref=" + GS(ins, "ReferenceType")
                          + "\tjnk=" + GS(ins, "JumpOffset")
                          + "\ts=" + GS(ins, "ValueString"));
        }
        dumped++;
    }
    sd.Insert(0, "== 导出 code 数 = " + dumped + " ==\n");
}
catch (Exception ex)
{
    sd.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outCodes, sd.ToString(), new UTF8Encoding(false));
