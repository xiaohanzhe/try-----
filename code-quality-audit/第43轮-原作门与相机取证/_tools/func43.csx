using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 探针 B：全量函数引用普查 + 过渡/相机/背景相关资源名单 + 指定 code 指令流
// 产出 <data.win 同级>/func43.txt 与 func43.json 与 func43_codes.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "func43.txt");
string outJson = Path.Combine(dir, "func43.json");
string outCodes = Path.Combine(dir, "func43_codes.txt");
var sb = new StringBuilder();
var cb = new StringBuilder();
var jb = new StringBuilder();

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
    return cv == null ? null : cv.ToString();
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

string[] KW = new string[] {
    "camera","view_","viewx","viewy","view_w","view_h","view[",
    "bg_","background","layer_","room_",
    "fade","transition","wipe","dissolve","flash","shader",
    "screen","shake","scroll","parallax",
    "dark","fountain","warp","portal","teleport","cutscene",
    "instance_create","with(","depth"
};

bool Has(string s, string[] ks)
{
    if (s == null) return false;
    foreach (string k in ks)
        if (s.IndexOf(k, StringComparison.OrdinalIgnoreCase) >= 0) return true;
    return false;
}

try
{
    // ===== [A] 全量函数引用普查 =====
    var codes = (IList)GO(Data, "Code");
    var funcCnt = new Dictionary<string, int>();
    int nInstr = 0;
    for (int i = 0; i < codes.Count; i++)
    {
        object cd = codes[i];
        object instrs = GO(cd, "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        for (int k = 0; k < li.Count; k++)
        {
            nInstr++;
            string fn = ResName(GO(li[k], "ValueFunction"));
            if (fn == null) continue;
            if (!funcCnt.ContainsKey(fn)) funcCnt[fn] = 0;
            funcCnt[fn]++;
        }
    }
    sb.AppendLine("== [A] Code=" + codes.Count + " ；指令总数=" + nInstr
                  + " ；不同函数名 = " + funcCnt.Count + " ==");
    sb.AppendLine("-- 关键字命中的函数（按出现次数降序）--");
    var hits = new List<KeyValuePair<string, int>>();
    foreach (var kv in funcCnt) if (Has(kv.Key, KW)) hits.Add(kv);
    hits.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { int c = b.Value.CompareTo(a.Value); return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key); });
    foreach (var kv in hits) sb.AppendLine("   " + kv.Key + " x" + kv.Value);
    sb.AppendLine("命中函数数 = " + hits.Count);
    sb.AppendLine();

    // ===== [B] Code 名单（关键字）=====
    sb.AppendLine("== [B] UndertaleCode 名单（关键字命中）==");
    var codeHits = new List<string>();
    for (int i = 0; i < codes.Count; i++)
    {
        string cn = ResName(codes[i]);
        if (Has(cn, KW)) codeHits.Add(cn);
    }
    foreach (string s in codeHits) sb.AppendLine("   " + s);
    sb.AppendLine("命中 code 数 = " + codeHits.Count);
    sb.AppendLine();

    // ===== [C] Scripts / GameObjects / Functions 名单 =====
    var scripts = (IList)GO(Data, "Scripts");
    sb.AppendLine("== [C] Scripts=" + (scripts == null ? -1 : scripts.Count) + " （关键字命中）==");
    if (scripts != null)
        for (int i = 0; i < scripts.Count; i++)
        {
            string sn = ResName(scripts[i]);
            if (Has(sn, KW)) sb.AppendLine("   " + sn);
        }
    sb.AppendLine();

    var objs = (IList)GO(Data, "GameObjects");
    sb.AppendLine("== [D] GameObjects=" + (objs == null ? -1 : objs.Count) + " （关键字命中）==");
    var objHits = new List<string>();
    if (objs != null)
        for (int i = 0; i < objs.Count; i++)
        {
            string on = ResName(objs[i]);
            if (Has(on, KW)) { objHits.Add(on); sb.AppendLine("   " + on); }
        }
    sb.AppendLine("命中 obj 数 = " + objHits.Count);
    sb.AppendLine();

    // ===== [E] 指定 code 的完整指令流 =====
    var DUMPKW = new string[] {
        "transition","fade","camera","view","screen","darkfountain","darkdoor",
        "mainchara","overworldc","warp","portal","roomchange","roomswitch","parallax"
    };
    int dumped = 0;
    for (int i = 0; i < codes.Count; i++)
    {
        object cd = codes[i];
        string cn = ResName(cd);
        if (!Has(cn, DUMPKW)) continue;
        object instrs = GO(cd, "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        cb.AppendLine("### " + cn + " ins=" + li.Count);
        for (int k = 0; k < li.Count; k++)
        {
            object ins = li[k];
            cb.AppendLine("  " + k + "\t" + GS(ins, "Kind")
                          + "\tT1=" + GS(ins, "Type1") + "\tT2=" + GS(ins, "Type2")
                          + "\tS=" + GS(ins, "ValueShort") + "\tI=" + GS(ins, "ValueInt")
                          + "\tL=" + GS(ins, "ValueLong") + "\tD=" + GS(ins, "ValueDouble")
                          + "\tfn=" + ResName(GO(ins, "ValueFunction"))
                          + "\tvar=" + ResName(GO(ins, "ValueVariable"))
                          + "\tref=" + GS(ins, "ReferenceType")
                          + "\tjnk=" + GS(ins, "JumpOffset"));
        }
        dumped++;
    }
    sb.AppendLine("== [E] 完整导出的 code 数 = " + dumped + " （见 func43_codes.txt）==");
    sb.AppendLine();

    jb.Append("{\"n_codes\": ").Append(codes.Count).Append(",\n");
    jb.Append(" \"n_instr\": ").Append(nInstr).Append(",\n");
    jb.Append(" \"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append(" \"func_hits\": {");
    int kk = 0;
    foreach (var kv in hits)
    {
        if (kk++ > 0) jb.Append(",");
        jb.Append("\n  ").Append(JsonS(kv.Key)).Append(": ").Append(kv.Value);
    }
    jb.Append("\n },\n \"code_hits\": [");
    kk = 0;
    foreach (string s in codeHits) { if (kk++ > 0) jb.Append(","); jb.Append("\n  ").Append(JsonS(s)); }
    jb.Append("\n ],\n \"obj_hits\": [");
    kk = 0;
    foreach (string s in objHits) { if (kk++ > 0) jb.Append(","); jb.Append("\n  ").Append(JsonS(s)); }
    jb.Append("\n ]\n}\n");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
    File.WriteAllText(outCodes, cb.ToString(), new UTF8Encoding(false));
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
