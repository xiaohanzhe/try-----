// probe_api120.csx —— 这个版本的 UTMT 到底把反编译器放在哪（名字/签名都别猜）
using System;
using System.IO;
using System.Text;
using System.Reflection;

EnsureDataLoaded();
string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath)) { ScriptError("UTMT_OUT not set"); return; }

var sb = new StringBuilder();
sb.Append("asm\ttype\tmember\tsignature\n");
foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
{
    Type[] types;
    try { types = asm.GetTypes(); } catch { continue; }
    foreach (var t in types)
    {
        string fn = t.FullName ?? "";
        if (fn.IndexOf("Decompil", StringComparison.Ordinal) < 0) continue;
        sb.Append(asm.GetName().Name).Append('\t').Append(fn).Append("\t<\t>\n");
        foreach (var m in t.GetMethods(BindingFlags.Public | BindingFlags.Static))
        {
            if (m.Name.IndexOf("Decompile", StringComparison.Ordinal) < 0) continue;
            var ps = new StringBuilder();
            foreach (var p in m.GetParameters())
                ps.Append(p.ParameterType.Name).Append(' ').Append(p.Name).Append(", ");
            sb.Append(asm.GetName().Name).Append('\t').Append(fn).Append('\t')
              .Append(m.Name).Append('\t').Append(ps.ToString()).Append('\n');
        }
    }
}
File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("api dump done");
