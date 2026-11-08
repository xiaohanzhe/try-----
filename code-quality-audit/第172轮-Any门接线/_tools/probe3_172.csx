// 第172轮 · 探针3（只读）：ROOM_INITIALIZE 这类名字到底是什么、doorRoom 是不是全局
// A. 扫 GlobalInitScripts（779 个），找出给 ROOM_INITIALIZE / room_title_placeholder /
//    room_battletest 赋值的地方，或 globalvar 声明
// B. 拿 obj_doorW 的代码做对照：它也写裸 doorRoom 吗（⇒ doorRoom 是 globalvar 共享）
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
if (String.IsNullOrEmpty(outJson)) { Console.WriteLine("probe3: 缺 PROBE172_OUT"); return; }

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
    var gd = new GlobalDecompileContext(Data, null);
    Func<object, string> decomp = delegate (object co)
    {
        UndertaleCode uc = co as UndertaleCode;
        if (uc == null) return null;
        try { return new DecompileContext(gd, uc, null).DecompileToString(); }
        catch (Exception ex) { return "__DECOMP_FAIL__ " + ex.GetType().Name; }
    };

    string[] wants = new string[] { "ROOM_INITIALIZE", "room_title_placeholder", "room_battletest", "globalvar" };

    // ---- A. 扫全局初始化脚本 ----
    var hitRows = new List<string>();
    int nScan = 0, nHit = 0;
    IEnumerable gis = GO(Data, "GlobalInitScripts") as IEnumerable;
    if (gis != null)
    {
        foreach (object sc in gis)
        {
            string sn = ResName(sc);
            string sname = sn == null ? "" : sn;
            // 脚本表里可能是 UndertaleGlobalInit{Code}；也兼容直接是 Code
            object codeObj = GO(sc, "Code");
            if (codeObj == null) codeObj = sc;
            nScan++;
            string gml = decomp(codeObj);
            if (String.IsNullOrEmpty(gml)) continue;
            bool hit = false;
            for (int i = 0; i < wants.Length; i++)
                if (gml.IndexOf(wants[i]) >= 0) { hit = true; break; }
            if (!hit) continue;
            nHit++;
            // 只留命中的那几行（±1 行上下文）
            var lines = gml.Replace("\r\n", "\n").Split('\n');
            var keep = new List<string>();
            for (int i = 0; i < lines.Length; i++)
            {
                bool h = false;
                for (int w = 0; w < wants.Length; w++)
                    if (lines[i].IndexOf(wants[w]) >= 0) { h = true; break; }
                if (!h) continue;
                if (i > 0) keep.Add(lines[i - 1]);
                keep.Add(lines[i]);
                if (i + 1 < lines.Length) keep.Add(lines[i + 1]);
                if (keep.Count > 60) break;
            }
            string cname = ResName(codeObj);
            hitRows.Add("  {\"script\": " + JsonS(sname) + ", \"code\": " + JsonS(cname)
                + ", \"lines\": " + JsonS(String.Join("\n", keep.ToArray())) + "}");
        }
    }

    // ---- B. obj_doorW 对照 ----
    var wRows = new List<string>();
    IEnumerable allCode = GO(Data, "Code") as IEnumerable;
    if (allCode != null)
    {
        foreach (object c in allCode)
        {
            string cn = ResName(c);
            if (String.IsNullOrEmpty(cn)) continue;
            if (cn.IndexOf("gml_Object_obj_doorW_") != 0 && cn.IndexOf("gml_Object_obj_doorw_musfade_") != 0) continue;
            wRows.Add("  {\"name\": " + JsonS(cn) + ", \"gml\": " + JsonS(decomp(c)) + "}");
        }
    }

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_scan\": ").Append(nScan).Append(",\n");
    jb.Append("\"n_hit\": ").Append(nHit).Append(",\n");
    jb.Append("\"hits\": [\n").Append(String.Join(",\n", hitRows)).Append("\n],\n");
    jb.Append("\"doorw_codes\": [\n").Append(String.Join(",\n", wRows)).Append("\n]\n}\n");
    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe3 OK  scan=" + nScan + " hits=" + nHit + " doorw_codes=" + wRows.Count);
    Console.WriteLine("out=" + outJson);
}
catch (Exception ex)
{
    Console.WriteLine("probe3 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
