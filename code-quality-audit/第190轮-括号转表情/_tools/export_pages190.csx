// 第190轮 · 把游戏包的**整张贴图页**导成 PNG（走 UTMT 自己的解码）。
//
// 为什么必须整页导
// ----------------
// 第71轮走 `TextureWorker.ExportAsPNG(UndertaleTexturePageItem, path)`（按 sprite 裁切），
// 结果 UTY 的 ceroba/undyne 脸只有 2 色（纯黑+纯白），肉眼确认是**蒙版**不是彩图。
// 自写 QOI 解码器又连试三种起点都是"解满但只吃 ~500 字节 / 出彩条噪声"⇒ 那条路放弃。
//
// 现在走最上游：`TexData.Image` 是 UTMT **自己解出来的**原位图。
// 它若也是蒙版，说明这是工具链上限（可正当登记"素材在但取不出颜色"），不是我写错。
//
// ★★ 本轮实测的 API 事实（别再猜）：
//   · UTMT 0.9.2 用 **ImageMagick / Magick.NET**，**不用** System.Drawing
//     ⇒ `using System.Drawing.Imaging;` 会 CS0234，`Bitmap` 直接不存在。
//   · 整页导出的现成入口是 `TextureWorker.GetEmbeddedTexture(UndertaleEmbeddedTexture)`
//     → `MagickImage`，再 `TextureWorker.SaveImageToFile(img, path)`。
//   · `TexData` 上直接有 `FormatQOI` / `FormatBZ2` 两个布尔
//     ⇒ "哪些页被压缩"不用我反推字节，UTMT 已经告诉我们了。
//
// 产物：__OUTDIR__/pages/pNNN.png + __OUTDIR__/pages.tsv
//       idx, w, h, qoi, bz2, bytes, status
//       （颜色数交给 Python 的 PLL 侧统计，C# 里不重复造轮子）

using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

string outDir = @"__OUTDIR__";
string pageDir = Path.Combine(outDir, "pages");
Directory.CreateDirectory(pageDir);

var pages = Data.EmbeddedTextures;
if (pages == null)
{
    File.WriteAllText(Path.Combine(outDir, "pages.tsv"),
        "idx\tw\th\tqoi\tbz2\tbytes\tstatus\n", new UTF8Encoding(false));
    Console.WriteLine("[失败] Data.EmbeddedTextures 为 null");
    return;
}
Console.WriteLine("页面总数 = " + pages.Count);

var rows = new List<string>();
int nOk = 0, nFail = 0, nQoi = 0, nBz2 = 0;
long t0 = Environment.TickCount;

using (var worker = new TextureWorker())
{
    for (int i = 0; i < pages.Count; i++)
    {
        var tex = pages[i];
        string status = "ok";
        int w = 0, h = 0;
        bool qoi = false, bz2 = false;
        long bytes = 0;

        if (tex == null)
        {
            rows.Add(i + "\t0\t0\t0\t0\t0\tnull");
            nFail++;
            continue;
        }

        try
        {
            var td = tex.TextureData;
            if (td != null)
            {
                qoi = td.FormatQOI;
                bz2 = td.FormatBZ2;
                if (qoi) nQoi++;
                if (bz2) nBz2++;
            }
        }
        catch (Exception e) { status = "fmt:" + e.GetType().Name; }

        try
        {
            var img = worker.GetEmbeddedTexture(tex);
            if (img == null)
            {
                status = "noimg";
                nFail++;
            }
            else
            {
                w = (int)img.Width;
                h = (int)img.Height;
                string fn = Path.Combine(pageDir, "p" + i.ToString("D3") + ".png");
                TextureWorker.SaveImageToFile(img, fn);
                bytes = new FileInfo(fn).Length;
                nOk++;
                try { img.Dispose(); } catch { }
            }
        }
        catch (Exception e)
        {
            status = "exp:" + e.GetType().Name;
            nFail++;
        }

        rows.Add(string.Join("\t", new string[] {
            i.ToString(), w.ToString(), h.ToString(),
            qoi ? "1" : "0", bz2 ? "1" : "0", bytes.ToString(), status
        }));
    }
}

var sb = new StringBuilder();
sb.Append("idx\tw\th\tqoi\tbz2\tbytes\tstatus\n");
foreach (var r in rows) sb.Append(r).Append('\n');
File.WriteAllText(Path.Combine(outDir, "pages.tsv"), sb.ToString(), new UTF8Encoding(false));

Console.WriteLine("[done] 成功 " + nOk + " / " + pages.Count + "，失败 " + nFail
    + "，FormatQOI=" + nQoi + "，FormatBZ2=" + nBz2
    + "，" + ((Environment.TickCount - t0) / 1000) + "s");
Console.WriteLine("[out] " + Path.Combine(outDir, "pages.tsv"));
