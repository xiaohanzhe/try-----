using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 导出房间结构清单（修正版：正确解析资源真名）
// 产出 <data.win 同级>/rooms_map.json
EnsureDataLoaded();

string outPath = Path.Combine(Path.GetDirectoryName(FilePath), "rooms_map.json");
var sb = new StringBuilder();
sb.Append("{\n  \"source\": ").Append(JsonStr(FilePath)).Append(",\n");
sb.Append("  \"rooms\": [");

for (int i = 0; i < Data.Rooms.Count; i++)
{
    UndertaleRoom room = Data.Rooms[i];
    if (i > 0) sb.Append(",");
    sb.Append("\n    {\"index\": ").Append(i);
    sb.Append(", \"name\": ").Append(JsonStr(room.Name == null ? "" : room.Name.Content));
    sb.Append(", \"width\": ").Append(room.Width).Append(", \"height\": ").Append(room.Height);
    sb.Append(", \"layers\": [");

    if (room.Layers != null)
    {
        for (int j = 0; j < room.Layers.Count; j++)
        {
            UndertaleRoom.Layer ly = room.Layers[j];
            if (j > 0) sb.Append(",");
            string lname = (ly.LayerName == null) ? "" : ly.LayerName.Content;
            sb.Append("\n      {\"name\": ").Append(JsonStr(lname));
            sb.Append(", \"type\": ").Append(JsonStr(ly.LayerType.ToString()));
            sb.Append(", \"depth\": ").Append(ly.LayerDepth);
            sb.Append(", \"visible\": ").Append(ly.IsVisible ? "true" : "false");

            if (ly.BackgroundData != null && ly.BackgroundData.Sprite != null)
                sb.Append(", \"bg_sprite\": ").Append(JsonStr(ResolveName(ly.BackgroundData.Sprite)));

            if (ly.AssetsData != null)
            {
                var a1 = CollectRefs(ly.AssetsData, "Sprites");    if (a1.Count > 0) sb.Append(", \"asset_sprites\": ").Append(Parts(a1));
                var a2 = CollectRefs(ly.AssetsData, "Sequences");  if (a2.Count > 0) sb.Append(", \"asset_sequences\": ").Append(Parts(a2));
                var a3 = CollectRefs(ly.AssetsData, "NineSlices"); if (a3.Count > 0) sb.Append(", \"asset_nineslices\": ").Append(Parts(a3));
            }
            if (ly.InstancesData != null)
            {
                var a4 = CollectRefs(ly.InstancesData, "Instances"); if (a4.Count > 0) sb.Append(", \"instances\": ").Append(Parts(a4));
            }
            if (ly.TilesData != null)
            {
                var a5 = CollectRefs(ly.TilesData, "TileData"); if (a5.Count > 0) sb.Append(", \"tiles\": ").Append(Parts(a5));
            }

            sb.Append("}");
        }
    }
    sb.Append("]}");
}
sb.Append("\n  ]\n}\n");

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));

// ---------- helpers ----------

// 取出 UTMT 资源的名字：Name.Content
string PlainName(object v)
{
    if (v == null) return null;
    PropertyInfo np = v.GetType().GetProperty("Name");
    if (np == null) return null;
    object nv = null;
    try { nv = np.GetValue(v); } catch (Exception) { return null; }
    if (nv == null) return null;
    PropertyInfo cp = nv.GetType().GetProperty("Content");
    if (cp == null) return null;
    object cv = null;
    try { cv = cp.GetValue(nv); } catch (Exception) { return null; }
    return cv == null ? null : cv.ToString();
}

// 先看自己有没有名字；没有再看它引用了谁
string ResolveName(object o)
{
    if (o == null) return "null";
    string own = PlainName(o);
    if (!String.IsNullOrEmpty(own)) return own;

    Type t = o.GetType();
    foreach (string pn in new string[] { "Sprite", "BackgroundDefinition", "SpriteDefinition",
                                         "ObjectDefinition", "Texture" })
    {
        PropertyInfo p = t.GetProperty(pn);
        if (p == null) continue;
        object v = null;
        try { v = p.GetValue(o); } catch (Exception) { continue; }
        if (v == null) continue;
        string nm = PlainName(v);
        if (!String.IsNullOrEmpty(nm)) return nm;
    }
    return o.GetType().Name;
}

List<string> CollectRefs(object container, string propName)
{
    var res = new List<string>();
    PropertyInfo p = container.GetType().GetProperty(propName);
    if (p == null) return res;
    object col = null;
    try { col = p.GetValue(container); } catch (Exception) { return res; }
    IEnumerable en = col as IEnumerable;
    if (en == null) return res;
    int guard = 0;
    foreach (object item in en)
    {
        if (guard++ > 5000) break;
        res.Add(ResolveName(item));
    }
    return res;
}

string Parts(List<string> xs)
{
    var b = new StringBuilder("[");
    for (int k = 0; k < xs.Count; k++)
    {
        if (k > 0) b.Append(", ");
        b.Append(JsonStr(xs[k]));
    }
    b.Append("]");
    return b.ToString();
}

string JsonStr(string s)
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
