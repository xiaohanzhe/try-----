// 第171轮 · 列出所有 code 条目名（只挑 door/marker 相关）
// 目的：GMS2 里每个对象事件都有独立 code 条目 `gml_Object_<Obj>_Alarm_2`。
//   · 若 `gml_Object_obj_doorAny_Alarm_2` **存在** ⇒ obj_doorAny 有自己的 Alarm_2，
//     不会执行 obj_doorW 的代码 ⇒ "该房只有 obj_doorAny" 的房间不能借 W 分支算边。
//   · 若**不存在**且 obj_doorAny 有 Parent=obj_doorW ⇒ 它继承 W 的 Alarm_2。
// 输出走环境变量 INST171_CODES
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string outJson = Environment.GetEnvironmentVariable("INST171_CODES");
if (String.IsNullOrEmpty(outJson))
{
    Console.WriteLine("codes171 FAILED: 环境变量 INST171_CODES 未设置");
    return;
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
        else if (c < 32) b.Append("\\u").Append(((int)c).ToString("x4"));
        else b.Append(c);
    }
    b.Append("\"");
    return b.ToString();
}

try
{
    var codes = (IList)GO(Data, "Code");
    var names = new List<string>();
    for (int i = 0; i < codes.Count; i++)
    {
        string n = ResName(codes[i]);
        if (String.IsNullOrEmpty(n)) continue;
        string low = n.ToLowerInvariant();
        if (low.IndexOf("door") >= 0 || low.IndexOf("marker") >= 0) names.Add(n);
    }
    names.Sort(StringComparer.OrdinalIgnoreCase);
    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_code_total\": ").Append(codes.Count).Append(",\n");
    jb.Append("\"n_code_hit\": ").Append(names.Count).Append(",\n");
    jb.Append("\"names\": [\n  ").Append(String.Join(",\n  ", names.ConvertAll(x => JsonS(x)).ToArray())).Append("\n]\n}\n");
    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("codes171 OK codes=" + codes.Count + " hit=" + names.Count);
}
catch (Exception ex)
{
    Console.WriteLine("codes171 FAILED: " + ex.GetType().Name + ": " + ex.Message);
}
