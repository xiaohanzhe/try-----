// 第172轮 · 探针4（只读）：全量扫 Data.Code，找出所有碰 doorRoom 的代码
// 目的：确认「image_index=0 的 Any 门」的 doorRoom 有没有别的地方赋值。
//       如果只有 obj_doorAny_Step_0 一处赋值 ⇒ 那些门在原作里就是空的。
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
if (String.IsNullOrEmpty(outJson)) { Console.WriteLine("probe4: 缺 PROBE172_OUT"); return; }

string ResName(object res)
{
    if (res == null) return null;
    PropertyInfo p = res.GetType().GetProperty("Name");
    if (p == null) return null;
    object nv = null;
    try { nv = p.GetValue(res); } catch (Exception) { return null; }
    if (nv == null) return null;
    PropertyInfo cp = nv.GetType().GetProperty("Content");
    if (cp != null) { object cv = null; try { cv = cp.GetValue(nv); } catch (Exception) { } if (cv != null) return cv.ToString(); }
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
    var rows = new List<string>();
    int nScan = 0, nFail = 0, nHit = 0;
    IEnumerable allCode = null;
    PropertyInfo pc = Data.GetType().GetProperty("Code");
    if (pc != null) allCode = pc.GetValue(Data) as IEnumerable;
    if (allCode == null) { Console.WriteLine("probe4 FAILED: 拿不到 Data.Code"); return; }

    foreach (object c in allCode)
    {
        nScan++;
        string cn = ResName(c);
        string gml = null;
        try { gml = new DecompileContext(gd, (UndertaleCode)c, null).DecompileToString(); }
        catch (Exception) { nFail++; continue; }
        if (String.IsNullOrEmpty(gml)) continue;
        if (gml.IndexOf("doorRoom") < 0) continue;
        nHit++;
        // 只留含 doorRoom 的行（±0），最多 80 行
        var keep = new List<string>();
        foreach (string ln in gml.Replace("\r\n", "\n").Split('\n'))
        {
            if (ln.IndexOf("doorRoom") < 0) continue;
            keep.Add(ln.Trim());
            if (keep.Count >= 80) break;
        }
        rows.Add("  {\"name\": " + JsonS(cn) + ", \"n_lines\": " + keep.Count
            + ", \"lines\": " + JsonS(String.Join("\n", keep.ToArray())) + "}");
    }

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_scan\": ").Append(nScan).Append(",\n");
    jb.Append("\"n_decomp_fail\": ").Append(nFail).Append(",\n");
    jb.Append("\"n_hit\": ").Append(nHit).Append(",\n");
    jb.Append("\"hits\": [\n").Append(String.Join(",\n", rows)).Append("\n]\n}\n");
    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe4 OK  scan=" + nScan + " fail=" + nFail + " hits=" + nHit);
    Console.WriteLine("out=" + outJson);
}
catch (Exception ex)
{
    Console.WriteLine("probe4 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
