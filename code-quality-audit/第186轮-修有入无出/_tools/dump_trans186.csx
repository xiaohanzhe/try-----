using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第186轮取证 b：**全量扫**所有含换房调用的代码段（obj / script 都算）。
// 目的：3 间没有门对象的房（cc_fountain / alphysclass / dark_chase2）出口到底谁写。
// 上一版只按"房里摆着的对象"筛，49 段里几乎没有 room_goto ⇒ 出口不在房内对象的事件里。
EnsureDataLoaded();

string dir = @"__OUTDIR__";
if (dir == "__" + "OUTDIR__" || dir.Length == 0)
{
    dir = Path.GetDirectoryName(FilePath);
}
var utf8 = new UTF8Encoding(false);

MethodInfo MI = null;
object IMP = null;
SetupDecompiler();
Console.WriteLine("ready, code_total=" + Data.Code.Count);
Console.Out.Flush();

var sb = new StringBuilder();
int nHit = 0, nGoto = 0;

for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;

    // 先把明显无关的便宜挡掉：名字里连 room/script 都不用管，直接全反编译再判内容。
    string src = Decomp(c);
    if (src == null) src = "";
    if (!src.Contains("room_goto") && !src.Contains("room_restart")) continue;

    if (src.Contains("room_goto")) nGoto++;

    if (nHit > 0) sb.Append(",\n");
    sb.Append("  { \"name\": ").Append(JsonStr(nm));
    sb.Append(", \"len\": ").Append(src.Length);
    sb.Append(", \"src\": ").Append(JsonStr(src));
    sb.Append("}");
    nHit++;
    if (nHit % 25 == 0)
    {
        Console.WriteLine("  hit=" + nHit + "  " + nm);
        Console.Out.Flush();
    }
}

File.WriteAllText(Path.Combine(dir, "trans_codes186.json"),
    "{\n \"code_total\": " + Data.Code.Count + ",\n \"hit\": " + nHit
    + ",\n \"with_room_goto\": " + nGoto
    + ",\n \"codes\": [\n" + sb.ToString() + "\n ]\n}\n", utf8);

ScriptMessage("R186-TRANS total=" + Data.Code.Count + " hit=" + nHit
    + " withGoto=" + nGoto);

void SetupDecompiler()
{
    Type t = null;
    foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
    {
        t = a.GetType("UndertaleModLib.Compiler.CodeImportGroup");
        if (t != null) break;
    }
    if (t == null) return;
    foreach (MethodInfo m in t.GetMethods(
            BindingFlags.Public | BindingFlags.NonPublic |
            BindingFlags.Instance | BindingFlags.DeclaredOnly))
    {
        if (m.Name == "DecompileExistingCode") { MI = m; break; }
    }
    if (MI == null) return;
    Type gdcT = null;
    foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
    {
        gdcT = a.GetType("UndertaleModLib.Decompiler.GlobalDecompileContext");
        if (gdcT != null) break;
    }
    object gdc = null;
    if (gdcT != null)
    {
        foreach (ConstructorInfo ci in gdcT.GetConstructors(
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
        {
            ParameterInfo[] ps = ci.GetParameters();
            if (ps.Length != 2) continue;
            if (ps[0].ParameterType.Name != "UndertaleData") continue;
            try { gdc = ci.Invoke(new object[] { Data, null }); } catch (Exception) { }
            if (gdc != null) break;
        }
    }
    foreach (ConstructorInfo ci in t.GetConstructors(
            BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
    {
        ParameterInfo[] ps = ci.GetParameters();
        if (ps.Length != 3) continue;
        if (ps[0].ParameterType.Name != "UndertaleData") continue;
        try { IMP = ci.Invoke(new object[] { Data, gdc, null }); } catch (Exception) { }
        if (IMP != null) break;
    }
}

string Decomp(UndertaleCode c)
{
    if (MI == null || IMP == null) return "";
    try
    {
        object r = MI.Invoke(IMP, new object[] { c });
        string s = (r == null) ? "" : r.ToString();
        if (s.Length > 0) return s;
        return UndertaleModLib.Decompiler.Disassembler.Disassemble(c, null, null, true);
    }
    catch (Exception e)
    {
        return "<DECOMP-FAIL: " + e.Message + ">";
    }
}

string JsonStr(string s)
{
    if (s == null) return "null";
    var b = new StringBuilder("\"");
    foreach (char ch in s)
    {
        if (ch == '"') b.Append("\\\"");
        else if (ch == '\\') b.Append("\\\\");
        else if (ch == '\n') b.Append("\\n");
        else if (ch == '\r') b.Append("\\r");
        else if (ch == '\t') b.Append("\\t");
        else if (ch < 32) b.Append("\\u").Append(((int)ch).ToString("x4"));
        else b.Append(ch);
    }
    b.Append("\"");
    return b.ToString();
}
