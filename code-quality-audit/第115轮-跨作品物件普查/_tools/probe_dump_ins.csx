// probe_dump_ins.csx —— 反射一个指令对象的**全部字段**，找出 `PushBltn` 的内置变量存在哪
//
// 之前两次都栽在同一处：按猜的属性名去 GF()，取不到就静默打空（`BUILTIN=` 一次没出现）。
// 这一次不猜了 —— 直接把指令对象的属性/字段全列出来，名字和值都打。
//
// 顺带把 room1 / room2 的 Alarm 前 60 条也打出来（上一版被 `done>=6` 截掉了）。
//
// 用法：UndertaleModCli.exe load <game.droid 副本> -s probe_dump_ins.csx
// 输出：probe_dump_ins.txt
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
string outTxt = Path.Combine(dir, "probe_dump_ins.txt");

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

string Val(object v)
{
    if (v == null) return "(null)";
    if (v is UndertaleString) return "'" + ((UndertaleString)v).Content + "'";
    object nm = GF(v, "Name");
    if (nm is UndertaleString) return "{" + ((UndertaleString)nm).Content + "}";
    return Convert.ToString(v);
}

void DumpIns(StringBuilder sb, object ins, int idx)
{
    sb.Append("---- ins[").Append(idx).Append("] 类型=")
      .Append(ins == null ? "null" : ins.GetType().FullName).Append('\n');
    if (ins == null) return;
    Type t = ins.GetType();
    foreach (PropertyInfo p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance))
    {
        if (!p.CanRead) continue;
        if (p.GetIndexParameters().Length > 0) continue;
        object v = null;
        try { v = p.GetValue(ins, null); } catch { continue; }
        if (v == null) continue;
        string s = Val(v);
        if (s == "0" || s == "False" || s == "") continue;
        sb.Append("      ").Append(p.Name).Append(" = ").Append(s).Append('\n');
    }
}

try
{
    var sb = new StringBuilder();
    int dumped = 0;
    int reflected = 0;

    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        if (cn.IndexOf("obj_readable", StringComparison.Ordinal) < 0) continue;
        if (cn.IndexOf("_Alarm_", StringComparison.Ordinal) < 0) continue;
        bool wantDump = cn.IndexOf("room1", StringComparison.Ordinal) >= 0
                     || cn.IndexOf("room2", StringComparison.Ordinal) >= 0;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null || ins.Count == 0) continue;

        if (wantDump)
        {
            dumped++;
            sb.Append("\n===== ").Append(cn).Append("  ins=").Append(ins.Count).Append(" =====\n");
            int lim = Math.Min(60, ins.Count);
            for (int j = 0; j < lim; j++)
            {
                string k = GS(ins[j], "Kind");
                string st = null;
                object vs = GF(ins[j], "ValueString");
                if (vs is UndertaleString) st = ((UndertaleString)vs).Content;
                object bv = GF(ins[j], "ValueBuiltinVariable");
                object vi = GF(ins[j], "ValueInt");
                object vsh = GF(ins[j], "ValueShort");
                sb.Append(String.Format("{0,5}: {1}", j, k));
                if (st != null) sb.Append(" str='").Append(st).Append("'");
                if (bv != null) sb.Append(" BLTN=").Append(Val(bv));
                if (vi != null) sb.Append(" int=").Append(Val(vi));
                if (vsh != null) sb.Append(" short=").Append(Val(vsh));
                sb.Append('\n');
            }
        }

        // 只在第一条 PushBltn 上做一次全字段反射（够回答问题，不刷屏）
        if (reflected < 2)
        {
            for (int j = 0; j < ins.Count; j++)
            {
                if (GS(ins[j], "Kind") != "PushBltn") continue;
                sb.Append("\n>>>> 反射 PushBltn @").Append(cn).Append(" ins[").Append(j).Append("]\n");
                DumpIns(sb, ins[j], j);
                reflected++;
                break;
            }
        }
    }
    sb.Append("\n[room 段] = ").Append(dumped).Append("  [反射] = ").Append(reflected).Append('\n');

    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_dump_ins OK  dumped=" + dumped + " reflected=" + reflected);
}
catch (Exception ex)
{
    Console.WriteLine("probe_dump_ins FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
