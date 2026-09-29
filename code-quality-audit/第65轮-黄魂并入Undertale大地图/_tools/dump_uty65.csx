using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

// ============================================================================
// 第65轮 · 黄魂（Undertale Yellow）门实例 + 门对象代码 转储  (v2)
//
// 为什么必须重跑：第61轮只抓了 room 的 layer 元数据（0 个实例），
// 而 Undertale 侧拓扑（第63轮 ut_topology63.json）是靠 UTMT 实例转储建的
// ⇒ 黄魂要并入同一张大地图，缺的正是"门实例 + 门对象代码"。
//
// v1 编译失败（Data.Objects 不存在）⇒ v2 三处修正，均以既有可用脚本为准：
//   ① 枚举对象用 `Data.GameObjects`（第61/64轮 csx 实测可用）；
//   ② 取事件代码**不走 Events/Actions**，改为"先列全部 code 名，再按对象名做子串命中"
//      （第64轮 dump_ghost64.csx 证明 `Data.Code.ByName` 可靠；少一个 API 假设就少一处风险）；
//   ③ 实例仍用反射读 ObjectDefinition（第63轮 dump_instances63.csx 实测可用）。
//
// ★★ 铁律：UTMT CLI 的 stdout 必须是文件（PIPE 会崩/挂）；由 run_dump65.py 负责。
//
// 输出（目录取自环境变量 R65_OUT，缺省 = datafile 同级的 r65/）：
//   r65_rooms.json     房间表（index/name/w/h）
//   r65_doorinst.json  门类对象的实例（房号/对象名/x/y + 实例创建代码）
//   r65_objnames.txt   全部对象名
//   r65_codenames.txt  全部 code 名（供 Python 侧复核"命中面"）
//   gml65/<codename>.gml            门相关 code 的反编译
//   r65_index.json     code -> 产出文件
//   r65_log.txt        全过程日志（含 A/B 锚点判定）
// ============================================================================

EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outDir = Environment.GetEnvironmentVariable("R65_OUT");
if (String.IsNullOrEmpty(outDir)) outDir = Path.Combine(dir, "r65");
Directory.CreateDirectory(outDir);
string gmlDir = Path.Combine(outDir, "gml65");
Directory.CreateDirectory(gmlDir);

var utf8 = new UTF8Encoding(false);
var log = new StringBuilder();

GlobalDecompileContext ctx = new GlobalDecompileContext(Data);
Underanalyzer.Decompiler.IDecompileSettings ds = Data.ToolInfo.DecompilerSettings;

// ---------------- 门类对象判定（宽匹配，Python 侧再收窄） ----------------
string[] EXACT = new string[] {
    "obj_door", "obj_doorway", "obj_exit", "obj_drexit", "obj_hiddenentrance",
    "obj_fakedoorway", "obj_locked_door", "obj_dalvDoor", "obj_doorparent"
};
bool IsDoor(string n)
{
    if (String.IsNullOrEmpty(n)) return false;
    if (Array.IndexOf(EXACT, n) >= 0) return true;
    string s = n.ToLowerInvariant();
    if (s.StartsWith("obj_doorway")) return true;
    if (s.Contains("_door") || s.Contains("_doors") || s.Contains("_exit")
        || s.Contains("_entrance") || s.Contains("door_")) return true;
    return false;
}

// ---------------- 对象名清单 ----------------
var objNames = new List<string>();
var doorObjs = new List<string>();
for (int i = 0; i < Data.GameObjects.Count; i++)
{
    UndertaleGameObject o = Data.GameObjects[i];
    string nm = (o.Name == null) ? "" : o.Name.Content;
    objNames.Add(nm);
    if (IsDoor(nm)) doorObjs.Add(nm);
}
File.WriteAllLines(Path.Combine(outDir, "r65_objnames.txt"), objNames.ToArray(), utf8);

// ---------------- ① 房间表 ----------------
var sr = new StringBuilder();
sr.Append("{\n \"source\": ").Append(JsonStr(FilePath));
sr.Append(",\n \"rooms\": [");
for (int i = 0; i < Data.Rooms.Count; i++)
{
    UndertaleRoom room = Data.Rooms[i];
    if (i > 0) sr.Append(",");
    sr.Append("\n  {\"index\": ").Append(i);
    sr.Append(", \"name\": ").Append(JsonStr(room.Name == null ? "" : room.Name.Content));
    sr.Append(", \"w\": ").Append(room.Width).Append(", \"h\": ").Append(room.Height).Append("}");
}
sr.Append("\n ]\n}\n");
File.WriteAllText(Path.Combine(outDir, "r65_rooms.json"), sr.ToString(), utf8);

