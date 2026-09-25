using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

// 第49轮 · 按名字清单非交互反编译（NPC / 跟随 / 球容器 取证）
// 输入：<data.win 同级>/dump_names49.txt（一行一个 code 名）
// 输出：<data.win 同级>/gml49/<name>.gml  +  dump_log49.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string namesFile = Path.Combine(dir, "dump_names49.txt");
string outDir = Path.Combine(dir, "gml49");
Directory.CreateDirectory(outDir);

var log = new StringBuilder();
if (!File.Exists(namesFile))
{
    Console.WriteLine("dump49: 缺名字清单 " + namesFile);
    return;
}

GlobalDecompileContext ctx = new GlobalDecompileContext(Data);
Underanalyzer.Decompiler.IDecompileSettings ds = Data.ToolInfo.DecompilerSettings;

int ok = 0, miss = 0, fail = 0;
foreach (string raw in File.ReadAllLines(namesFile))
{
    string n = raw.Trim();
    if (n.Length == 0 || n.StartsWith("#")) continue;
    UndertaleCode code = null;
    try { code = Data.Code.ByName(n); } catch (Exception) { code = null; }
    if (code == null) { log.AppendLine("MISS\t" + n); miss++; continue; }
    string gml;
    try
    {
        gml = new Underanalyzer.Decompiler.DecompileContext(ctx, code, ds).DecompileToString();
    }
    catch (Exception e)
    {
        gml = "// DECOMPILE FAILED: " + e.GetType().Name + ": " + e.Message;
        fail++;
    }
    int nins = -1;
    try
    {
        var ins = code.Instructions;
        nins = ins == null ? -1 : ins.Count;
    }
    catch (Exception) { }
    File.WriteAllText(Path.Combine(outDir, n + ".gml"), gml, new UTF8Encoding(false));
    log.AppendLine("OK\t" + n + "\tchars=" + gml.Length + "\tins=" + nins);
    if (fail == 0 || !gml.StartsWith("// DECOMPILE FAILED")) ok++;
}

File.WriteAllText(Path.Combine(dir, "dump_log49.txt"), log.ToString(), new UTF8Encoding(false));
Console.WriteLine("dump49 OK=" + ok + " MISS=" + miss + " FAIL=" + fail);
