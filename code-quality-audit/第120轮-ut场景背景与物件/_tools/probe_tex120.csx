// probe_tex120.csx —— 第120轮探针：UTMT CLI 能不能把「背景贴图 / 精灵首帧」导出成 PNG
//
// 为什么要这一步：ut / outertale 的场景在产品里是空壳（objects 0 条、bg 全 null），
// 补它们的前提是**拿得到原作的图**。仓库里 499 张 bg 全是 deltarune + oneshot，
// 一张 ut 都没有 —— 说明这条路以前走过、但没把图落到仓库里。
//
// 用法：set UTMT_OUT=<输出 tsv> 后  load <data> -s probe_tex120.csx
// 产物：
//   <UTMT_OUT>              文本报告（计数 + 抽样名）
//   <UTMT_OUT 所在目录>/tex/ 抽样导出的 PNG（3 张背景 + 3 张精灵首帧）
//
// 判据：只有 PNG 真的落盘且非 0 字节，才说明 TextureWorker 在 CLI 下可用。
using System;
using System.IO;
using System.Text;
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
sb.Append("key\tvalue\n");
sb.Append("IsGameMaker2\t").Append(Data.IsGameMaker2()).Append('\n');
sb.Append("EmbeddedTextures\t").Append(Data.EmbeddedTextures.Count).Append('\n');
sb.Append("Sprites\t").Append(Data.Sprites.Count).Append('\n');
sb.Append("Backgrounds\t").Append(Data.Backgrounds.Count).Append('\n');
sb.Append("Rooms\t").Append(Data.Rooms.Count).Append('\n');
sb.Append("GameObjects\t").Append(Data.GameObjects.Count).Append('\n');

// ---- 抽样：3 张背景 ----
int nBg = 0, okBg = 0;
int nSpr = 0, okSpr = 0;
using (TextureWorker worker = new TextureWorker())
{
    foreach (var bg in Data.Backgrounds)
    {
        if (nBg >= 3) break;
        if (bg == null || bg.Name == null) continue;
        string nm = bg.Name.Content;
        nBg++;
        string f = Path.Combine(texDir, "bg_" + nm + ".png");
        try
        {
            if (bg.Texture == null)
            {
                sb.Append("BG_NULLTEX\t").Append(nm).Append('\n');
                continue;
            }
            worker.ExportAsPNG(bg.Texture, f);
            long sz = new FileInfo(f).Length;
            sb.Append("BG_EXPORT\t").Append(nm).Append('\t').Append(sz).Append('\n');
            if (sz > 0) okBg++;
        }
        catch (Exception ex)
        {
            sb.Append("BG_FAIL\t").Append(nm).Append('\t').Append(ex.GetType().Name)
              .Append(": ").Append(ex.Message).Append('\n');
        }
    }

    // ---- 抽样：3 张精灵首帧 ----
    foreach (var spr in Data.Sprites)
    {
        if (nSpr >= 3) break;
        if (spr == null || spr.Name == null) continue;
        if (spr.Textures == null || spr.Textures.Count == 0) continue;
        string nm = spr.Name.Content;
        nSpr++;
        string f = Path.Combine(texDir, nm + "_0.png");
        try
        {
            if (spr.Textures[0] == null || spr.Textures[0].Texture == null)
            {
                sb.Append("SPR_NULLTEX\t").Append(nm).Append('\n');
                continue;
            }
            worker.ExportAsPNG(spr.Textures[0].Texture, f);
            long sz = new FileInfo(f).Length;
            sb.Append("SPR_EXPORT\t").Append(nm).Append('\t').Append(sz)
              .Append('\t').Append(spr.Width).Append('x').Append(spr.Height).Append('\n');
            if (sz > 0) okSpr++;
        }
        catch (Exception ex)
        {
            sb.Append("SPR_FAIL\t").Append(nm).Append('\t').Append(ex.GetType().Name)
              .Append(": ").Append(ex.Message).Append('\n');
        }
    }

    // ---- 抽样：房间的 Backgrounds / Tiles 结构（决定能不能合成背景） ----
    if (Data.Rooms.Count > 2 && Data.Rooms[2] != null)
    {
        var r = Data.Rooms[2];
        sb.Append("ROOM2\t").Append(r.Name == null ? "" : r.Name.Content)
          .Append('\t').Append(r.Width).Append('x').Append(r.Height).Append('\n');
        sb.Append("ROOM2_BackgroundDefs\t").Append(r.Backgrounds == null ? -1 : r.Backgrounds.Count).Append('\n');
        if (r.Backgrounds != null)
        {
            int k = 0;
            foreach (var rb in r.Backgrounds)
            {
                if (k >= 6) break;
                k++;
                sb.Append("RBG\t").Append(k).Append('\t')
                  .Append(rb.BackgroundDefinition == null || rb.BackgroundDefinition.Name == null
                          ? "?" : rb.BackgroundDefinition.Name.Content)
                  .Append("\tx=").Append(rb.X).Append("\ty=").Append(rb.Y)
                  .Append("\tht=").Append(rb.TiledHorizontally).Append("\tvt=").Append(rb.TiledVertically)
                  .Append("\tstretch=").Append(rb.Stretch).Append("\ten=").Append(rb.Enabled)
                  .Append("\tfg=").Append(rb.Foreground).Append('\n');
            }
        }
        sb.Append("ROOM2_Tiles\t").Append(r.Tiles == null ? -1 : r.Tiles.Count).Append('\n');
        if (r.Tiles != null)
        {
            int k = 0;
            foreach (var t in r.Tiles)
            {
                if (k >= 4) break;
                k++;
                sb.Append("TILE\t").Append(t.BackgroundDefinition == null || t.BackgroundDefinition.Name == null
                          ? "?" : t.BackgroundDefinition.Name.Content).Append('\t')
                  .Append("x=").Append(t.X).Append("\ty=").Append(t.Y)
                  .Append("\tsrc=").Append(t.SourceX).Append(',').Append(t.SourceY)
                  .Append("\twh=").Append(t.Width).Append('x').Append(t.Height)
                  .Append("\tscale=").Append(t.ScaleX).Append(',').Append(t.ScaleY)
                  .Append("\tdepth=").Append(t.TileDepth).Append('\n');
            }
        }
    }
}

sb.Append("OK_BG\t").Append(okBg).Append('\n');
sb.Append("OK_SPR\t").Append(okSpr).Append('\n');

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("probe done -> " + outPath);
