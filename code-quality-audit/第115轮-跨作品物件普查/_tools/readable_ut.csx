// readable_ut.csx —— 抽 obj_readable* 事件里的字符串常量
// 用法：UndertaleModCli.exe load <game.droid 副本> -s readable_ut.csx
// 输出：readable_ut.json（UTF-8 无 BOM）
//
// ★★ 已废弃（留作证伪记录）：本 csx 抽到的 616 个字符串**全是变量名**
//    （obj_readable_room1_64 这种），正文并不在这里。正文在
//    `gml_Script_textdata_en / _ja / textdata_cn` 三张表里，见 readable_text.csx 与报告 §15。
//    保留它是因为"这条路走不通"本身是要留档的结论，别再有人从头试一遍。
//
// ★ 走 Data.Code 按 code 名匹配，**不去遍历 GameObjects.Events**：
//   后者实测 actions=0（反射拿不到 Actions 列表），而 code 名本身就带对象名
//   （`gml_Object_obj_readable_flowers1_Draw_0`），既准又省事。
// ★ 一个对象可能有多个事件（Draw / Create / Alarm），各自成条，不合并 ——
//   合并了就分不清哪段是正文、哪段是字体名。
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outJson = Path.Combine(dir, "readable_ut.json");

object GF(object o, string pn)
{
    if (o == null) return null;
    Type t = o.GetType();
    PropertyInfo p = t.GetProperty(pn);
    if (p != null && p.CanRead) return p.GetValue(o, null);
    FieldInfo f = t.GetField(pn, BindingFlags.Public | BindingFlags.Instance);
    if (f != null) return f.GetValue(o);
    return null;
}

string GS(object o, string pn)
{
    object v = GF(o, pn);
    if (v == null) return "";
    UndertaleString us = v as UndertaleString;
    if (us != null) return us.Content;
    return Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture);
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
    // 先收集可读物对象名（长的排前面，防止 obj_readable_a 抢 obj_readable_ab 的匹配）
    var objs = new List<string>();
    foreach (var obj in Data.GameObjects)
    {
        string on = GS(obj, "Name");
        if (!String.IsNullOrEmpty(on) && on.StartsWith("obj_readable")) objs.Add(on);
    }
    objs.Sort(delegate(string a, string b) { return b.Length.CompareTo(a.Length); });

    var items = new List<string>();
    int nCode = 0, nHit = 0, nStr = 0;

    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn) || !cn.StartsWith("gml_Object_")) continue;
        nCode++;
        string body = cn.Substring("gml_Object_".Length);
        string on = null;
        foreach (string o in objs)
        {
            if (body.StartsWith(o + "_")) { on = o; break; }
        }
        if (on == null) continue;
        nHit++;

        var ins = (IList)GF(code, "Instructions");
        if (ins == null) continue;
        var strs = new List<string>();
        for (int k = 0; k < ins.Count; k++)
        {
            object in1 = ins[k];
            if (GS(in1, "Kind") != "Push") continue;
            if (GS(in1, "Type1") != "String") continue;
            object vs = GF(in1, "ValueString");
            if (vs != null && !(vs is UndertaleString))
            {
                object res = GF(vs, "Resource");
                if (res is UndertaleString) vs = res;
            }
            string sv = (vs is UndertaleString) ? ((UndertaleString)vs).Content : Convert.ToString(vs);
            if (String.IsNullOrEmpty(sv)) continue;
            strs.Add(sv);
        }
        if (strs.Count == 0) continue;
        nStr += strs.Count;

        string ev = body.Substring(on.Length + 1);
        var sb = new StringBuilder();
        sb.Append("{\"obj\": ").Append(JsonS(on));
        sb.Append(", \"event\": ").Append(JsonS(ev));
        sb.Append(", \"code\": ").Append(JsonS(cn));
        sb.Append(", \"strings\": [");
        for (int i = 0; i < strs.Count; i++)
        {
            if (i > 0) sb.Append(", ");
            sb.Append(JsonS(strs[i]));
        }
        sb.Append("]}");
        items.Add(sb.ToString());
    }

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_readable_objs\": ").Append(objs.Count).Append(",\n");
    jb.Append("\"n_codes\": ").Append(nCode).Append(",\n");
    jb.Append("\"n_hit\": ").Append(nHit).Append(",\n");
    jb.Append("\"n_items\": ").Append(items.Count).Append(",\n");
    jb.Append("\"n_strings\": ").Append(nStr).Append(",\n");
    jb.Append("\"items\": [\n  ").Append(String.Join(",\n  ", items)).Append("\n]\n}\n");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("readable OK  objs=" + objs.Count + " codes=" + nCode
        + " hit=" + nHit + " items=" + items.Count + " strings=" + nStr);
}
catch (Exception ex)
{
    Console.WriteLine("readable FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
