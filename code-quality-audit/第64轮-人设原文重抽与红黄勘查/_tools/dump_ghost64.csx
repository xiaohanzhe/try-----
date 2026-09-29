using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

// 第64轮 · 反编译「红与黄」里**幽灵**相关的全部 code（取证：幽灵感怎么来的 / 谁能看见）。
// ★ E 盘 dirty 常态 ⇒ 名单从 C: 侧读、gml 落 %TEMP%。
// 输入：...\_tools\dump_names64.txt
// 输出：%TEMP%\gml64\<name>.gml + dump_log64.txt
EnsureDataLoaded();

string namesFile = @"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第64轮-人设原文重抽与红黄勘查\_tools\dump_names64.txt";
string outDir = Path.Combine(Path.GetTempPath(), "gml64");
Directory.CreateDirectory(outDir);

var log = new StringBuilder();
if (!File.Exists(namesFile))
{
    Console.WriteLine("dump64: 缺名字清单 " + namesFile);
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
    bool bad = false;
    try
    {
        gml = new Underanalyzer.Decompiler.DecompileContext(ctx, code, ds).DecompileToString();
    }
    catch (Exception e)
    {
        gml = "// DECOMPILE FAILED: " + e.GetType().Name + ": " + e.Message;
        fail++; bad = true;
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
    if (!bad) ok++;
}

File.WriteAllText(Path.Combine(outDir, "dump_log64.txt"), log.ToString(), new UTF8Encoding(false));
Console.WriteLine("dump64 OK=" + ok + " MISS=" + miss + " FAIL=" + fail + " out=" + outDir);
