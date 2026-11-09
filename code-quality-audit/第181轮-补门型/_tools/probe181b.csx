// 第181轮 · 补门型取证（之二）：**反编译**版
//
// 与 probe181.csx 的区别：
//   probe181 出的是**原始指令**（逐条 Push/Call），够用来判 room_goto 常量；
//   本脚本出的是**反编译后的 GML 文本**，用来判"目标写在实例变量里"的情况
//   （`obj_shortcut_door` 的 `door_destination`、`obj_climb_door` 的 `doorRoom`）。
//
// 输出（UTF-8 无 BOM，落 P181B_OUT）：
//   A. 名字含 door 的对象事件代码 → 反编译 GML
//   B. 名字含 door 的房间实例 → 坐标 / 物件 / **PreCreateCode 反编译 GML** / Properties
//
// ★ 实例级创建代码挂在 `PreCreateCode`，`CreationCode` 全是 null（第172轮踩过）。
// ★ UTMT 三坑（第171轮）：stdin 须 DEVNULL；本脚本一次 load 全出；产物自己写。
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Decompiler;
using Underanalyzer.Decompiler;

EnsureDataLoaded();

string outJson = Environment.GetEnvironmentVariable("P181B_OUT");
if (String.IsNullOrEmpty(outJson))
{
    Console.WriteLine("probe181b FAILED: 环境变量 P181B_OUT 未设置");
    return;
}

object GO(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

string GS(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    object v = null;
    try { v = p.GetValue(o); } catch (Exception) { return null; }
    return v == null ? null : v.ToString();
}

string ResName(object res)
{
    if (res == null) return null;
    object nv = GO(res, "Name");
    if (nv == null) return null;
    object cv = GO(nv, "Content");
    if (cv != null) return cv.ToString();
    return nv.ToString();
}

string Num(object v)
{
    if (v == null) return "null";
    string s = v.ToString();
    if (s == "NaN" || s == "Infinity" || s == "-Infinity") return "null";
    return s;
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

try
{
    GlobalDecompileContext gd = null;
    try { gd = new GlobalDecompileContext(Data, null); }
    catch (Exception ex) { Console.WriteLine("probe181b WARN: decompile context: " + ex.Message); }

    string TryDecomp(object codeObj)
    {
        if (codeObj == null || gd == null) return null;
        UndertaleCode uc = codeObj as UndertaleCode;
        if (uc == null) return null;
        try { return new DecompileContext(gd, uc, null).DecompileToString(); }
        catch (Exception ex) { return "__DECOMP_FAIL__ " + ex.GetType().Name; }
    }

    var rooms = (IList)GO(Data, "Rooms");
    var roomNames = new List<string>();
    for (int ri = 0; ri < rooms.Count; ri++) roomNames.Add(ResName(rooms[ri]));

    // ---- A. door 对象事件代码（反编译）----
    var codeRows = new List<string>();
    IEnumerable allCode = GO(Data, "Code") as IEnumerable;
    int nCode = 0;
    if (allCode != null)
    {
        foreach (object c in allCode)
        {
            string cn = ResName(c);
            if (String.IsNullOrEmpty(cn)) continue;
            if (cn.ToLowerInvariant().IndexOf("door") < 0) continue;
            nCode++;
            codeRows.Add("  {\"name\": " + JsonS(cn) + ", \"gml\": " + JsonS(TryDecomp(c)) + "}");
        }
    }

    // ---- B. door 实例 ----
    var instRows = new List<string>();
    int nInst = 0, nWithCC = 0;
    for (int ri = 0; ri < rooms.Count; ri++)
    {
        object r = rooms[ri];
        string rn = roomNames[ri];
        IEnumerable layers = GO(r, "Layers") as IEnumerable;
        if (layers == null) continue;
        foreach (object ly in layers)
        {
            object id = GO(ly, "InstancesData");
            if (id == null) continue;
            IEnumerable ins = GO(id, "Instances") as IEnumerable;
            if (ins == null) continue;
            foreach (object it in ins)
            {
                string on = ResName(GO(it, "ObjectDefinition"));
                if (String.IsNullOrEmpty(on)) continue;
                if (on.ToLowerInvariant().IndexOf("door") < 0) continue;
                nInst++;

                object cc = GO(it, "PreCreateCode");
                if (cc == null) cc = GO(it, "CreationCode");
                string ccGml = null;
                if (cc != null) { nWithCC++; ccGml = TryDecomp(cc); }

                var propRows = new List<string>();
                IEnumerable props = GO(it, "Properties") as IEnumerable;
                if (props != null)
                {
                    foreach (object pr in props)
                    {
                        string pn = GS(pr, "Name");
                        string pv = GS(pr, "Value");
                        if (pn == null && pv == null) continue;
                        propRows.Add("{\"name\": " + JsonS(pn) + ", \"value\": " + JsonS(pv) + "}");
                    }
                }

                instRows.Add("  {\"room\": " + JsonS(rn) + ", \"room_index\": " + ri
                    + ", \"x\": " + Num(GO(it, "X")) + ", \"y\": " + Num(GO(it, "Y"))
                    + ", \"obj\": " + JsonS(on)
                    + ", \"instance_id\": " + Num(GO(it, "InstanceID"))
                    + ", \"creation_code\": " + JsonS(ResName(cc))
                    + ", \"creation_gml\": " + JsonS(ccGml)
                    + ", \"props\": [" + String.Join(", ", propRows) + "]}");
            }
        }
    }

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_rooms\": ").Append(rooms.Count).Append(",\n");
    jb.Append("\"n_door_codes\": ").Append(nCode).Append(",\n");
    jb.Append("\"n_door_inst\": ").Append(nInst).Append(",\n");
    jb.Append("\"n_inst_with_cc\": ").Append(nWithCC).Append(",\n");
    var roomRows = new List<string>();
    for (int ri = 0; ri < roomNames.Count; ri++)
        roomRows.Add("  {\"index\": " + ri + ", \"name\": " + JsonS(roomNames[ri]) + "}");
    jb.Append("\"rooms\": [\n").Append(String.Join(",\n", roomRows)).Append("\n],\n");
    jb.Append("\"codes\": [\n").Append(String.Join(",\n", codeRows)).Append("\n],\n");
    jb.Append("\"instances\": [\n").Append(String.Join(",\n", instRows)).Append("\n]\n}\n");

    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("probe181b OK rooms=" + rooms.Count + " codes=" + nCode
        + " inst=" + nInst + " inst_with_cc=" + nWithCC);
    Console.WriteLine("out=" + outJson);
}
catch (Exception ex)
{
    Console.WriteLine("probe181b FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
