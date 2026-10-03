using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第84轮取证：Deltarune 侧「交互 / 附身 / 操控 / 互动技能」相关对象与代码
// 目的：把"原作该有的互动技能"摊开成可核对的清单。
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

// ---------- 1. 对象清单：把与交互/操控相关的对象全捞出来 ----------
var sb = new StringBuilder();
sb.Append("{\n  \"objects\": [");
int nObj = 0;
for (int i = 0; i < Data.GameObjects.Count; i++)
{
    var o = Data.GameObjects[i];
    if (o == null || o.Name == null) continue;
    string nm = o.Name.Content;
    string low = nm.ToLowerInvariant();
    bool keep =
        low.Contains("interact") || low.Contains("caterpillar") ||
        low.Contains("chara") || low.Contains("heart") || low.Contains("soul") ||
        low.Contains("overworld") || low.Contains("time") ||
        low.Contains("door") || low.Contains("marker") ||
        low.Contains("npc") || low.Contains("talk") ||
        low.Contains("climb") || low.Contains("susie") || low.Contains("ralsei") ||
        low.Contains("lancer") || low.Contains("noelle") || low.Contains("kris");
    if (!keep) continue;
    if (nObj > 0) sb.Append(",");
    string sp = (o.Sprite != null && o.Sprite.Name != null) ? o.Sprite.Name.Content : "";
    string par = (o.ParentId != null && o.ParentId.Name != null)
                  ? o.ParentId.Name.Content : "";
    sb.Append("\n    {\"i\": ").Append(i);
    sb.Append(", \"name\": ").Append(JsonStr(nm));
    sb.Append(", \"sprite\": ").Append(JsonStr(sp));
    sb.Append(", \"parent\": ").Append(JsonStr(par));
    sb.Append(", \"n_events\": ").Append(o.Events != null ? o.Events.Count : 0);
    sb.Append("}");
    nObj++;
}
sb.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "dr_objects.json"), sb.ToString(), utf8);

// ---------- 2. 代码：把所有交互相关 code 原文导出 ----------
var sbC = new StringBuilder();
int nCode = 0, nNonEmpty = 0, nGmlSyntax = 0;
for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;
    string low = nm.ToLowerInvariant();
    bool keep =
        low.Contains("interact") || low.Contains("caterpillar") ||
        low.Contains("chara") || low.Contains("heart") || low.Contains("soul") ||
        low.Contains("overworld") || low.Contains("obj_time") ||
        low.Contains("door") || low.Contains("marker") ||
        low.Contains("climb") || low.Contains("susie") || low.Contains("ralsei") ||
        low.Contains("lancer") || low.Contains("noelle") || low.Contains("kris") ||
        low.Contains("talk") || low.Contains("move");
    if (!keep) continue;
    string src = Decomp(c);
    if (src == null) src = "";
    if (src.Contains("pushi.e")) nGmlSyntax = -1;
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
File.WriteAllText(Path.Combine(dir, "dr_code.json"), sbOut.ToString(), utf8);

// ---------- 3. 脚本名清单（scr_*，用来找"互动技能"的公共函数） ----------
var sbS = new StringBuilder();
int nScr = 0;
for (int i = 0; i < Data.Scripts.Count; i++)
{
    var s = Data.Scripts[i];
    if (s == null || s.Name == null) continue;
    string nm = s.Name.Content;
    string low = nm.ToLowerInvariant();
    bool keep =
        low.Contains("interact") || low.Contains("npc") || low.Contains("talk") ||
        low.Contains("caterpillar") || low.Contains("depth") || low.Contains("chara") ||
        low.Contains("door") || low.Contains("heart") || low.Contains("save") ||
        low.Contains("shop") || low.Contains("item") || low.Contains("menu") ||
        low.Contains("party") || low.Contains("follow") || low.Contains("walk");
    if (!keep) continue;
    if (nScr > 0) sbS.Append(",\n");
    sbS.Append("  ").Append(JsonStr(nm));
    nScr++;
}
File.WriteAllText(Path.Combine(dir, "dr_scripts.json"),
    "{\n \"scripts\": [\n" + sbS.ToString() + "\n ]\n}\n", utf8);

ScriptMessage("DR-EXPORT objects=" + nObj + " codes=" + nCode
    + " nonempty=" + nNonEmpty + " gml_ok=" + (nGmlSyntax == 0)
    + " scripts=" + nScr);

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
