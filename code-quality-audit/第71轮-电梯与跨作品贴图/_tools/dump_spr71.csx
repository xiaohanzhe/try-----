using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

// ============================================================================
// 第71轮 · 定向 sprite 导出（只导清单里的名字，不做全量）
//
// 为什么要"定向"：全量导出 UT(2904) / 黄魂(3814) 需要很久且吃掉几百 MB，
// 而本轮真正要的只有 44 个名字（电梯 15 + ut_ 14 + hy_ 15）。
// 少一个数量级的 IO = 少一个数量级的失败面。
//
// 输入（环境变量）：
//   R71_LIST  清单文件路径（每行一个 sprite 名，# 开头跳过）
//   R71_OUT   输出目录（缺省 = datafile 同级的 r71/）
// 输出：
//   <out>/<name>_<frame>.png
//   <out>/r71_sprites.json   {source, ok:[{name, frames:[...]}], missing:[...]}
//
// ★ 纪律（记忆 §43.7）："提取成功" ≠ "提取正确"。
//   本脚本只负责**提取**；"提取正确"由 Python 侧的 A/B 锚点独立复核
//   （已知真值站点必须命中、乱造名必须落空、frame 数与元数据一致）。
// ============================================================================

EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outDir = Environment.GetEnvironmentVariable("R71_OUT");
if (String.IsNullOrEmpty(outDir)) outDir = Path.Combine(dir, "r71");
Directory.CreateDirectory(outDir);

string listPath = Environment.GetEnvironmentVariable("R71_LIST");
if (String.IsNullOrEmpty(listPath) || !File.Exists(listPath))
{
    Console.WriteLine("dump71 ERROR: R71_LIST 未设置或不存在: " + listPath);
    return;
}

var want = new List<string>();
foreach (string line in File.ReadAllLines(listPath))
{
    string s = line.Trim();
    if (s.Length == 0 || s.StartsWith("#")) continue;
    if (!want.Contains(s)) want.Add(s);
}

var byName = new Dictionary<string, UndertaleSprite>();
for (int i = 0; i < Data.Sprites.Count; i++)
{
    UndertaleSprite sp = Data.Sprites[i];
    if (sp == null || sp.Name == null) continue;
    string nm = sp.Name.Content;
    if (nm == null || nm.Length == 0) continue;
    if (!byName.ContainsKey(nm)) byName[nm] = sp;
}

var sb = new StringBuilder();
int nOk = 0, nMiss = 0, nPng = 0, nSprFail = 0;
var miss = new List<string>();

sb.Append("{\n \"source\": ").Append(JsonStr(FilePath));
sb.Append(",\n \"total_sprites_in_data\": ").Append(Data.Sprites.Count);
sb.Append(",\n \"want\": ").Append(want.Count);
sb.Append(",\n \"ok\": [");
bool firstRec = true;

using (var worker = new TextureWorker())
{
    foreach (string nm in want)
    {
        UndertaleSprite sp;
        if (!byName.TryGetValue(nm, out sp))
        {
            nMiss++;
            miss.Add(nm);
            continue;
        }
        nOk++;
        var frames = new List<string>();
        int ntex = 0;
        if (sp.Textures != null)
        {
            for (int f = 0; f < sp.Textures.Count; f++)
            {
                if (sp.Textures[f] == null || sp.Textures[f].Texture == null)
                {
                    nSprFail++;
                    continue;
                }
                ntex++;
                string fn = nm + "_" + f + ".png";
                try
                {
                    worker.ExportAsPNG(sp.Textures[f].Texture, Path.Combine(outDir, fn));
                    frames.Add(fn);
                    nPng++;
                }
                catch (Exception)
                {
                    nSprFail++;
                }
            }
        }
        if (!firstRec) sb.Append(",");
        firstRec = false;
        sb.Append("\n  {\"name\": ").Append(JsonStr(nm));
        sb.Append(", \"w\": ").Append(sp.Width).Append(", \"h\": ").Append(sp.Height);
        sb.Append(", \"martix\": ").Append(sp.Textures == null ? 0 : sp.Textures.Count);
        sb.Append(", \"frames\": [");
        for (int k = 0; k < frames.Count; k++)
        {
            if (k > 0) sb.Append(", ");
            sb.Append(JsonStr(frames[k]));
        }
        sb.Append("]}");
    }
}
sb.Append("\n ],\n \"missing\": [");
for (int k = 0; k < miss.Count; k++)
{
    if (k > 0) sb.Append(", ");
    sb.Append(JsonStr(miss[k]));
}
sb.Append("]\n}\n");
File.WriteAllText(Path.Combine(outDir, "r71_sprites.json"), sb.ToString(), new UTF8Encoding(false));

Console.WriteLine("dump71 want=" + want.Count + " ok=" + nOk + " miss=" + nMiss
    + " png=" + nPng + " sprfail=" + nSprFail + " out=" + outDir);

string JsonStr(string s)
{
    if (s == null) return "null";
    var b = new StringBuilder("\"");
    foreach (char c in s)
    {
        if (c == '"') b.Append("\\\"");
        else if (c == '\\') b.Append("\\\\");
        else if (c == '\n') b.Append("\\n");
        else if (c == '\r') b.Append("\\r");
        else if (c == '\t') b.Append("\\t");
        else if (c < 32) b.Append("\\u").Append(((int)c).ToString("x4"));
        else b.Append(c);
    }
    b.Append("\"");
    return b.ToString();
}
