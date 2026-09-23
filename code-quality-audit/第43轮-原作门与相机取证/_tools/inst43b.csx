using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 探针 G：对象创建普查 v2（修正参数顺序：GMS2 字节码从右往左压栈）
// instance_create(x, y, obj)              -> 压栈顺序 obj, y, x        => pend[Count-3] 是 obj
// instance_create_depth(x, y, depth, obj) -> 压栈顺序 obj, depth, y, x => pend[Count-4] 是 obj
// instance_create_layer(x, y, layer, obj) -> 同上
// A/B 校验锚点：ch1 的 obj_doorA_musfade_Alarm_2 必须解出 obj_persistentfadein(=145)
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "inst43b.txt");
var sb = new StringBuilder();

string GS(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    object v = null;
    try { v = p.GetValue(o); } catch (Exception) { return null; }
    return v == null ? null : v.ToString();
}

object GO(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

string ResName(object res)
{
    if (res == null) return null;
    object nv = GO(res, "Name");
    if (nv == null) return null;
    object cv = GO(nv, "Content");
    return cv == null ? null : cv.ToString();
}

try
{
    var objs = (IList)GO(Data, "GameObjects");
    var oname = new Dictionary<long, string>();
    for (int i = 0; i < objs.Count; i++) oname[i] = ResName(objs[i]);

    var codes = (IList)GO(Data, "Code");
    var createCnt = new Dictionary<string, int>();
    var createBy = new Dictionary<string, List<string>>();
    int nSites = 0, nUnknown = 0;
    var lines = new List<string>();

    for (int i = 0; i < codes.Count; i++)
    {
        object cd = codes[i];
        string cn = ResName(cd);
        object instrs = GO(cd, "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        var pend = new List<string>();
        for (int k = 0; k < li.Count; k++)
        {
            object ins = li[k];
            string kind = GS(ins, "Kind");
            if (kind != null && kind.StartsWith("Push"))
            {
                string t1 = GS(ins, "Type1");
                string v = null;
                if (t1 == "Int16") v = GS(ins, "ValueShort");
                else if (t1 == "Int32") v = GS(ins, "ValueInt");
                else if (t1 == "Int64") v = GS(ins, "ValueLong");
                if (v != null) { pend.Add(v); if (pend.Count > 8) pend.RemoveAt(0); }
            }
            string fn = ResName(GO(ins, "ValueFunction"));
            if (fn != null && fn.IndexOf("instance_create", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                nSites++;
                int n;
                if (fn.IndexOf("_depth", StringComparison.OrdinalIgnoreCase) >= 0
                    || fn.IndexOf("_layer", StringComparison.OrdinalIgnoreCase) >= 0) n = 4;
                else n = 3;
                string oidx = pend.Count >= n ? pend[pend.Count - n] : "?";
                long oi;
                string onm;
                if (Int64.TryParse(oidx, out oi) && oname.ContainsKey(oi)) onm = oname[oi];
                else { onm = "?未知(idx=" + oidx + ")"; nUnknown++; }
                if (!createCnt.ContainsKey(onm)) createCnt[onm] = 0;
                createCnt[onm]++;
                if (!createBy.ContainsKey(onm)) createBy[onm] = new List<string>();
                if (createBy[onm].Count < 60) createBy[onm].Add(cn);
                lines.Add("   " + cn + "  -> " + onm + "  (idx=" + oidx + ", argn=" + n + ")");
                pend.Clear();
            }
            else if (fn != null) pend.Clear();
        }
    }

    // A/B 校验锚点
    sb.AppendLine("== A/B 校验（ch1 已知真值）==");
    sb.AppendLine("  期望: obj_doorA_musfade_Alarm_2 -> obj_persistentfadein (idx 145)");
    foreach (string l in lines)
        if (l.IndexOf("obj_doorA_musfade_Alarm_2") >= 0) sb.AppendLine("  实测: " + l.Trim());
    sb.AppendLine();
    sb.AppendLine("== instance_create* 调用点 = " + nSites + " ；参数解不出对象名 = " + nUnknown + " ==");
    sb.AppendLine();
    sb.AppendLine("== 被创建的对象（按次数降序）==");
    var sorted = new List<KeyValuePair<string, int>>(createCnt);
    sorted.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { int c = b.Value.CompareTo(a.Value); return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key); });
    foreach (var kv in sorted)
    {
        sb.AppendLine("   " + kv.Value + "\t" + kv.Key);
        foreach (string s in createBy[kv.Key]) sb.AppendLine("        " + s);
    }
    sb.AppendLine();
    sb.AppendLine("== 全部调用点 ==");
    foreach (string l in lines) sb.AppendLine(l);
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
