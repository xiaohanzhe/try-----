// 第172轮 · 一次性：把「解压器到底叫什么」问出来（反射，不改任何东西）
using System;
using System.Reflection;
using System.Collections;

EnsureDataLoaded();

int nAsm = 0, nType = 0;
foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
{
    string an = asm.GetName().Name;
    if (an.IndexOf("Underanalyzer") < 0 && an.IndexOf("UndertaleModLib") < 0) continue;
    nAsm++;
    Type[] ts = null;
    try { ts = asm.GetTypes(); }
    catch (ReflectionTypeLoadException ex) { ts = ex.Types; }
    catch (Exception ex) { Console.WriteLine("ASM " + an + " GetTypes FAILED: " + ex.Message); continue; }
    if (ts == null) continue;
    foreach (Type t in ts)
    {
        if (t == null || t.FullName == null) continue;
        if (t.FullName.IndexOf("Decompil") < 0) continue;
        if (t.FullName.IndexOf("Node") >= 0) continue;
        nType++;
        if (t.FullName == "Underanalyzer.Decompiler.DecompileContext")
        {
            Console.WriteLine("CTOR " + t.FullName);
            foreach (ConstructorInfo ci in t.GetConstructors())
            {
                var ps = new ArrayList();
                foreach (ParameterInfo pi in ci.GetParameters())
                    ps.Add(pi.ParameterType.Name + " " + pi.Name
                        + (pi.HasDefaultValue ? ("=" + (pi.DefaultValue == null ? "null" : pi.DefaultValue.ToString())) : ""));
                Console.WriteLine("    ctor(" + String.Join(", ", (string[])ps.ToArray(typeof(string))) + ")");
            }
        }
        MethodInfo[] ms;
        try { ms = t.GetMethods(BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly); }
        catch (Exception) { continue; }
        var names = new ArrayList();
        foreach (MethodInfo m in ms)
        {
            if (m.Name.IndexOf("Decompile") != 0) continue;
            var ps = new ArrayList();
            foreach (ParameterInfo pi in m.GetParameters())
                ps.Add(pi.ParameterType.Name + " " + pi.Name);
            names.Add((m.IsStatic ? "static " : "") + m.Name
                + "(" + String.Join(", ", (string[])ps.ToArray(typeof(string))) + ")");
        }
        Console.WriteLine("TYPE " + t.FullName);
        if (names.Count == 0) Console.WriteLine("    (no Decompile* method)");
        foreach (object o in names) Console.WriteLine("    " + o);
    }
}
Console.WriteLine("api172 DONE asm=" + nAsm + " type=" + nType);
