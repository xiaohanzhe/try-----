// probe_key_users.csx —— 反查：某个文本键到底被**谁**引用（排除 textdata 表自身）
//
// 为什么需要：`obj_readable_*_Alarm_0` 里确实出现键名（switch1 有 6 个），
//   但那些是"填进槽位"（Call → Pop 到某个下标），不是"按实例选"。
//   要知道「这间房用哪个键」，必须找**真正的消费方** —— 通常是房间创建代码
//   （`gml_RoomCC_*`）或基类 `obj_readable` 的 Step。
//
// 做法：抽若干键（每个对象取前 2 个），扫描全库每段 Code 的字符串常量，
//       列出「含该键」的代码名（跳过 textdata_* 自己），并给出该键在其中的指令序号。
//
// 用法：UndertaleModCli.exe load <game.droid 副本> -s probe_key_users.csx
// 输出：probe_key_users.txt
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
string outTxt = Path.Combine(dir, "probe_key_users.txt");

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

try
{
    var sb = new StringBuilder();

    // ---- 收集全部 Code 的 (name, ins) ----
    var codes = new List<object>();
    var cnames = new List<string>();
    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        codes.Add(code);
        cnames.Add(cn);
    }
    sb.Append("[Code 总数] = ").Append(codes.Count).Append('\n');

    // ---- 抽样本键：从 readable 的 Alarm 里取（每对象前 2 个）----
    var samples = new List<string>();
    var seen = new Dictionary<string, int>();
    foreach (var code in codes)
    {
        string cn = GS(code, "Name");
        if (cn.IndexOf("obj_readable", StringComparison.Ordinal) < 0) continue;
        if (cn.IndexOf("_Alarm_", StringComparison.Ordinal) < 0) continue;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null) continue;
        string prefix = null;
        int taken = 0;
        for (int k = 0; k < ins.Count && taken < 2; k++)
        {
            string s = StrOf(ins[k]);
            if (s == null || !s.StartsWith("obj_readable")) continue;
            int dot = s.LastIndexOf('_');
            if (dot < 0) continue;
            string pfx = s.Substring(0, dot);
            if (prefix == null) prefix = pfx;
            if (pfx != prefix) continue;
            if (samples.Contains(s)) continue;
            samples.Add(s);
            taken++;
        }
    }
    sb.Append("[样本键] = ").Append(samples.Count).Append('\n');
    foreach (var s in samples) sb.Append("   ").Append(s).Append('\n');

    // ---- 反查每个样本键 ----
    sb.Append("\n=== 引用者（跳过 textdata_*）===\n");
    foreach (var key in samples)
    {
        sb.Append("\n### ").Append(key).Append('\n');
        int hits = 0;
        for (int i = 0; i < codes.Count; i++)
        {
            string cn = cnames[i];
            if (cn.IndexOf("textdata", StringComparison.OrdinalIgnoreCase) >= 0) continue;
            var ins = (IList)GF(codes[i], "Instructions");
            if (ins == null || ins.Count == 0) continue;
            for (int k = 0; k < ins.Count; k++)
            {
                string s = StrOf(ins[k]);
                if (s == null || s != key) continue;
                hits++;
                sb.Append("    ").Append(cn).Append("  @").Append(k)
                  .Append("/").Append(ins.Count).Append('\n');
                if (hits > 40) { sb.Append("    …（超过 40 处，截断）\n"); break; }
                break;   // 同一段代码里出现多次只报一次
            }
            if (hits > 40) break;
        }
        if (hits == 0) sb.Append("    (无：只有 textdata 表自己有)\n");
    }

    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_key_users OK  samples=" + samples.Count);
}
catch (Exception ex)
{
    Console.WriteLine("probe_key_users FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
