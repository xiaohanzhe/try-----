using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · GeneralInfo / Options（帧率、窗口尺寸、渲染参数）
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "gi43.txt");
var sb = new StringBuilder();

object GO(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

string GS(object o, string pn)
{
    object v = GO(o, pn);
    return v == null ? null : v.ToString();
}

void Dump(object o, string label)
{
    if (o == null) { sb.AppendLine(label + " = (null)"); return; }
    sb.AppendLine("--- " + label + " :: " + o.GetType().Name + " ---");
    foreach (PropertyInfo p in o.GetType().GetProperties())
    {
        string s = null;
        try { object v = p.GetValue(o); s = v == null ? "null" : v.ToString(); }
        catch (Exception e) { s = "<err " + e.GetType().Name + ">"; }
        sb.AppendLine("   " + p.Name + " = " + s);
    }
}

try
{
    Dump(GO(Data, "GeneralInfo"), "Data.GeneralInfo");
    sb.AppendLine();
    object opts = GO(Data, "Options");
    if (opts is IList)
    {
        IList ol = (IList)opts;
        sb.AppendLine("Data.Options.Count = " + ol.Count);
        for (int i = 0; i < ol.Count; i++) Dump(ol[i], "Option[" + i + "]");
    }
    else Dump(opts, "Data.Options");
    sb.AppendLine();
    sb.AppendLine("Data.Sequences = " + (GO(Data, "Sequences") == null ? "null" : "有"));
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
