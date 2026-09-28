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
var utf8 = new UTF8Encoding(false);

var sb = new StringBuilder();
sb.Append("{\n  \"rooms\": [");
for (int i = 0; i < Data.Rooms.Count; i++)
{
    UndertaleRoom room = Data.Rooms[i];
    if (i > 0) sb.Append(",");
    sb.Append("\n    {\"index\": ").Append(i);
    sb.Append(", \"name\": ").Append(JsonStr(room.Name == null ? "" : room.Name.Content));
    sb.Append(", \"w\": ").Append(room.Width).Append(", \"h\": ").Append(room.Height);
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
                var a1 = CollectRefs(ly.AssetsData, "Sprites");
                if (a1.Count > 0) sb.Append(", \"asset_sprites\": ").Append(Parts(a1));
            }
            sb.Append("}");
        }
    }
    sb.Append("]}");
}
sb.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_rooms.json"), sb.ToString(), utf8);

var sbS = new StringBuilder();
sbS.Append("{\n  \"sprites\": [");
for (int i = 0; i < Data.Sprites.Count; i++)
{
    var s = Data.Sprites[i];
    if (i > 0) sbS.Append(",");
    int nf = (s.Textures != null) ? s.Textures.Count : 0;
    sbS.Append("\n    {\"i\": ").Append(i);
    sbS.Append(", \"name\": ").Append(JsonStr(s.Name == null ? "" : s.Name.Content));
    sbS.Append(", \"w\": ").Append(s.Width).Append(", \"h\": ").Append(s.Height);
    sbS.Append(", \"frames\": ").Append(nf);
    sbS.Append("}");
}
sbS.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_sprites.json"), sbS.ToString(), utf8);

var sbO = new StringBuilder();
sbO.Append("{\n  \"objects\": [");
for (int i = 0; i < Data.GameObjects.Count; i++)
{
    var o = Data.GameObjects[i];
    if (i > 0) sbO.Append(",");
    string sp = "";
    if (o.Sprite != null && o.Sprite.Name != null) sp = o.Sprite.Name.Content;
    sbO.Append("\n    {\"i\": ").Append(i);
    sbO.Append(", \"name\": ").Append(JsonStr(o.Name == null ? "" : o.Name.Content));
    sbO.Append(", \"sprite\": ").Append(JsonStr(sp));
    sbO.Append("}");
}
sbO.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_objects.json"), sbO.ToString(), utf8);

var sbB = new StringBuilder();
sbB.Append("{\n  \"backgrounds\": [");
for (int i = 0; i < Data.Backgrounds.Count; i++)
{
    var b = Data.Backgrounds[i];
    if (i > 0) sbB.Append(",");
    sbB.Append("\n    {\"i\": ").Append(i);
    sbB.Append(", \"name\": ").Append(JsonStr(b.Name == null ? "" : b.Name.Content));
    sbB.Append("}");
}
sbB.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_bg.json"), sbB.ToString(), utf8);

var sbT = new StringBuilder();
sbT.Append("{\n  \"strings\": [");
for (int i = 0; i < Data.Strings.Count; i++)
{
    if (i > 0) sbT.Append(",");
    sbT.Append("\n    ").Append(JsonStr(Data.Strings[i].Content));
}
sbT.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_strings.json"), sbT.ToString(), utf8);

ScriptMessage("EXPORT-OK rooms=" + Data.Rooms.Count + " sprites=" + Data.Sprites.Count
    + " objects=" + Data.GameObjects.Count + " strings=" + Data.Strings.Count);

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
