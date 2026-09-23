using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 对象创建/引用普查：instance_create* 的 object 参数 + 变量名复核
// 产出 inst43.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "inst43.txt");
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
    var createCnt = new Dictionary<string, int>();   // 对象名 → 被创建次数
    var createBy = new Dictionary<string, List<string>>();
    int nSites = 0;
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
                if (v != null) { pend.Add(v); if (pend.Count > 6) pend.RemoveAt(0); }
            }
            string fn = ResName(GO(ins, "ValueFunction"));
            if (fn != null && fn.IndexOf("instance_create", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                nSites++;
                // instance_create(x, y, obj) 的 obj 是最后一个 PushI
                // instance_create_depth/layer(x, y, depth/layer, obj) 同
                string oidx = pend.Count > 0 ? pend[pend.Count - 1] : "?";
                long oi;
                string onm = "(未知)";
                if (Int64.TryParse(oidx, out oi) && oname.ContainsKey(oi)) onm = oname[oi];
                if (!createCnt.ContainsKey(onm)) createCnt[onm] = 0;
                createCnt[onm]++;
                if (!createBy.ContainsKey(onm)) createBy[onm] = new List<string>();
                if (createBy[onm].Count < 60) createBy[onm].Add(cn);
                lines.Add("   " + cn + "  --" + fn + "--> " + onm + "  (idx=" + oidx + ")");
                pend.Clear();
            }
            else if (fn != null) pend.Clear();
        }
    }

    sb.AppendLine("== instance_create* 调用点 = " + nSites + " ==");
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

    // 变量复核
    sb.AppendLine();
    sb.AppendLine("== 变量名复核 ==");
    var varCnt = new Dictionary<string, int>();
    for (int i = 0; i < codes.Count; i++)
    {
        object instrs = GO(codes[i], "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        for (int k = 0; k < li.Count; k++)
        {
            string vn = ResName(GO(li[k], "ValueVariable"));
            if (vn == null) continue;
            if (!varCnt.ContainsKey(vn)) varCnt[vn] = 0;
            varCnt[vn]++;
        }
    }
    foreach (string probe in new string[] { "initwd", "initht", "entrance", "doormarker", "cmarker", "thismarker", "darkzone", "plot", "touched", "panner", "bdir", "active", "timer" })
        sb.AppendLine("   " + probe + " = " + (varCnt.ContainsKey(probe) ? varCnt[probe].ToString() : "(不存在)"));
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
