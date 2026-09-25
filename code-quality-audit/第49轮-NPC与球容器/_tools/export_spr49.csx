using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

// 第49轮 · 按名字清单**非交互**导出精灵帧 PNG（官方 ExportAllSprites.csx 要弹目录/提问，这里跳过）
// 输入：<data.win 同级>/spr_names49.txt（一行一个 sprite 名）
// 输出：<data.win 同级>/spr49/<sprite>_<i>.png  +  spr_log49.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string namesFile = Path.Combine(dir, "spr_names49.txt");
string outDir = Path.Combine(dir, "spr49");
Directory.CreateDirectory(outDir);

var log = new StringBuilder();
if (!File.Exists(namesFile))
{
    Console.WriteLine("spr49: 缺名字清单 " + namesFile);
    return;
}

var wanted = new HashSet<string>();
foreach (string raw in File.ReadAllLines(namesFile))
{
    string n = raw.Trim();
    if (n.Length > 0 && !n.StartsWith("#")) wanted.Add(n);
}

int okSpr = 0, okFrame = 0, miss = 0, skip = 0;
using (TextureWorker worker = new TextureWorker())
{
    foreach (UndertaleSprite spr in Data.Sprites)
    {
        string name = spr.Name == null ? null : spr.Name.Content;
        if (name == null || !wanted.Contains(name)) continue;
        if (spr.SSpriteType != UndertaleSprite.SpriteType.Normal || spr.Textures == null || spr.Textures.Count == 0)
        {
            log.AppendLine("SKIP\t" + name + "\ttype=" + spr.SSpriteType);
            skip++;
            continue;
        }
        int n = 0;
        for (int i = 0; i < spr.Textures.Count; i++)
        {
            var it = spr.Textures[i];
            if (it == null || it.Texture == null) continue;
            string path = Path.Combine(outDir, name + "_" + i + ".png");
            try
            {
                worker.ExportAsPNG(it.Texture, path, null, false);
                n++; okFrame++;
            }
            catch (Exception e)
            {
                log.AppendLine("FAILFRAME\t" + name + "\t" + i + "\t" + e.GetType().Name);
            }
        }
        log.AppendLine("OK\t" + name + "\tframes=" + n + "\tw=" + spr.Width + "\th=" + spr.Height
                       + "\txorig=" + spr.OriginX + "\tyorig=" + spr.OriginY);
        okSpr++;
    }
}

File.WriteAllText(Path.Combine(dir, "spr_log49.txt"), log.ToString(), new UTF8Encoding(false));
Console.WriteLine("spr49 sprites=" + okSpr + " frames=" + okFrame + " skip=" + skip
                  + " MISS=" + miss + " wanted=" + wanted.Count);
