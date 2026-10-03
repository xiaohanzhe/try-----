using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第82轮 R5 取证：UT 侧「灵魂 / 操控 / 附身」相关对象与代码
// 目的：从原作 data 里检出 overworld 控制器、heart/hero 对象及其事件代码。
EnsureDataLoaded();
string dir = Path.GetDirectoryName(FilePath);
var utf8 = new UTF8Encoding(false);

var sb = new StringBuilder();
sb.Append("{\n  \"objects\": [");
int nObj = 0;
for (int i = 0; i < Data.GameObjects.Count; i++)
{
    var o = Data.GameObjects[i];
    if (o == null || o.Name == null) continue;
    string nm = o.Name.Content;
    string low = nm.ToLowerInvariant();
    // 只留与"灵魂/主角/操控/交互"相关的对象
    bool keep =
        low.Contains("heart") || low.Contains("hero") || low.Contains("soul") ||
        low.Contains("controller") || low.Contains("obj_chara") ||
        low.Contains("obj_mainchara") || low.Contains("interact") ||
        low.Contains("friskmove") || low.Contains("overworld") ||
        low.Contains("obj_door") || low.Contains("obj_move");
    if (!keep) continue;
    if (nObj > 0) sb.Append(",");
    string sp = (o.Sprite != null && o.Sprite.Name != null) ? o.Sprite.Name.Content : "";
    sb.Append("\n    {\"i\": ").Append(i);
    sb.Append(", \"name\": ").Append(JsonStr(nm));
    sb.Append(", \"sprite\": ").Append(JsonStr(sp));
    int nev = (o.Events != null) ? o.Events.Count : 0;
    sb.Append(", \"n_events\": ").Append(nev);
    sb.Append("}");
    nObj++;
}
sb.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_r5_objects.json"), sb.ToString(), utf8);

// ---- 代码：把所有名字命中上面关键词的 code 条目原文导出 ----
var sbC = new StringBuilder();
int nCode = 0;
int nNonEmpty = 0;
int nGmlSyntax = 0;
for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;
    string low = nm.ToLowerInvariant();
    bool keep =
        low.Contains("heart") || low.Contains("hero") ||
        low.Contains("soul") || low.Contains("overworld") ||
        low.Contains("mainchara") || low.Contains("chara") ||
        low.Contains("moveheart") || low.Contains("interact") ||
        low.Contains("friskmove") || low.Contains("door");
    if (!keep) continue;
    string src = Decomp(c);
    if (src == null) src = "";
    // ★ 真判据（防"提取成功但内容不是 GML"）：产物里必须出现 GML 语法特征。
    if (src.IndexOf("pushi.e", StringComparison.Ordinal) >= 0) nGmlSyntax = -1;
    if (src.Length > 0) nNonEmpty++;
    if (nCode > 0) sbC.Append(",\n");
    sbC.Append("  { \"name\": ").Append(JsonStr(nm));
    sbC.Append(", \"len\": ").Append(src.Length);
    sbC.Append(", \"src\": ").Append(JsonStr(src));
    sbC.Append("}");
    nCode++;
}
var sbOut = new StringBuilder();
sbOut.Append("{\n \"code_count\": ").Append(nCode).Append(",\n \"codes\": [\n");
sbOut.Append(sbC);
sbOut.Append("\n ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_r5_code.json"), sbOut.ToString(), utf8);

ScriptMessage("R5-EXPORT-OK objects=" + nObj + " codes=" + nCode
    + " nonempty=" + nNonEmpty + " gml_ok=" + (nGmlSyntax == 0));

// ★★ 反编译（不是反汇编）：本版 UTMT 的唯一反编译入口是
//   `UndertaleModLib.Compiler.CodeImportGroup.DecompileExistingCode(UndertaleCode)`
//   —— **nonPUBLIC 实例方法**，全程序集扫描才找到（第82轮实测）。
//   ★ 真实命名空间是 `.Compiler`（不是 `.Project`）；构造器要 3 个参数：
//     `(UndertaleData, GlobalDecompileContext, IDecompileSettings)`。
//   ★★★ 这一路踩了 3 个坑（全记下来）：
//     ① `UndertaleCode` **没有**实例 `Disassemble` ⇒ 旧反射 foreach 一次都不进
//        循环 ⇒ 静默返回 null ⇒ 469 段**全空**，而 rc=0「看起来成功」；
//     ② `Disassembler.Disassemble(...)` 存在，但输出**字节码汇编**
//        （`: [0] pushglb.v global.asp`），不是 GML —— 当"原作代码"没法读；
//     ③ 命名空间猜错（`.Project`）⇒ `<NO-CodeImportGroup>`。
//   ⇒ 真判据：产物里出现 `if (` / `global.` 这类 **GML 语法**，而不是 `pushi.e`。
string Decomp(UndertaleCode c)
{
    try
    {
        Type t = null;
        foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
        {
            t = a.GetType("UndertaleModLib.Compiler.CodeImportGroup");
            if (t != null) break;
        }
        if (t == null) return "<NO-CodeImportGroup>";
        MethodInfo mi = null;
        foreach (MethodInfo m in t.GetMethods(
                BindingFlags.Public | BindingFlags.NonPublic |
                BindingFlags.Instance | BindingFlags.DeclaredOnly))
        {
            if (m.Name == "DecompileExistingCode") { mi = m; break; }
        }
        if (mi == null) return "<NO-DecompileExistingCode>";
        // 构造：先建 GlobalDecompileContext(data, null)，settings 传 null
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
        object inst = null;
        foreach (ConstructorInfo ci in t.GetConstructors(
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
        {
            ParameterInfo[] ps = ci.GetParameters();
            if (ps.Length != 3) continue;
            if (ps[0].ParameterType.Name != "UndertaleData") continue;
            try { inst = ci.Invoke(new object[] { Data, gdc, null }); } catch (Exception) { }
            if (inst != null) break;
        }
        if (inst == null) return "<NO-CTOR>";
        object r = mi.Invoke(inst, new object[] { c });
        string s = (r == null) ? "" : r.ToString();
        if (s.Length > 0) return s;
        // 反编译返回空 ⇒ 退回反汇编（宁可给字节码，也不要空）
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
