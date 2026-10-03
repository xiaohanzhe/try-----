using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();
string dir = Path.GetDirectoryName(FilePath);
var utf8 = new UTF8Encoding(false);

var sbC = new StringBuilder();
int nCode = 0, nNonEmpty = 0;
for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    if (c == null || c.Name == null) continue;
    string nm = c.Name.Content;
    string low = nm.ToLowerInvariant();
    bool keep = low.Contains("obj_time") || low.Contains("obj_doorparent") ||
                low.Contains("obj_interactable") || low.Contains("obj_hero");
    if (!keep) continue;
    string src = Decomp(c);
    if (src == null) src = "";
    if (src.Length > 0) nNonEmpty++;
    if (nCode > 0) sbC.Append(",\n");
    sbC.Append("  { \"name\": ").Append(JsonStr(nm));
    sbC.Append(", \"len\": ").Append(src.Length);
    sbC.Append(", \"src\": ").Append(JsonStr(src));
    sbC.Append("}");
    nCode++;
}
var sbOut = new StringBuilder();
sbOut.Append("{\n \"code_count\": ").Append(nCode).Append(",\n \"codes\": [\n");
sbOut.Append(sbC);
sbOut.Append("\n ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_r5b_code.json"), sbOut.ToString(), utf8);
ScriptMessage("R5B-OK codes=" + nCode + " nonempty=" + nNonEmpty);

string Decomp(UndertaleCode c)
{
    try
    {
        Type t = null;
        foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
        {
            t = a.GetType("UndertaleModLib.Compiler.CodeImportGroup");
            if (t != null) break;
        }
        if (t == null) return "<NO-CodeImportGroup>";
        MethodInfo mi = null;
        foreach (MethodInfo m in t.GetMethods(
                BindingFlags.Public | BindingFlags.NonPublic |
                BindingFlags.Instance | BindingFlags.DeclaredOnly))
            if (m.Name == "DecompileExistingCode") { mi = m; break; }
        if (mi == null) return "<NO-DecompileExistingCode>";
        Type gdcT = null;
        foreach (var a in AppDomain.CurrentDomain.GetAssemblies())
        {
            gdcT = a.GetType("UndertaleModLib.Decompiler.GlobalDecompileContext");
            if (gdcT != null) break;
        }
        object gdc = null;
        if (gdcT != null)
            foreach (ConstructorInfo ci in gdcT.GetConstructors(
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
            {
                ParameterInfo[] ps = ci.GetParameters();
                if (ps.Length != 2 || ps[0].ParameterType.Name != "UndertaleData") continue;
                try { gdc = ci.Invoke(new object[] { Data, null }); } catch (Exception) { }
                if (gdc != null) break;
            }
        object inst = null;
        foreach (ConstructorInfo ci in t.GetConstructors(
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
        {
            ParameterInfo[] ps = ci.GetParameters();
            if (ps.Length != 3 || ps[0].ParameterType.Name != "UndertaleData") continue;
            try { inst = ci.Invoke(new object[] { Data, gdc, null }); } catch (Exception) { }
            if (inst != null) break;
        }
        if (inst == null) return "<NO-CTOR>";
        object r = mi.Invoke(inst, new object[] { c });
        string s = (r == null) ? "" : r.ToString();
        return s;
    }
    catch (Exception e) { return "<DECOMP-FAIL: " + e.Message + ">"; }
}

string JsonStr(string s)
{
    if (s == null) return "null";
    var b = new StringBuilder("\"");
    foreach (char ch in s)
    {
        if (ch == '"') b.Append("\\\"");
        else if (ch == '\\') b.Append("\\\\");
        else if (ch == '\n') b.Append("\\n");
        else if (ch == '\r') b.Append("\\r");
        else if (ch == '\t') b.Append("\\t");
        else if (ch < 32) b.Append("\\u").Append(((int)ch).ToString("x4"));
        else b.Append(ch);
    }
    b.Append("\"");
    return b.ToString();
}
