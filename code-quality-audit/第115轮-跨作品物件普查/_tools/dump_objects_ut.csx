// dump_objects_ut.csx —— 导出 GameObject 索引（名字 / 精灵 / 可见 / 持久）
// 用法：UndertaleModCli.exe load <game.droid 副本> -s dump_objects_ut.csx
// 输出：objmap_ut.txt（UTF-8 无 BOM），逐行
//   <id>\t<name>\tspr=<sprite 名>\tvis=<True|False>\tpers=<True|False>
// 末尾附 "== Rooms = N ==" 段（房间名索引），便于对房间数
//
// 与第43轮 objmap43.csx 的区别只有输出文件名与目录 —— 字段格式**完全一致**，
// 这样 props 分级脚本可以原样复用 load_objmap()。
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
string outObj = Path.Combine(dir, "objmap_ut.txt");
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
        object vobj = GO(o, "Visible");
        object pobj = GO(o, "Persistent");
        string vis = vobj == null ? "?" : vobj.ToString();
        string pers = pobj == null ? "?" : pobj.ToString();
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
ScriptMessage("OBJMAP OK objs=" + ((IList)GO(Data, "GameObjects")).Count.ToString());
