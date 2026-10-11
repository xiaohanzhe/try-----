using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第109轮补（b）：Deltarune ch1 的「门」实现取证。
// 用户口径：「门是在原作每个场景对应的触发点的」「那个字母到时候隐藏掉」
//           「门就用三角符文里那个任意门就好」
// ⇒ 要看清：① obj_doorparent / obj_door<字母> 的绘制逻辑（字母从哪来、怎么藏）
//            ② obj_darkdoor（黑暗之门 = "任意门"）的形态
//            ③ obj_marker<字母> 与门的关系（markers 是不是另一套）
EnsureDataLoaded();

string dir = @"__OUTDIR__";
if (dir == "__" + "OUTDIR__" || dir.Length == 0)
{
    dir = Path.GetDirectoryName(FilePath);
}
var utf8 = new UTF8Encoding(false);

var wantNames = new List<string>();
wantNames.Add("obj_doorparent");
wantNames.Add("obj_doorA");
wantNames.Add("obj_doorB");
wantNames.Add("obj_doorE");
wantNames.Add("obj_doorX");
wantNames.Add("obj_darkdoor");
wantNames.Add("obj_darkdoorevent");
wantNames.Add("obj_shortcut_door");
wantNames.Add("obj_marker");
wantNames.Add("obj_markerA");
wantNames.Add("obj_markerX");
wantNames.Add("obj_marker2");

// ---------- 1. 所有含 door / marker 的 code（事件级反编译）----------
var sbC = new StringBuilder();
int nCode = 0, nGml = 0;
for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;
    string low = nm.ToLowerInvariant();
    if (!low.Contains("door") && !low.Contains("marker")) continue;
    string src = Decomp(c);
    if (src == null) src = "";
    bool looksGml = src.Contains("if (") || src.Contains("global.")
                    || src.Contains("draw_") || src.Contains("image_");
    if (src.Contains("pushi.e")) looksGml = false;
    if (looksGml) nGml++;
    if (nCode > 0) sbC.Append(",\n");
    sbC.Append("  { \"name\": ").Append(JsonStr(nm));
    sbC.Append(", \"len\": ").Append(src.Length);
    sbC.Append(", \"gml\": ").Append(looksGml ? "true" : "false");
    sbC.Append(", \"src\": ").Append(JsonStr(src));
    sbC.Append("}");
    nCode++;
}
File.WriteAllText(Path.Combine(dir, "door_codes109b.json"),
    "{\n \"code_count\": " + nCode + ",\n \"gml_ok\": " + nGml
    + ",\n \"codes\": [\n" + sbC.ToString() + "\n ]\n}\n", utf8);

// ---------- 2. 对象元信息（只取确定字段，不碰 EventHandler）----------
var sbO = new StringBuilder();
int nObj = 0;
var got = new List<string>();
for (int i = 0; i < Data.GameObjects.Count; i++)
{
    var o = Data.GameObjects[i];
    if (o == null || o.Name == null) continue;
    string nm = o.Name.Content;
    if (!wantNames.Contains(nm)) continue;
    got.Add(nm);
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
File.WriteAllText(Path.Combine(dir, "door_objs109b.json"),
    "{\n \"obj_count\": " + nObj + ",\n \"objects\": [\n" + sbO.ToString()
    + "\n ]\n}\n", utf8);

// ---------- 3. 精灵元信息（spr_door*/spr_marker*/spr_darkdoor）----------
var sbS = new StringBuilder();
int nSpr = 0;
for (int i = 0; i < Data.Sprites.Count; i++)
{
    var sp = Data.Sprites[i];
    if (sp == null || sp.Name == null) continue;
    string nm = sp.Name.Content;
    string low = nm.ToLowerInvariant();
    if (!low.Contains("door") && !low.Contains("marker")) continue;
    int w = 0, h = 0;
    try {
        w = (int)sp.Width; h = (int)sp.Height;
    } catch (Exception) { }
    if (nSpr > 0) sbS.Append(",\n");
    sbS.Append("  { \"name\": ").Append(JsonStr(nm));
    sbS.Append(", \"w\": ").Append(w).Append(", \"h\": ").Append(h);
    sbS.Append(", \"frames\": ").Append(sp.Textures == null ? 0 : sp.Textures.Count);
    sbS.Append("}");
    nSpr++;
}
File.WriteAllText(Path.Combine(dir, "door_sprites109b.json"),
    "{\n \"spr_count\": " + nSpr + ",\n \"sprites\": [\n" + sbS.ToString()
    + "\n ]\n}\n", utf8);

ScriptMessage("DR109B-EXPORT codes=" + nCode + " gml=" + nGml
    + " objs=" + nObj + " sprs=" + nSpr);

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
