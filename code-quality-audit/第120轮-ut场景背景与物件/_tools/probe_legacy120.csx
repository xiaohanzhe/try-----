// probe_legacy120.csx —— Assets 层里的 LegacyTiles 到底装的是什么类型
// (GMS2 会把 GMS1.4 的 tiles 保留成 "legacy tiles"，UT 的房间美术很可能全在这里)
using System;
using System.IO;
using System.Text;
using System.Reflection;
using System.Collections;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();
string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath)) { ScriptError("UTMT_OUT not set"); return; }

var sb = new StringBuilder();
sb.Append("key\tvalue\n");
int nLayerWithLegacy = 0;
long nLegacy = 0;
bool dumpedType = false;
Type elemType = null;

for (int ri = 0; ri < Data.Rooms.Count; ri++)
{
    var r = Data.Rooms[ri];
    if (r?.Layers == null) continue;
    foreach (var lay in r.Layers)
    {
        if (lay == null || lay.AssetsData == null) continue;
        var lt = lay.AssetsData.LegacyTiles;
        if (lt == null || lt.Count == 0) continue;
        nLayerWithLegacy++;
        nLegacy += lt.Count;
        if (!dumpedType)
        {
            dumpedType = true;
            sb.Append("ROOM\t").Append(ri).Append('\n');
            sb.Append("LAYER\t").Append(lay.LayerName?.Content).Append('\t').Append(lay.LayerDepth).Append('\n');
            object first = lt[0];
            sb.Append("FIRST_TYPE\t").Append(first == null ? "<null>" : first.GetType().FullName).Append('\n');
            if (first != null)
            {
                elemType = first.GetType();
                foreach (var p in elemType.GetProperties(BindingFlags.Public | BindingFlags.Instance))
                    sb.Append("P\t").Append(p.Name).Append('\t').Append(p.PropertyType.Name).Append('\n');
                foreach (var f in elemType.GetFields(BindingFlags.Public | BindingFlags.Instance))
                    sb.Append("F\t").Append(f.Name).Append('\t').Append(f.FieldType.Name).Append('\n');
            }
            // 头 3 个元素的取值
            for (int i = 0; i < Math.Min(3, lt.Count); i++)
            {
                object o = lt[i];
                if (o == null) continue;
                var s2 = new StringBuilder();
                s2.Append("SAMPLE\t").Append(i);
                foreach (var p in o.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
                {
                    object v = null;
                    try { v = p.GetValue(o); } catch { }
                    string vs = v is UndertaleNamedResource nr ? (nr.Name?.Content ?? "<noname>")
                              : (v is UndertaleTexturePageItem tp ? ("tpag sx=" + tp.SourceX + " sy=" + tp.SourceY)
                              : (v == null ? "<null>" : v.ToString()));
                    s2.Append('\t').Append(p.Name).Append('=').Append(vs);
                }
                sb.Append(s2.ToString()).Append('\n');
            }
        }
    }
}
sb.Append("LAYERS_WITH_LEGACY\t").Append(nLayerWithLegacy).Append('\n');
sb.Append("LEGACY_TOTAL\t").Append(nLegacy).Append('\n');
File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("legacy probe done");
