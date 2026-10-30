// dump_roomviz120.csx —— 第120轮：把「房间怎么画」需要的东西全部导出来
//
// 为什么要它：ut / outertale 在产品里是空壳（bg 全 null）。deltarune 那边每间房的
// 背景是一张现成 PNG，UT 不是 —— UT 的场景 = 背景层（可能平铺/拉伸）+ 图块层（Tiles）
// + 背景色。要还原，必须把这三样的**原始参数**导出来，再由 Python 合成一张 PNG。
//
// 用法：UTMT_OUT=<tsv> load <data> -s dump_roomviz120.csx
// 产物：
//   <UTMT_OUT>                       参数表（TSV）
//   <UTMT_OUT 同目录>/tex/bg_<名>.png  每个 Background/Tileset 一张（TextureWorker 导出）
//
// TSV 段（每行第一列是段名）：
//   META   key  value                  全局计数
//   ROOM   idx name w h bgcolor drawbgcolor
//   RBG    roomIdx slot asset x y ht vt stretch enabled fg calcsx calcsy
//   TILE   roomIdx asset x y srcx srcy w h sx sy depth sheetx sheety relx rely
//   ASSET  name pngW pngH sheetx sheety
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

// ---- 1. 导出所有 Background / Tileset 的贴图 ----
// 名字里可能有 Windows 非法字符 ⇒ 统一替换成 '_'，并记下原名以便回查。
var used = new Dictionary<string, string>();
int nExport = 0, nFail = 0;
using (TextureWorker worker = new TextureWorker())
{
    foreach (var bg in Data.Backgrounds)
    {
        if (bg == null || bg.Name == null) continue;
        string nm = bg.Name.Content;
        string safe = nm;
        foreach (char c in Path.GetInvalidFileNameChars()) safe = safe.Replace(c, '_');
        if (safe != nm) sb.Append("RENAME\t").Append(nm).Append('\t').Append(safe).Append('\n');
        if (used.ContainsKey(safe))
        {
            sb.Append("DUPNAME\t").Append(nm).Append('\n');
            safe = safe + "_" + nExport;
        }
        used[safe] = nm;
        string f = Path.Combine(texDir, "bg_" + safe + ".png");
        try
        {
            if (bg.Texture == null)
            {
                sb.Append("ASSET_NULLTEX\t").Append(nm).Append('\n');
                continue;
            }
            worker.ExportAsPNG(bg.Texture, f);
            var fi = new FileInfo(f);
            int sw = (int)bg.Texture.SourceX, sh = (int)bg.Texture.SourceY;
            sb.Append("ASSET\t").Append(nm).Append('\t').Append(fi.Length)
              .Append('\t').Append(sw).Append('\t').Append(sh).Append('\n');
            nExport++;
        }
        catch (Exception ex)
        {
            sb.Append("ASSET_FAIL\t").Append(nm).Append('\t').Append(ex.GetType().Name)
              .Append(": ").Append(ex.Message).Append('\n');
            nFail++;
        }
    }
}

sb.Append("META\tIsGameMaker2\t").Append(Data.IsGameMaker2()).Append('\n');
sb.Append("META\tRooms\t").Append(Data.Rooms.Count).Append('\n');
sb.Append("META\tBackgrounds\t").Append(Data.Backgrounds.Count).Append('\n');
sb.Append("META\tExportOK\t").Append(nExport).Append('\n');
sb.Append("META\tExportFail\t").Append(nFail).Append('\n');

// ---- 2. 逐房间 dump ----
string SafeName(UndertaleString s)
{
    if (s == null) return "";
    string t = s.Content;
    var b = new StringBuilder(t.Length);
    foreach (char c in t) b.Append(c == '\t' || c == '\n' || c == '\r' ? ' ' : c);
    return b.ToString();
}

long nTileRows = 0;
int nRooms = 0;
for (int ri = 0; ri < Data.Rooms.Count; ri++)
{
    var r = Data.Rooms[ri];
    if (r == null) continue;
    nRooms++;
    sb.Append("ROOM\t").Append(ri).Append('\t').Append(SafeName(r.Name))
      .Append('\t').Append(r.Width).Append('\t').Append(r.Height)
      .Append('\t').Append(r.BackgroundColor).Append('\t').Append(r.DrawBackgroundColor)
      .Append('\n');

    if (r.Backgrounds != null)
    {
        int slot = 0;
        foreach (var rb in r.Backgrounds)
        {
            if (rb == null) { slot++; continue; }
            sb.Append("RBG\t").Append(ri).Append('\t').Append(slot).Append('\t')
              .Append(rb.BackgroundDefinition == null ? "" : SafeName(rb.BackgroundDefinition.Name))
              .Append('\t').Append(rb.X).Append('\t').Append(rb.Y)
              .Append('\t').Append(rb.TiledHorizontally ? 1 : 0)
              .Append('\t').Append(rb.TiledVertically ? 1 : 0)
              .Append('\t').Append(rb.Stretch ? 1 : 0)
              .Append('\t').Append(rb.Enabled ? 1 : 0)
              .Append('\t').Append(rb.Foreground ? 1 : 0)
              .Append('\t').Append(rb.CalcScaleX.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
              .Append('\t').Append(rb.CalcScaleY.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
              .Append('\n');
            slot++;
        }
    }

    if (r.Tiles != null)
    {
        foreach (var t in r.Tiles)
        {
            if (t == null) continue;
            int sheetX = 0, sheetY = 0;
            string an = "";
            if (t.BackgroundDefinition != null)
            {
                an = SafeName(t.BackgroundDefinition.Name);
                var pg = t.BackgroundDefinition.Texture;
                if (pg != null) { sheetX = (int)pg.SourceX; sheetY = (int)pg.SourceY; }
            }
            sb.Append("TILE\t").Append(ri).Append('\t').Append(an)
              .Append('\t').Append(t.X).Append('\t').Append(t.Y)
              .Append('\t').Append(t.SourceX).Append('\t').Append(t.SourceY)
              .Append('\t').Append(t.Width).Append('\t').Append(t.Height)
              .Append('\t').Append(t.ScaleX.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
              .Append('\t').Append(t.ScaleY.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
              .Append('\t').Append(t.TileDepth)
              .Append('\t').Append(sheetX).Append('\t').Append(sheetY)
              .Append('\t').Append(t.SourceX - sheetX).Append('\t').Append(t.SourceY - sheetY)
              .Append('\n');
            nTileRows++;
        }
    }
}

sb.Append("META\tRoomsDumped\t").Append(nRooms).Append('\n');
sb.Append("META\tTileRows\t").Append(nTileRows).Append('\n');

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("roomviz done -> " + outPath);
