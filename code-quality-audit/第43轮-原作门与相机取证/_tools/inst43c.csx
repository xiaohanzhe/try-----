using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 探针 I：对象创建普查 v3
// ★ 修正 v2 的 bug：变量 push（PushVar / PushLoc / PushBltn / PushGlb）也占一个压栈槽位。
//   必须把【所有】 Kind.StartsWith("Push") 的指令都算一槽，再用 pend[Count-n] 取第 1 个参数。
// GMS2 字节码：实参【从右往左】压栈 ⇒ f(a,b,c) 的压栈顺序是 c, b, a。
//   instance_create(x, y, obj)              n=3 -> pend[Count-3] = obj
//   instance_create_depth/layer(x,y,..,obj)  n=4 -> pend[Count-4] = obj
// A/B 三重锚点（ch1 已知真值）：
//   1) obj_doorA_musfade_Alarm_2           -> obj_persistentfadein (145)
//   2) obj_skychain_Step_0                 -> obj_fadechain       (250)
//   3) obj_getsusieevent_Create_0 第3处    -> obj_doorA           (97)
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "inst43c.txt");
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
        var pend = new List<string>();       // 每个元素 = 一个压栈槽（字符串或 "?"）
        for (int k = 0; k < li.Count; k++)
        {
            object ins = li[k];
            string kind = GS(ins, "Kind") ?? "";
            if (kind.StartsWith("Push"))
            {
                string t1 = GS(ins, "Type1");
                string v = null;
                if (t1 == "Int16") v = GS(ins, "ValueShort");
                else if (t1 == "Int32") v = GS(ins, "ValueInt");
                else if (t1 == "Int64") v = GS(ins, "ValueLong");
                else if (t1 == "Variable") v = ResName(GO(ins, "ValueVariable"));
                else if (t1 == "String") v = GS(ins, "ValueString");
                pend.Add(v == null ? "?" : v);
                if (pend.Count > 10) pend.RemoveAt(0);
                continue;
            }
            string fn = ResName(GO(ins, "ValueFunction"));
            if (fn != null && fn.IndexOf("instance_create", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                nSites++;
                int n = (fn.IndexOf("_depth", StringComparison.OrdinalIgnoreCase) >= 0
                         || fn.IndexOf("_layer", StringComparison.OrdinalIgnoreCase) >= 0) ? 4 : 3;
                string oidx = pend.Count >= n ? pend[pend.Count - n] : "?";
                long oi;
                string onm;
                if (Int64.TryParse(oidx, out oi) && oname.ContainsKey(oi)) onm = oname[oi];
                else { onm = "?未知(arg=" + oidx + ")"; nUnknown++; }
                if (!createCnt.ContainsKey(onm)) createCnt[onm] = 0;
                createCnt[onm]++;
                if (!createBy.ContainsKey(onm)) createBy[onm] = new List<string>();
                if (createBy[onm].Count < 80) createBy[onm].Add(cn);
                lines.Add("   " + cn + "  --" + fn + "--> " + onm + "  (arg=" + oidx + ", n=" + n + ")");
            }
            if (fn != null) pend.Clear();
        }
    }

    // ---- A/B 三重锚点 ----
    sb.AppendLine("== A/B 锚点校验 ==");
    string[] anchors = new string[] { "obj_doorA_musfade_Alarm_2", "obj_skychain_Step_0", "obj_getsusieevent_Create_0" };
    foreach (string a in anchors)
        foreach (string l in lines)
            if (l.IndexOf(a + "  --", StringComparison.OrdinalIgnoreCase) >= 0) sb.AppendLine("  " + l.Trim());
    sb.AppendLine();
    sb.AppendLine("== instance_create* 调用点 = " + nSites + " ；解不出对象名 = " + nUnknown + " ==");
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
