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

// 同时从两处取实例：① room.GameObjects（展平表）② 各层的 InstancesData.Instances。
// 两者可能互为重复视图 ⇒ 分键输出，由 Python 侧对齐，避免"以为取全了其实漏了"。
var sb = new StringBuilder();
sb.Append("{\n  \"rooms\": [");
long totalG = 0, totalL = 0;
for (int i = 0; i < Data.Rooms.Count; i++)
{
    UndertaleRoom room = Data.Rooms[i];
    if (i > 0) sb.Append(",");
    sb.Append("\n    {\"index\": ").Append(i);
    sb.Append(", \"name\": ").Append(JsonStr(room.Name == null ? "" : room.Name.Content));
    sb.Append(", \"w\": ").Append(room.Width).Append(", \"h\": ").Append(room.Height);

    sb.Append(", \"instances\": [");
    bool first = true;
    IEnumerable geo = Prop(room, "GameObjects") as IEnumerable;
    if (geo != null)
    {
        foreach (object g in geo)
        {
            totalG++;
            if (!first) sb.Append(",");
            first = false;
            sb.Append("\n      ").Append(InstJson(g));
        }
    }
    sb.Append("]");

    sb.Append(", \"layer_instances\": [");
    first = true;
    IEnumerable lays = Prop(room, "Layers") as IEnumerable;
    if (lays != null)
    {
        foreach (object ly in lays)
        {
            object idata = Prop(ly, "InstancesData");
            if (idata == null) continue;
            IEnumerable li = Prop(idata, "Instances") as IEnumerable;
            if (li == null) continue;
            foreach (object g in li)
            {
                totalL++;
                if (!first) sb.Append(",");
                first = false;
                sb.Append("\n      ").Append(InstJson(g));
            }
        }
    }
    sb.Append("]}");
}
sb.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "ut_instances.json"), sb.ToString(), utf8);

ScriptMessage("EXPORT-OK rooms=" + Data.Rooms.Count
    + " gameobjects_instances=" + totalG + " layer_instances=" + totalL);

string InstJson(object g)
{
    var b = new StringBuilder("{");
    b.Append("\"obj\": ").Append(JsonStr(ResolveName(Prop(g, "ObjectDefinition"))));
    b.Append(", \"x\": ").Append(Num(g, "X")).Append(", \"y\": ").Append(Num(g, "Y"));
    b.Append(", \"sx\": ").Append(Num(g, "ScaleX")).Append(", \"sy\": ").Append(Num(g, "ScaleY"));
    b.Append(", \"rot\": ").Append(Num(g, "Rotation"));
    b.Append(", \"id\": ").Append(Num(g, "InstanceID"));
    b.Append("}");
    return b.ToString();
}

object Prop(object o, string n)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(n);
    if (p == null) return null;
    try { return p.GetValue(o); } catch (Exception) { return null; }
}

string Num(object o, string n)
{
    object v = Prop(o, n);
    if (v == null) return "null";
    try { return Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture); }
    catch (Exception) { return "null"; }
}

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
