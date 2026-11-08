// 第171轮 · 四章（ch1/ch3/ch4/ch5）逐房间「门/出生点」实例快照
// schema 对齐第42轮 ch2_inst42.json，另加两个字段：
//   n_all        = 该房间的**全部**实例数（不限关键字），用来区分
//                  「这间房没摆门」 vs 「这间房根本没被 dump 到」
//   n_rooms_listed = 写进 rooms[] 的房间数（本轮=全部房间，含 n==0 的）
// 输出路径走环境变量 INST171_OUT；不往 data.win 所在目录写任何东西。
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string outJson = Environment.GetEnvironmentVariable("INST171_OUT");
if (String.IsNullOrEmpty(outJson))
{
    Console.WriteLine("inst171 FAILED: 环境变量 INST171_OUT 未设置");
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
    var rooms = (IList)GO(Data, "Rooms");
    var roomRows = new List<string>();
    var ctr = new Dictionary<string, int>();
    string[] keys = new string[] { "door", "marker", "cutscene", "fountain", "savepoint",
                                   "rotate", "entrance", "warp", "portal", "closet",
                                   "elevator", "stair", "darkwake", "fallpaper" };
    int nRoom = 0, nInst = 0, nAll = 0;
    for (int ri = 0; ri < rooms.Count; ri++)
    {
        object r = rooms[ri];
        string rn = ResName(r);
        var insts = new List<string>();
        int nAllRoom = 0;
        IEnumerable layers = GO(r, "Layers") as IEnumerable;
        if (layers != null)
        {
            foreach (object ly in layers)
            {
                string lname = StrC(GO(ly, "LayerName"));
                string ldepth = GS(ly, "LayerDepth");
                object id = GO(ly, "InstancesData");
                if (id == null) continue;
                IEnumerable ins = GO(id, "Instances") as IEnumerable;
                if (ins == null) continue;
                foreach (object it in ins)
                {
                    string on = ResName(GO(it, "ObjectDefinition"));
                    if (String.IsNullOrEmpty(on)) continue;
                    nAllRoom++;
                    string low = on.ToLowerInvariant();
                    bool hit = false;
                    for (int k = 0; k < keys.Length; k++) { if (low.IndexOf(keys[k]) >= 0) { hit = true; break; } }
                    if (!hit) continue;
                    nInst++;
                    ctr[on] = (ctr.ContainsKey(on) ? ctr[on] : 0) + 1;
                    insts.Add("      {\"obj\": " + JsonS(on) + ", \"x\": " + Num(GO(it, "X"))
                        + ", \"y\": " + Num(GO(it, "Y"))
                        + ", \"layer\": " + JsonS(lname) + ", \"depth\": " + JsonS(ldepth) + "}");
                }
            }
        }
        nAll += nAllRoom;
        if (insts.Count > 0) nRoom++;
        roomRows.Add("  {\"index\": " + ri + ", \"name\": " + JsonS(rn)
            + ", \"w\": " + Num(GO(r, "Width")) + ", \"h\": " + Num(GO(r, "Height"))
            + ", \"n\": " + insts.Count + ", \"n_all\": " + nAllRoom + ", \"insts\": ["
            + (insts.Count == 0 ? "" : "\n" + String.Join(",\n", insts) + "\n  ") + "]}");
    }

    var top = new List<KeyValuePair<string, int>>(ctr);
    top.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { return b.Value.CompareTo(a.Value); });
    var tb = new List<string>();
    for (int i = 0; i < top.Count && i < 200; i++)
        tb.Add("  " + JsonS(top[i].Key) + ": " + top[i].Value);

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_rooms_total\": ").Append(rooms.Count).Append(",\n");
    jb.Append("\"n_rooms_hit\": ").Append(nRoom).Append(",\n");
    jb.Append("\"n_rooms_listed\": ").Append(roomRows.Count).Append(",\n");
    jb.Append("\"n_inst\": ").Append(nInst).Append(",\n");
    jb.Append("\"n_inst_all\": ").Append(nAll).Append(",\n");
    jb.Append("\"top\": {\n").Append(String.Join(",\n", tb)).Append("\n},\n");
    jb.Append("\"rooms\": [\n").Append(String.Join(",\n", roomRows)).Append("\n]\n}\n");
    Directory.CreateDirectory(Path.GetDirectoryName(outJson));
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("inst171 OK  rooms=" + rooms.Count + " rooms_hit=" + nRoom
        + " inst=" + nInst + " inst_all=" + nAll + " distinct=" + ctr.Count);
    Console.WriteLine("out=" + outJson);
}
catch (Exception ex)
{
    Console.WriteLine("inst171 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
