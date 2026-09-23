using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第42轮 · 补齐缺口：obj_doorAny / obj_doorE / obj_doorF / obj_overworldc 的 code 指令流
// 产出 <data.win 同级>/probe42b.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "probe42b.txt");

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
    var codes = (IList)GO(Data, "Code");
    var tw = new StringBuilder();
    string[] keys = new string[] { "doorAny", "obj_doorE", "obj_doorF", "overworldc",
                                  "obj_door_solid" };
    int nCode = 0, nInsTotal = 0;
    for (int ci = 0; ci < codes.Count; ci++)
    {
        object c = codes[ci];
        string cn = ResName(c);
        if (String.IsNullOrEmpty(cn) || !cn.StartsWith("gml_")) continue;
        bool hit = false;
        for (int k = 0; k < keys.Length; k++) { if (cn.IndexOf(keys[k]) >= 0) { hit = true; break; } }
        if (!hit) continue;
        IEnumerable insEn = GO(c, "Instructions") as IEnumerable;
        if (insEn == null) continue;
        var list = new List<object>();
        foreach (object x in insEn) { list.Add(x); if (list.Count > 4000) break; }
        if (list.Count == 0) continue;
        nCode++;
        tw.AppendLine("### " + cn + "   ins=" + list.Count);
        for (int k = 0; k < list.Count; k++)
        {
            object in1 = list[k];
            string kind = GS(in1, "Kind");
            string t1 = GS(in1, "Type1");
            string t2 = GS(in1, "Type2");
            string extra = "";
            if (kind != null && kind.StartsWith("Push"))
            {
                if (t1 == "Int16") extra = GS(in1, "ValueShort");
                else if (t1 == "Int32") extra = GS(in1, "ValueInt");
                else if (t1 == "Int64") extra = GS(in1, "ValueLong");
                else if (t1 == "Double") extra = GS(in1, "ValueDouble");
            }
            string fn = ResName(GO(in1, "ValueFunction"));
            string vv = ResName(GO(in1, "ValueVariable"));
            string vs = GS(in1, "ValueString");
            if (fn != null) extra = "FN=" + fn;
            else if (vv != null) extra = "VAR=" + vv;
            else if (vs != null) extra = "STR=" + vs;
            tw.AppendLine(String.Format("   {0,4}  {1,-14} {2,-9} {3,-9} {4}",
                k, kind, t1, t2, extra));
            nInsTotal++;
        }
        tw.AppendLine("");
    }
    tw.Insert(0, "codes matched=" + nCode + "  ins_total=" + nInsTotal + "\n\n");
    File.WriteAllText(outTxt, tw.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe42b OK  codes=" + nCode + "  ins=" + nInsTotal);
}
catch (Exception ex)
{
    Console.WriteLine("probe42b FAILED: " + ex.GetType().Name + ": " + ex.Message);
}
