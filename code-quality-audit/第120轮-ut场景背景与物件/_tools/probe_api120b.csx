// probe_api120b.csx —— 补一次：Disassembler / DecompileContext 的全部公开方法
using System;
using System.IO;
using System.Text;
using System.Reflection;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();
string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath)) { ScriptError("UTMT_OUT not set"); return; }

var sb = new StringBuilder();
sb.Append("type\tkind\tname\tsignature\n");

void DumpAll(Type t)
{
    if (t == null) { sb.Append("?\t?\t<null>\t\n"); return; }
    sb.Append("###\t").Append(t.FullName).Append('\n');
    foreach (var m in t.GetMethods(BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly))
    {
        var ps = new StringBuilder();
        foreach (var p in m.GetParameters())
            ps.Append(p.ParameterType.Name).Append(' ').Append(p.Name).Append(", ");
        sb.Append(t.Name).Append('\t').Append(m.IsStatic ? "static" : "inst").Append('\t')
          .Append(m.Name).Append('\t').Append('(').Append(ps.ToString()).Append(") -> ")
          .Append(m.ReturnType.Name).Append('\n');
    }
    foreach (var c in t.GetConstructors(BindingFlags.Public | BindingFlags.Instance))
    {
        var ps = new StringBuilder();
        foreach (var p in c.GetParameters())
            ps.Append(p.ParameterType.Name).Append(' ').Append(p.Name).Append(", ");
        sb.Append(t.Name).Append("\tctor\t").Append(t.Name).Append('\t').Append('(').Append(ps.ToString()).Append(")\n");
    }
}

DumpAll(typeof(UndertaleModLib.Decompiler.Disassembler));
DumpAll(typeof(UndertaleModLib.Decompiler.GlobalDecompileContext));
foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
{
    Type t = asm.GetType("Underanalyzer.Decompiler.DecompileContext");
    if (t != null) DumpAll(t);
}

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("api b done");
