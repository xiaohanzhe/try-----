using System;
using System.IO;
using System.Text;
using System.Reflection;
using UndertaleModLib;
using UndertaleModLib.Models;
EnsureDataLoaded();
string dir = Path.GetDirectoryName(FilePath);
var sb = new StringBuilder();
sb.Append("=== 已加载程序集 ===\n");
foreach (var a in AppDomain.CurrentDomain.GetAssemblies()) {
    sb.Append("  ").Append(a.GetName().Name).Append("\n");
    Type t = null;
    try { t = a.GetType("UndertaleModLib.Project.CodeImportGroup"); } catch (Exception) {}
    if (t != null) sb.Append("     !!! 命中 CodeImportGroup\n");
}
sb.Append("=== 全程序集扫描 DecompileExistingCode ===\n");
foreach (var a in AppDomain.CurrentDomain.GetAssemblies()) {
    Type[] ts = null;
    try { ts = a.GetTypes(); } catch (Exception) { continue; }
    foreach (Type t in ts) {
        if (t.Name != "CodeImportGroup") continue;
        sb.Append("FOUND ").Append(t.AssemblyQualifiedName).Append("\n");
        foreach (var ci in t.GetConstructors(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance)) {
            sb.Append("   ctor(");
            foreach (var p in ci.GetParameters()) sb.Append(p.ParameterType.Name).Append(" ");
            sb.Append(")\n");
        }
    }
}
File.WriteAllText(Path.Combine(dir, "ut_sig4.txt"), sb.ToString(), new UTF8Encoding(false));
ScriptMessage("SIG4-OK");
