// dump_doors123.csx —— UT 的**全部 door 对象事件代码**（反编译文本）
// 用法：UndertaleModCli.exe load <game.droid 副本> -s dump_doors123.csx
// 输出：<数据文件同目录>/door_codes123.json（UTF-8 无 BOM）
//
// 为什么需要它（第123轮）：
//   第122轮的 110 条对象级路由只覆盖 `obj_door_ruins13` / `obj_door_s_musfade` /
//   `obj_door_t/u/v/w` / `obj_doorXmusicfade` 这类"在 Alarm 里写死 `if (room == X)
//   room_goto(Y)`"的门。剩下 751 个实例是 `obj_doorB`(321) / `obj_doorBmusicfade`(113) /
//   `obj_doorAmusicfade`(101) / `obj_doorCmusicfade` / `obj_doorDmusicfade` /
//   `obj_elevatordoor`(13) —— 它们在 `conn_ut.json`（全量 8,120 个 code 的 room_goto 扫描）
//   里**一条都没有** ⇒ 它们根本不靠 `room_goto` 换房。
//   ⇒ 必须把它们自己的事件代码整段反编译出来，看真正的机制是什么（父对象 / 变量 /
//      实例 Creation Code / 还是 `room_goto_next` 但写在别处）。
//
// ★ 反编译走第109轮的反射配方（`CodeImportGroup.DecompileExistingCode`；
//   拿不到就退回 `Disassembler.Disassemble`），踩过的坑不再重踩。
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
var utf8 = new UTF8Encoding(false);

var sb = new StringBuilder();
int nCode = 0, nGml = 0, nFail = 0;
var byPrefix = new Dictionary<string, int>();

for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;
    if (nm == null) continue;
    string low = nm.ToLowerInvariant();
    // 门相关的都取：door 字样（含 elevatordoor / demodoorA / coredoor）
    if (!low.Contains("door")) continue;

    string src = Decomp(c);
    bool looksGml = !(src == null || src.Length == 0
                      || src.StartsWith("<")           // <NO-...> / <DECOMP-FAIL: ...>
                      || src.Contains("pushi.e"));
    if (!looksGml) nFail++; else nGml++;

    if (nCode > 0) sb.Append(",\n");
    sb.Append("  { \"name\": ").Append(JsonStr(nm));
    sb.Append(", \"len\": ").Append(src == null ? 0 : src.Length);
    sb.Append(", \"gml\": ").Append(looksGml ? "true" : "false");
    sb.Append(", \"src\": ").Append(JsonStr(src == null ? "" : src));
    sb.Append("}");
    nCode++;
}

File.WriteAllText(Path.Combine(dir, "door_codes123.json"),
    "{\n \"source\": " + JsonStr(FilePath)
    + ",\n \"code_count\": " + nCode
    + ",\n \"gml_ok\": " + nGml
    + ",\n \"not_gml\": " + nFail
    + ",\n \"codes\": [\n" + sb.ToString() + "\n ]\n}\n", utf8);

// ---------- 对象元数据（★ 必须带 Parent）----------
// 为什么：`obj_doorBmusicfade` / `obj_doorAmusicfade` **自己没有 Alarm_2** ——
// 它们的换房逻辑从父对象继承（PreCreate 里 `event_inherited()` 就是证据）。
// 不查父链就会把"继承来的 −1/+1"当成"没有机制"，从而少写一大批门。
var sbO = new StringBuilder();
int nObj = 0, nWithParent = 0;
for (int i = 0; i < Data.GameObjects.Count; i++)
{
    var o = Data.GameObjects[i];
    if (o == null || o.Name == null) continue;
    string nm = o.Name.Content;
    if (nm == null || !nm.ToLowerInvariant().Contains("door")) continue;
    string pn = "";
    try
    {
        if (o.ParentId != null && o.ParentId.Name != null) pn = o.ParentId.Name.Content;
    }
    catch (Exception) { }
    if (pn.Length > 0) nWithParent++;
    if (nObj > 0) sbO.Append(",\n");
    sbO.Append("  { \"name\": ").Append(JsonStr(nm));
    sbO.Append(", \"parent\": ").Append(JsonStr(pn));
    sbO.Append(", \"sprite\": ").Append(JsonStr(
        (o.Sprite != null && o.Sprite.Name != null) ? o.Sprite.Name.Content : ""));
    sbO.Append(", \"visible\": ").Append(o.Visible ? "true" : "false");
    sbO.Append(", \"persistent\": ").Append(o.Persistent ? "true" : "false");
    sbO.Append(", \"depth\": ").Append(o.Depth);
    sbO.Append("}");
    nObj++;
}
File.WriteAllText(Path.Combine(dir, "door_objects123.json"),
    "{\n \"obj_count\": " + nObj
    + ",\n \"with_parent\": " + nWithParent
    + ",\n \"objects\": [\n" + sbO.ToString() + "\n ]\n}\n", utf8);

ScriptMessage("DR123-EXPORT codes=" + nCode + " gml=" + nGml + " notgml=" + nFail
    + " objs=" + nObj + " withparent=" + nWithParent);

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
