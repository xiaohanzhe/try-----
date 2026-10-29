// probe_readable_alarm.csx —— 可读物的正文到底怎么落到实例上
//
// 第一版探针结论：Create 事件只初始化变量（无字符串），正文在 `Alarm_0`
// （room1 有 1882 条指令，room2 1595，room3 773，room4 647，room5 723）。
//
// 这一版要回答两个互斥的可能：
//   (A) Alarm_0 里**内联**了正文（`if (room == X) text = "..."`）⇒ 根本不需要键，直接按房取文
//   (B) Alarm_0 里**按实例算出键**再查 textdata ⇒ 才需要"实例→键"的规则
//
// 做法：对每个 readable 对象的 Alarm_0，统计字符串字面量数量、打印前 120 条指令、
//       并把**前 6 个字符串常量**原样列出来（够判断是正文还是键名）。
//
// 用法：UndertaleModCli.exe load <game.droid 副本> -s probe_readable_alarm.csx
// 输出：probe_readable_alarm.txt
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
string outTxt = Path.Combine(dir, "probe_readable_alarm.txt");

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
    object v = GF(ins, "ValueString");
    if (v != null && !(v is UndertaleString))
    {
        object res = GF(v, "Resource");
        if (res is UndertaleString) v = res;
    }
    if (v is UndertaleString) return ((UndertaleString)v).Content;
    return null;
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
    string s = StrOf(ins);
    if (s != null) sb.Append(" str='").Append(s).Append("'");
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
    int n = 0;

    // ① 先列 scr_textdata* 的代码名（键名解引用那一层）
    sb.Append("=== ① 名字含 textdata 的 Code ===\n");
    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        if (cn.IndexOf("textdata", StringComparison.OrdinalIgnoreCase) < 0) continue;
        var ins0 = (IList)GF(code, "Instructions");
        sb.Append(String.Format("  {0,-46} ins={1}\n", cn, ins0 == null ? -1 : ins0.Count));
    }

    // ② 每个 readable 对象的 Alarm_0
    sb.Append("\n=== ② readable 的 Alarm_0：字符串统计 + 前 120 指令 ===\n");
    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        if (cn.IndexOf("obj_readable", StringComparison.Ordinal) < 0) continue;
        if (cn.IndexOf("_Alarm_", StringComparison.Ordinal) < 0) continue;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null || ins.Count == 0) continue;
        n++;

        int nstr = 0;
        var heads = new List<string>();
        for (int k = 0; k < ins.Count; k++)
        {
            string s = StrOf(ins[k]);
            if (s == null) continue;
            nstr++;
            if (heads.Count < 6) heads.Add(s.Length > 70 ? s.Substring(0, 70) + "…" : s);
        }

        sb.Append("\n----- ").Append(cn).Append("  ins=").Append(ins.Count)
          .Append("  字符串常量=").Append(nstr).Append(" -----\n");
        for (int k = 0; k < heads.Count; k++)
            sb.Append("   str#").Append(k + 1).Append(": '").Append(heads[k]).Append("'\n");

        int lim = Math.Min(120, ins.Count);
        for (int j = 0; j < lim; j++)
            sb.Append(String.Format("{0,5}: {1}\n", j, Describe(ins[j])));
        if (ins.Count > lim) sb.Append("   …（共 ").Append(ins.Count).Append(" 条，此处截断）\n");
    }
    sb.Append("\n[Alarm 段数] = ").Append(n).Append('\n');

    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_readable_alarm OK  alarms=" + n);
}
catch (Exception ex)
{
    Console.WriteLine("probe_readable_alarm FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
