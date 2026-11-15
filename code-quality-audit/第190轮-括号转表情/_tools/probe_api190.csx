// 第190轮 · 反射探测 UTMT 的导出 API 与贴图页数据结构。
//
// 为什么先探测再写
// ----------------
// 直接写 `TextureWorker.ExportAsPNG(embedded, path)` 是在猜重载是否存在；
// 直接写 `System.Drawing.Imaging` 已证 CS0234（该命名空间没被引用）。
// 猜错的代价是每轮 3 秒的编译失败 + 一次往返。
// 用反射把**真实签名**打印出来，一次问清。
//
// ★ 同时打印 UndertaleEmbeddedTexture.TextureData 的成员，
//   因为"整页 Bitmap 到底叫 Image 还是别的名字"也一直在猜。

using System;
using System.IO;
using System.Reflection;
using System.Text;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Util;

string outDir = @"__OUTDIR__";
Directory.CreateDirectory(outDir);
var sb = new StringBuilder();

sb.Append("### Data.EmbeddedTextures = ")
  .Append(Data.EmbeddedTextures == null ? "null" : Data.EmbeddedTextures.Count.ToString())
  .Append('\n');

// ① TextureWorker 的静态方法（重点：ExportAsPNG 的所有重载）
sb.Append("\n### TextureWorker methods\n");
try
{
    var tw = typeof(TextureWorker);
    foreach (var m in tw.GetMethods(BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance))
    {
        var ps = m.GetParameters();
        var names = new string[ps.Length];
        for (int k = 0; k < ps.Length; k++)
            names[k] = ps[k].ParameterType.Name + " " + ps[k].Name;
        sb.Append("  ").Append(m.IsStatic ? "static " : "inst   ")
          .Append(m.ReturnType.Name).Append(' ').Append(m.Name)
          .Append('(').Append(string.Join(", ", names)).Append(")\n");
    }
}
catch (Exception e) { sb.Append("  [err] ").Append(e.GetType().Name).Append('\n'); }

// ② UndertaleEmbeddedTexture 的成员
sb.Append("\n### UndertaleEmbeddedTexture members\n");
try
{
    var t = typeof(UndertaleEmbeddedTexture);
    foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance))
        sb.Append("  prop ").Append(p.PropertyType.Name).Append(' ').Append(p.Name).Append('\n');
    foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Instance))
        sb.Append("  field ").Append(f.FieldType.Name).Append(' ').Append(f.Name).Append('\n');
}
catch (Exception e) { sb.Append("  [err] ").Append(e.GetType().Name).Append('\n'); }

// ③ TextureData 的类型与其成员（这里才是 Bitmap 与原始字节所在）
sb.Append("\n### TexData members\n");
try
{
    if (Data.EmbeddedTextures != null && Data.EmbeddedTextures.Count > 0)
    {
        var tex0 = Data.EmbeddedTextures[0];
        if (tex0 != null && tex0.TextureData != null)
        {
            var dt = tex0.TextureData.GetType();
            sb.Append("  type = ").Append(dt.FullName).Append('\n');
            foreach (var p in dt.GetProperties(BindingFlags.Public | BindingFlags.Instance))
                sb.Append("  prop ").Append(p.PropertyType.Name).Append(' ').Append(p.Name).Append('\n');
            foreach (var f in dt.GetFields(BindingFlags.Public | BindingFlags.Instance))
                sb.Append("  field ").Append(f.FieldType.Name).Append(' ').Append(f.Name).Append('\n');
        }
        else sb.Append("  [null] TextureData\n");
    }
}
catch (Exception e) { sb.Append("  [err] ").Append(e.GetType().Name).Append('\n'); }

// ④ 贴图页 Bitmap 的**真实类型**（决定后面能不能 Save / GetPixel）
//
// ★★ 坑（本轮实测）：不要用 `Type.GetType("System.Drawing.Bitmap, System.Drawing")` 探测。
//   在 .NET 10 + Roslyn 脚本下它会走 RuntimeAssembly.GetTypeCore，
//   直接 **FailFast 0xC0000006**（进程猝死、rc=3221225478），连 try/catch 都拦不住。
//   改成"从已加载程序集里翻类型"，纯托管遍历，翻不到就是 null，不会崩。
sb.Append("\n### 已加载程序集里与图像相关的类型\n");
try
{
    foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
    {
        string an = "";
        try { an = asm.GetName().Name; } catch { continue; }
        if (an.IndexOf("Drawing", StringComparison.OrdinalIgnoreCase) < 0
            && an.IndexOf("ImageSharp", StringComparison.OrdinalIgnoreCase) < 0
            && an.IndexOf("UndertaleModLib", StringComparison.OrdinalIgnoreCase) < 0)
            continue;
        sb.Append("  asm ").Append(an).Append('\n');
        Type[] ts;
        try { ts = asm.GetTypes(); } catch { sb.Append("    [GetTypes 失败]\n"); continue; }
        int shown = 0;
        foreach (var t in ts)
        {
            string fn = "";
            try { fn = t.FullName ?? ""; } catch { continue; }
            if (fn.IndexOf("Bitmap", StringComparison.OrdinalIgnoreCase) < 0
                && fn.IndexOf("ImageFormat", StringComparison.OrdinalIgnoreCase) < 0
                && fn.IndexOf("Image`", StringComparison.OrdinalIgnoreCase) < 0
                && fn.IndexOf("TextureWorker", StringComparison.OrdinalIgnoreCase) < 0)
                continue;
            sb.Append("    type ").Append(fn).Append('\n');
            if (++shown > 25) { sb.Append("    ...\n"); break; }
        }
    }
}
catch (Exception e) { sb.Append("  [err] ").Append(e.GetType().Name).Append('\n'); }

File.WriteAllText(Path.Combine(outDir, "api_probe.txt"), sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("[probe] 写入 " + Path.Combine(outDir, "api_probe.txt"));
Console.WriteLine(sb.ToString());
