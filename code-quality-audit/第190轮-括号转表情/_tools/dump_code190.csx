// 第190轮 · 在游戏代码里找"肖像是怎么画出来的"。
//
// 为什么必须查代码
// ----------------
// 实证结果：`spr_portrait_*`（黄魂 124 个角色肖像）**整族都是黑底白线稿**，
// ceroba / starlo / asgore / moray / alphys / axis 全部 2 色，ace/kanako/mooch 也只有 3 色，
// 肉眼确认 8 张全是白线稿，没有任何肤色。
//
// 但 wiki 明确写 Ceroba 是"米色皮毛 + 姜黄色头发"，游戏里不可能是纯线稿。
// ⇒ 只剩两种可能，**必须由代码裁决**，不能靠我猜：
//     ① 原作就是线稿，颜色由别的机制给（调色板/着色器/叠加精灵）
//     ② 彩色另有精灵，我给的名字/坐标找错了
//
// 本脚本把所有**含 portrait 的代码段**整段导出，看 draw_* 调用带不带颜色参数。

using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

string outDir = @"__OUTDIR__";
Directory.CreateDirectory(outDir);
var sb = new StringBuilder();

string[] keys = new string[] { "portrait", "spr_portrait", "draw_self", "face" };

int nScan = 0, nHit = 0;
var hitNames = new List<string>();

for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content ?? "";
    nScan++;

    string txt = "";
    try
    {
        // 老版本字段叫 Instructions，字符串化后就是 GML 反汇编
        if (c.Instructions != null) txt = c.Instructions.ToString();
    }
    catch { }

    bool hit = false;
    string low = txt.ToLowerInvariant();
    for (int k = 0; k < keys.Length; k++)
        if (low.IndexOf(keys[k], StringComparison.Ordinal) >= 0) { hit = true; break; }

    if (!hit) continue;
    nHit++;
    hitNames.Add(nm);

    sb.Append("// ===== 代码段 ").Append(nm).Append(" =====\n");
    sb.Append(txt).Append("\n\n");
}

var sb2 = new StringBuilder();
sb2.Append("# 扫描代码段 ").Append(nScan).Append(" 个，命中 ").Append(nHit).Append(" 个\n");
sb2.Append("# 命中名单：").Append(string.Join(", ", hitNames.ToArray())).Append("\n\n");
sb2.Append(sb.ToString());

File.WriteAllText(Path.Combine(outDir, "code_portrait.txt"), sb2.ToString(), new UTF8Encoding(false));
Console.WriteLine("[done] 扫描 " + nScan + "，命中 " + nHit);
Console.WriteLine("[名单] " + string.Join(", ", hitNames.ToArray()));
