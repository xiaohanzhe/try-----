using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

// 第48轮 · 补采版（v2）：与 dump_items48.csx 同逻辑，只把**输出目录换成新的**。
// 原因：E:\Download\_tmp 存在「已存在文件被拒写（PermissionError 13）」的间歇故障，
//       覆盖 gml48/ 下的旧文件会失败 ⇒ 换 gml48b/ 走"新建文件"这条路。
// 输入：<data.win 同级>/dump_names48.txt
// 输出：<data.win 同级>/gml48b/<name>.gml  +  dump_log48b.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string namesFile = Path.Combine(dir, "dump_names48.txt");
string outDir = Path.Combine(dir, "gml48b");
Directory.CreateDirectory(outDir);

var log = new StringBuilder();
if (!File.Exists(namesFile))
{
    Console.WriteLine("dump48b: 缺名字清单 " + namesFile);
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
    if (!gml.StartsWith("// DECOMPILE FAILED")) ok++;
}

File.WriteAllText(Path.Combine(dir, "dump_log48b.txt"), log.ToString(), new UTF8Encoding(false));
Console.WriteLine("dump48b OK=" + ok + " MISS=" + miss + " FAIL=" + fail);
