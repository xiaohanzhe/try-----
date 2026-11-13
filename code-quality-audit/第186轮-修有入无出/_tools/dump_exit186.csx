using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第186轮取证：ch1 那 5 间「有入无出」的房里，出口到底由谁写。
// 用途：3 间没有门对象的房（cc_fountain / alphysclass / dark_chase2），
//       出门只能靠房内某个对象的 Step/Alarm/Create 里那句 room_goto。
// 做法：只反编译「这几间房里摆着的对象」的事件代码（按对象名前缀筛），不做全量反编译。
EnsureDataLoaded();

string dir = @"__OUTDIR__";
if (dir == "__" + "OUTDIR__" || dir.Length == 0)
{
    dir = Path.GetDirectoryName(FilePath);
}
var utf8 = new UTF8Encoding(false);

// 3 间房里出现的对象（来自 115 轮 rooms_map 的 layer.instances，原样抄）
var wantObjs = new List<string>();
wantObjs.Add("obj_fountainkris");
wantObjs.Add("obj_darkfountain");
wantObjs.Add("obj_classscene");
wantObjs.Add("obj_alphysdesk");
wantObjs.Add("obj_tem_school");
wantObjs.Add("obj_npc_facing");
wantObjs.Add("obj_overworldc");
wantObjs.Add("obj_darkcontroller");
wantObjs.Add("obj_lancerslideevent");
wantObjs.Add("obj_readable_room1");
wantObjs.Add("obj_mainchara");
wantObjs.Add("obj_markerA");

// 三个目标房名：命中即为「谁提到这间房」
var wantRooms = new List<string>();
wantRooms.Add("room_cc_fountain");
wantRooms.Add("room_alphysclass");
wantRooms.Add("room_dark_chase2");

var sb = new StringBuilder();
int nHit = 0, nGml = 0, nRoomHit = 0;

// ★ 关键：`GlobalDecompileContext` 与 `CodeImportGroup` **只建一次**。
//   旧写法（109 轮那个）是"每条代码都新建一次上下文"，64 条还能忍，
//   这里要遍历全表 + 命中上百条，那样会慢到不可用。
MethodInfo MI = null;
object IMP = null;
SetupDecompiler();
Console.WriteLine("decompiler ready, code_total=" + Data.Code.Count);
Console.Out.Flush();

for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;

    bool byObj = false;
    foreach (string o in wantObjs)
    {
        if (nm.Contains("_" + o + "_") || nm.EndsWith("_" + o)) { byObj = true; break; }
    }
    if (!byObj) continue;

    string src = Decomp(c);
    if (src == null) src = "";
    bool looksGml = src.Contains("if (") || src.Contains("room_goto")
                    || src.Contains("global.") || src.Contains("instance_create");
    if (src.Contains("pushi.e")) looksGml = false;
    if (looksGml) nGml++;
    bool roomHit = false;
    foreach (string r in wantRooms)
    {
        if (src.Contains(r)) { roomHit = true; break; }
    }
    if (roomHit) nRoomHit++;

    if (nHit > 0) sb.Append(",\n");
    sb.Append("  { \"name\": ").Append(JsonStr(nm));
    sb.Append(", \"len\": ").Append(src.Length);
    sb.Append(", \"gml\": ").Append(looksGml ? "true" : "false");
    sb.Append(", \"room_hit\": ").Append(roomHit ? "true" : "false");
    sb.Append(", \"src\": ").Append(JsonStr(src));
    sb.Append("}");
    nHit++;
    if (nHit % 10 == 0)
    {
        Console.WriteLine("  hit=" + nHit + "  " + nm);
        Console.Out.Flush();
    }
}

File.WriteAllText(Path.Combine(dir, "exit_codes186.json"),
    "{\n \"code_total\": " + Data.Code.Count + ",\n \"hit\": " + nHit
    + ",\n \"gml_ok\": " + nGml + ",\n \"room_hit\": " + nRoomHit
    + ",\n \"codes\": [\n" + sb.ToString() + "\n ]\n}\n", utf8);

ScriptMessage("R186-EXPORT total=" + Data.Code.Count + " hit=" + nHit
    + " gml=" + nGml + " roomHit=" + nRoomHit);

void SetupDecompiler()
{
    Type t = null;
    foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
    {
        t = a.GetType("UndertaleModLib.Compiler.CodeImportGroup");
        if (t != null) break;
    }
    if (t == null) { MI = null; IMP = null; return; }

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
    if (MI == null || IMP == null) return "<NO-DECOMPILER>";
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
