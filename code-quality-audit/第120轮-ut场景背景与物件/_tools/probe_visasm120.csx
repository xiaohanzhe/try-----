// probe_visasm120.csx —— 用**反汇编**（不是反编译）判「对象在 Create 里把自己设成不可见」
//
// 为什么用汇编：这版 UTMT 没有可直接调用的 `Decompiler.Decompile`（只有 Underanalyzer 的
// `DecompileContext`，构造参数没文档），而 `Disassembler.Disassemble` 是明确的公开静态方法。
// 汇编里赋值就是 `push.e 0` + `pop.v [self] visible` 这一对，够判了。
//
// 用法：UTMT_OUT=<tsv> load <data> -s probe_visasm120.csx
// 产物：一行一条含 visible 的汇编语句 + 它前一条（给判据看"赋的是 0 还是 1"）
//   L \t obj \t idx \t prev \t cur
//
// ★ 只对「房间里摆了的对象」跑（全量 1720 个 × 反汇编太久，且没摆的也用不上）。
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Decompiler;

EnsureDataLoaded();
string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath)) { ScriptError("UTMT_OUT not set"); return; }

// 1) 房间实例引用到的对象名
var placed = new HashSet<string>(StringComparer.Ordinal);
foreach (var r in Data.Rooms)
{
    if (r?.Layers == null) continue;
    foreach (var lay in r.Layers)
    {
        if (lay == null || lay.LayerType != UndertaleRoom.LayerType.Instances) continue;
        var id = lay.InstancesData;
        if (id?.Instances == null) continue;
        foreach (var inst in id.Instances)
        {
            var o = inst?.ObjectDefinition as UndertaleGameObject;
            if (o?.Name != null) placed.Add(o.Name.Content);
        }
    }
}

// 2) 代码项索引
var codeByName = new Dictionary<string, UndertaleCode>(StringComparer.Ordinal);
var drawObjs = new HashSet<string>(StringComparer.Ordinal);
foreach (var c in Data.Code)
{
    if (c?.Name == null) continue;
    string n = c.Name.Content;
    if (String.IsNullOrEmpty(n) || !n.StartsWith("gml_Object_", StringComparison.Ordinal)) continue;
    if (!codeByName.ContainsKey(n)) codeByName[n] = c;
    if (n.Contains("_Draw_"))
    {
        int a = "gml_Object_".Length;
        int b = n.IndexOf("_Draw_", StringComparison.Ordinal);
        if (b > a) drawObjs.Add(n.Substring(a, b - a));
    }
}

var sb = new StringBuilder();
sb.Append("#\tobj\tidx\tprev\tcur\n");
int nDone = 0, nFail = 0, nWithVisible = 0;

foreach (var nm in placed)
{
    string cn = "gml_Object_" + nm + "_Create_0";
    UndertaleCode code;
    if (!codeByName.TryGetValue(cn, out code) || code == null)
    {
        sb.Append("NOCREATE\t").Append(nm).Append("\t\t\n");
        continue;
    }
    try
    {
        string asm = Disassembler.Disassemble(code, Data.Variables, null, true);
        string[] lines = asm.Replace("\r\n", "\n").Split('\n');
        bool any = false;
        for (int i = 0; i < lines.Length; i++)
        {
            string cur = lines[i];
            if (cur.IndexOf("visible", StringComparison.Ordinal) < 0) continue;
            string prev = i > 0 ? lines[i - 1] : "";
            sb.Append("L\t").Append(nm).Append('\t').Append(i).Append('\t')
              .Append(prev.Replace('\t', ' ')).Append('\t').Append(cur.Replace('\t', ' ')).Append('\n');
            any = true;
        }
        if (any) nWithVisible++;
        nDone++;
    }
    catch (Exception ex)
    {
        sb.Append("ASM_FAIL\t").Append(nm).Append('\t').Append(ex.GetType().Name)
          .Append(": ").Append(ex.Message).Append("\t\n");
        nFail++;
    }
}

sb.Append("META\tPlaced\t").Append(placed.Count).Append('\n');
sb.Append("META\tDone\t").Append(nDone).Append('\n');
sb.Append("META\tFail\t").Append(nFail).Append('\n');
sb.Append("META\tWithVisible\t").Append(nWithVisible).Append('\n');
foreach (var d in drawObjs) sb.Append("DRAW\t").Append(d).Append('\n');

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("visasm done");
