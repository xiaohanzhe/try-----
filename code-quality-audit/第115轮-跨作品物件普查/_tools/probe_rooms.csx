// 第119轮：Data.Rooms 的「列表下标 vs 资源 id vs 名字」三列对照
// 目的：`dump_readable_bind.csx` 记的 `room_idx` 是**指令里的整数**，
// 而 `inst_full.tsv` 的 `R <i>` 是**列表下标**。若两者不是同一套编号，
// 就会把 A 房间的正文绑到 B 房间上 —— 而且**不报错**（第117轮已中招一次）。
//
// 用法：set UTMT_OUT=<输出 tsv> 后 load <data> -s probe_rooms.csx
// 产物：index \t asset_id \t name
using System;
using System.IO;
using System.Text;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath))
{
    ScriptError("UTMT_OUT not set");
    return;
}

var sb = new StringBuilder();
sb.Append("index\tname\n");
int n = 0;
foreach (var r in Data.Rooms)
{
    string nm = (r == null || r.Name == null) ? "" : r.Name.Content;
    sb.Append(n).Append('\t').Append(nm).Append('\n');
    n++;
}
File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("rooms=" + n);
