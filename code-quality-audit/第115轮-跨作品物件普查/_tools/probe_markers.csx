// probe_markers.csx —— 找「谁在处理文本控制符」(/ % & ^1 ^2)
//
// 目的：可读物正文里带 `%` `&` `/` `^1` `^2`（第117轮资产原样保留、未解码）。
// 解码规则**不许拍脑袋**，必须从原作的文本绘制代码取证。本探针只做一件事：
// 在全部 `Data.Code` 的指令流里找「把 "/" / "%" / "&" / "^" 当字符串常量 push」
// 的位置 —— 谁拿来跟字符比，谁就是规则所在。
//
// 输出（UTF-8 无 BOM）：
//   MARK   <code 名>  <该 code 里命中的标记常量集合>  <命中次数>
//   CAND   <code 名>  <指令数>       —— 名字像文本框/绘字、且规模不大，供第二轮 dump
//   TOTAL  codes=…  hits=…  cands=…
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
string outTxt = Path.Combine(dir, "probe_markers.txt");

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

// 是否是「标记常量」：长度 1~4 且**全部由标记字符组成**（/ % & ^ 及 ^ 后的数字）
bool IsMarker(string s)
{
    if (String.IsNullOrEmpty(s) || s.Length > 4) return false;
    foreach (char c in s)
    {
        if (c != '/' && c != '%' && c != '&' && c != '^'
            && !(c >= '0' && c <= '9')) return false;
    }
    foreach (char c in s)
    {
        if (c == '/' || c == '%' || c == '&' || c == '^') return true;
    }
    return false;
}

try
{
    var sb = new StringBuilder();
    int codes = 0, hits = 0, cands = 0;

    foreach (var code in Data.Code)
    {
        codes++;
        string cn = GS(code, "Name");
        if (String.IsNullOrEmpty(cn)) continue;
        var ins = (IList)GF(code, "Instructions");
        if (ins == null || ins.Count == 0) continue;

        // ---- CAND：名字像文本绘制的 code，规模不大 ⇒ 值得整段 dump ----
        string low = cn.ToLowerInvariant();
        bool nameLike = (low.IndexOf("text") >= 0 || low.IndexOf("msg") >= 0
                         || low.IndexOf("dialog") >= 0 || low.IndexOf("dialoguer") >= 0)
                        && low.IndexOf("textdata") < 0;   // 正文表本身排除
        if (nameLike && ins.Count <= 400)
        {
            sb.Append("CAND\t").Append(cn).Append('\t').Append(ins.Count).Append('\n');
            cands++;
        }

        // ---- MARK：指令流里出现标记字符串常量 ----
        var seen = new SortedSet<string>();
        int n = 0;
        for (int j = 0; j < ins.Count; j++)
        {
            string kind = GS(ins[j], "Kind");
            if (kind != "Push") continue;
            string s = StrOf(ins[j]);
            if (!IsMarker(s)) continue;
            seen.Add(s);
            n++;
        }
        if (n > 0)
        {
            sb.Append("MARK\t").Append(cn).Append('\t');
            bool first = true;
            foreach (var s in seen)
            {
                if (!first) sb.Append(',');
                sb.Append(s);
                first = false;
            }
            sb.Append('\t').Append(n).Append('\n');
            hits++;
        }
    }

    sb.Append("TOTAL\tcodes=").Append(codes).Append("\thits=").Append(hits)
      .Append("\tcands=").Append(cands).Append('\n');

    File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_markers OK  codes=" + codes + " hits=" + hits + " cands=" + cands);
}
catch (Exception ex)
{
    Console.WriteLine("probe_markers FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
