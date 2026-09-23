using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 对象索引映射（instance_create 的整型参数靠它解码）
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outObj = Path.Combine(dir, "objmap43.txt");
var so = new StringBuilder();

object GO(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
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

try
{
    var objs = (IList)GO(Data, "GameObjects");
    so.AppendLine("GameObjects = " + objs.Count);
    for (int i = 0; i < objs.Count; i++)
    {
        object o = objs[i];
        string nm = ResName(o);
        string sp = ResName(GO(o, "Sprite"));
        string vis = GO(o, "Visible") == null ? "?" : GO(o, "Visible").ToString();
        string pers = GO(o, "Persistent") == null ? "?" : GO(o, "Persistent").ToString();
        so.AppendLine(i + "\t" + nm + "\tspr=" + sp + "\tvis=" + vis + "\tpers=" + pers);
    }
    var rooms = (IList)GO(Data, "Rooms");
    so.AppendLine();
    so.AppendLine("== Rooms = " + rooms.Count + " ==");
    for (int i = 0; i < rooms.Count; i++) so.AppendLine(i + "\t" + ResName(rooms[i]));
}
catch (Exception ex)
{
    so.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outObj, so.ToString(), new UTF8Encoding(false));
