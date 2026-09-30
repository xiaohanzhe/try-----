using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第68轮 · 可交互道具实例补采（在 inst42 关键词表基础上扩容）
//   第42轮 `inst42.csx` 的 keys 表**不含** readable/sign/chest/treasure/pickup/
//   interactable 等可交互类 ⇒ 这些类的实例**从未被导出**，导致第48轮
//   `item_interact.PROP_CLASSES` 里它们只能标 `in_data=False`（缺口 1）。
//   本脚本 = inst42 + 可交互类关键词，产出 <data.win 同级>/inst68.json。
//   ★ 不改 inst42.csx（保住既有基线），产出独立文件名。
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outJson = Path.Combine(dir, "inst68.json");

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
    // ★ 第42轮的 14 个键（原样保留）+ 第68轮新增的**可交互类**键。
    //   匹配是 `IndexOf >= 0` 的子串匹配，故键要挑"够专一"的词。
    string[] keys = new string[] {
        // --- 第42轮原样（保一致性） ---
        "door", "marker", "cutscene", "fountain", "savepoint",
        "rotate", "entrance", "warp", "portal", "closet",
        "elevator", "stair", "darkwake", "fallpaper",
        // --- 第68轮新增：可交互类 ---
        "readable", "sign", "chest", "treasure", "pickup",
        "interactable", "alphysdesk", "schooldesk", "desk",
        "trash", "bed", "shop", "vending"
    };
    int nRoom = 0, nInst = 0;
    for (int ri = 0; ri < rooms.Count; ri++)
    {
        object r = rooms[ri];
        string rn = ResName(r);
        var insts = new List<string>();
        IEnumerable layers = GO(r, "Layers") as IEnumerable;
        if (layers == null) continue;
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
                string low = on.ToLowerInvariant();
                bool hit = false;
                for (int k = 0; k < keys.Length; k++) { if (low.IndexOf(keys[k]) >= 0) { hit = true; break; } }
                if (!hit) continue;
                nInst++;
                ctr[on] = (ctr.ContainsKey(on) ? ctr[on] : 0) + 1;
                insts.Add("    {\"obj\": " + JsonS(on) + ", \"x\": " + Num(GO(it, "X"))
                    + ", \"y\": " + Num(GO(it, "Y"))
                    + ", \"layer\": " + JsonS(lname) + ", \"depth\": " + JsonS(ldepth) + "}");
            }
        }
        if (insts.Count == 0) continue;
        nRoom++;
        roomRows.Add("  {\"index\": " + ri + ", \"name\": " + JsonS(rn)
            + ", \"w\": " + Num(GO(r, "Width")) + ", \"h\": " + Num(GO(r, "Height"))
            + ", \"n\": " + insts.Count + ", \"insts\": [\n"
            + String.Join(",\n", insts) + "\n  ]}");
    }

    var top = new List<KeyValuePair<string, int>>(ctr);
    top.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { return b.Value.CompareTo(a.Value); });
    var tb = new List<string>();
    for (int i = 0; i < top.Count && i < 400; i++)
        tb.Add("  " + JsonS(top[i].Key) + ": " + top[i].Value);

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_rooms_total\": ").Append(rooms.Count).Append(",\n");
    jb.Append("\"n_rooms_hit\": ").Append(nRoom).Append(",\n");
    jb.Append("\"n_inst\": ").Append(nInst).Append(",\n");
    jb.Append("\"n_distinct\": ").Append(ctr.Count).Append(",\n");
    jb.Append("\"top\": {\n").Append(String.Join(",\n", tb)).Append("\n},\n");
    jb.Append("\"rooms\": [\n").Append(String.Join(",\n", roomRows)).Append("\n]\n}\n");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("inst68 OK  rooms=" + rooms.Count + " rooms_hit=" + nRoom
        + " inst=" + nInst + " distinct=" + ctr.Count);
}
catch (Exception ex)
{
    Console.WriteLine("inst68 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
