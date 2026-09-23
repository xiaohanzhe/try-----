using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第42轮 · [A] 门/传送/入口类对象定义  [B] ch1 现实世界房间实例坐标表  [C] 门对象 code 指令流
// 产出 <data.win 同级>/probe42.json  与  probe42_codes.txt
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outJson = Path.Combine(dir, "probe42.json");
string outTxt = Path.Combine(dir, "probe42_codes.txt");

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
    if (cv != null) return cv.ToString();
    return nv.ToString();
}

string Num(object v)
{
    if (v == null) return "null";
    string s = v.ToString();
    if (s == "NaN" || s == "Infinity" || s == "-Infinity") return "null";
    return s;
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

try
{
    var jb = new StringBuilder();
    jb.Append("{\n\"source\": ").Append(JsonS(FilePath)).Append(",\n");

    // ================= [A] 门/传送/入口类对象定义 =================
    var gos = (IList)GO(Data, "GameObjects");
    var objRows = new List<string>();
    int nObj = 0;
    string[] keysA = new string[] { "door", "gate", "warp", "entrance", "portal",
                                    "fountain", "closet", "darkfount", "savepoint",
                                    "elevator", "stairs" };
    for (int i = 0; i < gos.Count && i < 20000; i++)
    {
        object o = gos[i];
        string nm = ResName(o);
        if (String.IsNullOrEmpty(nm)) continue;
        string low = nm.ToLowerInvariant();
        bool hitA = false;
        for (int k = 0; k < keysA.Length; k++) { if (low.Contains(keysA[k])) { hitA = true; break; } }
        if (!hitA) continue;
        nObj++;
        object spr = GO(o, "Sprite");
        string sprN = (spr == null) ? null : ResName(spr);
        var evNames = new List<string>();
        object evs = GO(o, "Events");
        IEnumerable evEn = evs as IEnumerable;
        if (evEn != null)
        {
            foreach (object ev in evEn)
            {
                string et = GS(ev, "EventType");
                string es = GS(ev, "EventSubtype");
                if (et == null) et = "?";
                evNames.Add(et + (es == null || es == "0" ? "" : (":" + es)));
                if (evNames.Count > 24) break;
            }
        }
        var eb = new StringBuilder("[");
        for (int k = 0; k < evNames.Count; k++) { if (k > 0) eb.Append(", "); eb.Append(JsonS(evNames[k])); }
        eb.Append("]");
        objRows.Add("  {\"name\": " + JsonS(nm)
            + ", \"sprite\": " + JsonS(sprN)
            + ", \"depth\": " + Num(GO(o, "Depth"))
            + ", \"visible\": " + GS(o, "Visible")
            + ", \"solid\": " + GS(o, "Solid")
            + ", \"parent\": " + JsonS(ResName(GO(o, "ParentId")))
            + ", \"events\": " + eb.ToString() + "}");
    }
    jb.Append("\"n_objects\": ").Append(nObj).Append(",\n\"objects\": [\n")
      .Append(String.Join(",\n", objRows)).Append("\n],\n");

    // ================= [B] ch1 现实世界房间实例坐标表 =================
    var rooms = (IList)GO(Data, "Rooms");
    var roomRows = new List<string>();
    var instCounter = new Dictionary<string, int>();
    int nRooms = 0, nInst = 0;
    for (int ri = 2; ri <= 33 && ri < rooms.Count; ri++)
    {
        object r = rooms[ri];
        string rn = ResName(r);
        var insts = new List<string>();
        object layers = GO(r, "Layers");
        IEnumerable lyEn = layers as IEnumerable;
        if (lyEn != null)
        {
            foreach (object ly in lyEn)
            {
                string lname = ResName(GO(ly, "LayerName"));
                string ltype = GS(ly, "LayerType");
                string ldepth = GS(ly, "LayerDepth");
                object id = GO(ly, "InstancesData");
                if (id == null) continue;
                IEnumerable insEn = GO(id, "Instances") as IEnumerable;
                if (insEn == null) continue;
                foreach (object inst in insEn)
                {
                    string on = ResName(GO(inst, "ObjectDefinition"));
                    if (on == null) on = "?";
                    instCounter[on] = (instCounter.ContainsKey(on) ? instCounter[on] : 0) + 1;
                    nInst++;
                    insts.Add("    {\"obj\": " + JsonS(on)
                        + ", \"x\": " + Num(GO(inst, "X"))
                        + ", \"y\": " + Num(GO(inst, "Y"))
                        + ", \"layer\": " + JsonS(lname)
                        + ", \"depth\": " + (ldepth == null ? "null" : ldepth)
                        + ", \"scx\": " + Num(GO(inst, "ScaleX"))
                        + ", \"scy\": " + Num(GO(inst, "ScaleY"))
                        + ", \"rot\": " + Num(GO(inst, "Rotation"))
                        + "}");
                }
            }
        }
        nRooms++;
        roomRows.Add("  {\"index\": " + ri + ", \"name\": " + JsonS(rn)
            + ", \"w\": " + Num(GO(r, "Width")) + ", \"h\": " + Num(GO(r, "Height"))
            + ", \"n_inst\": " + insts.Count + ",\n   \"instances\": [\n"
            + String.Join(",\n", insts) + "\n   ]}");
    }
    jb.Append("\"n_rooms\": ").Append(nRooms).Append(",\n\"n_inst\": ").Append(nInst).Append(",\n");
    jb.Append("\"rooms\": [\n").Append(String.Join(",\n", roomRows)).Append("\n],\n");

    var cntRows = new List<string>();
    foreach (KeyValuePair<string, int> kv in instCounter)
        cntRows.Add("  {" + JsonS(kv.Key) + ": " + kv.Value + "}");
    jb.Append("\"inst_counter\": [\n").Append(String.Join(",\n", cntRows)).Append("\n]\n}\n");

    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));

    // ================= [C] 门对象 code 指令流 =================
    var codes = (IList)GO(Data, "Code");
    var tw = new StringBuilder();
    string[] keysC = new string[] { "obj_doorX", "obj_doorAny", "obj_doorA", "obj_doorB",
                                    "obj_doorC", "obj_doorD", "obj_doorW", "obj_carcutscene",
                                    "obj_krisroom", "DEVICE_CONTACT", "obj_insideclosetcutscene",
                                    "obj_darkdoor", "obj_schoollobbycutscene", "obj_darkcontroller",
                                    "obj_darkfountain" };
    int nCode = 0, nInsTotal = 0;
    for (int ci = 0; ci < codes.Count && ci < 40000; ci++)
    {
        object c = codes[ci];
        string cn = ResName(c);
        if (String.IsNullOrEmpty(cn)) continue;
        if (!cn.StartsWith("gml_")) continue;
        bool hitC = false;
        for (int k = 0; k < keysC.Length; k++) { if (cn.IndexOf(keysC[k]) >= 0) { hitC = true; break; } }
        if (!hitC) continue;
        object ins = GO(c, "Instructions");
        IEnumerable insEn = ins as IEnumerable;
        if (insEn == null) continue;
        var list = new List<object>();
        foreach (object x in insEn) list.Add(x);
        if (list.Count == 0) continue;
        nCode++;
        tw.AppendLine("### " + cn + "   ins=" + list.Count);
        for (int k = 0; k < list.Count; k++)
        {
            object in1 = list[k];
            string kind = GS(in1, "Kind");
            string t1 = GS(in1, "Type1");
            string t2 = GS(in1, "Type2");
            string fn = ResName(GO(in1, "ValueFunction"));
            string vv = ResName(GO(in1, "ValueVariable"));
            string vs = GS(in1, "ValueString");
            string extra = "";
            if (kind != null && kind.StartsWith("Push"))
            {
                if (t1 == "Int16") extra = GS(in1, "ValueShort");
                else if (t1 == "Int32") extra = GS(in1, "ValueInt");
                else if (t1 == "Int64") extra = GS(in1, "ValueLong");
                else if (t1 == "Double") extra = GS(in1, "ValueDouble");
            }
            if (fn != null) extra = "FN=" + fn;
            if (vv != null) extra = "VAR=" + vv;
            if (vs != null) extra = "STR=" + vs;
            tw.AppendLine(String.Format("   {0,4}  {1,-14} {2,-9} {3,-9} {4}",
                k, kind, t1, t2, extra));
            nInsTotal++;
        }
        tw.AppendLine("");
    }
    tw.Insert(0, "codes matched=" + nCode + "  ins_total=" + nInsTotal + "\n\n");
    File.WriteAllText(outTxt, tw.ToString(), new UTF8Encoding(false));

    Console.WriteLine("probe42 OK  objects=" + nObj + "  rooms=" + nRooms + "  inst=" + nInst
        + "  codes=" + nCode + "  ins=" + nInsTotal);
}
catch (Exception ex)
{
    Console.WriteLine("probe42 FAILED: " + ex.GetType().Name + ": " + ex.Message);
    Console.WriteLine(ex.StackTrace);
}
