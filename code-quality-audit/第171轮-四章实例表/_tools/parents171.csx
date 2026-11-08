// 第171轮 · 门对象继承链探针
// 目的：判断 `obj_doorB` / `obj_doorAny` / `obj_doorw_musfade` 是否是 `obj_doorW` 的
// **子对象**（子对象会执行父对象的 Alarm_2 代码）。
// 若 `obj_doorAny` 不是子对象，那么"该房只有 obj_doorAny、但 GML 里 obj_doorW 有
// 这条 room 分支"就不能算一条边 —— 代码永远不执行。
// 输出路径走环境变量 INST171_PARENTS
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string outJson = Environment.GetEnvironmentVariable("INST171_PARENTS");
if (String.IsNullOrEmpty(outJson))
{
    Console.WriteLine("parents171 FAILED: 环境变量 INST171_PARENTS 未设置");
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

string StrC(object s)
{
    if (s == null) return null;
    object cv = GO(s, "Content");
    if (cv != null) return cv.ToString();
    return s.ToString();
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
    var objs = (IList)GO(Data, "GameObjects");
    var events = (IList)GO(Data, "Code");   // 只为确认索引可用
    var rows = new List<string>();
    int n = 0;
    for (int i = 0; i < objs.Count; i++)
    {
        object o = objs[i];
        string on = ResName(o);
        if (String.IsNullOrEmpty(on)) continue;
        string low = on.ToLowerInvariant();
        if (low.IndexOf("door") < 0 && low.IndexOf("marker") < 0) continue;
        string par = ResName(GO(o, "Parent"));
        // 事件里 Alarm_2 是否有代码
        int nEvent = 0;
        var codes = new List<string>();
        IEnumerable evs = GO(o, "Events") as IEnumerable;
        if (evs != null)
        {
            foreach (object ev in evs)
            {
                IEnumerable subs = GO(ev, "Events") as IEnumerable;
                if (subs == null) continue;
                foreach (object sub in subs)
                {
                    object act = GO(sub, "Actions");
                    if (act == null) continue;
                    IEnumerable acts = act as IEnumerable;
                    if (acts == null) continue;
                    int k = 0;
                    foreach (object a in acts) { k++; object cd = GO(a, "CodeId"); if (cd != null) codes.Add(StrC(GO(cd, "Name")) ?? "?"); }
                    nEvent += k;
                }
            }
        }
        n++;
        rows.Add("  {\"obj\": " + JsonS(on) + ", \"parent\": " + JsonS(par)
            + ", \"n_action\": " + nEvent + ", \"codes\": [" + String.Join(", ", codes.ConvertAll(x => JsonS(x)).ToArray()) + "]}");
    }
    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_obj\": ").Append(objs.Count).Append(",\n");
    jb.Append("\"n_door_marker_obj\": ").Append(n).Append(",\n");
    jb.Append("\"rows\": [\n").Append(String.Join(",\n", rows)).Append("\n]\n}\n");
    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("parents171 OK objs=" + objs.Count + " door_marker=" + n);
    Console.WriteLine("out=" + outJson);
}
catch (Exception ex)
{
    Console.WriteLine("parents171 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
