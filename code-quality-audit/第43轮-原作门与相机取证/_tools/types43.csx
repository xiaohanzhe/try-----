using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 类型名录：列出所有含 View/Room/Layer/Background/Effect 的类型全名
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "types43.txt");
var sb = new StringBuilder();

try
{
    Assembly asm = typeof(UndertaleModLib.Models.UndertaleRoom).Assembly;
    Type[] ts = asm.GetTypes();
    sb.AppendLine("assembly = " + asm.FullName);
    sb.AppendLine("type count = " + ts.Length);
    sb.AppendLine();
    foreach (Type t in ts)
    {
        string n = t.FullName;
        if (n == null) continue;
        if (n.IndexOf("View", StringComparison.OrdinalIgnoreCase) >= 0
            || n.IndexOf("Room", StringComparison.OrdinalIgnoreCase) >= 0
            || n.IndexOf("Layer", StringComparison.OrdinalIgnoreCase) >= 0
            || n.IndexOf("Effect", StringComparison.OrdinalIgnoreCase) >= 0
            || n.IndexOf("Camera", StringComparison.OrdinalIgnoreCase) >= 0
            || n.IndexOf("Background", StringComparison.OrdinalIgnoreCase) >= 0)
        {
            sb.AppendLine(t.IsNested ? "NESTED  " + n : "        " + n);
        }
    }
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
