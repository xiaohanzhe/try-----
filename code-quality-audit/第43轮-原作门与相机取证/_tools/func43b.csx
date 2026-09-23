using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 探针 C：全量函数普查 + 调用者索引 + 关键 code 完整导出
// 产出 func43_all.txt / func43_callers.txt / func43b_codes.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outAll = Path.Combine(dir, "func43_all.txt");
string outCallers = Path.Combine(dir, "func43_callers.txt");
string outCodes = Path.Combine(dir, "func43b_codes.txt");
var sa = new StringBuilder();
var sc = new StringBuilder();
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

// ---- 调用者索引的目标函数 ----
string[] TARGETS = new string[] {
    "camera_set_view_pos","camera_set_view_size","camera_set_view_speed",
    "camera_set_view_border","camera_set_view_target","camera_set_view_angle",
    "camera_create","view_get_camera","view_set_camera",
    "gml_Script___view_set","gml_Script___view_set_internal","gml_Script___view_get",
    "layer_hspeed","layer_vspeed","layer_x","layer_y","layer_get_hspeed","layer_get_vspeed",
    "layer_background_htiled","layer_background_vtiled","layer_background_xscale",
    "layer_background_yscale","layer_background_change","layer_background_create",
    "tile_layer_shift","scr_outside_camera","scr_depth",
    "scr_get_id_by_room_index","scr_get_room_by_id","scr_get_room_list","scr_dark_marker",
    "scr_darkbox","scr_darkbox_black","scr_become_dark","scr_shakeobj","scr_minishakeobj",
    "scr_oflash","scr_enable_screen_border","instance_create","layer_create","layer_destroy",
    "draw_background_ext","draw_background_tiled_ext","draw_background_part_ext"
};

// ---- 完整导出的 code（子串匹配）----
string[] DUMP = new string[] {
    "gml_Script___view_get","gml_Script___view_set","gml_Script___view_set_internal",
    "gml_Script_scr_outside_camera","gml_Script_scr_depth",
    "gml_Script_scr_get_id_by_room_index","gml_Script_scr_get_room_by_id","gml_Script_scr_get_room_list",
    "gml_Script_scr_dark_marker","gml_Script_scr_darkbox","gml_Script_scr_become_dark",
    "gml_Script_scr_shakeobj","gml_Script_scr_oflash",
    "gml_Object_obj_backgrounder","gml_Object_obj_backgrounderparent",
    "gml_Object_obj_fadein","gml_Object_obj_fadeout","gml_Object_obj_fadechain",
    "gml_Object_obj_persistentfadein","gml_Object_obj_loadscreen","gml_Object_obj_oflash",
    "gml_Object_obj_darkcontroller","gml_Object_obj_darkslide","gml_Object_obj_darklanding",
    "gml_Object_obj_darkwakeevent","gml_Object_obj_darkdoorevent",
    "gml_Object_obj_darkfountain","gml_Object_obj_fountainkris","gml_Object_obj_shakeobj"
};

try
{
    var codes = (IList)GO(Data, "Code");

    // ===== [A] 全量函数普查 =====
    var funcCnt = new Dictionary<string, int>();
    int nInstr = 0;
    for (int i = 0; i < codes.Count; i++)
    {
        object instrs = GO(codes[i], "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        for (int k = 0; k < li.Count; k++)
        {
            nInstr++;
            string fn = ResName(GO(li[k], "ValueFunction"));
            if (fn == null) continue;
            if (!funcCnt.ContainsKey(fn)) funcCnt[fn] = 0;
            funcCnt[fn]++;
        }
    }
    var all = new List<KeyValuePair<string, int>>(funcCnt);
    all.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { int c = b.Value.CompareTo(a.Value); return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key); });
    sa.AppendLine("Code=" + codes.Count + " 指令=" + nInstr + " 不同函数=" + funcCnt.Count);
    foreach (var kv in all) sa.AppendLine(kv.Value + "\t" + kv.Key);

    // ===== [B] 调用者索引 =====
    var callers = new Dictionary<string, List<string>>();
    foreach (string t in TARGETS) callers[t] = new List<string>();
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
            if (fn == null) continue;
            foreach (string t in TARGETS)
            {
                if (fn == t && !seen.ContainsKey(t))
                {
                    seen[t] = true;
                    callers[t].Add(cn);
                }
            }
        }
    }
    sc.AppendLine("== 调用者索引（ch1）==");
    foreach (string t in TARGETS)
    {
        sc.AppendLine("-- " + t + "  ← " + callers[t].Count + " 处调用者");
        foreach (string s in callers[t]) sc.AppendLine("     " + s);
    }

    // ===== [C] 完整导出指定 code =====
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
                          + "\tjnk=" + GS(ins, "JumpOffset"));
        }
        dumped++;
    }
    sc.AppendLine();
    sc.AppendLine("完整导出 code 数 = " + dumped);
}
catch (Exception ex)
{
    sa.AppendLine("!! EXCEPTION: " + ex.ToString());
    sc.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outAll, sa.ToString(), new UTF8Encoding(false));
File.WriteAllText(outCallers, sc.ToString(), new UTF8Encoding(false));
File.WriteAllText(outCodes, sd.ToString(), new UTF8Encoding(false));
