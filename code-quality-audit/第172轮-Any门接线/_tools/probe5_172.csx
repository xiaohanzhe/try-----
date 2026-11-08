// 第172轮 · 探针5（只读）：实例创建代码到底挂在哪个属性上
// 1) 把一扇 Any 门实例的**全部属性名 + 值预览**吐出来
// 2) 清点 gml_RoomCC_* 代码（这是实例级创建代码的命名），看有几个、能不能解压
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
if (String.IsNullOrEmpty(outJson)) { Console.WriteLine("probe5: 缺 PROBE172_OUT"); return; }

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
string Peek(object v)
{
    if (v == null) return "null";
    string s;
    try { s = v.ToString(); } catch (Exception) { return "<ToString 抛异常>"; }
    if (s != null && s.Length > 90) s = s.Substring(0, 90) + "…";
    return s;
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
    var gd = new GlobalDecompileContext(Data, null);
    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");

    // ---- 1. 样例实例的全部属性 ----
    var propRows = new List<string>();
    IEnumerable rooms = GO(Data, "Rooms") as IEnumerable;
    bool done = false;
    if (rooms != null)
    {
        foreach (object r in rooms)
        {
            if (done) break;
            IEnumerable layers = GO(r, "Layers") as IEnumerable;
            if (layers == null) continue;
            foreach (object ly in layers)
            {
                object iid = GO(ly, "InstancesData");
                if (iid == null) continue;
                IEnumerable ins = GO(iid, "Instances") as IEnumerable;
                if (ins == null) continue;
                foreach (object it in ins)
                {
                    string on = ResName(GO(it, "ObjectDefinition"));
                    if (on == null || on.ToLowerInvariant().IndexOf("doorany") < 0) continue;
                    propRows.Add("  {\"room\": " + JsonS(ResName(r)) + ", \"props\": [");
                    var pr = new List<string>();
                    foreach (PropertyInfo p in it.GetType().GetProperties())
                    {
                        object v = null;
                        try { v = p.GetValue(it); } catch (Exception ex) { pr.Add("{\"name\": " + JsonS(p.Name) + ", \"value\": " + JsonS("<EX " + ex.GetType().Name + ">") + "}"); continue; }
                        string extra = "";
                        ICollection col = v as ICollection;
                        if (col != null) extra = " n=" + col.Count;
                        string rn = ResName(v);
                        if (rn != null && rn.Length < 60) extra += " name=" + rn;
                        pr.Add("{\"name\": " + JsonS(p.Name) + ", \"type\": " + JsonS(p.GetType().Name)
                            + ", \"value\": " + JsonS(Peek(v) + extra) + "}");
                    }
                    propRows[propRows.Count - 1] += String.Join(", ", pr) + "]}";
                    done = true;
                    break;
                }
                if (done) break;
            }
        }
    }
    jb.Append("\"sample_props\": [\n").Append(String.Join(",\n", propRows)).Append("\n],\n");

    // ---- 2. gml_RoomCC_* 清点 ----
    var ccRows = new List<string>();
    int nCC = 0, nCCok = 0, nCCfail = 0, nCCdoor = 0;
    IEnumerable allCode = GO(Data, "Code") as IEnumerable;
    if (allCode != null)
    {
        foreach (object c in allCode)
        {
            string cn = ResName(c);
            if (String.IsNullOrEmpty(cn)) continue;
            if (cn.IndexOf("gml_RoomCC_") != 0) continue;
            nCC++;
            string gml = null;
            try { gml = new DecompileContext(gd, (UndertaleCode)c, null).DecompileToString(); nCCok++; }
            catch (Exception) { nCCfail++; continue; }
            bool door = gml != null && gml.IndexOf("doorRoom") >= 0;
            if (door) nCCdoor++;
            if (!door) continue;
            var keep = new List<string>();
            foreach (string ln in gml.Replace("\r\n", "\n").Split('\n'))
                if (ln.IndexOf("doorRoom") >= 0) keep.Add(ln.Trim());
            ccRows.Add("  {\"code\": " + JsonS(cn) + ", \"lines\": " + JsonS(String.Join("\n", keep.ToArray())) + "}");
        }
    }
    jb.Append("\"n_roomcc\": ").Append(nCC).Append(",\n");
    jb.Append("\"n_roomcc_ok\": ").Append(nCCok).Append(",\n");
    jb.Append("\"n_roomcc_fail\": ").Append(nCCfail).Append(",\n");
    jb.Append("\"n_roomcc_door\": ").Append(nCCdoor).Append(",\n");
    jb.Append("\"roomcc\": [\n").Append(String.Join(",\n", ccRows)).Append("\n]\n}\n");

    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe5 OK  roomcc=" + nCC + " ok=" + nCCok + " fail=" + nCCfail + " door=" + nCCdoor);
    Console.WriteLine("out=" + outJson);
}
catch (Exception ex)
{
    Console.WriteLine("probe5 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
