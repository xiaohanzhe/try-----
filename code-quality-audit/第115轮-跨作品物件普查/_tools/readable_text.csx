// readable_text.csx —— 抽「可读物正文」：找 `变量名 -> 文本` 的赋值
// 用法：UndertaleModCli.exe load <game.droid 副本> -s readable_text.csx
// 输出：readable_text.json
//
// ★ 为什么不能只看 obj_readable* 的事件：那些事件里 616 个字符串**全是变量名**
//   （obj_readable_room1_64 这种），正文不在里面 —— 正文是别处赋给这些名字的。
//   所以这里扫**全部** code，找这种形状：
//       Push(String "obj_readable_xxx_N")  Push(String "正文")  Call(variable_*_set)
//   即"名字后面紧跟的那一个字符串常量"就是正文。
// ★ 认不出来（正文是变量而非字面量）的，就记成 null —— 不猜。
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
string outJson = Path.Combine(dir, "readable_text.json");

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

string StrOf(object ins)
{
    object vs = GF(ins, "ValueString");
    if (vs != null && !(vs is UndertaleString))
    {
        object res = GF(vs, "Resource");
        if (res is UndertaleString) vs = res;
    }
    if (vs is UndertaleString) return ((UndertaleString)vs).Content;
    return null;
}

bool IsPushStr(object ins, out string s)
{
    s = null;
    if (ins == null) return false;
    if (GS(ins, "Kind") != "Push") return false;
    if (GS(ins, "Type1") != "String") return false;
    s = StrOf(ins);
    return s != null;
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
    var items = new List<string>();
    int nCodes = 0, nNamed = 0, nPairs = 0, nFar = 0;

    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        nCodes++;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null) continue;
        int n = ins.Count;
        for (int k = 0; k + 1 < n; k++)
        {
            string a;
            if (!IsPushStr(ins[k], out a)) continue;
            if (a == null || !a.StartsWith("obj_readable")) continue;
            nNamed++;
            // ★ 名字后面**不紧跟**正文：实测中间隔着 4~6 条
            //   （Conv / PushGlb / Call(44) / Popz），所以往后找第一个字符串常量。
            //   之前那版要求"紧邻" => pairs=0（已踩过，别再退回）。
            string b = null;
            int dist = -1;
            for (int j = k + 1; j < n && j <= k + 12; j++)
            {
                if (IsPushStr(ins[j], out b))
                {
                    dist = j - k;
                    break;
                }
            }
            if (b == null || String.IsNullOrEmpty(b)) { nFar++; continue; }
            nPairs++;
            var sb = new StringBuilder();
            sb.Append("{\"code\": ").Append(JsonS(cn));
            sb.Append(", \"name\": ").Append(JsonS(a));
            sb.Append(", \"text\": ").Append(JsonS(b));
            sb.Append(", \"dist\": ").Append(dist);
            sb.Append("}");
            items.Add(sb.ToString());
        }
    }

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_codes\": ").Append(nCodes).Append(",\n");
    jb.Append("\"n_named\": ").Append(nNamed).Append(",\n");
    jb.Append("\"n_unmatched\": ").Append(nFar).Append(",\n");
    jb.Append("\"n_items\": ").Append(items.Count).Append(",\n");
    jb.Append("\"items\": [\n  ").Append(String.Join(",\n  ", items)).Append("\n]\n}\n");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("rtext OK  codes=" + nCodes + " named=" + nNamed
        + " pairs=" + nPairs + " unmatched=" + nFar + " items=" + items.Count);
}
catch (Exception ex)
{
    Console.WriteLine("rtext FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