// ---------------- ② 门实例（含实例创建代码） ----------------
var si = new StringBuilder();
si.Append("{\n \"source\": ").Append(JsonStr(FilePath));
si.Append(",\n \"rooms\": [");
long nG = 0, nL = 0, nCC = 0, nDoor = 0;
for (int i = 0; i < Data.Rooms.Count; i++)
{
    UndertaleRoom room = Data.Rooms[i];
    if (i > 0) si.Append(",");
    si.Append("\n  {\"index\": ").Append(i);
    si.Append(", \"name\": ").Append(JsonStr(room.Name == null ? "" : room.Name.Content));
    si.Append(", \"doors\": [");
    bool first = true;

    IEnumerable geo = Prop(room, "GameObjects") as IEnumerable;
    if (geo != null)
    {
        foreach (object g in geo)
        {
            string on = ResolveName(Prop(g, "ObjectDefinition"));
            nG++;
            if (!IsDoor(on)) continue;
            nDoor++;
            if (!first) si.Append(",");
            first = false;
            si.Append("\n   ").Append(InstJson(g, on, "gameobjects", ref nCC));
        }
    }
    IEnumerable lays = Prop(room, "Layers") as IEnumerable;
    if (lays != null)
    {
        foreach (object ly in lays)
        {
            object idata = Prop(ly, "InstancesData");
            if (idata == null) continue;
            IEnumerable li = Prop(idata, "Instances") as IEnumerable;
            if (li == null) continue;
            foreach (object g in li)
            {
                string on = ResolveName(Prop(g, "ObjectDefinition"));
                nL++;
                if (!IsDoor(on)) continue;
                nDoor++;
                if (!first) si.Append(",");
                first = false;
                si.Append("\n   ").Append(InstJson(g, on, "layer", ref nCC));
            }
        }
    }
    si.Append("]}");
}
si.Append("\n ]\n}\n");
File.WriteAllText(Path.Combine(outDir, "r65_doorinst.json"), si.ToString(), utf8);

// ---------------- ③ 门相关 code（按名子串命中） ----------------
var codeNames = new List<string>();
for (int i = 0; i < Data.Code.Count; i++)
{
    UndertaleCode c = Data.Code[i];
    string nm = (c.Name == null) ? "" : c.Name.Content;
    if (nm != null) codeNames.Add(nm);
}
File.WriteAllLines(Path.Combine(outDir, "r65_codenames.txt"), codeNames.ToArray(), utf8);

var idx = new StringBuilder();
idx.Append("{\n \"objs\": [");
bool firstObj = true;
int nObj = 0, nFile = 0, nFail = 0, nHit = 0;
var hitSet = new HashSet<string>();

foreach (string on in doorObjs)
{
    string low = on.ToLowerInvariant();
    nObj++;
    if (!firstObj) idx.Append(",");
    firstObj = false;
    idx.Append("\n  {\"obj\": ").Append(JsonStr(on)).Append(", \"files\": [");
    bool firstF = true;
    bool anyHit = false;

    foreach (string cn in codeNames)
    {
        if (String.IsNullOrEmpty(cn)) continue;
        if (cn.ToLowerInvariant().IndexOf(low, StringComparison.Ordinal) < 0) continue;
        anyHit = true;
        nHit++;
        UndertaleCode code = null;
        try { code = Data.Code.ByName(cn); } catch (Exception) { code = null; }
        if (code == null) { nFail++; continue; }
        string gml;
        try
        {
            gml = new Underanalyzer.Decompiler.DecompileContext(ctx, code, ds).DecompileToString();
        }
        catch (Exception e)
        {
            gml = "// DECOMPILE FAILED: " + e.GetType().Name + ": " + e.Message;
            nFail++;
        }
        string fn = SafeName(cn) + ".gml";
        File.WriteAllText(Path.Combine(gmlDir, fn), gml, utf8);
        nFile++;
        if (!firstF) idx.Append(",");
        firstF = false;
        idx.Append("\n    {\"file\": ").Append(JsonStr(fn))
           .Append(", \"code\": ").Append(JsonStr(cn))
           .Append(", \"chars\": ").Append(gml.Length).Append("}");
    }
    if (anyHit) hitSet.Add(on);
    idx.Append("]}");
}
idx.Append("\n ]\n}\n");
File.WriteAllText(Path.Combine(outDir, "r65_index.json"), idx.ToString(), utf8);

// ---------------- ③b 房间/实例创建代码（gml_RoomCC*） ----------------
// Undertale 侧的特殊转场（如 obj_doorA 里的 room_castle_prebarrier 例外）与
// "非门体系"转场往往写在 RoomCC 里 ⇒ 一并取回，供 Python 侧判读。
string ccDir = Path.Combine(outDir, "gml65roomcc");
Directory.CreateDirectory(ccDir);
int nCCFile = 0;
foreach (string cn in codeNames)
{
    if (String.IsNullOrEmpty(cn)) continue;
    if (!cn.StartsWith("gml_RoomCC")) continue;
    UndertaleCode code = null;
    try { code = Data.Code.ByName(cn); } catch (Exception) { code = null; }
    if (code == null) continue;
    string gml;
    try
    {
        gml = new Underanalyzer.Decompiler.DecompileContext(ctx, code, ds).DecompileToString();
    }
    catch (Exception e)
    {
        gml = "// DECOMPILE FAILED: " + e.GetType().Name + ": " + e.Message;
    }
    File.WriteAllText(Path.Combine(ccDir, SafeName(cn) + ".gml"), gml, utf8);
    nCCFile++;
}

