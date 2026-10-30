// probe_types120.csx —— 反射 dump 关键类型的成员名（避免一次次撞 CS1061 编译红）
// 用法：UTMT_OUT=<tsv> load <data> -s probe_types120.csx
//
// 第120轮追加：递归展开 UndertaleRoom 的**所有嵌套类型**（GMS2 的房间内容在 Layers 里，
// 而 Layer 的数据类是嵌套类，名字猜不中就是编译红）。
using System;
using System.IO;
using System.Text;
using System.Reflection;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

EnsureDataLoaded();

string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath))
{
    ScriptError("UTMT_OUT not set");
    return;
}

var sb = new StringBuilder();
sb.Append("owner\tkind\tname\tvalueType\n");

void Dump(Type t, int depth)
{
    if (t == null || depth > 2) return;
    sb.Append("###\t").Append(t.FullName).Append('\n');
    foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Instance))
        sb.Append(t.Name).Append("\tfield\t").Append(f.Name).Append('\t').Append(f.FieldType.Name).Append('\n');
    foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance))
        sb.Append(t.Name).Append("\tprop\t").Append(p.Name).Append('\t').Append(p.PropertyType.Name).Append('\n');
    foreach (var nt in t.GetNestedTypes(BindingFlags.Public))
        Dump(nt, depth + 1);
}

Dump(typeof(UndertaleRoom), 0);
Dump(typeof(UndertaleBackground), 0);
Dump(typeof(UndertaleSprite), 0);

// TextureWorker 的方法签名（ExportAsPNG 有几个重载，参数顺序别猜）
foreach (var m in typeof(TextureWorker).GetMethods(BindingFlags.Public | BindingFlags.Instance))
{
    var ps = new StringBuilder();
    foreach (var p in m.GetParameters())
        ps.Append(p.ParameterType.Name).Append(' ').Append(p.Name).Append(", ");
    sb.Append("TextureWorker\tmethod\t").Append(m.Name).Append('\t').Append(ps.ToString()).Append('\n');
}

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("types done -> " + outPath);
