// 第181轮 · 补门型取证：一次 load 导出本章**全部** door 相关 code 的指令序列。
//
// 为什么用 csx 而不是 `dump -c`：
//   第171轮实测 `dump -c` **一次只吃一个 code 名**，而本轮要对 ~30 种门型 × 5 章取证，
//   每次都重新 load 一份 150 MB 的 data.win ⇒ 不可行。csx 一次 load 全出。
//
// 输出（UTF-8 无 BOM，落 P181_OUT）：
//   [A] 名字含 door 的 GameObject 定义（name / sprite / parent / events）——查继承用
//   [B] 名字含 door 的 Code 的**完整指令序列**——查 room_goto 用
//   [C] 名字含 door 的 Room 的 CreationCode 指令——查"目标写在房间里"的情况
//
// ★ UTMT 三坑（第171轮 §171.2）：stdin 必须 DEVNULL；本脚本一次 load 全出，不碰 `-c`；产物自己写。
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string outTxt = Environment.GetEnvironmentVariable("P181_OUT");
if (String.IsNullOrEmpty(outTxt))
{
    Console.WriteLine("probe181 FAILED: 环境变量 P181_OUT 未设置");
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

// 把一条指令压成一行：kind / type / 值
string OneIns(object in1)
{
    string kind = GS(in1, "Kind");
    string t1 = GS(in1, "Type1");
    string val = "";
    if (kind != null && kind.StartsWith("Push"))
    {
        if (t1 == "Int16") val = "V=" + GS(in1, "ValueShort");
        else if (t1 == "Int32") val = "V=" + GS(in1, "ValueInt");
        else if (t1 == "Int64") val = "V=" + GS(in1, "ValueLong");
        else if (t1 == "Double") val = "V=" + GS(in1, "ValueDouble");
        else if (t1 == "String") val = "S=" + GS(in1, "ValueString");
    }
    string fn = ResName(GO(in1, "ValueFunction"));
    string vv = ResName(GO(in1, "ValueVariable"));
    string ins2 = ResName(GO(in1, "ValueInstance"));
    if (fn != null) val = "FN=" + fn;
    else if (vv != null) val = "VAR=" + vv;
    else if (ins2 != null) val = "INST=" + ins2;
    return String.Format("{0}|{1}|{2}", kind, t1, val);
}

void DumpCode(StringBuilder tw, object c, string header)
{
    string cn = ResName(c);
    object ins = GO(c, "Instructions");
    IEnumerable en = ins as IEnumerable;
    var list = new List<object>();
    if (en != null) foreach (object x in en) list.Add(x);
    tw.AppendLine("");
    tw.AppendLine("### " + header + " " + cn + "  ins=" + list.Count);
    for (int k = 0; k < list.Count; k++)
    {
        tw.AppendLine(String.Format("{0,5}  {1}", k, OneIns(list[k])));
    }
}

try
{
    var tw = new StringBuilder();
    tw.AppendLine("source=" + FilePath);

    // ============ [A] door 对象定义 ============
    var gos = (IList)GO(Data, "GameObjects");
    tw.AppendLine("");
    tw.AppendLine("========== [A] GameObjects（名字含 door） ==========");
    int nObj = 0;
    for (int i = 0; i < gos.Count; i++)
    {
        object o = gos[i];
        string nm = ResName(o);
        if (String.IsNullOrEmpty(nm)) continue;
        if (nm.ToLowerInvariant().IndexOf("door") < 0) continue;
        nObj++;
        var evNames = new List<string>();
        object evs = GO(o, "Events");
        IEnumerable evEn = evs as IEnumerable;
        if (evEn != null)
        {
            foreach (object ev in evEn)
            {
                string et = GS(ev, "EventType");
                string es = GS(ev, "EventSubtype");
                if (et == null) et = "?";
                evNames.Add(et + (es == null || es == "0" ? "" : (":" + es)));
            }
        }
        tw.AppendLine(String.Format("  {0,-52} sprite={1,-30} parent={2,-24} persistent={3} events=[{4}]",
            nm, ResName(GO(o, "Sprite")), ResName(GO(o, "ParentId")),
            GS(o, "Persistent"), String.Join(",", evNames.ToArray())));
    }
    tw.AppendLine("  (door 对象共 " + nObj + " 个)");

    // ============ [B] door 相关 code 的完整指令 ============
    var codes = (IList)GO(Data, "Code");
    tw.AppendLine("");
    tw.AppendLine("========== [B] Code（名字含 door）完整指令 ==========");
    int nCode = 0;
    for (int ci = 0; ci < codes.Count; ci++)
    {
        object c = codes[ci];
        string cn = ResName(c);
        if (String.IsNullOrEmpty(cn)) continue;
        if (cn.ToLowerInvariant().IndexOf("door") < 0) continue;
        DumpCode(tw, c, "CODE");
        nCode++;
    }
    tw.AppendLine("");
    tw.AppendLine("  (door code 共 " + nCode + " 段)");

    // ============ [C] 房间 CreationCode（名字含 door 的房间） ============
    var rooms = (IList)GO(Data, "Rooms");
    tw.AppendLine("");
    tw.AppendLine("========== [C] Room CreationCode（房间名含 door） ==========");
    int nRoom = 0;
    for (int ri = 0; ri < rooms.Count; ri++)
    {
        object r = rooms[ri];
        string rn = ResName(r);
        if (String.IsNullOrEmpty(rn)) continue;
        if (rn.ToLowerInvariant().IndexOf("door") < 0) continue;
        object cc = GO(r, "CreationCode");
        if (cc == null) continue;
        DumpCode(tw, cc, "ROOMCC #" + ri);
        nRoom++;
    }
    tw.AppendLine("");
    tw.AppendLine("  (含 creationCode 的 door 房间共 " + nRoom + " 间)");

    Directory.CreateDirectory(Path.GetDirectoryName(outTxt));
    File.WriteAllText(outTxt, tw.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe181 OK objs=" + nObj + " codes=" + nCode + " roomcc=" + nRoom);
}
catch (Exception ex)
{
    Console.WriteLine("probe181 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
