using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第44轮续 · 原作房间与门的**全量**取证
//   产出 <data.win 同级>/rooms44.txt 与 rooms44.json
//   [A] Rooms 全序（index == Data.Rooms index，与 scr_roomname 对齐）
//   [B] 每个 room 的宽高 / 图层数 / 图层类型
//   [C] 门与落点实例：obj_door* / obj_marker* 的 (x, y, object名)
//       —— 门的"连到哪"由 obj_doorA~F 的 Data.Rooms ±N 关系表达（第43轮已解），
//          这里只取**实例坐标**，用于配对"门 ↔ 落点"
//   [D] 锚点：多帧 / 动画帧数（用于背景）
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "rooms44.txt");
string outJson = Path.Combine(dir, "rooms44.json");
var sb = new StringBuilder();
var jb = new StringBuilder();

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

string JsonS(string s)
{
    if (s == null) return "null";
    var b = new StringBuilder("\"");
    foreach (char c in s)
    {
        if (c == '"') b.Append("\\\"");
        else if (c == '\\') b.Append("\\\\");
        else if (c == '\n') b.Append("\\n");
        else if (c == '\r') b.Append("\\r");
        else if (c == '\t') b.Append("\\t");
        else if (c < 32) b.Append("\\u").Append(((int)c).ToString("x4"));
        else b.Append(c);
    }
    b.Append("\"");
    return b.ToString();
}

string S(object o)
{
    return o == null ? null : o.ToString();
}

// ★ JSON 里布尔必须小写（C# 的 bool.ToString() 给的是 "False" ⇒ 会让 json.load 报
//   "Expecting value"）。所有要进 JSON 的标量一律走这个规整函数。
string J(object o)
{
    if (o == null) return "null";
    if (o is bool) return ((bool)o) ? "true" : "false";
    string s = o.ToString();
    if (s == "True") return "true";
    if (s == "False") return "false";
    // 数值/其它原样
    return s.Length == 0 ? "null" : s;
}

bool IsDoor(string nm)
{
    if (nm == null) return false;
    return nm.StartsWith("obj_door", StringComparison.OrdinalIgnoreCase);
}

bool IsMarker(string nm)
{
    if (nm == null) return false;
    return nm.StartsWith("obj_marker", StringComparison.OrdinalIgnoreCase);
}

try
{
    var rooms = (IList)GO(Data, "Rooms");
    sb.AppendLine("== [A] Rooms 总数 = " + rooms.Count + " ==");

    jb.Append("{\"n_rooms\": ").Append(rooms.Count).Append(",\n");
    jb.Append(" \"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append(" \"rooms\": [\n");

    int nDoor = 0, nMarker = 0;
    for (int i = 0; i < rooms.Count; i++)
    {
        object r = rooms[i];
        string rn = ResName(r);
        string w = S(GO(r, "Width"));
        string h = S(GO(r, "Height"));
        string pers = S(GO(r, "Persistent"));

        // 图层
        var layers = GO(r, "Layers") as IList;
        int nLayer = layers == null ? 0 : layers.Count;
        var layerNames = new List<string>();
        int nTileLayer = 0, nBgLayer = 0;
        if (layers != null)
            for (int k = 0; k < layers.Count; k++)
            {
                string ln = ResName(layers[k]);
                layerNames.Add(ln == null ? "?" : ln);
                string lt = S(GO(layers[k], "LayerType"));
                if (lt != null && lt.IndexOf("Tiles", StringComparison.OrdinalIgnoreCase) >= 0) nTileLayer++;
                if (lt != null && lt.IndexOf("Background", StringComparison.OrdinalIgnoreCase) >= 0) nBgLayer++;
            }

        // ★ 实例住在 **layer.InstancesData.Instances**（UTMT 的 LayerInstancesData 子对象）。
        //   第 44 轮连踩两次路径坑：先误用 room.GameObjects（GMS2 里恒空），
        //   再误用 layer.Instances（Layer 上没这个属性）⇒ 门/落点全统计成 0（假结论）。
        //   正确路径由 probeinst44.csx 实测确认：Layer.Data / Layer.InstancesData
        //   （两者同指一个 LayerInstancesData），其 .Instances 才是实例表。
        var doors = new List<string>();
        var markers = new List<string>();
        int nInstTotal = 0;
        if (layers != null)
            for (int k = 0; k < layers.Count; k++)
            {
                object layer = layers[k];
                object lid = GO(layer, "InstancesData");
                if (lid == null) lid = GO(layer, "Data");
                var li = GO(lid, "Instances") as IList;
                if (li == null) continue;
                for (int m = 0; m < li.Count; m++)
                {
                    object inst = li[m];
                    nInstTotal++;
                    // ★ 对象引用属性名 = **ObjectDefinition**（UTMT 的 UndertaleRoom+GameObject）。
                    //   误用 "Object" 会静默拿 null ⇒ 门/落点又全 0（本轮第 3 次同型坑）。
                    string on = ResName(GO(inst, "ObjectDefinition"));
                    if (on == null) on = ResName(GO(inst, "Object"));
                    string ix = S(GO(inst, "X"));
                    string iy = S(GO(inst, "Y"));
                    if (IsDoor(on)) doors.Add(ix + "," + iy + "," + on);
                    else if (IsMarker(on)) markers.Add(ix + "," + iy + "," + on);
                }
            }

        nDoor += doors.Count;
        nMarker += markers.Count;
        sb.AppendLine(i + "\t" + rn + "\t" + w + "x" + h
                      + "\tpers=" + pers
                      + "\tlayers=" + nLayer + "(tile" + nTileLayer + "/bg" + nBgLayer + ")"
                      + "\tinst=" + nInstTotal
                      + "\tdoors=" + doors.Count + "\tmarkers=" + markers.Count);
        if (doors.Count > 0)
            foreach (string d in doors) sb.AppendLine("      D " + d);
        if (markers.Count > 0)
            foreach (string m in markers) sb.AppendLine("      M " + m);

        jb.Append("  {\"id\": ").Append(i).Append(", \"name\": ").Append(JsonS(rn))
          .Append(", \"w\": ").Append(J(GO(r, "Width")))
          .Append(", \"h\": ").Append(J(GO(r, "Height")))
          .Append(", \"persistent\": ").Append(J(GO(r, "Persistent")))
          .Append(", \"n_layers\": ").Append(nLayer)
          .Append(", \"layer_names\": [");
        for (int k = 0; k < layerNames.Count; k++)
        { if (k > 0) jb.Append(","); jb.Append(JsonS(layerNames[k])); }
        jb.Append("], \"doors\": [");
        for (int k = 0; k < doors.Count; k++)
        { if (k > 0) jb.Append(","); jb.Append(JsonS(doors[k])); }
        jb.Append("], \"markers\": [");
        for (int k = 0; k < markers.Count; k++)
        { if (k > 0) jb.Append(","); jb.Append(JsonS(markers[k])); }
        jb.Append("]}");
        if (i < rooms.Count - 1) jb.Append(",");
        jb.Append("\n");
    }
    jb.Append(" ]}\n");

    sb.AppendLine();
    sb.AppendLine("== [C] 门实例总数 = " + nDoor + " ；落点实例总数 = " + nMarker + " ==");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
