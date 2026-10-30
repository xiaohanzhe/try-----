// dump_tiles120.csx —— 第120轮：GMS2 的「legacy tiles」全量导出
//
// 事实（probe_legacy120 实测）：ut 的 484 个 Assets 层里躺着 **68,889 块 legacy tile**，
// 类型是 `UndertaleRoom.Tile`，`spriteMode=True` ⇒ 每块 = 从某个 Sprite 上抠
// (SourceX,SourceY,W,H) 的一块贴到 (X,Y)。UT 的房间美术（地板/墙/瓦）**全在这里**。
//
// 关键技巧：每块 tile 自带 `Tpag`（**正好就是那块子的纹理页子项**），所以不必自己算
// sprite-sheet 的裁剪坐标，直接把 Tpag 导成 PNG 就能贴 —— 少一整层易错的数学。
// 去重靠 `Data.TexturePageItems.IndexOf(Tpag)`。
//
// 用法：UTMT_OUT=<tsv> load <data> -s dump_tiles120.csx
// 产物：
//   <UTMT_OUT>                 参数表
//   <outdir>/tex/t_<tpag>.png  每张用到的 tile 图
//
// TSV 段：
//   META key value
//   TP   tpagIdx bytes boundingW boundingH sourceX sourceY
//   TLE  roomIdx layerDepth tpagIdx x y srcX srcY w h sx sy color vis
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

EnsureDataLoaded();

string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath))
{
    ScriptError("UTMT_OUT not set");
    return;
}

string dir = Path.GetDirectoryName(outPath);
string texDir = Path.Combine(dir, "tex");
Directory.CreateDirectory(texDir);

var sb = new StringBuilder();
var seen = new Dictionary<int, UndertaleTexturePageItem>();
long nTiles = 0;

for (int ri = 0; ri < Data.Rooms.Count; ri++)
{
    var r = Data.Rooms[ri];
    if (r?.Layers == null) continue;
    int li = 0;
    foreach (var lay in r.Layers)
    {
        if (lay == null) { li++; continue; }
        if (lay.LayerType == UndertaleRoom.LayerType.Assets && lay.AssetsData != null
            && lay.AssetsData.LegacyTiles != null && lay.AssetsData.LegacyTiles.Count > 0)
        {
            int depth = lay.LayerDepth;
            bool vis = lay.IsVisible;
            foreach (var t in lay.AssetsData.LegacyTiles)
            {
                if (t == null) continue;
                int idx = -1;
                if (t.Tpag != null)
                {
                    idx = Data.TexturePageItems.IndexOf(t.Tpag);
                    if (!seen.ContainsKey(idx)) seen[idx] = t.Tpag;
                }
                sb.Append("TLE\t").Append(ri).Append('\t').Append(depth).Append('\t').Append(idx)
                  .Append('\t').Append(t.X).Append('\t').Append(t.Y)
                  // ★ 第120轮修正：Tpag 是**精灵整帧**，tile 抠的是它内部的 (SourceX,SourceY,W,H)。
                  //   漏了 SourceX/SourceY 就会把整帧当一块贴上去（画面全糊），必须记下来。
                  .Append('\t').Append(t.SourceX).Append('\t').Append(t.SourceY)
                  .Append('\t').Append(t.Width).Append('\t').Append(t.Height)
                  .Append('\t').Append(t.ScaleX.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
                  .Append('\t').Append(t.ScaleY.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
                  .Append('\t').Append(t.Color)
                  .Append('\t').Append(vis ? 1 : 0)
                  .Append('\n');
                nTiles++;
            }
        }
        li++;
    }
}

sb.Append("META\tTiles\t").Append(nTiles).Append('\n');
sb.Append("META\tUniqueTpag\t").Append(seen.Count).Append('\n');

int ok = 0, fail = 0;
using (TextureWorker worker = new TextureWorker())
{
    foreach (var kv in seen)
    {
        var tp = kv.Value;
        if (tp == null) continue;
        string f = Path.Combine(texDir, "t_" + kv.Key + ".png");
        try
        {
            // ★ includePadding=true：导出尺寸 = BoundingWidth/Height，和 tile 的
            //   (SourceX,SourceY,W,H) **同一坐标系**。默认 false 会把透明边裁掉，
            //   裁剪坐标就会整体偏几个像素（实测 137 张里有 44 张尺寸不一致）。
            worker.ExportAsPNG(tp, f, null, true);
            sb.Append("TP\t").Append(kv.Key).Append('\t').Append(new FileInfo(f).Length)
              .Append('\t').Append(tp.BoundingWidth).Append('\t').Append(tp.BoundingHeight)
              .Append('\t').Append(tp.SourceX).Append('\t').Append(tp.SourceY)
              .Append('\n');
            ok++;
        }
        catch (Exception ex)
        {
            sb.Append("TP_FAIL\t").Append(kv.Key).Append('\t').Append(ex.GetType().Name)
              .Append(": ").Append(ex.Message).Append('\n');
            fail++;
        }
    }
}
sb.Append("META\tExportOK\t").Append(ok).Append('\n');
sb.Append("META\tExportFail\t").Append(fail).Append('\n');

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("tiles done -> " + outPath);
