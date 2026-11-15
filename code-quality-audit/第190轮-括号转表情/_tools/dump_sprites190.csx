using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第190轮取证：把游戏包里的**全部 Sprite 名单**导出来，用来回答
//   「原作到底给哪些角色画了脸（face / portrait）」。
//
// ★ 只导元信息（名字 / 尺寸 / 帧数），**不导图片** —— 导出图片很慢且本轮先用名单判覆盖。
// ★ 判据（自证）：产物行数必须 == Data.Sprites.Count（脚本里直接算，写进文件头）。
// ★ stdout 必须重定向到文件（UTMT CLI 的 stdout 不能是 PIPE）——由 utmt190.py 保证。
EnsureDataLoaded();

string dir = @"__OUTDIR__";
if (dir == "__" + "OUTDIR__" || dir.Length == 0)
{
    dir = Path.GetDirectoryName(FilePath);
}
ScriptMessage("OUTDIR=" + dir);
var utf8 = new UTF8Encoding(false);

var sb = new StringBuilder();
int n = 0;
for (int i = 0; i < Data.Sprites.Count; i++)
{
    var s = Data.Sprites[i];
    if (s == null || s.Name == null) continue;
    string nm = s.Name.Content;
    int frames = (s.Textures != null) ? s.Textures.Count : 0;
    // TSV：名字 \t 宽 \t 高 \t 帧数（名字里不会有 \t）
    sb.Append(nm).Append('\t').Append(s.Width).Append('\t')
      .Append(s.Height).Append('\t').Append(frames).Append('\n');
    n++;
}

int total = Data.Sprites.Count;
File.WriteAllText(Path.Combine(dir, "sprites.tsv"),
    "# total=" + total + " written=" + n + "\n" + sb.ToString(), utf8);

ScriptMessage("DR190-EXPORT sprites=" + n + " total=" + total);
