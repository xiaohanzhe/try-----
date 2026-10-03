using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第85轮取证：Deltarune 侧「移速表 / 跑动 / 互动闸 / 剧情进度标记」相关对象与代码
// 目的：把 I1（Shift 跑）/ I2（暗世界移速）/ I4（myinteract+global.interact）/ I5（onebuffer）
//       / I10（global.plot 剧情标记）五条的依据摊开成可逐字核对的产物。
EnsureDataLoaded();
// ★★ 产物目录（第84轮实测）：CLI 下 `FilePath` 不一定是 .csx 路径
// （可能是 data.win 或空）⇒ 用 __OUTDIR__ 占位符由驱动替换成**绝对路径**，
// 占位符还在就用 Path.GetDirectoryName(FilePath) 兜底。
string dir = @"__OUTDIR__";
if (dir == "__" + "OUTDIR__" || dir.Length == 0)
{
    dir = Path.GetDirectoryName(FilePath);
}
ScriptMessage("OUTDIR=" + dir);
var utf8 = new UTF8Encoding(false);

// ---------- 1. 代码：移速 / 跑动 / 互动闸 / 剧情进度相关 code 原文 ----------
// ★ 关键词收紧到本轮要的五件事，避免产物过大：
//   mainchara（主角移速表/跑动三段）｜interact（互动闸 myinteract/global.interact）
//   buffer（onebuffer/twobuffer/threebuffer 输入缓冲）｜plot（剧情进度计数器）
//   darkzone（光/暗世界判定）｜walkmove/npcwalk（NPC 走路速度，供对照）｜runtimer（跑表）
var sbC = new StringBuilder();
int nCode = 0, nNonEmpty = 0, nGmlOk = 0;
for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;
    string low = nm.ToLowerInvariant();
    bool keep =
        low.Contains("obj_mainchara") || low.Contains("interact") ||
        low.Contains("buffer") || low.Contains("plot") ||
        low.Contains("darkzone") || low.Contains("darkmode") ||
        low.Contains("walkmove") || low.Contains("npcwalk") ||
        low.Contains("runtimer") || low.Contains("susiedark") ||
        low.Contains("doora") || low.Contains("obj_door");
    if (!keep) continue;
    string src = Decomp(c);
    if (src == null) src = "";
    // ★ 真判据 = 产物里能看见真 GML 语法（`if (` / `global.`）。
    //   负控制 = 不含 `pushi.e`（那是反汇编，不是反编译）。
    bool looksGml = src.Contains("if (") || src.Contains("global.");
    if (src.Contains("pushi.e")) looksGml = false;
    if (src.Length > 0) nNonEmpty++;
    if (looksGml) nGmlOk++;
    if (nCode > 0) sbC.Append(",\n");
    sbC.Append("  { \"name\": ").Append(JsonStr(nm));
    sbC.Append(", \"len\": ").Append(src.Length);
    sbC.Append(", \"gml\": ").Append(looksGml ? "true" : "false");
    sbC.Append(", \"src\": ").Append(JsonStr(src));
    sbC.Append("}");
    nCode++;
}
var sbOut = new StringBuilder();
sbOut.Append("{\n \"code_count\": ").Append(nCode);
sbOut.Append(",\n \"nonempty\": ").Append(nNonEmpty);
sbOut.Append(",\n \"gml_ok\": ").Append(nGmlOk);
sbOut.Append(",\n \"codes\": [\n");
sbOut.Append(sbC);
sbOut.Append("\n ]\n}\n");
File.WriteAllText(Path.Combine(dir, "dr85_code.json"), sbOut.ToString(), utf8);

// ---------- 2. 全局变量清单：把 plot / interact / darkzone / flag 等找出来 ----------
// ★ 为什么要它：I10 的锚点是 `global.plot >= 30`，I4 是 `global.interact`。
//   只导出名字与类型，不导出值（值是运行时的事）。
var sbV = new StringBuilder();
int nV = 0;
for (int i = 0; i < Data.Variables.Count; i++)
{
    var v = Data.Variables[i];
    if (v == null || v.Name == null) continue;
    string nm = v.Name.Content;
    string low = nm.ToLowerInvariant();
    bool keep =
        low == "plot" || low.Contains("interact") || low.Contains("darkzone") ||
        low.Contains("facing") || low.Contains("sp") || low.Contains("flag") ||
        low.Contains("menuno") || low.Contains("autrun") || low.Contains("autorun");
    if (!keep) continue;
    if (nV > 0) sbV.Append(",\n");
    // ★ 字段名先探再写（第84轮教训）：`UndertaleVariable` 没有 `VarType`
    //   （实测 CS1061）。这版 UTMT 只有 `InstanceType` / `Name`。
    sbV.Append("  {\"name\": ").Append(JsonStr(nm));
    sbV.Append(", \"instance\": ").Append(JsonStr(v.InstanceType.ToString()));
    sbV.Append("}");
    nV++;
}
File.WriteAllText(Path.Combine(dir, "dr85_globals.json"),
    "{\n \"global_count\": " + nV + ",\n \"globals\": [\n" + sbV.ToString() + "\n ]\n}\n",
    utf8);

// ---------- 3. 字符串表：找"剧情已过""不能附身"这类提示文本（I10 的用户可见面） ----------
// ★ 只找与剧情进度/互动被禁相关的短语，避免整表几万条导出。
var sbS = new StringBuilder();
int nS = 0;
for (int i = 0; i < Data.Strings.Count; i++)
{
    var s = Data.Strings[i];
    if (s == null || s.Content == null) continue;
    string t = s.Content;
    string low = t.ToLowerInvariant();
    bool keep =
        low.Contains("plot") || low.Contains("already") ||
        low.Contains("can't") && (low.Contains("now") || low.Contains("right now"));
    if (!keep) continue;
    if (t.Length > 120) continue;
    if (nS > 0) sbS.Append(",\n");
    sbS.Append("  ").Append(JsonStr(t));
    nS++;
}
File.WriteAllText(Path.Combine(dir, "dr85_strings.json"),
    "{\n \"str_count\": " + nS + ",\n \"strings\": [\n" + sbS.ToString() + "\n ]\n}\n",
    utf8);

ScriptMessage("DR85-EXPORT codes=" + nCode + " nonempty=" + nNonEmpty
    + " gml_ok=" + nGmlOk + " globals=" + nV + " strings=" + nS);

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
