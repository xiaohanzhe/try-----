using System;
using System.IO;
using System.Text;
using System.Collections;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第48轮 · 导出全部 code / script / object 名字（一行一个），便于本地检索
// 产出 <data.win 同级>/names48.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "names48.txt");

object GO(object o, string pn)
{
    if (o == null) return null;
    var p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

string ResName(object res)
{
    if (res == null) return null;
    object nv = GO(res, "Name");
    if (nv == null) return null;
    object cv = GO(nv, "Content");
    return cv == null ? null : cv.ToString();
}

var sb = new StringBuilder();
var code = (IList)GO(Data, "Code");
if (code != null)
    for (int i = 0; i < code.Count; i++) sb.AppendLine("CODE\t" + ResName(code[i]));
var scripts = (IList)GO(Data, "Scripts");
if (scripts != null)
    for (int i = 0; i < scripts.Count; i++) sb.AppendLine("SCRIPT\t" + ResName(scripts[i]));
var objs = (IList)GO(Data, "GameObjects");
if (objs != null)
    for (int i = 0; i < objs.Count; i++) sb.AppendLine("OBJ\t" + ResName(objs[i]));
var sprs = (IList)GO(Data, "Sprites");
if (sprs != null)
    for (int i = 0; i < sprs.Count; i++) sb.AppendLine("SPR\t" + ResName(sprs[i]));

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine("names48 OK");
