using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using System.Globalization;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第43轮 · 探针 A：房间 view/camera 数据 + 层几何实值 + 层动态效果
// 产出 <data.win 同级>/view43.txt 与 view43.json
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "view43.txt");
string outJson = Path.Combine(dir, "view43.json");
var sb = new StringBuilder();
var jb = new StringBuilder();

string GS(object o, string pn)
{
    if (o == null) return null;
    PropertyInfo p = o.GetType().GetProperty(pn);
    if (p == null) return null;
    object v = null;
    try { v = p.GetValue(o); } catch (Exception) { return null; }
    return v == null ? null : v.ToString();
}

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

string Num(object o, string pn)
{
    object v = GO(o, pn);
    if (v == null) return "null";
    double d;
    try { d = Convert.ToDouble(v, CultureInfo.InvariantCulture); }
    catch (Exception) { return "null"; }
    return d.ToString("0.####", CultureInfo.InvariantCulture);
}

void DumpProps(Type t)
{
    sb.AppendLine("  --- " + t.Name + " ---");
    PropertyInfo[] ps = t.GetProperties();
    foreach (PropertyInfo p in ps)
    {
        string rt = "";
        try { rt = p.PropertyType.Name; } catch (Exception) { rt = "?"; }
        sb.AppendLine("    " + p.Name + " : " + rt);
    }
}

