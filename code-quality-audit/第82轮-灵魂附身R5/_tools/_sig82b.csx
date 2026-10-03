using System;
using System.IO;
using System.Text;
using System.Reflection;
using UndertaleModLib;
using UndertaleModLib.Models;

// 作用域探针：看看 csx 默认 using 里有哪些命名空间/类型
var sb = new StringBuilder();
sb.Append("=== AppDomain 已加载程序集的外层命名空间 ===\n");
foreach (var a in AppDomain.CurrentDomain.GetAssemblies()) {
    Type[] ts = null;
    try { ts = a.GetTypes(); } catch (Exception) { continue; }
    var ns = new System.Collections.Generic.HashSet<string>();
    foreach (Type t in ts) { if (t.Namespace != null) ns.Add(t.Namespace); }
    sb.Append("[").Append(a.GetName().Name).Append("]\n");
    foreach (string n in ns) sb.Append("    ").Append(n).Append("\n");
}

sb.Append("=== 关键类型全名 ===\n");
string[] targets = new string[] {
    "GlobalDecompileContext", "IDecompileSettings", "GlobalDecompileSettings",
    "DecompileContext", "CodeImportGroup", "Decompiler", "Disassembler"
};
foreach (var a in AppDomain.CurrentDomain.GetAssemblies()) {
    Type[] ts = null;
    try { ts = a.GetTypes(); } catch (Exception) { continue; }
    foreach (Type t in ts) {
        foreach (string nm in targets) {
            if (t.Name == nm) {
                sb.Append("TYPE ").Append(t.AssemblyQualifiedName).Append("\n");
                foreach (var ci in t.GetConstructors(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance)) {
                    sb.Append("   ctor(");
                    foreach (var p in ci.GetParameters()) sb.Append(p.ParameterType.Name).Append(":").Append(p.ParameterType.FullName).Append(" ");
                    sb.Append(")\n");
                }
            }
        }
    }
}
File.WriteAllText(Path.Combine(Path.GetDirectoryName(FilePath), "ut_sig5.txt"), sb.ToString(), new UTF8Encoding(false));
ScriptMessage("SIG5-OK");
