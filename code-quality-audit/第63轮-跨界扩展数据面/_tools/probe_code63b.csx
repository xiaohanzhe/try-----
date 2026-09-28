using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

// ① 打印 UndertaleInstruction 的公开成员（属性 + 字段），搞清 API 真实形状。
//    ★ Data.Code[0] 可能是**空壳根节点**，必须找到第一个真正有指令的 code。
var members = new StringBuilder();
object ins0 = null;
string code0nm = "";
if (Data.Code != null)
{
    foreach (var c in Data.Code)
    {
        if (c.Instructions != null && c.Instructions.Count > 0)
        {
            ins0 = c.Instructions[0];
            code0nm = (c.Name == null) ? "?" : c.Name.Content;
            break;
        }
    }
}
if (ins0 != null)
{
    Type t = ins0.GetType();
    members.Append("CODE=").Append(code0nm).Append(" TYPE=").Append(t.FullName).Append(" | ");
    foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance))
        members.Append("P:").Append(p.Name).Append(" ");
    foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Instance))
        members.Append("F:").Append(f.Name).Append(" ");
}
ScriptMessage("MEMBERS " + members.ToString());

// ② 用"属性 + 字段"两路取值，统计有多少指令带 Room 引用。
var refTypes = new Dictionary<string, int>();
var valTypes = new Dictionary<string, int>();
long total = 0, withVal = 0, roomRef = 0;
if (Data.Code != null)
{
    foreach (var c in Data.Code)
    {
        if (c.Instructions == null) continue;
        foreach (var ins in c.Instructions)
        {
            total++;
            object v = Any(ins, "Value");
            if (v != null)
            {
                withVal++;
                string vt = v.GetType().Name;
                Bump(valTypes, vt);
                if (vt.IndexOf("Room") >= 0) roomRef++;
            }
            object rt = Any(ins, "ReferenceType");
            if (rt != null) Bump(refTypes, rt.ToString());
        }
    }
}
ScriptMessage("CODE instrs=" + total + " withValue=" + withVal + " roomRef=" + roomRef);
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

object Any(object o, string n)
{
    if (o == null) return null;
    Type t = o.GetType();
    PropertyInfo p = t.GetProperty(n);
    if (p != null)
    {
        try { return p.GetValue(o); } catch (Exception) { }
    }
    FieldInfo f = t.GetField(n);
    if (f != null)
    {
        try { return f.GetValue(o); } catch (Exception) { }
    }
    return null;
}
