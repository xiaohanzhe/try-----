using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第41轮 · 连接图提取（v2：按 Type1 选常量字段；Kind 用前缀匹配）
// 产出 <data.win 同级>/edges41.json  +  edges41.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
var sb = new StringBuilder();
var jb = new StringBuilder();

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
    return cv == null ? null : cv.ToString();
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
string RoomName(IList rooms, int idx)
{
    if (idx < 0 || idx >= rooms.Count) return null;
    object r = rooms[idx];
    object nv = GO(r, "Name");
    if (nv == null) return null;
    object cv = GO(nv, "Content");
    return cv == null ? null : cv.ToString();
}

var edges = new List<string>();
int seenVar = 0, seenStr = 0, seenOutOfRange = 0, seenOk = 0;

try
{
    IList rooms = (IList)GO(Data, "Rooms");
    IList codes = (IList)GO(Data, "Code");

    for (int i = 0; i < codes.Count; i++)
    {
        object cd = codes[i];
        IList li = GO(cd, "Instructions") as IList;
        if (li == null) continue;
        string src = ResName(cd);
        int lastInt = -1;
        string lastKind = "none";
        for (int k = 0; k < li.Count; k++)
        {
            object ins = li[k];
            string kind = GS(ins, "Kind");
            if (kind == null) kind = "";
            if (kind.StartsWith("Push"))
            {
                string t1 = GS(ins, "Type1");
                lastInt = -1; lastKind = "none";
                if (t1 == "Int16")
                {
                    string s = GS(ins, "ValueShort");
                    int v; if (s != null && Int32.TryParse(s, out v)) { lastInt = v; lastKind = "Int16"; }
                }
                else if (t1 == "Int32")
                {
                    string s = GS(ins, "ValueInt");
                    int v; if (s != null && Int32.TryParse(s, out v)) { lastInt = v; lastKind = "Int32"; }
                }
                else if (t1 == "Int64")
                {
                    string s = GS(ins, "ValueLong");
                    long v; if (s != null && Int64.TryParse(s, out v) && v >= 0 && v < 100000) { lastInt = (int)v; lastKind = "Int64"; }
                }
                else if (t1 == "Variable") lastKind = "var";
                else if (t1 == "String") lastKind = "str";
                else lastKind = t1;
            }
            string fn = ResName(GO(ins, "ValueFunction"));
            if (fn == null) continue;
            string tag = null, to = null;
            if (fn == "room_goto") tag = "goto";
            else if (fn == "room_goto_next") tag = "next";
            else if (fn == "room_goto_previous") tag = "prev";
            else continue;

            if (tag != "goto") { edges.Add("{\"from\": " + JsonS(src) + ", \"kind\": " + JsonS(tag) + ", \"to\": null, \"to_index\": -1, \"arg\": \"-\"}"); continue; }
            if (lastKind == "var") { seenVar++; edges.Add("{\"from\": " + JsonS(src) + ", \"kind\": \"goto\", \"to\": null, \"to_index\": -1, \"arg\": \"var\"}"); continue; }
            if (lastKind == "str") { seenStr++; edges.Add("{\"from\": " + JsonS(src) + ", \"kind\": \"goto\", \"to\": null, \"to_index\": -1, \"arg\": \"str\"}"); continue; }
            string rn = (lastInt >= 0) ? RoomName(rooms, lastInt) : null;
            if (rn == null) { seenOutOfRange++; edges.Add("{\"from\": " + JsonS(src) + ", \"kind\": \"goto\", \"to\": null, \"to_index\": " + lastInt + ", \"arg\": \"oob" + lastKind + "\"}"); continue; }
            seenOk++;
            edges.Add("{\"from\": " + JsonS(src) + ", \"kind\": \"goto\", \"to\": " + JsonS(rn) + ", \"to_index\": " + lastInt + ", \"arg\": " + JsonS(lastKind) + "}");
        }
    }

    sb.AppendLine("== 连接图（v2：Type1-aware）==");
    sb.AppendLine("Rooms=" + rooms.Count + "  Code=" + codes.Count);
    sb.AppendLine("room_goto 解析成功(字面量房号) = " + seenOk);
    sb.AppendLine("room_goto 参数是变量 = " + seenVar + " ；是字符串 = " + seenStr + " ；字面量越界 = " + seenOutOfRange);
    int nNext = 0, nPrev = 0;
    foreach (string e in edges) { if (e.IndexOf("\"next\"") >= 0) nNext++; if (e.IndexOf("\"prev\"") >= 0) nPrev++; }
    sb.AppendLine("room_goto_next = " + nNext + " ；room_goto_previous = " + nPrev);
    sb.AppendLine();
    sb.AppendLine("== 全部边 ==");
    foreach (string e in edges) sb.AppendLine("  " + e);

    jb.Append("{\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append(" \"n_rooms\": ").Append(rooms.Count).Append(",\n");
    jb.Append(" \"n_edges\": ").Append(edges.Count).Append(",\n");
    jb.Append(" \"n_goto_literal\": ").Append(seenOk).Append(",\n");
    jb.Append(" \"edges\": [\n  ").Append(String.Join(",\n  ", edges.ToArray())).Append("\n ]\n}\n");
    File.WriteAllText(Path.Combine(dir, "edges41.json"), jb.ToString(), new UTF8Encoding(false));
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(Path.Combine(dir, "edges41.txt"), sb.ToString(), new UTF8Encoding(false));
