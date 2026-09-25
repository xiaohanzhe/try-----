using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第48轮 · 字符串表关键词普查（找「垃圾团 / 神秘力量 / 用不了」这类文本）
// 产出 <data.win 同级>/probe_strings48.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "probe_strings48.txt");

object GO(object o, string pn)
{
    if (o == null) return null;
    var p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

string StrC(object s)
{
    if (s == null) return null;
    object cv = GO(s, "Content");
    if (cv != null) return cv.ToString();
    return s.ToString();
}

try
{
    string[] kw = new string[] { "junk", "mysteri", "strange", "prevent", "cannot use",
                                 "can't use", "cant use", "not here", "does nothing",
                                 "ball of", "dark world", "light world", "useless",
                                 "no effect", "nothing happens" };
    var strings = (IList)GO(Data, "Strings");
    var sb = new StringBuilder();
    int n = 0, hit = 0;
    if (strings != null)
    {
        for (int i = 0; i < strings.Count; i++)
        {
            string v = StrC(strings[i]);
            n++;
            if (String.IsNullOrEmpty(v)) continue;
            string low = v.ToLowerInvariant();
            bool h = false;
            for (int k = 0; k < kw.Length; k++) { if (low.IndexOf(kw[k]) >= 0) { h = true; break; } }
            if (!h) continue;
            hit++;
            sb.AppendLine("[" + i + "]\t" + v.Replace("\r", "\\r").Replace("\n", "\\n"));
        }
    }
    sb.Insert(0, "== Strings=" + n + " 命中=" + hit + " ==\n");
    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_strings48 OK strings=" + n + " hits=" + hit);
}
catch (Exception ex)
{
    Console.WriteLine("probe_strings48 FAILED: " + ex.GetType().Name + ": " + ex.Message);
}
