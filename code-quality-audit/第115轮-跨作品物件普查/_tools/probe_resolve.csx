// probe_resolve.csx —— 把 readable Alarm 里的**内置变量名**与**调用函数名**解出来
//
// 上一版只看到 `PushBltn <int>` / `Call <int>`，不知道是 `room` 还是 `id`，
// 也不知道 Call 的是 `scr_textdata` 还是别的 —— 这一步不解析就只能猜，而猜测不算证据。
//
// 解析方式（三个都试，取第一个成功的）：
//   ① 值对象上的 `ValueBuiltinVariable` / `ValueFunction` 直接 ToString()
//   ② 其 `Type` 属性 / `Resource.Name`
//   ③ UTMT 的 `Data.Functions`（按索引取名）
//
// 用法：UndertaleModCli.exe load <game.droid 副本> -s probe_resolve.csx
// 输出：probe_resolve.txt
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
string outTxt = Path.Combine(dir, "probe_resolve.txt");

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

string ResolveName(object res)
{
    if (res == null) return null;
    if (res is UndertaleString) return ((UndertaleString)res).Content;
    object nm = GF(res, "Name");
    if (nm is UndertaleString) return ((UndertaleString)nm).Content;
    if (nm != null) return Convert.ToString(nm);
    return null;
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

string BuiltinOf(object ins)
{
    object v = GF(ins, "ValueBuiltinVariable");
    if (v == null) return null;
    string s = Convert.ToString(v);
    // 若枚举 ToString 给了数字（未定义值），退回 Type 字段
    if (!String.IsNullOrEmpty(s) && !Char.IsDigit(s[0])) return s;
    object ty = GF(v, "Type");
    if (ty != null) return Convert.ToString(ty);
    return s;
}

string FuncOf(object ins)
{
    object v = GF(ins, "ValueFunction");
    if (v == null) return null;
    string n = ResolveName(v);
    if (!String.IsNullOrEmpty(n)) return n;
    object res = GF(v, "Resource");
    n = ResolveName(res);
    if (!String.IsNullOrEmpty(n)) return n;
    return Convert.ToString(v);
}

string Describe(object ins)
{
    if (ins == null) return "(null)";
    var sb = new StringBuilder();
    string kind = GS(ins, "Kind");
    sb.Append(kind);
    string t1 = GS(ins, "Type1");
    if (t1 != "") sb.Append(" t1=").Append(t1);
    string s = StrOf(ins);
    if (s != null) sb.Append(" str='").Append(s).Append("'");
    string b = BuiltinOf(ins);
    if (!String.IsNullOrEmpty(b)) sb.Append(" BUILTIN=").Append(b);
    string fn = FuncOf(ins);
    if (!String.IsNullOrEmpty(fn)) sb.Append(" FN=").Append(fn);
    object vv = GF(ins, "ValueVariable");
    if (vv is UndertaleString) sb.Append(" var=").Append(((UndertaleString)vv).Content);
    object vi = GF(ins, "ValueInt");
    if (vi != null) sb.Append(" int=").Append(Convert.ToString(vi));
    object vsh = GF(ins, "ValueShort");
    if (vsh != null) sb.Append(" short=").Append(Convert.ToString(vsh));
    return sb.ToString();
}

try
{
    var sb = new StringBuilder();
    int done = 0;

    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        if (cn.IndexOf("obj_readable", StringComparison.Ordinal) < 0) continue;
        if (cn.IndexOf("_Alarm_", StringComparison.Ordinal) < 0) continue;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null || ins.Count == 0) continue;
        done++;

        sb.Append("\n----- ").Append(cn).Append("  ins=").Append(ins.Count).Append(" -----\n");
        int lim = Math.Min(60, ins.Count);
        for (int j = 0; j < lim; j++)
            sb.Append(String.Format("{0,5}: {1}\n", j, Describe(ins[j])));

        if (done >= 6) break;
    }
    sb.Append("\n[解析段数] = ").Append(done).Append('\n');

    // 附带：Data.Functions 前若干条，便于核对 Call 索引
    sb.Append("\n=== Data.Functions 抽样 ===\n");
    object fns = GF(Data, "Functions");
    if (fns is IList)
    {
        var fl = (IList)fns;
        sb.Append("count=").Append(fl.Count).Append('\n');
        for (int i = 0; i < fl.Count && i < 12; i++)
            sb.Append(String.Format("  [{0}] {1}\n", i, ResolveName(fl[i])));
        // 关键几个
        foreach (int idx in new int[] { 36, 56, 76, 104, 108, 244, 620, 4600, 10708 })
            if (idx < fl.Count)
                sb.Append(String.Format("  @{0} => {1}\n", idx, ResolveName(fl[idx])));
    }
    else sb.Append("(Data.Functions 取不到)\n");

    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_resolve OK  alarms=" + done);
}
catch (Exception ex)
{
    Console.WriteLine("probe_resolve FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
