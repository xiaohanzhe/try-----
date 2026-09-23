using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 探针 D：变量名 / 字符串 / 内建引用 全量普查
// 产出 var43.txt（关键字筛选）+ var43_all.txt（全量变量）
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "var43.txt");
string outAll = Path.Combine(dir, "var43_all.txt");
var sb = new StringBuilder();
var sa = new StringBuilder();

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

string[] KW = new string[] {
    "background","bg_","view","camera","shake","room","dark","fade","layer",
    "scroll","pan","transition","screen","depth","marker","offset","warp","prefetch"
};

bool Has(string s)
{
    if (s == null) return false;
    foreach (string k in KW)
        if (s.IndexOf(k, StringComparison.OrdinalIgnoreCase) >= 0) return true;
    return false;
}

try
{
    var codes = (IList)GO(Data, "Code");
    var varCnt = new Dictionary<string, int>();
    var strCnt = new Dictionary<string, int>();
    var bltnCnt = new Dictionary<string, int>();
    int nInstr = 0;
    for (int i = 0; i < codes.Count; i++)
    {
        object instrs = GO(codes[i], "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        for (int k = 0; k < li.Count; k++)
        {
            nInstr++;
            object ins = li[k];
            string vn = ResName(GO(ins, "ValueVariable"));
            if (vn != null) { if (!varCnt.ContainsKey(vn)) varCnt[vn] = 0; varCnt[vn]++; }
            string sn = GS(ins, "ValueString");
            if (sn != null) { if (!strCnt.ContainsKey(sn)) strCnt[sn] = 0; strCnt[sn]++; }
            string bn = ResName(GO(ins, "ValueFunction"));
            // ValueFunction 已单独统计；此处再收 PushBltn 形式
            if (bn == null) { bn = ResName(GO(ins, "ValueBuiltin")); }
            if (bn != null) { if (!bltnCnt.ContainsKey(bn)) bltnCnt[bn] = 0; bltnCnt[bn]++; }
            // 逐个属性名再兜底：builtin
            if (bn == null)
            {
                string kind = GS(ins, "Kind");
                if (kind != null && kind.IndexOf("Bltn", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    foreach (string pn in new string[] { "ValueBuiltIn", "ValueBuiltin", "Builtin", "Value" })
                    {
                        string x = ResName(GO(ins, pn));
                        if (x != null) { bn = x; break; }
                    }
                    if (bn != null) { if (!bltnCnt.ContainsKey(bn)) bltnCnt[bn] = 0; bltnCnt[bn]++; }
                }
            }
        }
    }

    sb.AppendLine("== [A] 指令=" + nInstr + " ；不同变量名=" + varCnt.Count
                  + " ；不同字符串=" + strCnt.Count + " ；不同函数/内建=" + bltnCnt.Count + " ==");
    sb.AppendLine();
    sb.AppendLine("-- 变量名（关键字命中，按次数降序）--");
    var vs = new List<KeyValuePair<string, int>>();
    foreach (var kv in varCnt) if (Has(kv.Key)) vs.Add(kv);
    vs.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { int c = b.Value.CompareTo(a.Value); return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key); });
    foreach (var kv in vs) sb.AppendLine("   " + kv.Value + "\t" + kv.Key);
    sb.AppendLine("命中变量数 = " + vs.Count);
    sb.AppendLine();

    sb.AppendLine("-- 字符串字面量（关键字命中，按次数降序）--");
    var ss = new List<KeyValuePair<string, int>>();
    foreach (var kv in strCnt) if (Has(kv.Key)) ss.Add(kv);
    ss.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { int c = b.Value.CompareTo(a.Value); return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key); });
    foreach (var kv in ss) sb.AppendLine("   " + kv.Value + "\t" + kv.Key);
    sb.AppendLine("命中字符串数 = " + ss.Count);
    sb.AppendLine();

    sb.AppendLine("-- 内建/函数（关键字命中，按次数降序）--");
    var bs = new List<KeyValuePair<string, int>>();
    foreach (var kv in bltnCnt) if (Has(kv.Key)) bs.Add(kv);
    bs.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { int c = b.Value.CompareTo(a.Value); return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key); });
    foreach (var kv in bs) sb.AppendLine("   " + kv.Value + "\t" + kv.Key);
    sb.AppendLine("命中内建数 = " + bs.Count);

    // 全量变量导出
    var vall = new List<KeyValuePair<string, int>>(varCnt);
    vall.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { int c = b.Value.CompareTo(a.Value); return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key); });
    sa.AppendLine("== 全量变量名（次数降序）==");
    foreach (var kv in vall) sa.AppendLine(kv.Value + "\t" + kv.Key);

    // 全量字符串（前 1500）
    var sall = new List<KeyValuePair<string, int>>(strCnt);
    sall.Sort(delegate (KeyValuePair<string, int> a, KeyValuePair<string, int> b)
    { int c = b.Value.CompareTo(a.Value); return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key); });
    sa.AppendLine();
    sa.AppendLine("== 全量字符串（次数降序，前 1500）==");
    int lim = 0;
    foreach (var kv in sall) { sa.AppendLine(kv.Value + "\t" + kv.Key); if (++lim >= 1500) break; }
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
File.WriteAllText(outAll, sa.ToString(), new UTF8Encoding(false));
