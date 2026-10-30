// dump_layers120.csx —— 第120轮：按 GMS2 的 Layers 结构导出「房间怎么画」
//
// 背景（为什么重写）：ut 的 game.droid 被 UTMT 判定为 **IsGameMaker2 = True**，
// 所以房间内容不在 `room.Backgrounds` / `room.Tiles` 里（那是 GMS1.4 的旧槽位，
// 34 轮/115 轮的脚本一直读它们 ⇒ UT 这边永远 0 条）。真数据在 `room.Layers`。
// 这一版按 Layers 导出，并把背景层引用的 **Sprite** 逐张导出成 PNG。
//
// 用法：UTMT_OUT=<tsv> load <data> -s dump_layers120.csx
// 产物：
//   <UTMT_OUT>                    参数表（TSV）
//   <outdir>/tex/bg_<name>.png    每个 Tileset/Background 一张
//   <outdir>/tex/spr_<name>.png   背景层引用到的 Sprite（首帧）
//
// TSV 段：
//   META   key value
//   ROOM   idx name w h bgcolor drawbg
//   LAYER  roomIdx layerIdx layerName type depth visible
//   LBG    roomIdx layerIdx sprite xoff yoff ht vt stretch fg vis calcsx calcsy
//   LTL    roomIdx layerIdx tileset tilesX tilesY
//   ASSET  kind name bytes sheetx sheety
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

string Safe(UndertaleString s)
{
    if (s == null) return "";
    string t = s.Content;
    var b = new StringBuilder(t.Length);
    foreach (char c in t) b.Append(c == '\t' || c == '\n' || c == '\r' ? ' ' : c);
    return b.ToString();
}

string Fname(string nm)
{
    string safe = nm;
    foreach (char c in Path.GetInvalidFileNameChars()) safe = safe.Replace(c, '_');
    return safe;
}

// ---------- 1. 收集「房间背景层引用的 Sprite」与「图块层引用的 Tileset」 ----------
var wantSpr = new SortedDictionary<string, UndertaleSprite>(StringComparer.Ordinal);
var wantTileset = new SortedDictionary<string, UndertaleBackground>(StringComparer.Ordinal);
var layerRows = new List<string>();
long tileCells = 0;

for (int ri = 0; ri < Data.Rooms.Count; ri++)
{
    var r = Data.Rooms[ri];
    if (r == null) continue;
    sb.Append("ROOM\t").Append(ri).Append('\t').Append(Safe(r.Name))
      .Append('\t').Append(r.Width).Append('\t').Append(r.Height)
      .Append('\t').Append(r.BackgroundColor).Append('\t').Append(r.DrawBackgroundColor)
      .Append('\n');
    if (r.Layers == null) continue;
    int li = 0;
    foreach (var lay in r.Layers)
    {
        if (lay == null) { li++; continue; }
        sb.Append("LAYER\t").Append(ri).Append('\t').Append(li).Append('\t')
          .Append(Safe(lay.LayerName)).Append('\t').Append(lay.LayerType)
          .Append('\t').Append(lay.LayerDepth).Append('\t').Append(lay.IsVisible ? 1 : 0)
          .Append('\n');

        if (lay.LayerType == UndertaleRoom.LayerType.Background && lay.BackgroundData != null)
        {
            var bd = lay.BackgroundData;
            string sn = bd.Sprite == null ? "" : Safe(bd.Sprite.Name);
            if (!String.IsNullOrEmpty(sn) && bd.Sprite != null && !wantSpr.ContainsKey(sn))
                wantSpr[sn] = bd.Sprite;
            sb.Append("LBG\t").Append(ri).Append('\t').Append(li).Append('\t').Append(sn)
              .Append('\t').Append(bd.XOffset.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture))
              .Append('\t').Append(bd.YOffset.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture))
              .Append('\t').Append(bd.TiledHorizontally ? 1 : 0)
              .Append('\t').Append(bd.TiledVertically ? 1 : 0)
              .Append('\t').Append(bd.Stretch ? 1 : 0)
              .Append('\t').Append(bd.Foreground ? 1 : 0)
              .Append('\t').Append(bd.Visible ? 1 : 0)
              .Append('\t').Append(bd.CalcScaleX.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
              .Append('\t').Append(bd.CalcScaleY.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
              .Append('\t').Append(bd.Color)
              .Append('\n');
        }
        else if (lay.LayerType == UndertaleRoom.LayerType.Tiles && lay.TilesData != null)
        {
            var td = lay.TilesData;
            string tn = td.Background == null ? "" : Safe(td.Background.Name);
            if (!String.IsNullOrEmpty(tn) && td.Background != null && !wantTileset.ContainsKey(tn))
                wantTileset[tn] = td.Background;
            sb.Append("LTL\t").Append(ri).Append('\t').Append(li).Append('\t').Append(tn)
              .Append('\t').Append(td.TilesX).Append('\t').Append(td.TilesY)
              .Append('\n');
            // 图块网格的**非零单元数**（判定"图块层到底铺了多少"）
            if (td.TileData != null)
            {
                foreach (var row in td.TileData)
                {
                    if (row == null) continue;
                    foreach (var v in row) if (v != 0) tileCells++;
                }
            }
        }
        li++;
    }
}