// ---------------- A/B 锚点判定 ----------------
string[] MUST_HIT = new string[] { "obj_doorway", "obj_exit", "obj_door" };
string[] MUST_MISS = new string[] { "obj_ghostint", "obj_battle_fade_in_screen" };
int hitOK = 0;
foreach (string a in MUST_HIT)
    if (hitSet.Contains(a)) hitOK++;
int missOK = 0;
foreach (string b in MUST_MISS)
    if (!hitSet.Contains(b)) missOK++;

log.AppendLine("EXPORT-OK");
log.AppendLine("rooms=" + Data.Rooms.Count + " gameobjects=" + Data.GameObjects.Count
               + " codes=" + Data.Code.Count);
log.AppendLine("instances gameobjects=" + nG + " layer=" + nL + " door_matched=" + nDoor);
log.AppendLine("creation_codes=" + nCC);
log.AppendLine("door_objects=" + nObj + " code_hits=" + nHit + " gml_files=" + nFile
               + " decode_fail=" + nFail);
log.AppendLine("roomcc_files=" + nCCFile);
log.AppendLine("ANCHOR_HIT " + hitOK + "/" + MUST_HIT.Length
    + " -> " + (hitOK == MUST_HIT.Length ? "PASS" : "FAIL"));
log.AppendLine("ANCHOR_MISS " + missOK + "/" + MUST_MISS.Length
    + " -> " + (missOK == MUST_MISS.Length ? "PASS" : "FAIL"));
log.AppendLine("outDir=" + outDir);
File.WriteAllText(Path.Combine(outDir, "r65_log.txt"), log.ToString(), utf8);

Console.WriteLine("dump65 rooms=" + Data.Rooms.Count
    + " doorinst=" + nDoor + " cc=" + nCC + " codes=" + Data.Code.Count
    + " gml=" + nFile + " roomcc=" + nCCFile + " fail=" + nFail
    + " anchorHIT=" + hitOK + "/" + MUST_HIT.Length
    + " anchorMISS=" + missOK + "/" + MUST_MISS.Length);

// ============================ 辅助函数 ============================

string InstJson(object g, string on, string src, ref long ncc)
{
    var b = new StringBuilder("{");
    b.Append("\"obj\": ").Append(JsonStr(on));
    b.Append(", \"src\": ").Append(JsonStr(src));
    b.Append(", \"x\": ").Append(Num(g, "X")).Append(", \"y\": ").Append(Num(g, "Y"));
    b.Append(", \"sx\": ").Append(Num(g, "ScaleX")).Append(", \"sy\": ").Append(Num(g, "ScaleY"));
    b.Append(", \"rot\": ").Append(Num(g, "Rotation"));
    b.Append(", \"id\": ").Append(Num(g, "InstanceID"));
    string cc = CreationCode(g);
    if (cc != null && cc.Trim().Length > 0)
    {
        ncc++;
        b.Append(", \"cc\": ").Append(JsonStr(cc));
    }
    b.Append("}");
    return b.ToString();
}

string CreationCode(object g)
{
    object cc = Prop(g, "CreationCode");
    if (cc == null) return null;
    UndertaleCode c = cc as UndertaleCode;
    if (c == null) return null;
    try
    {
        return new Underanalyzer.Decompiler.DecompileContext(ctx, c, ds).DecompileToString();
    }
    catch (Exception e)
    {
        return "// DECOMPILE FAILED: " + e.GetType().Name + ": " + e.Message;
    }
}

object Prop(object o, string n)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(n);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

string Num(object o, string n)
{
    object v = Prop(o, n);
    if (v == null) return "null";
    try { return Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture); }
    catch (Exception) { return "null"; }
}

string SafeName(string s)
{
    if (String.IsNullOrEmpty(s)) return "_";
    var b = new StringBuilder();
    foreach (char c in s)
        b.Append((Char.IsLetterOrDigit(c) || c == '_' || c == '-') ? c : '_');
    return b.ToString();
}

string PlainName(object v)
{
    if (v == null) return null;
    PropertyInfo np = v.GetType().GetProperty("Name");
    if (np == null) return null;
    object nv = null;
    try { nv = np.GetValue(v); } catch (Exception) { return null; }
    if (nv == null) return null;
    PropertyInfo cp = nv.GetType().GetProperty("Content");
    if (cp == null) return null;
    object cv = null;
    try { cv = cp.GetValue(nv); } catch (Exception) { return null; }
    return cv == null ? null : cv.ToString();
}

string ResolveName(object o)
{
    if (o == null) return "null";
    string own = PlainName(o);
    if (!String.IsNullOrEmpty(own)) return own;
    Type t = o.GetType();
    foreach (string pn in new string[] { "Sprite", "BackgroundDefinition", "SpriteDefinition",
                                         "ObjectDefinition", "Texture" })
    {
        PropertyInfo p = t.GetProperty(pn);
        if (p == null) continue;
        object v = null;
        try { v = p.GetValue(o); } catch (Exception) { continue; }
        if (v == null) continue;
        string nm = PlainName(v);
        if (!String.IsNullOrEmpty(nm)) return nm;
    }
    return o.GetType().Name;
}

string JsonStr(string s)
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
