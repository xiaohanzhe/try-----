using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

// 第64轮 · 导出「红与黄（Undertale Red & Yellow）」里的**幽灵**精灵帧 PNG。
// ★ E 盘是 dirty 常态（新建文件 Errno 22）⇒ 名单从 C: 侧读、PNG 落 %TEMP%，全程不碰 E:。
// 输出：%TEMP%\spr64_ry\<sprite>_<i>.png + spr_log64.txt
// 锚点：spr_ghost_chara_down / spr_truechara 必须 OK，否则提取不可信。
EnsureDataLoaded();

string namesFile = @"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第64轮-人设原文重抽与红黄勘查\_tools\spr_names64.txt";
string outDir = Path.Combine(Path.GetTempPath(), "spr64_ry");
Directory.CreateDirectory(outDir);

var log = new StringBuilder();
if (!File.Exists(namesFile))
{
    Console.WriteLine("spr64: 缺名字清单 " + namesFile);
    return;
}

var wanted = new HashSet<string>();
foreach (string raw in File.ReadAllLines(namesFile))
{
    string n = raw.Trim();
    if (n.Length > 0 && !n.StartsWith("#")) wanted.Add(n);
}

var found = new HashSet<string>();
int okSpr = 0, okFrame = 0, skip = 0;
using (TextureWorker worker = new TextureWorker())
{
    foreach (UndertaleSprite spr in Data.Sprites)
    {
        string name = spr.Name == null ? null : spr.Name.Content;
        if (name == null || !wanted.Contains(name)) continue;
        found.Add(name);
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

var miss = new List<string>();
foreach (string w in wanted) if (!found.Contains(w)) miss.Add(w);
log.AppendLine("MISS\t" + String.Join(", ", miss.ToArray()));

File.WriteAllText(Path.Combine(outDir, "spr_log64.txt"), log.ToString(), new UTF8Encoding(false));
Console.WriteLine("spr64 sprites=" + okSpr + " frames=" + okFrame + " skip=" + skip
                  + " MISS=" + miss.Count + " wanted=" + wanted.Count + " out=" + outDir);
