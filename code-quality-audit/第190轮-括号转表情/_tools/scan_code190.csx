// 第190轮 · 在反编译出的 GML 里搜"肖像到底怎么画的"。
//
// 上一版为什么失败
// ----------------
// `dump_code190.csx` 用的是 `c.Instructions.ToString()` —— 在 UTMT 0.9.2 上
// `Instructions` 不是带 ToString 反汇编的链表，拿到的是类型名，
// 于是 12186 个代码段**全部命中 0**（而且异常被 try/catch 吞掉，看起来"跑成功了"）。
// ★ 教训：判据恒空 = 恒真的反面。0 命中必须先怀疑"我根本没取到文本"。
//
// 正确姿势（抄 UTMT 自带的 Scripts/Resource Exporters/ExportSpecificCode.csx）：
//     GlobalDecompileContext ctx = new(Data);
//     var st = Data.ToolInfo.DecompilerSettings;
//     string gml = new Underanalyzer.Decompiler.DecompileContext(ctx, code, st).DecompileToString();
//
// 要回答的问题（用户已选 C）
// --------------------------
// 黄魂 `spr_portrait_*` 在数据里是**黑底白线稿**（§193.5 已实证）。
// 游戏是不是在运行时给它上色？三种可能，代码能分辨：
//   ① 用 `draw_sprite_ext(..., color, alpha)` 或 `image_blend` 着色
//   ② 用 shader / surface 调色板
//   ③ 根本不着色（那就是 B 走法：黑白线稿直接用）
//
// 产物：__OUTDIR__/code_hits.txt（只写命中的段，避免几百 MB）
//       __OUTDIR__/code_scan_stat.txt（总数 / 反编译失败数 / 命中数 —— 分母闸）

using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

string outDir = @"__OUTDIR__";
Directory.CreateDirectory(outDir);

if (Data.IsYYC())
{
    File.WriteAllText(Path.Combine(outDir, "code_hits.txt"),
        "/* YYC: no code available */\n", new UTF8Encoding(false));
    Console.WriteLine("[停手] YYC 无代码");
    return;
}

// ★ 关键词分组：命中哪一组直接决定结论，所以不能混成一锅
string[] K_PORTRAIT = new string[] { "portrait", "spr_portrait" };
string[] K_BLEND = new string[] { "image_blend", "draw_sprite_ext", "merge_colour",
                                  "merge_color", "image_alpha" };
string[] K_SHADER = new string[] { "shader_set", "shader_get", "surface_", "gpu_set_fog",
                                   "draw_surface", "shader_" };

var ctx = new UndertaleModLib.Decompiler.GlobalDecompileContext(Data);
var st = Data.ToolInfo.DecompilerSettings;

var hits = new StringBuilder();
int nTotal = 0, nSub = 0, nFail = 0, nHitP = 0, nHitB = 0, nHitS = 0, nDone = 0;
long t0 = Environment.TickCount;

for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    nTotal++;
    // 子代码段不能单独反编译（父段的输出里已经包含），跳过但记账
    if (c.ParentEntry != null) { nSub++; continue; }

    string nm = c.Name.Content ?? "";
    string gml;
    try
    {
        gml = new Underanalyzer.Decompiler.DecompileContext(ctx, c, st).DecompileToString();
    }
    catch (Exception)
    {
        nFail++;
        continue;
    }
    nDone++;

    string low = gml.ToLowerInvariant();
    bool hp = false, hb = false, hs = false;
    for (int k = 0; k < K_PORTRAIT.Length; k++)
        if (low.IndexOf(K_PORTRAIT[k], StringComparison.Ordinal) >= 0) { hp = true; break; }
    for (int k = 0; k < K_BLEND.Length; k++)
        if (low.IndexOf(K_BLEND[k], StringComparison.Ordinal) >= 0) { hb = true; break; }
    for (int k = 0; k < K_SHADER.Length; k++)
        if (low.IndexOf(K_SHADER[k], StringComparison.Ordinal) >= 0) { hs = true; break; }

    if (hp) nHitP++;
    if (hb) nHitB++;
    if (hs) nHitS++;

    // 只在**肖像相关**或**肖像所在段同时有着色**时落盘，否则文件会爆
    if (hp || (hb && low.IndexOf("draw", StringComparison.Ordinal) >= 0 && gml.Length < 40000))
    {
        hits.Append("// ===== ").Append(nm)
            .Append("  [portrait=").Append(hp ? "1" : "0")
            .Append(" blend=").Append(hb ? "1" : "0")
            .Append(" shader=").Append(hs ? "1" : "0")
            .Append(" len=").Append(gml.Length).Append("] =====\n");
        hits.Append(gml).Append("\n\n");
    }

    if (nDone % 500 == 0)
    {
        Console.WriteLine("[progress] done=" + nDone + " fail=" + nFail
            + " hitP=" + nHitP + " hitB=" + nHitB
            + " " + ((Environment.TickCount - t0) / 1000) + "s");
    }
}

File.WriteAllText(Path.Combine(outDir, "code_hits.txt"), hits.ToString(), new UTF8Encoding(false));

var stat = new StringBuilder();
stat.Append("total_code=").Append(nTotal).Append('\n');
stat.Append("sub_entries_skipped=").Append(nSub).Append('\n');
stat.Append("decompiled=").Append(nDone).Append('\n');
stat.Append("decompile_failed=").Append(nFail).Append('\n');
stat.Append("hit_portrait=").Append(nHitP).Append('\n');
stat.Append("hit_blend=").Append(nHitB).Append('\n');
stat.Append("hit_shader=").Append(nHitS).Append('\n');
stat.Append("hits_bytes=").Append(hits.Length).Append('\n');
stat.Append("elapsed_s=").Append((Environment.TickCount - t0) / 1000).Append('\n');
File.WriteAllText(Path.Combine(outDir, "code_scan_stat.txt"),
    stat.ToString(), new UTF8Encoding(false));

Console.WriteLine("[done] " + stat.ToString().Replace('\n', ' '));
