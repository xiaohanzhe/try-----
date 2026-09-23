using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 探针 E：调用者索引 v2（用真实 ValueFunction 全名）
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outCallers = Path.Combine(dir, "callers43.txt");
var sc = new StringBuilder();

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

string[] TARGETS = new string[] {
    "gml_Script_scr_depth","gml_Script_scr_outside_camera","gml_Script_scr_get_id_by_room_index",
    "gml_Script_scr_get_room_by_id","gml_Script_scr_get_room_list","gml_Script_scr_dark_marker",
    "gml_Script_scr_darkbox","gml_Script_scr_darkbox_black","gml_Script_scr_become_dark",
    "gml_Script_scr_shakeobj","gml_Script_scr_minishakeobj","gml_Script_scr_oflash",
    "gml_Script_scr_enable_screen_border","gml_Script_scr_pan_to_obj",
    "gml_Script___background_set","gml_Script___background_set_element",
    "gml_Script___background_set_internal","gml_Script___background_get_internal",
    "gml_Script___background_get_element","gml_Script___init_background",
    "gml_Script_draw_background_ext","gml_Script_tile_layer_shift",
    "gml_Script_scr_transition","gml_Script_scr_fade","gml_Script_scr_room_change",
    "gml_Object_obj_backgrounder_standard_Other_10",
    "gml_Object_obj_backgrounder_sprite_Other_10",
    "gml_Object_obj_backgrounder_sprite_Draw_0",
    "gml_Object_obj_panner_Step_0","gml_Object_obj_mainchara_Step_2",
    "gml_Object_obj_loadscreen_Step_0","gml_Object_obj_screen_loading_Alarm_0",
    "gml_Object_obj_fadein_Create_0","gml_Object_obj_fadeout_Create_0",
    "gml_Object_obj_darkcontroller_Step_0","gml_Object_obj_overworldc_Draw_0",
    "gml_Object_obj_marker_base_Create_0"
};

try
{
    var codes = (IList)GO(Data, "Code");
    var nameSet = new Dictionary<string, bool>();
    foreach (string t in TARGETS) nameSet[t] = true;
    var callers = new Dictionary<string, List<string>>();
    var exists = new Dictionary<string, bool>();
    foreach (string t in TARGETS) { callers[t] = new List<string>(); exists[t] = false; }
    for (int i = 0; i < codes.Count; i++) if (ResName(codes[i]) != null) exists[ResName(codes[i])] = true;

    for (int i = 0; i < codes.Count; i++)
    {
        object cd = codes[i];
        string cn = ResName(cd);
        object instrs = GO(cd, "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        var seen = new Dictionary<string, bool>();
        for (int k = 0; k < li.Count; k++)
        {
            string fn = ResName(GO(li[k], "ValueFunction"));
            if (fn == null || !nameSet.ContainsKey(fn)) continue;
            if (seen.ContainsKey(fn)) continue;
            seen[fn] = true;
            callers[fn].Add(cn);
        }
    }
    sc.AppendLine("== 调用者索引 v2（ValueFunction 全名）==");
    foreach (string t in TARGETS)
    {
        sc.AppendLine("-- " + t + (exists[t] ? "" : "  [该 code 不存在]") + "  ← " + callers[t].Count + " 处");
        foreach (string s in callers[t]) sc.AppendLine("     " + s);
    }
}
catch (Exception ex)
{
    sc.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outCallers, sc.ToString(), new UTF8Encoding(false));
