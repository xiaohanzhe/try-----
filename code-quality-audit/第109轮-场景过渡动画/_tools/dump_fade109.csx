using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第109轮取证：Deltarune ch1 的「场景过渡（fade out / fade in）」实现。
//
// 目的：用户口径「进入场景的时候按原作有过度动画」。第85轮已抓到**调用端**
//   （门对象 Other_19: instance_create(0,0,obj_fadeout); alarm[2]=8;
//           Alarm_2: instance_create(0,0,obj_persistentfadein); room_goto_next();）
//   但**没抓到 obj_fadeout / obj_persistentfadein 自身的实现**。
//   本轮补上：把这两个对象（及其 fade 家族）的**每个事件**反编译成可逐字核对的产物。
//
// ★ 判据（自证）：
//   - 必须出现真 GML（`if (` / `global.` / `alpha` / `draw_`），不是反汇编（`pushi.e`）。
//   - 负控制：产物里必须**至少有 1 条**含 `obj_fadeout` 或 `obj_persistentfadein` 的 name。
//   - 若某对象不存在，如实记 `found=false`（**不假装**）。
EnsureDataLoaded();

string dir = @"__OUTDIR__";
if (dir == "__" + "OUTDIR__" || dir.Length == 0)
{
    dir = Path.GetDirectoryName(FilePath);
}
ScriptMessage("OUTDIR=" + dir);
var utf8 = new UTF8Encoding(false);

// ---------- 1. 所有名字含 fade 的 code（事件级）----------
var sbC = new StringBuilder();
int nCode = 0, nGml = 0;
var fadeNames = new List<string>();
for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;
    string low = nm.ToLowerInvariant();
    // ★ 既抓 `fade`（光世界/通用门过渡），也抓 `dw_transition`（暗世界换房过渡）
    //   —— 后者是 scene_controller.switch() docstring 已点名的原作对象
    //   （"剪影走门 + 音高 0.1→1.0"）。漏掉它就会得出"原作只有 fade"的错结论。
    if (!low.Contains("fade") && !low.Contains("dw_transition")
        && !low.Contains("transition")) continue;
    string src = Decomp(c);
    if (src == null) src = "";
    bool looksGml = src.Contains("if (") || src.Contains("global.")
                    || src.Contains("alpha") || src.Contains("draw_");
    if (src.Contains("pushi.e")) looksGml = false;
    if (looksGml) nGml++;
    if (nCode > 0) sbC.Append(",\n");
    sbC.Append("  { \"name\": ").Append(JsonStr(nm));
    sbC.Append(", \"len\": ").Append(src.Length);
    sbC.Append(", \"gml\": ").Append(looksGml ? "true" : "false");
    sbC.Append(", \"src\": ").Append(JsonStr(src));
    sbC.Append("}");
    fadeNames.Add(nm);
    nCode++;
}
File.WriteAllText(Path.Combine(dir, "fade_codes.json"),
    "{\n \"code_count\": " + nCode + ",\n \"gml_ok\": " + nGml
    + ",\n \"codes\": [\n" + sbC.ToString() + "\n ]\n}\n", utf8);

// ---------- 2. 对象表：obj_fadeout / obj_persistentfadein 等的元信息 ----------
// ★ 只取**确定可用的字段**（第61轮实测 `Data.GameObjects` + `Name/Sprite/Depth/Visible/Persistent`）；
//   `o.EventHandler` 的遍历 API 易错（字段名随版本变），而**事件与 code 的对应关系
//   已能由 code 名重建**（`gml_Object_obj_fadeout_Draw_0` ⇒ 对象 obj_fadeout 的 Draw_0），
//   ⇒ 不碰 EventHandler，避开"字段名猜错 ⇒ 整个脚本编译失败"。
var sbO = new StringBuilder();
int nObj = 0;
var wantObj = new List<string>();
for (int i = 0; i < Data.GameObjects.Count; i++)
{
    var o = Data.GameObjects[i];
    if (o == null || o.Name == null) continue;
    string nm = o.Name.Content;
    string low = nm.ToLowerInvariant();
    bool keep = low.Contains("fade") || low.Contains("transition");
    if (!keep) continue;
    wantObj.Add(nm);
    if (nObj > 0) sbO.Append(",\n");
    sbO.Append("  { \"name\": ").Append(JsonStr(nm));
    sbO.Append(", \"sprite\": ").Append(JsonStr(
        (o.Sprite != null && o.Sprite.Name != null) ? o.Sprite.Name.Content : ""));
    sbO.Append(", \"visible\": ").Append(o.Visible ? "true" : "false");
    sbO.Append(", \"persistent\": ").Append(o.Persistent ? "true" : "false");
    sbO.Append(", \"depth\": ").Append(o.Depth);
    sbO.Append("}");
    nObj++;
}
File.WriteAllText(Path.Combine(dir, "fade_objects.json"),
    "{\n \"obj_count\": " + nObj + ",\n \"objects\": [\n" + sbO.ToString()
    + "\n ]\n}\n", utf8);

ScriptMessage("DR109-EXPORT codes=" + nCode + " gml=" + nGml
    + " objs=" + nObj + " (" + string.Join(",", wantObj.ToArray()) + ")");

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
