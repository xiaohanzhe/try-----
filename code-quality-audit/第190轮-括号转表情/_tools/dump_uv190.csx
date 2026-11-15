using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第190轮：导出「sprite → 贴图页 + UV 矩形」的对应表（**不导图片**）。
//
// 为什么要绕这一圈
// ----------------
// `TextureWorker.ExportAsPNG(页项, path)` 在 UTMT 0.9.2 上对这批包只吐出**黑白蒙版**
// （实测 ceroba/undyne 的脸都是 2 色）。而游戏包的贴图页本来就是内嵌的 PNG
// （hy 34 块 / ut 42 块，IEND 完整），所以改成：
//   ① 本脚本只吐 UV 表（名字/帧/页号/裁切矩形）；
//   ② Python 侧把包里的 PNG 原样切出来，再按 UV 裁 ⇒ 颜色一定是对的。
//
// ★ 输入（环境变量）：R190_LIST 清单（每行一个 sprite 名，# 跳过）
//                     R190_OUT  输出目录
// ★ 输出：uv.tsv        name \t frame \t pageIdx \t sx \t sy \t sw \t sh
//         pages.tsv     pageIdx \t width \t height      （用于和真实 PNG 尺寸对账）
EnsureDataLoaded();

string listPath = Environment.GetEnvironmentVariable("R190_LIST");
string outDir = Environment.GetEnvironmentVariable("R190_OUT");
if (String.IsNullOrEmpty(outDir))
{
    outDir = Path.GetDirectoryName(FilePath);
}
Directory.CreateDirectory(outDir);

var want = new List<string>();
if (!String.IsNullOrEmpty(listPath) && File.Exists(listPath))
{
    foreach (string line in File.ReadAllLines(listPath))
    {
        string s = line.Trim();
        if (s.Length == 0 || s.StartsWith("#")) continue;
        if (!want.Contains(s)) want.Add(s);
    }
}
if (want.Count == 0)
{
    ScriptMessage("R190-UV ERROR: R190_LIST 为空或不存在: " + listPath);
    return;
}

// ---- 页表：embedded texture 的下标（顺序 = 文件里 PNG 的存放顺序）----
var pageIdx = new Dictionary<object, int>();
var sbP = new StringBuilder();
for (int i = 0; i < Data.EmbeddedTextures.Count; i++)
{
    var t = Data.EmbeddedTextures[i];
    if (t == null) continue;
    pageIdx[t] = i;
    int w = -1, h = -1;
    try
    {
        if (t.TextureData != null && t.TextureData.Image != null)
        {
            w = t.TextureData.Image.Width;
            h = t.TextureData.Image.Height;
        }
    }
    catch (Exception) { }
    sbP.Append(i).Append('\t').Append(w).Append('\t').Append(h).Append('\n');
}
File.WriteAllText(Path.Combine(outDir, "pages.tsv"),
    "# embedded=" + Data.EmbeddedTextures.Count + "\n" + sbP.ToString(),
    new UTF8Encoding(false));

// ---- sprite → UV ----
var byName = new Dictionary<string, UndertaleSprite>();
for (int i = 0; i < Data.Sprites.Count; i++)
{
    var sp = Data.Sprites[i];
    if (sp == null || sp.Name == null) continue;
    string nm = sp.Name.Content;
    if (nm != null && nm.Length > 0 && !byName.ContainsKey(nm)) byName[nm] = sp;
}

var sb = new StringBuilder();
int nOk = 0, nMiss = 0, nNoPage = 0;
var miss = new List<string>();
foreach (string nm in want)
{
    UndertaleSprite sp;
    if (!byName.TryGetValue(nm, out sp)) { nMiss++; miss.Add(nm); continue; }
    nOk++;
    if (sp.Textures == null) continue;
    for (int f = 0; f < sp.Textures.Count; f++)
    {
        // ★ `sp.Textures[f]` 是 UndertaleSprite.TextureEntry，**没有** TexturePage 字段
        //   （第一版栽在这：CS1061）。持有页引用与 UV 的是 `.Texture`
        //   （UndertaleTexturePageItem）。
        var ent = sp.Textures[f];
        if (ent == null || ent.Texture == null) { nNoPage++; continue; }
        var it = ent.Texture;
        if (it.TexturePage == null) { nNoPage++; continue; }
        int pi;
        if (!pageIdx.TryGetValue(it.TexturePage, out pi)) { nNoPage++; continue; }
        sb.Append(nm).Append('\t').Append(f).Append('\t').Append(pi).Append('\t')
          .Append(it.SourceX).Append('\t').Append(it.SourceY).Append('\t')
          .Append(it.SourceWidth).Append('\t').Append(it.SourceHeight).Append('\n');
    }
}
File.WriteAllText(Path.Combine(outDir, "uv.tsv"),
    "# want=" + want.Count + " ok=" + nOk + " miss=" + nMiss + " nopage=" + nNoPage + "\n"
    + sb.ToString(), new UTF8Encoding(false));

ScriptMessage("R190-UV want=" + want.Count + " ok=" + nOk + " miss=" + nMiss
    + " nopage=" + nNoPage + " uvrows=" + sb.ToString().Split('\n').Length);
if (miss.Count > 0)
{
    ScriptMessage("R190-UV missing=" + string.Join(",", miss.ToArray()));
}
