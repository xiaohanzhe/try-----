using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第48轮 · 道具/菜单 名字普查（只列名字，不导正文）
// 产出 <data.win 同级>/probe_items48.json
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outJson = Path.Combine(dir, "probe_items48.json");

string GS(object o, string pn)
{
    if (o == null) return null;
    var p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    object v = null;
    try { v = p.GetValue(o); } catch (Exception) { return null; }
    return v == null ? null : v.ToString();
}

object GO(object o, string pn)
{
    if (o == null) return null;
    var p = o.GetType().GetProperty(pn);
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
    // 关键词：道具 / 菜单 / 背包 / 垃圾 / 宝箱 / 按键
    string[] keys = new string[] { "item", "menu", "junk", "chest", "inventory", "inv_",
                                   "keyconfig", "keyitem", "screw", "shop", "phone",
                                   "cell", "party", "stat", "equip", "weapon", "armor",
                                   "heal", "recruit", "option", "config", "setting",
                                   "pause", "save", "cursor", "select", "tp_" };

    var codeHits = new List<string>();      // Data.Code  名字（函数/事件体）
    var scriptHits = new List<string>();    // Data.Scripts 名字（global script 声明）

    var code = (IList)GO(Data, "Code");
    if (code != null)
    {
        for (int i = 0; i < code.Count; i++)
        {
            string n = ResName(code[i]);
            if (String.IsNullOrEmpty(n)) continue;
            string low = n.ToLowerInvariant();
            for (int k = 0; k < keys.Length; k++)
            {
                if (low.IndexOf(keys[k]) >= 0)
                {
                    string body = GS(code[i], "Instructions");
                    codeHits.Add("  " + JsonS(n) + ": " + (body == null ? "null" : body));
                    break;
                }
            }
        }
    }

    var scripts = (IList)GO(Data, "Scripts");
    if (scripts != null)
    {
        for (int i = 0; i < scripts.Count; i++)
        {
            string n = ResName(scripts[i]);
            if (String.IsNullOrEmpty(n)) continue;
            string low = n.ToLowerInvariant();
            for (int k = 0; k < keys.Length; k++)
            {
                if (low.IndexOf(keys[k]) >= 0)
                {
                    scriptHits.Add("  " + JsonS(n));
                    break;
                }
            }
        }
    }

    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append("\"n_code\": ").Append(code == null ? 0 : code.Count).Append(",\n");
    jb.Append("\"n_scripts\": ").Append(scripts == null ? 0 : scripts.Count).Append(",\n");
    jb.Append("\"code_hits\": [\n").Append(String.Join(",\n", codeHits)).Append("\n],\n");
    jb.Append("\"script_hits\": [\n").Append(String.Join(",\n", scriptHits)).Append("\n]\n}\n");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    Console.WriteLine("probe_items48 OK  code=" + (code == null ? 0 : code.Count)
        + " code_hits=" + codeHits.Count + " script_hits=" + scriptHits.Count);
}
catch (Exception ex)
{
    Console.WriteLine("probe_items48 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
