// probe_visible120.csx —— 为什么需要它：烘图时把 `obj_overworldcontroller` 画成了
// 左上角一颗红心（资产里 visible=True，但它在 Create 里把自己设成不可见）。
// 「资产字段 visible」不等于「运行时可见」，所以要看 GML。
//
// 做法：不做整套对象模型解析，直接按**代码项命名约定**取：
//   gml_Object_<对象名>_Create_0   → 解编译后找 `visible = false/0`
//   gml_Object_<对象名>_Draw_*     → 存在即"自定义绘制"（我们不模拟，跳过）
//
// 用法：UTMT_OUT=<tsv> load <data> -s probe_visible120.csx
// 产物：OBJ \t name \t sprite \t assetVis \t hasDraw \t createHidden
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Decompiler;
using Underanalyzer.Decompiler;

EnsureDataLoaded();

string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath))
{
    ScriptError("UTMT_OUT not set");
    return;
}

// 1) 先把所有代码项的名字收集起来（一次遍历，避免每个对象扫全表）
var codeNames = new HashSet<string>(StringComparer.Ordinal);
var codeByName = new Dictionary<string, UndertaleCode>(StringComparer.Ordinal);
foreach (var c in Data.Code)
{
    if (c == null || c.Name == null) continue;
    string n = c.Name.Content;
    if (String.IsNullOrEmpty(n)) continue;
    if (n.StartsWith("gml_Object_", StringComparison.Ordinal))
    {
        codeNames.Add(n);
        if (!codeByName.ContainsKey(n)) codeByName[n] = c;
    }
}

var sb = new StringBuilder();
sb.Append("#\tOBJ\tname\tsprite\tassetVis\thasDraw\tcreateHidden\n");

GlobalDecompileContext ctx = null;
int nHidden = 0, nDraw = 0, nObj = 0, nDecompFail = 0;

var reHidden = new Regex(@"(?m)^\s*visible\s*=\s*(false|0)\s*;?",
                         RegexOptions.IgnoreCase);
var reVisibleTrue = new Regex(@"(?m)^\s*visible\s*=\s*(true|1)\s*;?",
                              RegexOptions.IgnoreCase);

foreach (var obj in Data.GameObjects)
{
    if (obj == null || obj.Name == null) continue;
    string nm = obj.Name.Content;
    if (String.IsNullOrEmpty(nm)) continue;
    nObj++;

    bool hasDraw = false;
    foreach (var n in codeNames)
    {
        if (n.StartsWith("gml_Object_" + nm + "_Draw_", StringComparison.Ordinal)) { hasDraw = true; break; }
    }

    bool hidden = false;
    string createName = "gml_Object_" + nm + "_Create_0";
    UndertaleCode cc;
    if (codeByName.TryGetValue(createName, out cc) && cc != null)
    {
        try
        {
            if (ctx == null) ctx = new GlobalDecompileContext(Data);
            string src = Underanalyzer.Decompiler.Decompiler.Decompile(cc, ctx);
            // 只认"最后一次赋值"：先看有没有 true，再按出现顺序取最后一个
            Match mh = reHidden.Match(src);
            Match mt = reVisibleTrue.Match(src);
            if (mh.Success && (!mt.Success || mh.Index > mt.Index)) hidden = true;
        }
        catch (Exception ex)
        {
            nDecompFail++;
            sb.Append("DECOMP_FAIL\t").Append(nm).Append('\t').Append(ex.GetType().Name).Append('\n');
        }
    }

    if (hasDraw) nDraw++;
    if (hidden) nHidden++;

    string sprName = obj.Sprite == null || obj.Sprite.Name == null ? "" : obj.Sprite.Name.Content;
    sb.Append("OBJ\t").Append(nm).Append('\t').Append(sprName).Append('\t')
      .Append(obj.Visible ? 1 : 0).Append('\t').Append(hasDraw ? 1 : 0)
      .Append('\t').Append(hidden ? 1 : 0).Append('\n');
}

sb.Append("META\tObjects\t").Append(nObj).Append('\n');
sb.Append("META\tCodeNames\t").Append(codeNames.Count).Append('\n');
sb.Append("META\tHasDraw\t").Append(nDraw).Append('\n');
sb.Append("META\tCreateHidden\t").Append(nHidden).Append('\n');
sb.Append("META\tDecompFail\t").Append(nDecompFail).Append('\n');

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("visible probe done -> " + outPath);
