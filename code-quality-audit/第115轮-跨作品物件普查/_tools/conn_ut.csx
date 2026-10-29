// conn_ut.csx —— 导出 UT / UTY / Outertale 的换房指令（room_goto 全量）
// 用法：UndertaleModCli.exe load <game.droid 副本> -s conn_ut.csx
// 输出：conn_ut.json（UTF-8 无 BOM），字段同第42轮 conn42b.json
//
// 逐条记录：
//   (a) room_goto(常量) 且前面有 `room == N` 比较 -> {src:N, dst:M, op:"goto"}
//   (b) room_goto(常量) 没有前置比较             -> {src:-1, dst:M, op:"goto"}
//   (c) room_goto_next / room_goto_previous      -> {src:N或-1, dst:-1, op:"next"/"previous"}
//
// ★ 为什么 src 可能为 -1：GML 里换房常写成 `door` 对象在 Step 事件里按变量跳转，
//   源房间不在代码里写死。这种情况要靠「门对象实例落在哪间房」来补，见 conn_ut115.py。
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
string outJson = Path.Combine(dir, "conn_ut.json");

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
    var opCount = new Dictionary<string, int>();
    int nScanned = 0, nWithRoom = 0, nTrunc = 0, nonConst = 0;

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
                        else nonConst++;
                    }
                    if (dst >= 0)
                    {
                        items.Add("{\"src\": " + srcRoom + ", \"dst\": " + dst + ", \"op\": \"goto\", \"code\": " + JsonS(cn) + "}");
                        string kk = srcRoom >= 0 ? "goto_const_src" : "goto_const_nosrc";
                        opCount[kk] = opCount.ContainsKey(kk) ? opCount[kk] + 1 : 1;
                    }
                }
                else if (fn == "room_goto_next" || fn == "room_goto_previous")
                {
                    items.Add("{\"src\": " + srcRoom + ", \"dst\": -1, \"op\": " + JsonS(fn) + ", \"code\": " + JsonS(cn) + "}");
                    opCount[fn] = opCount.ContainsKey(fn) ? opCount[fn] + 1 : 1;
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
    jb.Append("\"n_nonconst_target\": ").Append(nonConst).Append(",\n");
    jb.Append("\"n_items\": ").Append(items.Count).Append(",\n");
    jb.Append("\"op_counts\": {");
    bool firstOp = true;
    foreach (var kv in opCount)
    {
        if (!firstOp) jb.Append(", ");
        jb.Append(JsonS(kv.Key)).Append(": ").Append(kv.Value);
        firstOp = false;
    }
    jb.Append("},\n\"room_names\": [");
    for (int i = 0; i < roomNames.Count; i++)
    {
        if (i > 0) jb.Append(", ");
        jb.Append(JsonS(roomNames[i]));
    }
    jb.Append("],\n\"items\": [\n  ").Append(String.Join(",\n  ", items)).Append("\n]\n}\n");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("conn_ut OK  rooms=" + rooms.Count + " codes=" + codes.Count
        + " scanned=" + nScanned + " with_room_goto=" + nWithRoom + " items=" + items.Count
        + " nonconst=" + nonConst + " trunc=" + nTrunc);
}
catch (Exception ex)
{
    Console.WriteLine("conn_ut FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
