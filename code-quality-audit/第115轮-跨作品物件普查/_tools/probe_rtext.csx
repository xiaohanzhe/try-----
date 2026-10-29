// probe_rtext.csx —— 看 `obj_readable_room1_64` 这类名字前后到底长什么样
// 用法：UndertaleModCli.exe load <game.droid 副本> -s probe_rtext.csx
// 输出：probe_rtext.txt（纯文本，给眼睛看）
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
string outTxt = Path.Combine(dir, "probe_rtext.txt");

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

string Describe(object ins)
{
    if (ins == null) return "(null)";
    var sb = new StringBuilder();
    sb.Append(GS(ins, "Kind"));
    string t1 = GS(ins, "Type1");
    string t2 = GS(ins, "Type2");
    if (t1 != "") sb.Append(" t1=").Append(t1);
    if (t2 != "") sb.Append(" t2=").Append(t2);
    object vs = GF(ins, "ValueString");
    if (vs != null && !(vs is UndertaleString))
    {
        object res = GF(vs, "Resource");
        if (res is UndertaleString) vs = res;
    }
    if (vs is UndertaleString) sb.Append(" str='").Append(((UndertaleString)vs).Content).Append("'");
    object vv = GF(ins, "ValueVariable");
    if (vv is UndertaleString) sb.Append(" var=").Append(((UndertaleString)vv).Content);
    object vf = GF(ins, "ValueFunction");
    if (vf is UndertaleString) sb.Append(" fn=").Append(((UndertaleString)vf).Content);
    object vi = GF(ins, "ValueInt");
    if (vi != null) sb.Append(" int=").Append(Convert.ToString(vi));
    object vsh = GF(ins, "ValueShort");
    if (vsh != null) sb.Append(" short=").Append(Convert.ToString(vsh));
    return sb.ToString();
}

try
{
    var sb = new StringBuilder();
    int found = 0;
    foreach (var code in Data.Code)
    {
        if (found >= 4) break;
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null) continue;
        for (int k = 0; k < ins.Count; k++)
        {
            string s = "";
            object v = GF(ins[k], "ValueString");
            if (v != null && !(v is UndertaleString))
            {
                object res = GF(v, "Resource");
                if (res is UndertaleString) v = res;
            }
            if (v is UndertaleString) s = ((UndertaleString)v).Content;
            if (s == null || !s.StartsWith("obj_readable")) continue;
            found++;
            sb.Append("\n=== [").Append(found).Append("] ").Append(cn)
              .Append("  @ins ").Append(k).Append("/").Append(ins.Count)
              .Append("  name=").Append(s).Append('\n');
            int lo = Math.Max(0, k - 5), hi = Math.Min(ins.Count - 1, k + 7);
            for (int j = lo; j <= hi; j++)
            {
                sb.Append(j == k ? " >> " : "    ").Append(j).Append(": ")
                  .Append(Describe(ins[j])).Append('\n');
            }
            if (found >= 4) break;
        }
    }
    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_rtext OK  found=" + found);
}
catch (Exception ex)
{
    Console.WriteLine("probe_rtext FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
