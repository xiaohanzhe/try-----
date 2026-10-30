// dump_viz120.csx —— 第120轮：导出「把这间房画出来」需要的全部原语
//
// 背景（为什么不是 dump_layers120）：ut 的 game.droid 是 **GMS2**，房间内容分三处：
//   ① 背景层（Background layer，引用 Sprite，可平铺/拉伸/染色）
//   ② 资源层（Assets layer 里的 SpriteInstance，直接摆一张精灵）
//   ③ 实例层（Instances layer 里的对象实例，对象再引用精灵）
// 三者都按 depth 排。所以「画一间房」= 背景色 + 这三类元素按 depth 从远到近盖。
// 因此要导出的不只是背景贴图，而是**每张被用到的精灵的每一帧**。
//
// 用法：UTMT_OUT=<tsv> load <data> -s dump_viz120.csx
// 产物：
//   <UTMT_OUT>                        参数表
//   <outdir>/tex/spr_<名>_<帧>.png     用到的精灵帧
//
// TSV 段：
//   META  key value
//   ROOM  idx name w h bgcolor drawbg
//   LAYER roomIdx layerIdx layerName type depth visible
//   LBG   roomIdx layerIdx sprite xoff yoff ht vt stretch fg vis calcsx calcsy color
//   LSP   roomIdx layerIdx idx sprite frame x y sx sy rot color
//   SPR   name frame bytes originX originY w h
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
    string s = nm;
    foreach (char c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_');
    return s;
}

// 名字 -> (精灵, 用到的帧集合)
var want = new Dictionary<string, KeyValuePair<UndertaleSprite, SortedSet<int>>>(StringComparer.Ordinal);

void Need(UndertaleSprite spr, int frame)
{
    if (spr == null || spr.Name == null) return;
    string nm = Safe(spr.Name);
    if (String.IsNullOrEmpty(nm)) return;
    KeyValuePair<UndertaleSprite, SortedSet<int>> cur;
    if (!want.TryGetValue(nm, out cur))
    {
        cur = new KeyValuePair<UndertaleSprite, SortedSet<int>>(spr, new SortedSet<int>());
        want[nm] = cur;
    }
    if (frame < 0) frame = 0;
    cur.Value.Add(frame);
}

long nInstance = 0, nSpriteInst = 0, nBgLayer = 0;

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
            Need(bd.Sprite, 0);
            nBgLayer++;
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

        if (lay.LayerType == UndertaleRoom.LayerType.Assets && lay.AssetsData != null
            && lay.AssetsData.Sprites != null)
        {
            int k = 0;
            foreach (var si in lay.AssetsData.Sprites)
            {
                if (si == null) { k++; continue; }
                string sn = si.Sprite == null ? Safe(si.Name) : Safe(si.Sprite.Name);
                int fr = si.WrappedFrameIndex >= 0 ? si.WrappedFrameIndex : 0;
                Need(si.Sprite, fr);
                nSpriteInst++;
                sb.Append("LSP\t").Append(ri).Append('\t').Append(li).Append('\t').Append(k)
                  .Append('\t').Append(sn).Append('\t').Append(fr)
                  .Append('\t').Append(si.X).Append('\t').Append(si.Y)
                  .Append('\t').Append(si.ScaleX.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
                  .Append('\t').Append(si.ScaleY.ToString("0.####", System.Globalization.CultureInfo.InvariantCulture))
                  .Append('\t').Append(si.Rotation.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture))
                  .Append('\t').Append(si.Color)
                  .Append('\t').Append(si.SpriteXOffset).Append('\t').Append(si.SpriteYOffset)
                  .Append('\n');
                k++;
            }
        }

        if (lay.LayerType == UndertaleRoom.LayerType.Instances && lay.InstancesData != null
            && lay.InstancesData.Instances != null)
        {
            int insDepth = lay.LayerDepth;
            foreach (var inst in lay.InstancesData.Instances)
            {
                if (inst == null) continue;
                nInstance++;
                // 实例的对象 → 精灵；可见性由 objmap（另一个产物）判，这里只要精灵
                var obj = inst.ObjectDefinition as UndertaleGameObject;
                UndertaleSprite spr = obj == null ? null : obj.Sprite;
                int fr = inst.ImageIndex >= 0 ? inst.ImageIndex : 0;
                Need(spr, fr);
            }
        }
        li++;
    }
}

int nPairs = 0;
foreach (var kv in want) nPairs += kv.Value.Value.Count;

sb.Append("META\tIsGameMaker2\t").Append(Data.IsGameMaker2()).Append('\n');
sb.Append("META\tRooms\t").Append(Data.Rooms.Count).Append('\n');
sb.Append("META\tInstances\t").Append(nInstance).Append('\n');
sb.Append("META\tSpriteInstances\t").Append(nSpriteInst).Append('\n');
sb.Append("META\tBgLayers\t").Append(nBgLayer).Append('\n');
sb.Append("META\tWantSprites\t").Append(want.Count).Append('\n');
sb.Append("META\tWantFrames\t").Append(nPairs).Append('\n');

int ok = 0, fail = 0, nulltex = 0;
using (TextureWorker worker = new TextureWorker())
{
    foreach (var kv in want)
    {
        var spr = kv.Value.Key;
        var frames = kv.Value.Value;
        if (spr.Textures == null || spr.Textures.Count == 0)
        {
            nulltex++;
            sb.Append("SPR_NULLTEX\t").Append(kv.Key).Append('\n');
            continue;
        }
        foreach (int fr in frames)
        {
            int use = fr;
            if (use >= spr.Textures.Count) use = spr.Textures.Count - 1;
            var ti = spr.Textures[use];
            if (ti == null || ti.Texture == null) { nulltex++; continue; }
            string f = Path.Combine(texDir, "spr_" + Fname(kv.Key) + "_" + use + ".png");
            try
            {
                worker.ExportAsPNG(ti.Texture, f);
                var fi = new FileInfo(f);
                // 帧尺寸：用 _Texture 的 Bounding 宽度（精灵 Width/Height 是**整张**尺寸，
                // 多帧时每帧未必等宽，但 UT 里绝大多数是等宽，先记下来给 Python 校验）
                sb.Append("SPR\t").Append(kv.Key).Append('\t').Append(use).Append('\t')
                  .Append(fi.Length).Append('\t')
                  .Append(spr.OriginX).Append('\t').Append(spr.OriginY).Append('\t')
                  .Append(spr.Width).Append('\t').Append(spr.Height).Append('\t')
                  .Append(ti.Texture.BoundingWidth).Append('\t').Append(ti.Texture.BoundingHeight)
                  .Append('\n');
                ok++;
            }
            catch (Exception ex)
            {
                sb.Append("SPR_FAIL\t").Append(kv.Key).Append('\t').Append(use).Append('\t')
                  .Append(ex.GetType().Name).Append(": ").Append(ex.Message).Append('\n');
                fail++;
            }
        }
    }
}
sb.Append("META\tExportOK\t").Append(ok).Append('\n');
sb.Append("META\tExportFail\t").Append(fail).Append('\n');
sb.Append("META\tNullTex\t").Append(nulltex).Append('\n');

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("viz done -> " + outPath);
