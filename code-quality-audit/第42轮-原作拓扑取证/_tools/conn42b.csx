using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第42轮 · 全量复原原作房间连接：扫描所有 Code，提取
//   (a) room_goto(常量)  带前置 Cmp 的源房间  -> pair{src,dst}
//   (b) room_goto(常量)  无前置              -> pair{src:-1,dst}
//   (c) room_goto_next / room_goto_previous  -> pair{src,dst:-1,op}
// 产出 <data.win 同级>/conn42b.json
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outJson = Path.Combine(dir, "conn42b.json");

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
    var roomNames = new List<string>();
    for (int i = 0; i < rooms.Count; i++) roomNames.Add(ResName(rooms[i]));

    var codes = (IList)GO(Data, "Code");
    var items = new List<string>();
    int nScanned = 0, nWithRoom = 0, nTrunc = 0;

    for (int ci = 0; ci < codes.Count; ci++)
    {
        object c = codes[ci];
        string cn = ResName(c);
        if (String.IsNullOrEmpty(cn) || !cn.StartsWith("gml_")) continue;
        nScanned++;
        IEnumerable insEn = GO(c, "Instructions") as IEnumerable;
        if (insEn == null) continue;
        var list = new List<object>();
        foreach (object x in insEn) { list.Add(x); if (list.Count > 60000) { nTrunc++; break; } }
        if (list.Count == 0) continue;

        bool hasRoom = false;
        for (int k = 0; k < list.Count; k++)
        {
            string fn0 = ResName(GO(list[k], "ValueFunction"));
            if (fn0 != null && fn0.StartsWith("room_goto")) { hasRoom = true; break; }
        }
        if (!hasRoom) continue;
        nWithRoom++;

        var pend = new List<string[]>();
        int srcRoom = -1;
        for (int k = 0; k < list.Count; k++)
        {
            object in1 = list[k];
            string kind = GS(in1, "Kind");
            if (kind == null) continue;
            string t1 = GS(in1, "Type1");
            if (kind.StartsWith("Push"))
            {
                string extra = "";
                if (t1 == "Int16") extra = GS(in1, "ValueShort");
                else if (t1 == "Int32") extra = GS(in1, "ValueInt");
                else if (t1 == "Int64") extra = GS(in1, "ValueLong");
                string vv = ResName(GO(in1, "ValueVariable"));
                string fn1 = ResName(GO(in1, "ValueFunction"));
                if (vv != null) extra = "VAR=" + vv;
                else if (fn1 != null) extra = "FN=" + fn1;
                if (extra == null) extra = "";
                pend.Add(new string[] { kind, t1, extra });
                if (pend.Count > 4) pend.RemoveAt(0);
            }
            else if (kind == "Cmp")
            {
                srcRoom = -1;
                if (pend.Count >= 2)
                {
                    string[] a = pend[pend.Count - 2];
                    string[] b = pend[pend.Count - 1];
                    if (a[0] == "PushBltn" && a[2] == "VAR=room" && b[0].StartsWith("PushI"))
                    {
                        int tmp; if (Int32.TryParse(b[2], out tmp)) srcRoom = tmp;
                    }
                }
                pend.Clear();
            }
            else if (kind == "Call")
            {
                string fn = ResName(GO(in1, "ValueFunction"));
                if (fn == "room_goto")
                {
                    int dst = -1;
                    if (pend.Count >= 1)
                    {
                        string[] b = pend[pend.Count - 1];
                        if (b[0].StartsWith("PushI")) { int tmp; if (Int32.TryParse(b[2], out tmp)) dst = tmp; }
                    }
                    if (dst >= 0)
                        items.Add("{\"src\": " + srcRoom + ", \"dst\": " + dst + ", \"op\": \"goto\", \"code\": " + JsonS(cn) + "}");
                }
                else if (fn == "room_goto_next" || fn == "room_goto_previous")
                {
                    items.Add("{\"src\": " + srcRoom + ", \"dst\": -1, \"op\": " + JsonS(fn) + ", \"code\": " + JsonS(cn) + "}");
                }
                pend.Clear();
            }
        }
    }

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_rooms\": ").Append(rooms.Count).Append(",\n");
    jb.Append("\"n_codes\": ").Append(codes.Count).Append(",\n");
    jb.Append("\"n_scanned\": ").Append(nScanned).Append(",\n");
    jb.Append("\"n_with_room_goto\": ").Append(nWithRoom).Append(",\n");
    jb.Append("\"n_items\": ").Append(items.Count).Append(",\n");
    jb.Append("\"room_names\": [");
    for (int i = 0; i < roomNames.Count; i++)
    {
        if (i > 0) jb.Append(", ");
        jb.Append(JsonS(roomNames[i]));
    }
    jb.Append("],\n\"items\": [\n  ").Append(String.Join(",\n  ", items)).Append("\n]\n}\n");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("conn42b OK  rooms=" + rooms.Count + " codes=" + codes.Count
        + " scanned=" + nScanned + " with_room_goto=" + nWithRoom + " items=" + items.Count
        + " trunc=" + nTrunc);
}
catch (Exception ex)
{
    Console.WriteLine("conn42b FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
