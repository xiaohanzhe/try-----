// probe_dump_scrtext.csx —— 整段 dump 文本绘制核心，用来定「控制符怎么解」
//
// 上一探针（probe_markers）在三款里都指出同一处：
//     MARK  gml_Script_SCR_TEXT  /%,&,%,%%,%%%   16(ut) / 22(outertale)
// 它会 push "/" "%" "&" "%%" "%%%" 这些常量 ⇒ 规则就在这段代码里。
//
// 本探针把 `SCR_TEXT*` 与 `obj_base_writer_Draw_0`（逐字机）**全字段**摊开，
// 后续靠人工还原分支（不猜：只认代码里真的出现的比较/跳转）。
//
// 输出：dump_scrtext.txt
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "dump_scrtext.txt");

object GF(object o, string pn)
{
    if (o == null) return null;
    Type t = o.GetType();
    PropertyInfo p = t.GetProperty(pn);
    if (p != null && p.CanRead) return p.GetValue(o, null);
    FieldInfo f = t.GetField(pn, BindingFlags.Public | BindingFlags.Instance);
    if (f != null) return f.GetValue(o);
    return null;
}

string GS(object o, string pn)
{
    object v = GF(o, pn);
    if (v == null) return "";
    UndertaleString us = v as UndertaleString;
    if (us != null) return us.Content;
    return Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture);
}

string Val(object v)
{
    if (v == null) return "null";
    UndertaleString us = v as UndertaleString;
    if (us != null) return "'" + us.Content + "'";
    try { return Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture); }
    catch { return v.GetType().Name; }
}

void DumpFull(StringBuilder sb, object ins, int j)
{
    sb.Append(String.Format("{0,5}: {1}\n", j, GS(ins, "Kind")));
    foreach (PropertyInfo p in ins.GetType().GetProperties())
    {
        if (!p.CanRead) continue;
        if (p.GetIndexParameters().Length > 0) continue;
        if (p.Name == "Kind") continue;
        object v = null;
        try { v = p.GetValue(ins, null); } catch { continue; }
        if (v == null) continue;
        string s;
        UndertaleString us = v as UndertaleString;
        if (us != null) s = "'" + us.Content + "'";
        else
        {
            // 资源对象（变量/函数）取 Name
            object nm = GF(v, "Name");
            if (nm is UndertaleString) s = "{" + ((UndertaleString)nm).Content + "}";
            else s = Val(v);
        }
        if (s == "0" || s == "False" || s == "0.0" || s == "None") continue;
        sb.Append("         ").Append(p.Name).Append(" = ").Append(s).Append('\n');
    }
}

try
{
    var sb = new StringBuilder();
    int dumped = 0;
    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        bool want = cn == "gml_Script_SCR_TEXT"
                 || cn.StartsWith("gml_Script_SCR_TEXT", StringComparison.Ordinal)
                 || cn == "gml_Object_obj_base_writer_Draw_0"
                 || cn == "gml_Object_obj_base_writer_Alarm_0";
        if (!want) continue;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null || ins.Count == 0) continue;
        dumped++;
        sb.Append("\n========== ").Append(cn).Append("  ins=").Append(ins.Count).Append(" ==========\n");
        for (int j = 0; j < ins.Count; j++) DumpFull(sb, ins[j], j);
    }
    sb.Append("\n[DUMPED] ").Append(dumped).Append('\n');
    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_dump_scrtext OK  dumped=" + dumped);
}
catch (Exception ex)
{
    Console.WriteLine("probe_dump_scrtext FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
