// dump_readable_bind.csx —— 把「房间 → 文本键」的绑定抽成结构化 TSV
//
// 已定的机理（三次探针逐步排除后剩下的唯一解释）：
//   `obj_readable_<kind>_Alarm_0` 里是一串
//       PushBltn{room} ; PushI <N> ; Cmp ; Bf <skip> ; Push 'obj_readable_<kind>_<M>' ; …
//   ⇒ **键由房间决定**，不是由实例坐标决定。
//   证据：`ValueVariable = {room}`（probe_dump_ins 的反射结果），
//         且每个键只被自己对象的 Alarm 引用一次（probe_key_users）。
//
// 输出列（TSV，UTF-8 无 BOM）：
//   alarm    obj    room_idx    key
//   room_idx = -1 表示"这条键前面没有 room 比较"（需人工看，不猜）
//
// 用法：UndertaleModCli.exe load <game.droid 副本> -s dump_readable_bind.csx
// 输出：readable_bind.tsv
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
string outTsv = Path.Combine(dir, "readable_bind.tsv");

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

string VarOf(object ins)
{
    object v = GF(ins, "ValueVariable");
    if (v is UndertaleString) return ((UndertaleString)v).Content;
    // ★ 实测：`PushBltn` 的 ValueVariable 是**资源对象**（反射出来是 `{room}`），
    //   名字在它的 `Name` 上。第一版只判 UndertaleString ⇒ guarded=0（静默全空）。
    object nm = GF(v, "Name");
    if (nm is UndertaleString) return ((UndertaleString)nm).Content;
    if (nm != null) return Convert.ToString(nm);
    return null;
}

int? IntOf(object ins)
{
    object sh = GF(ins, "ValueShort");
    object it = GF(ins, "ValueInt");
    if (sh != null)
    {
        try { return Convert.ToInt32(sh); } catch { }
    }
    if (it != null)
    {
        try { return Convert.ToInt32(it); } catch { }
    }
    return null;
}

try
{
    var sb = new StringBuilder();
    sb.Append("alarm\tobj\troom_idx\tkey\n");
    int rows = 0, guarded = 0;

    foreach (var code in Data.Code)
    {
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        if (cn.IndexOf("obj_readable", StringComparison.Ordinal) < 0) continue;
        if (cn.IndexOf("_Alarm_", StringComparison.Ordinal) < 0) continue;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null || ins.Count == 0) continue;

        // obj 名从 alarm 名里切出来：gml_Object_<obj>_Alarm_0
        string obj = cn;
        if (obj.StartsWith("gml_Object_")) obj = obj.Substring(11);
        int p1 = obj.IndexOf("_Alarm_", StringComparison.Ordinal);
        if (p1 > 0) obj = obj.Substring(0, p1);

        int pending = -1;      // 未消费的 room 守卫
        for (int j = 0; j < ins.Count; j++)
        {
            string kind = GS(ins[j], "Kind");
            if (kind == "PushBltn")
            {
                string v = VarOf(ins[j]);
                if (v == "room")
                {
                    // 期望形状：PushI <N> ; Cmp
                    if (j + 1 < ins.Count)
                    {
                        int? n = IntOf(ins[j + 1]);
                        string k2 = GS(ins[j + 1], "Kind");
                        if (n.HasValue && k2 == "PushI") pending = n.Value;
                    }
                }
                continue;
            }
            if (kind == "Push")
            {
                string s = StrOf(ins[j]);
                if (s == null || !s.StartsWith("obj_readable")) continue;
                sb.Append(cn).Append('\t').Append(obj).Append('\t')
                  .Append(pending).Append('\t').Append(s).Append('\n');
                rows++;
                if (pending >= 0) guarded++;
                pending = -1;    // 一个键只消费一次守卫
            }
        }
    }

    File.WriteAllText(outTsv, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("dump_readable_bind OK  rows=" + rows + " guarded=" + guarded);
}
catch (Exception ex)
{
    Console.WriteLine("dump_readable_bind FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
