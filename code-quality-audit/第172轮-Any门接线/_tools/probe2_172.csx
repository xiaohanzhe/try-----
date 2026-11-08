// 第172轮 · 探针2（只读）：父对象链 + 常量真值来源
// 1) Data 上有哪些 Macro/Variable/Const 相关的属性
// 2) obj_doorAny 的父对象链（PreCreate 里有 event_inherited()，可能有父）
// 3) 祖先对象的代码清单
// 4) 若是宏，把宏表吐出来（限定条数）
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Decompiler;
using Underanalyzer.Decompiler;

EnsureDataLoaded();

string outJson = Environment.GetEnvironmentVariable("PROBE172_OUT");
if (String.IsNullOrEmpty(outJson)) { Console.WriteLine("probe2: 缺 PROBE172_OUT"); return; }

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
string JsonS(string s)
{
    if (s == null) return "null";
    var b = new StringBuilder("\"");
    foreach (char c in s)
    {
        if (c == '"') b.Append("\\\"");
        else if (c == '\\') b.Append("\\\\");
        else if (c == '\n') b.Append("\\n");
        else if (c == '\r') b.Append("\\r");
        else if (c == '\t') b.Append("\\t");
        else if (c < 32) b.Append("\\u").Append(((int)c).ToString("x4"));
        else b.Append(c);
    }
    b.Append("\"");
    return b.ToString();
}

try
{
    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");

    // ---- 1. Data 的属性清单（找宏/变量表叫什么）----
    var propRows = new List<string>();
    foreach (PropertyInfo p in Data.GetType().GetProperties())
    {
        string pn = p.Name;
        string low = pn.ToLowerInvariant();
        if (low.IndexOf("macro") < 0 && low.IndexOf("variable") < 0
            && low.IndexOf("const") < 0 && low.IndexOf("global") < 0) continue;
        object v = null;
        try { v = p.GetValue(Data); } catch (Exception) { }
        int n = -1;
        if (v != null)
        {
            ICollection col = v as ICollection;
            if (col != null) n = col.Count;
        }
        propRows.Add("  {\"prop\": " + JsonS(pn) + ", \"type\": " + JsonS(p.GetType().Name)
            + ", \"count\": " + n + "}");
    }
    jb.Append("\"data_props\": [\n").Append(String.Join(",\n", propRows)).Append("\n],\n");

    // ---- 2. obj_doorAny 父链 ----
    var chain = new List<string>();
    object obj = null;
    IEnumerable gos = GO(Data, "GameObjects") as IEnumerable;
    if (gos != null)
    {
        foreach (object o in gos)
        {
            string on = ResName(o);
            if (on == "obj_doorAny") { obj = o; break; }
        }
    }
    var ancCodes = new List<string>();
    if (obj == null)
    {
        chain.Add("__obj_doorAny_NOT_FOUND__");
    }
    else
    {
        object cur = obj;
        for (int lv = 0; lv < 6; lv++)
        {
            string cn = ResName(cur);
            chain.Add(cn);
            object par = GO(cur, "Parent");
            string pn2 = ResName(par);
            if (String.IsNullOrEmpty(pn2)) break;
            cur = par;
        }
        // 祖先（含自己）的代码名
        var names = new Dictionary<string, bool>();
        IEnumerable allCode = GO(Data, "Code") as IEnumerable;
        if (allCode != null)
        {
            foreach (object c in allCode)
            {
                string cnm = ResName(c);
                if (String.IsNullOrEmpty(cnm)) continue;
                for (int i = 0; i < chain.Count; i++)
                {
                    if (cnm.IndexOf("gml_Object_" + chain[i] + "_") == 0)
                    {
                        if (!names.ContainsKey(cnm)) { names[cnm] = true; ancCodes.Add(cnm); }
                        break;
                    }
                }
            }
        }
    }
    jb.Append("\"parent_chain\": [");
    for (int i = 0; i < chain.Count; i++)
    {
        if (i > 0) jb.Append(", ");
        jb.Append(JsonS(chain[i]));
    }
    jb.Append("],\n");
    var acRows = new List<string>();
    foreach (string s in ancCodes) acRows.Add("  " + JsonS(s));
    jb.Append("\"ancestor_codes\": [\n").Append(String.Join(",\n", acRows)).Append("\n],\n");

    // ---- 3. 宏表（名字里带 room_ 的，或前 300 条）----
    var macroRows = new List<string>();
    int nMacro = 0;
    object mac = GO(Data, "Macros");
    IEnumerable mc = mac as IEnumerable;
    if (mc != null)
    {
        foreach (object m in mc)
        {
            nMacro++;
            string mn = ResName(m);
            string mv = GS(m, "Value");
            if (mn == null) continue;
            bool keep = mn.ToLowerInvariant().IndexOf("room") >= 0 || nMacro <= 40;
            if (!keep) continue;
            macroRows.Add("  {\"name\": " + JsonS(mn) + ", \"value\": " + JsonS(mv) + "}");
        }
    }
    jb.Append("\"n_macros\": ").Append(nMacro).Append(",\n");
    jb.Append("\"macros\": [\n").Append(String.Join(",\n", macroRows)).Append("\n],\n");

    // ---- 4. 变量表（全局变量定义常在 Data.Variables）----
    var varRows = new List<string>();
    int nVar = 0;
    IEnumerable vs = GO(Data, "Variables") as IEnumerable;
    if (vs != null)
    {
        foreach (object v in vs)
        {
            nVar++;
            string vn = ResName(v);
            if (vn == null) continue;
            if (vn.ToLowerInvariant().IndexOf("room") < 0 && vn.ToLowerInvariant().IndexOf("door") < 0) continue;
            varRows.Add("  " + JsonS(vn));
        }
    }
    jb.Append("\"n_variables\": ").Append(nVar).Append(",\n");
    jb.Append("\"variables_hit\": [\n").Append(String.Join(",\n", varRows)).Append("\n]\n}\n");

    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe2 OK  data_props=" + propRows.Count + " chain=" + String.Join(">", chain.ToArray())
        + " anc_codes=" + ancCodes.Count + " macros=" + nMacro + " vars=" + nVar);
    Console.WriteLine("out=" + outJson);
}
catch (Exception ex)
{
    Console.WriteLine("probe2 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
