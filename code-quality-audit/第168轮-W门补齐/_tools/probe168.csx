using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第168轮 · 坐实"出生点怎么选"：
//   [A] 全部 obj_marker* 对象定义（sprite / parent / events）
//   [B] 所有名字含 marker / entrance 的 code（含 GlobalScript）
//   [C] 指定房号的 room creation code（ch1: 9/10/11/13/18/27）
// 产出 <data.win 同级>/probe168.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "probe168.txt");

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
    if (cv != null) return cv.ToString();
    return nv.ToString();
}

try
{
    var tw = new StringBuilder();
    tw.AppendLine("source=" + FilePath);

    // ============ [A] obj_marker* 对象定义 ============
    var gos = (IList)GO(Data, "GameObjects");
    tw.AppendLine("");
    tw.AppendLine("========== [A] obj_marker* / obj_door* 对象定义 ==========");
    int nMark = 0;
    for (int i = 0; i < gos.Count && i < 40000; i++)
    {
        object o = gos[i];
        string nm = ResName(o);
        if (String.IsNullOrEmpty(nm)) continue;
        string low = nm.ToLowerInvariant();
        bool hit = low.Contains("marker");
        if (!hit) continue;
        nMark++;
        object spr = GO(o, "Sprite");
        var evNames = new List<string>();
        object evs = GO(o, "Events");
        IEnumerable evEn = evs as IEnumerable;
        if (evEn != null)
        {
            foreach (object ev in evEn)
            {
                string et = GS(ev, "EventType");
                string es = GS(ev, "EventSubtype");
                if (et == null) et = "?";
                evNames.Add(et + (es == null || es == "0" ? "" : (":" + es)));
            }
        }
        tw.AppendLine(String.Format("  {0,-26} sprite={1,-26} parent={2,-20} depth={3} vis={4} events=[{5}]",
            nm, ResName(spr), ResName(GO(o, "ParentId")), GS(o, "Depth"), GS(o, "Visible"),
            String.Join(",", evNames.ToArray())));
    }
    tw.AppendLine("  (marker 对象共 " + nMark + " 个)");

    // ============ [B] 名字含 marker / entrance 的 code ============
    var codes = (IList)GO(Data, "Code");
    tw.AppendLine("");
    tw.AppendLine("========== [B] code 名含 marker / entrance ==========");
    int nCode = 0;
    for (int ci = 0; ci < codes.Count && ci < 80000; ci++)
    {
        object c = codes[ci];
        string cn = ResName(c);
        if (String.IsNullOrEmpty(cn)) continue;
        string low = cn.ToLowerInvariant();
        if (!(low.Contains("marker") || low.Contains("entrance") || low.Contains("obj_doorw"))) continue;
        object ins = GO(c, "Instructions");
        IEnumerable insEn = ins as IEnumerable;
        if (insEn == null) continue;
        var list = new List<object>();
        foreach (object x in insEn) list.Add(x);
        if (list.Count == 0) continue;
        nCode++;
        tw.AppendLine("");
        tw.AppendLine("### " + cn + "   ins=" + list.Count);
        for (int k = 0; k < list.Count; k++)
        {
            object in1 = list[k];
            string kind = GS(in1, "Kind");
            string t1 = GS(in1, "Type1");
            string t2 = GS(in1, "Type2");
            string fn = ResName(GO(in1, "ValueFunction"));
            string vv = ResName(GO(in1, "ValueVariable"));
            string vs = GS(in1, "ValueString");
            string extra = "";
            if (kind != null && kind.StartsWith("Push"))
            {
                if (t1 == "Int16") extra = GS(in1, "ValueShort");
                else if (t1 == "Int32") extra = GS(in1, "ValueInt");
                else if (t1 == "Int64") extra = GS(in1, "ValueLong");
                else if (t1 == "Double") extra = GS(in1, "ValueDouble");
            }
            if (fn != null) extra = "FN=" + fn;
            if (vv != null) extra = "VAR=" + vv;
            if (vs != null) extra = "STR=" + vs;
            tw.AppendLine(String.Format("   {0,4}  {1,-14} {2,-9} {3,-9} {4}", k, kind, t1, t2, extra));
        }
    }
    tw.AppendLine("  (命中 code " + nCode + " 段)");

    // ============ [C] 指定房号的 room creation code ============
    var rooms = (IList)GO(Data, "Rooms");
    tw.AppendLine("");
    tw.AppendLine("========== [C] room creation code（ch1 门房 9/10/11/13/18/27）==========");
    int[] want = new int[] { 9, 10, 11, 13, 18, 27 };
    for (int wi = 0; wi < want.Length; wi++)
    {
        int ri = want[wi];
        if (ri >= rooms.Count) continue;
        object r = rooms[ri];
        tw.AppendLine("");
        tw.AppendLine("--- room #" + ri + " " + ResName(r));
        object cc = GO(r, "CreationCode");
        if (cc == null) { tw.AppendLine("    (无 creation code)"); continue; }
        string ccn = ResName(cc);
        tw.AppendLine("    creationCode=" + ccn);
        object ins = GO(cc, "Instructions");
        IEnumerable insEn = ins as IEnumerable;
        if (insEn == null) continue;
        var list = new List<object>();
        foreach (object x in insEn) list.Add(x);
        tw.AppendLine("    ins=" + list.Count);
        for (int k = 0; k < list.Count; k++)
        {
            object in1 = list[k];
            string kind = GS(in1, "Kind");
            string t1 = GS(in1, "Type1");
            string fn = ResName(GO(in1, "ValueFunction"));
            string vv = ResName(GO(in1, "ValueVariable"));
            string extra = "";
            if (kind != null && kind.StartsWith("Push"))
            {
                if (t1 == "Int16") extra = GS(in1, "ValueShort");
                else if (t1 == "Int32") extra = GS(in1, "ValueInt");
                else if (t1 == "Double") extra = GS(in1, "ValueDouble");
            }
            if (fn != null) extra = "FN=" + fn;
            if (vv != null) extra = "VAR=" + vv;
            tw.AppendLine(String.Format("     {0,4}  {1,-14} {2,-9} {3}", k, kind, t1, extra));
        }
    }

    // ============ [D] 各类门的 entrance 值（机制证据，机器可读） ============
    tw.AppendLine("");
    tw.AppendLine("========== [D] door Alarm_2 的 entrance / 守卫条数 ==========");
    string[] doorCodes = new string[] {
        "gml_Object_obj_doorA_Alarm_2", "gml_Object_obj_doorA_musfade_Alarm_2",
        "gml_Object_obj_doorB_Alarm_2", "gml_Object_obj_doorB_musfade_Alarm_2",
        "gml_Object_obj_doorC_Alarm_2", "gml_Object_obj_doorC_musfade_Alarm_2",
        "gml_Object_obj_doorD_Alarm_2", "gml_Object_obj_doorD_musfade_Alarm_2",
        "gml_Object_obj_doorX_Alarm_2", "gml_Object_obj_doorX_musfade_Alarm_2",
        "gml_Object_obj_doorW_Alarm_2", "gml_Object_obj_doorw_musfade_Alarm_2" };
    for (int di = 0; di < doorCodes.Length; di++)
    {
        object found = null;
        for (int ci = 0; ci < codes.Count && ci < 80000; ci++)
        {
            string cn = ResName(codes[ci]);
            if (cn == doorCodes[di]) { found = codes[ci]; break; }
        }
        if (found == null) { tw.AppendLine("  " + doorCodes[di] + "  (缺)"); continue; }
        IEnumerable insEn = GO(found, "Instructions") as IEnumerable;
        var list = new List<object>();
        if (insEn != null) foreach (object x in insEn) list.Add(x);
        int entrance = -999, nguard = 0;
        for (int k = 0; k < list.Count; k++)
        {
            object in1 = list[k];
            if (GS(in1, "Kind") == "Pop" && ResName(GO(in1, "ValueVariable")) == "entrance" && k > 0)
            {
                string pt = GS(list[k - 1], "Type1");
                string pv = (pt == "Int16") ? GS(list[k - 1], "ValueShort") : GS(list[k - 1], "ValueDouble");
                try { entrance = Convert.ToInt32(pv); } catch (Exception) { }
            }
            if (GS(in1, "Kind") == "Cmp" && ResName(GO(in1, "ValueVariable")) == "room") nguard++;
        }
        tw.AppendLine(String.Format("  {0,-46} entrance={1,-5} room_guard_cmp={2,-5} ins={3}",
            doorCodes[di], entrance, nguard, list.Count));
    }

    File.WriteAllText(outTxt, tw.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe168 OK  markers=" + nMark + "  codes=" + nCode);
}
catch (Exception ex)
{
    Console.WriteLine("probe168 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
