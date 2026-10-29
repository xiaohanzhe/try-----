// probe_readable_key.csx —— 可读物「实例 → 文本键」到底怎么算出来的
//
// 背景：`textdata_*` 里的键长这样 `obj_readable_room1_64`，但实测**键数多于实例数**
//       （room1 211 键 vs 126 实例）⇒ 不是"一实例一键"。必须读代码，不能按顺序猜。
//
// 这一版只做两件事（都给眼睛看，不做推断）：
//   ① 列出所有名字含 `readable` 的 Dat.Code —— 找那条算键的辅助脚本
//   ② 把可读物对象的 **Create 事件整段指令**打出来（不截断）
//
// 用法：UndertaleModCli.exe load <game.droid 副本> -s probe_readable_key.csx
// 输出：probe_readable_key.txt
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
string outTxt = Path.Combine(dir, "probe_readable_key.txt");

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
    else
    {
        object vv2 = GF(ins, "ValueVariable2");
        if (vv2 is UndertaleString) sb.Append(" var2=").Append(((UndertaleString)vv2).Content);
    }
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
    var readables = new List<object>();
    var names = new List<string>();

    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        if (cn.IndexOf("readable", StringComparison.OrdinalIgnoreCase) < 0) continue;
        readables.Add(code);
        names.Add(cn);
    }

    sb.Append("=== ① 名字含 readable 的 Code 共 ").Append(readables.Count).Append(" 个 ===\n");
    for (int i = 0; i < readables.Count; i++)
    {
        var ins = (IList)GF(readables[i], "Instructions");
        sb.Append(String.Format("{0,4}. {1,-62} ins={2}\n",
            i + 1, names[i], ins == null ? -1 : ins.Count));
    }

    // ② 可读物对象的 Create 事件：整段打出来（这是"键怎么算"的唯一权威）
    sb.Append("\n=== ② Create 事件整段指令 ===\n");
    int dumped = 0;
    for (int i = 0; i < readables.Count; i++)
    {
        string cn = names[i];
        if (cn.IndexOf("_Create_", StringComparison.Ordinal) < 0) continue;
        if (cn.IndexOf("obj_readable", StringComparison.Ordinal) < 0) continue;
        var ins = (IList)GF(readables[i], "Instructions");
        if (ins == null || ins.Count == 0) continue;
        dumped++;
        sb.Append("\n----- ").Append(cn).Append("  (").Append(ins.Count).Append(" ins) -----\n");
        for (int j = 0; j < ins.Count; j++)
        {
            sb.Append(String.Format("{0,4}: {1}\n", j, Describe(ins[j])));
        }
        if (dumped >= 16) break;
    }
    sb.Append("\n[dumped Create events] = ").Append(dumped).Append('\n');

    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_readable_key OK  readables=" + readables.Count + " dumped=" + dumped);
}
catch (Exception ex)
{
    Console.WriteLine("probe_readable_key FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
