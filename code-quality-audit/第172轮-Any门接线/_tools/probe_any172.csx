// 第172轮 · obj_doorAny 探针（**只读**，不改 data.win、不落边）
// 回答三件事：
//   A. obj_doorAny 的**对象级代码**（Create / Alarm_2 / Other_17…）里 doorRoom 怎么来的
//   B. 每扇 Any 门的**实例级创建代码**（room editor 里给的变量覆盖）里有没有 doorRoom = ...
//   C. 有没有前置条件（global 剧情 flag / if(room==N) / 章节判断）
// 输出路径走环境变量 PROBE172_OUT；绝不往 data.win 所在目录写任何东西。
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

string outJson = Environment.GetEnvironmentVariable("PROBE172_OUT");
if (String.IsNullOrEmpty(outJson))
{
    Console.WriteLine("probe172 FAILED: 环境变量 PROBE172_OUT 未设置");
    return;
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

object GO(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
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

string StrC(object s)
{
    if (s == null) return null;
    object cv = GO(s, "Content");
    if (cv != null) return cv.ToString();
    return s.ToString();
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
    // ★ UTMT 0.9.x 的解压入口不是静态 `Decompiler.Decompile`，而是
    //   `new Underanalyzer.Decompiler.DecompileContext(IGameContext, IGMCode, IDecompileSettings).DecompileToString()`。
    //   第二参不是 bool 而是 IGlobalFunctions（旧版签名），传 null 两边都编得过。
    //   已用 test_decomp172.csx 验过：脚本内解压 obj_doorAny_Alarm_2 的输出
    //   与第171轮 CLI `-c` 导出的 4 行**逐字相同**（两条独立路径互证）。
    GlobalDecompileContext gd = null;
    try { gd = new GlobalDecompileContext(Data, null); }
    catch (Exception ex) { Console.WriteLine("probe172 WARN: decompile context 建不起来: " + ex.Message); }

    string TryDecomp(object codeObj)
    {
        if (codeObj == null || gd == null) return null;
        UndertaleCode uc = codeObj as UndertaleCode;
        if (uc == null) return null;
        try { return new DecompileContext(gd, uc, null).DecompileToString(); }
        catch (Exception ex) { return "__DECOMP_FAIL__ " + ex.GetType().Name + ": " + ex.Message; }
    }

    // ---- 房名表（用来校验 doorRoom 落点是真房）----
    var rooms = (IList)GO(Data, "Rooms");
    var roomNames = new List<string>();
    for (int ri = 0; ri < rooms.Count; ri++) roomNames.Add(ResName(rooms[ri]));

    // ---- A. 对象级代码：名字里带 doorany 的 Data.Code ----
    var objRows = new List<string>();
    IEnumerable allCode = GO(Data, "Code") as IEnumerable;
    int nObj = 0;
    if (allCode != null)
    {
        foreach (object c in allCode)
        {
            string cn = ResName(c);
            if (String.IsNullOrEmpty(cn)) continue;
            if (cn.ToLowerInvariant().IndexOf("doorany") < 0) continue;
            nObj++;
            string gml = TryDecomp(c);
            objRows.Add("  {\"name\": " + JsonS(cn) + ", \"gml\": " + JsonS(gml) + "}");
        }
    }

    // ---- B. 实例级 ----
    var instRows = new List<string>();
    var roomCCRows = new List<string>();
    int nInst = 0, nWithCC = 0, nWithProp = 0, nRoomCC = 0;
    var perRoom = new Dictionary<string, int>();
    for (int ri = 0; ri < rooms.Count; ri++)
    {
        object r = rooms[ri];
        string rn = roomNames[ri];
        // 房间级创建代码：Any 门的 doorRoom 也可能在这里用 with(inst) 赋
        object rcc = GO(r, "CreationCode");
        if (rcc != null)
        {
            string rccGml = TryDecomp(rcc);
            if (!String.IsNullOrEmpty(rccGml))
            {
                nRoomCC++;
                roomCCRows.Add("  {\"room\": " + JsonS(rn) + ", \"room_index\": " + ri
                    + ", \"gml\": " + JsonS(rccGml) + "}");
            }
        }
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
                if (on.ToLowerInvariant().IndexOf("doorany") < 0) continue;
                nInst++;
                perRoom[rn] = (perRoom.ContainsKey(rn) ? perRoom[rn] : 0) + 1;

                // ★★★ 实例级创建代码挂在 `PreCreateCode` 上，**不是** `CreationCode`
                //     （CreationCode 全是 null；第172轮踩过这个坑，probe5 打属性表才发现）。
                object cc = GO(it, "PreCreateCode");
                if (cc == null) cc = GO(it, "CreationCode");
                string ccName = ResName(cc);
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
                        nWithProp++;
                        propRows.Add("{\"name\": " + JsonS(pn) + ", \"value\": " + JsonS(pv) + "}");
                    }
                }

                instRows.Add("  {\"room\": " + JsonS(rn) + ", \"room_index\": " + ri
                    + ", \"x\": " + Num(GO(it, "X")) + ", \"y\": " + Num(GO(it, "Y"))
                    + ", \"obj\": " + JsonS(on)
                    + ", \"instance_id\": " + Num(GO(it, "InstanceID"))
                    + ", \"image_index\": " + Num(GO(it, "ImageIndex"))
                    + ", \"image_speed\": " + Num(GO(it, "ImageSpeed"))
                    + ", \"scale_x\": " + Num(GO(it, "ScaleX"))
                    + ", \"scale_y\": " + Num(GO(it, "ScaleY"))
                    + ", \"rotation\": " + Num(GO(it, "Rotation"))
                    + ", \"colour\": " + Num(GO(it, "Color"))
                    + ", \"sprite\": " + JsonS(ResName(GO(it, "Sprite")))
                    + ", \"creation_code\": " + JsonS(ccName)
                    + ", \"creation_gml\": " + JsonS(ccGml)
                    + ", \"props\": [" + String.Join(", ", propRows) + "]}");
            }
        }
    }

    // ---- C. 关键词：这些门的对象代码里出现过哪些"条件/flag"迹象 ----
    //     不判对错，只把证据交出来（Python 侧分类）。
    // ---- C. 常量：Step_0 里 doorRoom = room ± {ROOM_INITIALIZE,...}，这些必须解出真值 ----
    var macroRows = new List<string>();
    int nMacro = 0;
    IEnumerable mcs = GO(Data, "Macros") as IEnumerable;
    if (mcs != null)
    {
        foreach (object m in mcs)
        {
            nMacro++;
            string mn = ResName(m);
            string mv = StrC(GO(m, "Value"));
            string ml = (mn == null ? "" : mn.ToLowerInvariant());
            if (ml.IndexOf("room_initialize") < 0 && ml.IndexOf("room_title_placeholder") < 0
                && ml.IndexOf("room_battletest") < 0) continue;
            macroRows.Add("  {\"name\": " + JsonS(mn) + ", \"value\": " + JsonS(mv) + "}");
        }
    }

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_rooms\": ").Append(rooms.Count).Append(",\n");
    jb.Append("\"n_obj_codes\": ").Append(nObj).Append(",\n");
    jb.Append("\"n_inst\": ").Append(nInst).Append(",\n");
    jb.Append("\"n_inst_with_creation_code\": ").Append(nWithCC).Append(",\n");
    jb.Append("\"n_inst_props\": ").Append(nWithProp).Append(",\n");
    jb.Append("\"n_room_cc\": ").Append(nRoomCC).Append(",\n");
    jb.Append("\"n_macros\": ").Append(nMacro).Append(",\n");
    var roomRows2 = new List<string>();
    for (int ri = 0; ri < roomNames.Count; ri++)
        roomRows2.Add("  {\"index\": " + ri + ", \"name\": " + JsonS(roomNames[ri]) + "}");
    jb.Append("\"rooms\": [\n").Append(String.Join(",\n", roomRows2)).Append("\n],\n");
    var roomRows = new List<string>();
    foreach (KeyValuePair<string, int> kv in perRoom)
        roomRows.Add("  " + JsonS(kv.Key) + ": " + kv.Value);
    jb.Append("\"per_room\": {\n").Append(String.Join(",\n", roomRows)).Append("\n},\n");
    jb.Append("\"obj_codes\": [\n").Append(String.Join(",\n", objRows)).Append("\n],\n");
    jb.Append("\"room_cc\": [\n").Append(String.Join(",\n", roomCCRows)).Append("\n],\n");
    jb.Append("\"macros\": [\n").Append(String.Join(",\n", macroRows)).Append("\n],\n");
    jb.Append("\"instances\": [\n").Append(String.Join(",\n", instRows)).Append("\n]\n}\n");

    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("probe172 OK  rooms=" + rooms.Count + " obj_codes=" + nObj
        + " inst=" + nInst + " with_cc=" + nWithCC + " props=" + nWithProp
        + " room_cc=" + nRoomCC + " macros=" + nMacro
        + " rooms_with_any=" + perRoom.Count);
    Console.WriteLine("out=" + outJson);
}
catch (Exception ex)
{
    Console.WriteLine("probe172 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
