using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第186轮取证 c：把 ch1 的**全部**代码段落盘到临时区（不进仓库），
// 之后本地随便 grep，省得为每个猜测重跑一次 UTMT。
EnsureDataLoaded();

string dir = @"__OUTDIR__";
var utf8 = new UTF8Encoding(false);

MethodInfo MI = null;
object IMP = null;
SetupDecompiler();
Console.WriteLine("ready, code_total=" + Data.Code.Count);
Console.Out.Flush();

var sb = new StringBuilder();
int n = 0;
for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;
    string src = Decomp(c);
    if (src == null) src = "";
    if (n > 0) sb.Append(",\n");
    sb.Append("  { \"name\": ").Append(JsonStr(nm));
    sb.Append(", \"len\": ").Append(src.Length);
    sb.Append(", \"src\": ").Append(JsonStr(src));
    sb.Append("}");
    n++;
    if (n % 200 == 0)
    {
        Console.WriteLine("  n=" + n);
        Console.Out.Flush();
    }
}

File.WriteAllText(Path.Combine(dir, "all_codes186.json"),
    "{\n \"code_total\": " + n + ",\n \"codes\": [\n" + sb.ToString() + "\n ]\n}\n", utf8);

ScriptMessage("R186-ALL n=" + n);

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
        // ★ 第186轮：反编译失败就**退回反汇编**，别把整段丢掉。
        //   第一版直接返回 "<DECOMP-FAIL: …>"，1680 段里丢了 387 段（23%），
        //   差点据此得出"cc_fountain 没有任何出口代码"的错误结论。
        try
        {
            return UndertaleModLib.Decompiler.Disassembler.Disassemble(c, null, null, true);
        }
        catch (Exception)
        {
            return "<DECOMP-FAIL: " + e.Message + ">";
        }
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
