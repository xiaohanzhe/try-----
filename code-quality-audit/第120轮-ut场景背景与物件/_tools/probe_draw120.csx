// probe_draw120.csx —— 判「这个对象的 Draw 事件是不是就是默认的 draw_self」
//
// 背景：烘图时 `obj_overworldcontroller` 在每间房左上角留下一颗红心 ——
// 它有 Draw 事件，精灵是 spr_heartgtfo，只在战斗里画，平时什么都不画。
// 只看"有没有 Draw 事件"会误杀一堆正常物件（门/存档点这类），所以要看它**画什么**：
//   · 没有 Draw 事件        → GM 默认 draw_self ⇒ 可以照资产精灵画
//   · Draw 里有 draw_self   ⇒ 等价默认 ⇒ 可以画
//   · Draw 里没有 draw_self ⇒ 自绘（战斗专用/条件绘制）⇒ **不画**（画了就是假的）
//
// 用法：UTMT_OUT=<tsv> load <data> -s probe_draw120.csx
// 产物：
//   D   obj  drawEventName  hasDrawSelf(0/1)  nDrawCalls
//   DL  obj  line            （Draw 里所有含 draw/call 的行，用于人工复核）
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

var codeByName = new Dictionary<string, UndertaleCode>(StringComparer.Ordinal);
foreach (var c in Data.Code)
{
    if (c?.Name == null) continue;
    string n = c.Name.Content;
    if (!String.IsNullOrEmpty(n) && n.StartsWith("gml_Object_", StringComparison.Ordinal)
        && !codeByName.ContainsKey(n)) codeByName[n] = c;
}

var sb = new StringBuilder();
sb.Append("kind\tobj\tfield\tvalue\n");
int nNone = 0, nSelf = 0, nCustom = 0, nFail = 0;

foreach (var nm in placed)
{
    // GMS2 的 Draw 事件代码名：gml_Object_<obj>_Draw_0（自绘事件）
    string dn = "gml_Object_" + nm + "_Draw_0";
    UndertaleCode code;
    if (!codeByName.TryGetValue(dn, out code) || code == null)
    {
        sb.Append("D\t").Append(nm).Append("\t-\t-\t0\n");
        nNone++;
        continue;
    }
    try
    {
        string asm = Disassembler.Disassemble(code, Data.Variables, null, true);
        string[] lines = asm.Replace("\r\n", "\n").Split('\n');
        bool self = false;
        int calls = 0;
        var detail = new List<string>();
        foreach (var ln in lines)
        {
            string t = ln.Trim();
            if (t.Length == 0) continue;
            if (t.IndexOf("draw", StringComparison.OrdinalIgnoreCase) >= 0
                || t.IndexOf("call", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                if (t.IndexOf("draw_self", StringComparison.Ordinal) >= 0) self = true;
                if (t.IndexOf("call", StringComparison.OrdinalIgnoreCase) >= 0) calls++;
                if (detail.Count < 40) detail.Add(t);
            }
        }
        sb.Append("D\t").Append(nm).Append('\t').Append(dn).Append('\t')
          .Append(self ? 1 : 0).Append('\t').Append(calls).Append('\n');
        foreach (var d in detail) sb.Append("DL\t").Append(nm).Append('\t').Append(d).Append("\t\n");
        if (self) nSelf++; else nCustom++;
    }
    catch (Exception ex)
    {
        sb.Append("D_FAIL\t").Append(nm).Append('\t').Append(ex.GetType().Name).Append("\t\n");
        nFail++;
    }
}

sb.Append("META\tPlaced\t").Append(placed.Count).Append('\n');
sb.Append("META\tNoDraw\t").Append(nNone).Append('\n');
sb.Append("META\tDrawSelf\t").Append(nSelf).Append('\n');
sb.Append("META\tCustom\t").Append(nCustom).Append('\n');
sb.Append("META\tFail\t").Append(nFail).Append('\n');

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("draw probe done");
