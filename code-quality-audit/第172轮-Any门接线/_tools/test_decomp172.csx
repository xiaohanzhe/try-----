// 第172轮 · 一次性：验证「解压一行代码」的正确调用姿势（只读）
using System;
using System.Collections;
using UndertaleModLib;
using UndertaleModLib.Models;
using UndertaleModLib.Decompiler;
using Underanalyzer.Decompiler;

EnsureDataLoaded();

string want = "gml_Object_obj_doorAny_Alarm_2";
UndertaleCode hit = null;
foreach (object c in (IEnumerable)Data.Code)
{
    UndertaleCode uc = c as UndertaleCode;
    if (uc == null || uc.Name == null) continue;
    if (uc.Name.Content == want) { hit = uc; break; }
}
if (hit == null) { Console.WriteLine("test172: 找不到 " + want); return; }
Console.WriteLine("test172: found " + hit.Name.Content + " instrs=" + (hit.Instructions == null ? -1 : hit.Instructions.Count));

var gd = new GlobalDecompileContext(Data, null);
var dc = new DecompileContext(gd, hit, null);
string gml = dc.DecompileToString();
Console.WriteLine("----GML----");
Console.WriteLine(gml);
Console.WriteLine("----END----");
Console.WriteLine("test172 OK");
