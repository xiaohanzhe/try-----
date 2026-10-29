// dump_ins_room119.csx —— 把指定代码入口的**完整指令流**按顺序打出来（含分支跳转目标）
//
// 为什么需要：第117轮的 `dump_readable_bind.csx` 用「`PushBltn room` 之后紧跟的 `PushI N`」
// 当作房间守卫，但它**没验证** N 到底是哪一间房。实测 `obj_readable_room5_177`
// 被记成 141（room_fire_lab1），而 GML 原文写的是 `room_fire2`（列表下标 138）——
// 两条取证路径冲突，必须回到指令流看**到底怎么编的**。
//
// 用法：set UTMT_OUT=<输出 txt>  set UTMT_CODES=<逗号分隔的代码名>  load <data> -s dump_ins_room119.csx
// 输出：idx \t kind \t value  （value 依次尝试 字符串 / 内置变量 / 整数 / 跳转偏移）
using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath)) { ScriptError("UTMT_OUT not set"); return; }
string want = Environment.GetEnvironmentVariable("UTMT_CODES");
if (String.IsNullOrEmpty(want)) { ScriptError("UTMT_CODES not set"); return; }
string[] codes = want.Split(',');

string GS(object o, string pn)
{
    if (o == null) return "";
    Type t = o.GetType();
    PropertyInfo p = t.GetProperty(pn, BindingFlags.Public | BindingFlags.Instance);
    object v = (p != null && p.CanRead) ? p.GetValue(o, null) : null;
    if (v == null)
    {
        FieldInfo f = t.GetField(pn, BindingFlags.Public | BindingFlags.Instance);
        if (f != null) v = f.GetValue(o);
    }
    if (v == null) return "";
    UndertaleString us = v as UndertaleString;
    if (us != null) return us.Content;
    PropertyInfo nm = v.GetType().GetProperty("Name");
    if (nm != null)
    {
        object nv = nm.GetValue(v, null);
        if (nv is UndertaleString) return "{" + ((UndertaleString)nv).Content + "}";
    }
    return Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture);
}

var sb = new StringBuilder();
int found = 0;
foreach (string cn in codes)
{
    var target = (UndertaleCode)null;
    foreach (var code in Data.Code)
    {
        if (code.Name != null && code.Name.Content == cn) { target = code; break; }
    }
    if (target == null) { sb.Append("!! 找不到 ").Append(cn).Append('\n'); continue; }
    found++;
    var ins = (IList)target.Instructions;
    sb.Append("===== ").Append(cn).Append("  ins=").Append(ins.Count).Append('\n');
    for (int j = 0; j < ins.Count; j++)
    {
        object it = ins[j];
        string kind = GS(it, "Kind");
        // 值：按 Push 类指令的类型分别取，取不到就留空（不猜）
        string val = GS(it, "ValueString");
        if (val.Length == 0) val = GS(it, "ValueVariable");
        if (val.Length == 0) val = GS(it, "ValueShort");
        if (val.Length == 0) val = GS(it, "ValueInt");
        // 跳转目标（BT/BF/JP 等）
        string jt = "";
        Type t = it.GetType();
        PropertyInfo jp = t.GetProperty("JumpOffset");
        if (jp != null)
        {
            object jv = jp.GetValue(it, null);
            if (jv != null) jt = Convert.ToString(jv);
        }
        if (jt.Length == 0)
        {
            PropertyInfo tp = t.GetProperty("Target");
            if (tp != null)
            {
                object tv = tp.GetValue(it, null);
                if (tv != null) jt = "@" + Convert.ToString(tv);
            }
        }
        sb.Append(j).Append('\t').Append(kind).Append('\t').Append(val);
        if (jt.Length > 0) sb.Append("\tjump=").Append(jt);
        sb.Append('\n');
    }
}

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("dump_ins_room119 OK found=" + found + "/" + codes.Length);