sb.Append("META\tIsGameMaker2\t").Append(Data.IsGameMaker2()).Append('\n');
sb.Append("META\tRooms\t").Append(Data.Rooms.Count).Append('\n');
sb.Append("META\tWantSprites\t").Append(wantSpr.Count).Append('\n');
sb.Append("META\tWantTilesets\t").Append(wantTileset.Count).Append('\n');
sb.Append("META\tTileCells\t").Append(tileCells).Append('\n');

// ---------- 2. 导出贴图 ----------
int okS = 0, failS = 0, okT = 0, failT = 0;
using (TextureWorker worker = new TextureWorker())
{
    foreach (var kv in wantSpr)
    {
        var spr = kv.Value;
        string f = Path.Combine(texDir, "spr_" + Fname(kv.Key) + ".png");
        try
        {
            if (spr.Textures == null || spr.Textures.Count == 0 || spr.Textures[0] == null
                || spr.Textures[0].Texture == null)
            {
                sb.Append("SPR_NULLTEX\t").Append(kv.Key).Append('\n');
                continue;
            }
            worker.ExportAsPNG(spr.Textures[0].Texture, f);
            sb.Append("ASSET\tspr\t").Append(kv.Key).Append('\t').Append(new FileInfo(f).Length)
              .Append('\t').Append(spr.Textures[0].Texture.SourceX)
              .Append('\t').Append(spr.Textures[0].Texture.SourceY)
              .Append('\t').Append(spr.Width).Append('\t').Append(spr.Height)
              .Append('\n');
            okS++;
        }
        catch (Exception ex)
        {
            sb.Append("ASSET_FAIL\tspr\t").Append(kv.Key).Append('\t').Append(ex.GetType().Name)
              .Append(": ").Append(ex.Message).Append('\n');
            failS++;
        }
    }
    foreach (var kv in wantTileset)
    {
        var bg = kv.Value;
        string f = Path.Combine(texDir, "bg_" + Fname(kv.Key) + ".png");
        try
        {
            if (bg.Texture == null) { sb.Append("ASSET_NULLTEX\t").Append(kv.Key).Append('\n'); continue; }
            worker.ExportAsPNG(bg.Texture, f);
            sb.Append("ASSET\tbg\t").Append(kv.Key).Append('\t').Append(new FileInfo(f).Length)
              .Append('\t').Append(bg.Texture.SourceX).Append('\t').Append(bg.Texture.SourceY)
              .Append('\t').Append(bg.GMS2TileWidth).Append('\t').Append(bg.GMS2TileHeight)
              .Append('\t').Append(bg.GMS2TileColumns).Append('\t').Append(bg.GMS2TileSeparationX)
              .Append('\t').Append(bg.GMS2TileSeparationY)
              .Append('\n');
            okT++;
        }
        catch (Exception ex)
        {
            sb.Append("ASSET_FAIL\tbg\t").Append(kv.Key).Append('\t').Append(ex.GetType().Name)
              .Append(": ").Append(ex.Message).Append('\n');
            failT++;
        }
    }
}
sb.Append("META\tExportSprOK\t").Append(okS).Append('\n');
sb.Append("META\tExportSprFail\t").Append(failS).Append('\n');
sb.Append("META\tExportBgOK\t").Append(okT).Append('\n');
sb.Append("META\tExportBgFail\t").Append(failT).Append('\n');

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("layers done -> " + outPath);
