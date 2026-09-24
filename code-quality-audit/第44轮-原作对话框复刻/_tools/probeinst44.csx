using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 探针：UTMT 里 room → layer → instance 的**真实属性路径**
// 产出 <data.win 同级>/probeinst44.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "probeinst44.txt");
var sb = new StringBuilder();

object GO(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

void DumpProps(object o, string label, int max)
{
    if (o == null) { sb.AppendLine(label + " = null"); return; }
    sb.AppendLine(label + " :: " + o.GetType().FullName);
    var ps = o.GetType().GetProperties();
    int n = 0;
    foreach (var p in ps)
    {
        if (n++ >= max) break;
        string vs = "?";
        try { object v = p.GetValue(o); vs = v == null ? "null" : v.GetType().Name + "(" + (v.ToString().Length > 60 ? v.ToString().Substring(0, 60) : v.ToString()) + ")"; }
        catch (Exception e) { vs = "!! " + e.GetType().Name; }
        sb.AppendLine("   ." + p.Name + " : " + p.PropertyType.Name + " = " + vs);
    }
}

try
{
    var rooms = (IList)GO(Data, "Rooms");
    sb.AppendLine("Rooms = " + rooms.Count);
    // 找一个有内容的房间（ch1 里 room_town_north）
    object target = null;
    for (int i = 0; i < rooms.Count; i++)
    {
        string nm = null;
        object nv = GO(rooms[i], "Name");
        if (nv != null) { object cv = GO(nv, "Content"); nm = cv == null ? null : cv.ToString(); }
        if (nm != null && nm.IndexOf("town_north", StringComparison.OrdinalIgnoreCase) >= 0)
        { target = rooms[i]; sb.AppendLine("命中房间 index=" + i + " name=" + nm); break; }
    }
    if (target == null) target = rooms[Math.Min(10, rooms.Count - 1)];

    sb.AppendLine();
    sb.AppendLine("=== room 的属性 ===");
    DumpProps(target, "Room", 40);

    var layers = GO(target, "Layers") as IList;
    sb.AppendLine();
    sb.AppendLine("=== Layers = " + (layers == null ? -1 : layers.Count) + " ===");
    if (layers != null && layers.Count > 0)
    {
        object L0 = layers[0];
        sb.AppendLine("--- layer[0] 的属性 ---");
        DumpProps(L0, "Layer", 40);
        for (int k = 0; k < Math.Min(layers.Count, 6); k++)
        {
            object L = layers[k];
            string lt = GO(L, "LayerType") == null ? "?" : GO(L, "LayerType").ToString();
            var ins = GO(L, "Instances") as IList;
            var tiles = GO(L, "Tiles") as IList;
            sb.AppendLine("  [" + k + "] type=" + lt
                          + " instances=" + (ins == null ? "-" : ins.Count.ToString())
                          + " tiles=" + (tiles == null ? "-" : tiles.Count.ToString()));
            // ★ 走 InstancesData / Data 两条候选，打出真实属性
            object lid = GO(L, "InstancesData");
            if (lid == null) lid = GO(L, "Data");
            sb.AppendLine("     InstancesData=" + (lid == null ? "null" : lid.GetType().FullName));
            if (lid != null)
            {
                DumpProps(lid, "     <InstancesData>", 20);
                var ins2 = GO(lid, "Instances") as IList;
                sb.AppendLine("     InstancesData.Instances = "
                              + (ins2 == null ? "null" : ins2.Count.ToString()));
                if (ins2 != null && ins2.Count > 0)
                {
                    DumpProps(ins2[0], "     <Instance[0]>", 25);
                    // 看看对象名
                    object iobj = GO(ins2[0], "Object");
                    sb.AppendLine("     Object 属性类型 = "
                                  + (iobj == null ? "null" : iobj.GetType().FullName));
                    DumpProps(iobj, "     <ObjRef>", 12);
                }
            }
            // RoomsLayer 的其它可能名字
            var objs = GO(L, "GameObjects") as IList;
            if (objs != null && objs.Count > 0)
                sb.AppendLine("   (layer 也有 GameObjects=" + objs.Count + ")");
        }
    }
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
