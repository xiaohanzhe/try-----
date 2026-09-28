using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

// 目的：探清 `UndertaleInstruction` 在本版本里的"引用类型"表达方式，
// 以及 Data.Code 里到底有没有指向 Room 的引用（room_goto 的必要条件）。
// ★ 只统计、不输出大文件 —— 先探针，再决定怎么写。
var refTypes = new Dictionary<string, int>();
var valTypes = new Dictionary<string, int>();
long total = 0, withVal = 0, withRef = 0;
int codes = 0;

if (Data.Code != null)
{
    foreach (var c in Data.Code)
    {
        codes++;
        if (c.Instructions == null) continue;
        foreach (var ins in c.Instructions)
        {
            total++;
            object v = Prop(ins, "Value");
            if (v != null)
            {
                withVal++;
                string vt = v.GetType().Name;
                Bump(valTypes, vt);
            }
            object rt = Prop(ins, "ReferenceType");
            if (rt != null)
            {
                string rs = rt.ToString();
                Bump(refTypes, rs);
                if (rs != "None" && rs != "Instance") withRef++;
            }
        }
    }
}
ScriptMessage("CODE codes=" + codes + " instrs=" + total
    + " withValue=" + withVal + " withRef=" + withRef);
ScriptMessage("VALTYPES " + Dump(valTypes));
ScriptMessage("REFTYPES " + Dump(refTypes));

void Bump(Dictionary<string, int> d, string k)
{
    if (k == null) k = "(null)";
    if (!d.ContainsKey(k)) d[k] = 0;
    d[k] = d[k] + 1;
}

string Dump(Dictionary<string, int> d)
{
    var b = new StringBuilder();
    foreach (var kv in d) b.Append(kv.Key).Append("=").Append(kv.Value).Append(" ");
    return b.ToString();
}

object Prop(object o, string n)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(n);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}
