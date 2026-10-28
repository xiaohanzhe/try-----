// dump_instances.csx  —— 导出每间房、每个 Instances 层里每个实例的坐标/缩放/旋转
// 用法：set UTMT_OUT=<输出 tsv> 后  UndertaleModCli.exe load <data.win 副本> -s dump_instances.csx
// 输出（TSV，UTF-8 无 BOM）：
//   H\t<rooms>\t<gameObjectsTotal>
//   R\t<roomIndex>\t<roomName>\t<w>\t<h>\t<layerCount>\t<instSumInLayers>\t<gameObjectsCount>
//   I\t<objName>\t<x>\t<y>\t<sx>\t<sy>\t<rot>\t<imgIndex>\t<imgSpeed>\t<depth>\t<layerName>
using System;
using System.IO;
using System.Text;
using System.Globalization;
using System.Reflection;
using System.Collections;
using UndertaleModLib;
using UndertaleModLib.Models;

EnsureDataLoaded();

string outPath = Environment.GetEnvironmentVariable("UTMT_OUT");
if (String.IsNullOrEmpty(outPath))
{
    ScriptError("UTMT_OUT not set");
    return;
}

object GF(object obj, string name)
{
    if (obj == null) return null;
    Type t = obj.GetType();
    PropertyInfo p = t.GetProperty(name, BindingFlags.Public | BindingFlags.Instance);
    if (p != null && p.CanRead) return p.GetValue(obj, null);
    FieldInfo f = t.GetField(name, BindingFlags.Public | BindingFlags.Instance);
    if (f != null) return f.GetValue(obj);
    return null;
}

string GS(object obj, string name)
{
    object v = GF(obj, name);
    if (v == null) return "";
    UndertaleString us = v as UndertaleString;
    if (us != null) return us.Content;
    return Convert.ToString(v, CultureInfo.InvariantCulture);
}

double GD(object obj, string name)
{
    object v = GF(obj, name);
    if (v == null) return 0.0;
    try { return Convert.ToDouble(v, CultureInfo.InvariantCulture); }
    catch { return 0.0; }
}

string IName(object inst)
{
    object oref = GF(inst, "Object");
    if (oref == null) oref = GF(inst, "ObjectDefinition");
    if (oref == null) return "";
    object res = GF(oref, "Resource");
    object tgt = (res != null) ? res : oref;
    object nm = GF(tgt, "Name");
    if (nm == null) return "";
    UndertaleString us = nm as UndertaleString;
    if (us != null) return us.Content;
    return Convert.ToString(nm, CultureInfo.InvariantCulture);
}

StringBuilder sb = new StringBuilder(1 << 24);
sb.Append("H\t").Append(Data.Rooms.Count).Append('\t').Append(Data.GameObjects.Count).Append('\n');

int nInst = 0;
for (int ri = 0; ri < Data.Rooms.Count; ri++)
{
    var room = Data.Rooms[ri];
    int instSum = 0;
    var lines = new StringBuilder(1 << 16);
    for (int li = 0; li < room.Layers.Count; li++)
    {
        var ly = room.Layers[li];
        object idata = GF(ly, "InstancesData");
        if (idata == null) continue;
        object lst = GF(idata, "Instances");
        IList arr = lst as IList;
        if (arr == null) continue;
        string lname = GS(ly, "LayerName");
        int depth = (int)GD(ly, "LayerDepth");
        for (int k = 0; k < arr.Count; k++)
        {
            object inst = arr[k];
            string on = IName(inst);
            double x = GD(inst, "X");
            double y = GD(inst, "Y");
            double sx = GD(inst, "ScaleX");
            double sy = GD(inst, "ScaleY");
            double rot = GD(inst, "Rotation");
            double ii = GD(inst, "ImageIndex");
            double isp = GD(inst, "ImageSpeed");
            lines.Append("I\t").Append(on).Append('\t')
                 .Append(x.ToString("0.####", CultureInfo.InvariantCulture)).Append('\t')
                 .Append(y.ToString("0.####", CultureInfo.InvariantCulture)).Append('\t')
                 .Append(sx.ToString("0.####", CultureInfo.InvariantCulture)).Append('\t')
                 .Append(sy.ToString("0.####", CultureInfo.InvariantCulture)).Append('\t')
                 .Append(rot.ToString("0.####", CultureInfo.InvariantCulture)).Append('\t')
                 .Append(((int)ii).ToString(CultureInfo.InvariantCulture)).Append('\t')
                 .Append(isp.ToString("0.####", CultureInfo.InvariantCulture)).Append('\t')
                 .Append(depth.ToString(CultureInfo.InvariantCulture)).Append('\t')
                 .Append(lname).Append('\n');
            instSum++;
        }
    }
    sb.Append("R\t").Append(ri.ToString(CultureInfo.InvariantCulture)).Append('\t')
      .Append(GS(room, "Name")).Append('\t')
      .Append(((int)GD(room, "Width")).ToString(CultureInfo.InvariantCulture)).Append('\t')
      .Append(((int)GD(room, "Height")).ToString(CultureInfo.InvariantCulture)).Append('\t')
      .Append(room.Layers.Count.ToString(CultureInfo.InvariantCulture)).Append('\t')
      .Append(instSum.ToString(CultureInfo.InvariantCulture)).Append('\t')
      .Append(room.GameObjects.Count.ToString(CultureInfo.InvariantCulture)).Append('\n');
    sb.Append(lines);
    nInst += instSum;
}

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
ScriptMessage("DUMP OK rooms=" + Data.Rooms.Count.ToString() + " inst=" + nInst.ToString());