try
{
    // ===== [0] 反射：房间 / view / 层（嵌套类型名不确定，改成实例运行时反射）=====
    sb.AppendLine("== [0] 反射 ==");
    DumpProps(typeof(UndertaleRoom));
    DumpProps(typeof(UndertaleRoom.View));
    DumpProps(typeof(UndertaleRoom.Layer));
    DumpProps(typeof(UndertaleRoom.Layer.LayerData));
    DumpProps(typeof(UndertaleRoom.Layer.LayerBackgroundData));
    DumpProps(typeof(UndertaleRoom.Layer.LayerTilesData));
    DumpProps(typeof(UndertaleRoom.Layer.LayerInstancesData));
    DumpProps(typeof(UndertaleRoom.Layer.LayerAssetsData));
    DumpProps(typeof(UndertaleRoom.Layer.LayerEffectData));
    DumpProps(typeof(UndertaleRoom.EffectProperty));
    DumpProps(typeof(UndertaleRoom.Background));
    DumpProps(typeof(UndertaleRoom.LayerType));
    DumpProps(typeof(UndertaleRoom.RoomEntryFlags));
    sb.AppendLine();

    var rooms = (IList)GO(Data, "Rooms");
    sb.AppendLine("== [1] Rooms=" + rooms.Count + " ==");

    // ===== [2] view/camera 普查 =====
    int roomsViewEnabled = 0, roomsWithViews = 0;
    var viewW = new Dictionary<string, int>();
    var viewObjId = new Dictionary<string, int>();
    var roomList = new List<string>();
    var layerList = new List<string>();
    int layerTotal = 0, layerGeoNonZero = 0, layerEffect = 0;
    var effTypeHist = new Dictionary<string, int>();
    var bgParallax = new Dictionary<string, int>();
    var flagHist = new Dictionary<string, int>();

    for (int i = 0; i < rooms.Count; i++)
    {
        UndertaleRoom r = (UndertaleRoom)rooms[i];
        string rname = r.Name == null ? null : r.Name.Content;

        // Flags
        string flags = GS(r, "Flags");
        if (flags == null) flags = "(null)";
        if (!flagHist.ContainsKey(flags)) flagHist[flags] = 0;
        flagHist[flags]++;
        if (flags.IndexOf("View", StringComparison.OrdinalIgnoreCase) >= 0) roomsViewEnabled++;

        // Views
        object viewsO = GO(r, "Views");
        int nv = (viewsO is IList) ? ((IList)viewsO).Count : -1;
        if (nv > 0) roomsWithViews++;

        var vlist = new List<string>();
        if (viewsO is IList && nv > 0)
        {
            IList vl = (IList)viewsO;
            for (int k = 0; k < vl.Count; k++)
            {
                object v = vl[k];
                string vw = GS(v, "ViewWidth");
                string vh = GS(v, "ViewHeight");
                string vx = GS(v, "ViewX");
                string vy = GS(v, "ViewY");
                string pw = GS(v, "PortWidth");
                string ph = GS(v, "PortHeight");
                string px = GS(v, "PortX");
                string py = GS(v, "PortY");
                string oid = ResName(GO(v, "ObjectId"));
                string key = vw + "x" + vh;
                if (!viewW.ContainsKey(key)) viewW[key] = 0;
                viewW[key]++;
                if (oid != null)
                {
                    if (!viewObjId.ContainsKey(oid)) viewObjId[oid] = 0;
                    viewObjId[oid]++;
                }
                vlist.Add("{\"vx\":" + (vx == null ? "null" : vx) + ",\"vy\":" + (vy == null ? "null" : vy)
                          + ",\"vw\":" + (vw == null ? "null" : vw) + ",\"vh\":" + (vh == null ? "null" : vh)
                          + ",\"px\":" + (px == null ? "null" : px) + ",\"py\":" + (py == null ? "null" : py)
                          + ",\"pw\":" + (pw == null ? "null" : pw) + ",\"ph\":" + (ph == null ? "null" : ph)
                          + ",\"obj\":" + JsonS(oid) + "}");
            }
        }

        // Layers
        var ll = new List<string>();
        if (r.Layers != null)
        {
            foreach (UndertaleRoom.Layer ly in r.Layers)
            {
                layerTotal++;
                string lt = ly.LayerType.ToString();
                string ln = GS(ly, "LayerName");
                string lname = ly.LayerName == null ? null : ly.LayerName.Content;
                string xs = Num(ly, "XOffset"), ys = Num(ly, "YOffset");
                string hs = Num(ly, "HSpeed"), vs = Num(ly, "VSpeed");
                bool nonzero = (xs != "0" || ys != "0" || hs != "0" || vs != "0");
                bool eff = false;
                string eo = GS(ly, "EffectEnabled");
                if (eo != null && eo.Equals("True", StringComparison.OrdinalIgnoreCase)) eff = true;
                if (nonzero) layerGeoNonZero++;
                if (eff)
                {
                    layerEffect++;
                    string et = ResName(GO(ly, "EffectType"));
                    if (et == null) et = GS(ly, "EffectType");
                    if (et == null) et = "(null)";
                    if (!effTypeHist.ContainsKey(et)) effTypeHist[et] = 0;
                    effTypeHist[et]++;
                }
                if (lt == "Background" && (hs != "0" || vs != "0"))
                {
                    string key = "h=" + hs + " v=" + vs;
                    if (!bgParallax.ContainsKey(key)) bgParallax[key] = 0;
                    bgParallax[key]++;
                }
                // 只记有意义的层（几何非零 / 有效果 / 是 Background 且带精灵）
                string bgSpr = null, bgTiled = null;
                object bd = GO(ly, "BackgroundData");
                if (bd != null) { bgSpr = ResName(GO(bd, "Sprite")); bgTiled = GS(bd, "Tiled"); }
                if (nonzero || eff || bgSpr != null)
                {
                    ll.Add("{\"name\":" + JsonS(lname) + ",\"type\":" + JsonS(lt)
                           + ",\"depth\":" + GS(ly, "LayerDepth")
                           + ",\"visible\":" + (GS(ly, "IsVisible") == "True" ? "true" : "false")
                           + ",\"x\":" + xs + ",\"y\":" + ys + ",\"hs\":" + hs + ",\"vs\":" + vs
                           + ",\"eff\":" + (eff ? "true" : "false")
                           + ",\"effType\":" + JsonS(ResName(GO(ly, "EffectType")))
                           + ",\"bgSpr\":" + JsonS(bgSpr) + ",\"bgTiled\":" + JsonS(bgTiled) + "}");
                }
            }
        }

        roomList.Add("{\"i\":" + i + ",\"name\":" + JsonS(rname)
                     + ",\"w\":" + GS(r, "Width") + ",\"h\":" + GS(r, "Height")
                     + ",\"flags\":" + JsonS(flags)
                     + ",\"nv\":" + nv
                     + ",\"views\":[" + String.Join(",", vlist.ToArray()) + "]"
                     + ",\"layers\":[" + String.Join(",", ll.ToArray()) + "]}");
    }

    sb.AppendLine("房间 Flags 分布: ");
    foreach (var kv in flagHist) sb.AppendLine("   " + kv.Key + " → " + kv.Value);
    sb.AppendLine("含 'View' 标志的房间 = " + roomsViewEnabled + " / " + rooms.Count);
    sb.AppendLine("Views 列表非空的房间 = " + roomsWithViews);
    sb.AppendLine("view 尺寸分布: ");
    foreach (var kv in viewW) sb.AppendLine("   " + kv.Key + " → " + kv.Value);
    sb.AppendLine("view.ObjectId 分布: ");
    foreach (var kv in viewObjId) sb.AppendLine("   " + kv.Key + " → " + kv.Value);
    sb.AppendLine();

    // ===== [3] 层几何 / 视差 / 效果 汇总 =====
    sb.AppendLine("== [2] 层几何 / 视差 / 效果 ==");
    sb.AppendLine("层总数 = " + layerTotal + " ；几何非零层 = " + layerGeoNonZero
                  + " ；启用效果的层 = " + layerEffect);
    sb.AppendLine("EffectType 分布: ");
    foreach (var kv in effTypeHist) sb.AppendLine("   " + kv.Key + " → " + kv.Value);
    sb.AppendLine("Background 层视差 (HSpeed/VSpeed 非零) 分布: ");
    foreach (var kv in bgParallax) sb.AppendLine("   " + kv.Key + " → " + kv.Value);
    sb.AppendLine();

    jb.Append("{\"n_rooms\": ").Append(rooms.Count).Append(",\n");
    jb.Append(" \"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append(" \"rooms\": [\n  ").Append(String.Join(",\n  ", roomList.ToArray())).Append("\n ]\n}\n");
    File.WriteAllText(outJson, jb.ToString().Replace(": True", ": true").Replace(": False", ": false"),
                      new UTF8Encoding(false));
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
