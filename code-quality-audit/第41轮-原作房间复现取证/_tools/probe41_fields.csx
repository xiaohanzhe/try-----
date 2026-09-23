using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第41轮 · 反射探针（v2：全反射，不硬编码任何集合名，避免编译期 CS1061）
// 产出 <data.win 同级>/probe41_fields.txt
EnsureDataLoaded();

string outPath = Path.Combine(Path.GetDirectoryName(FilePath), "probe41_fields.txt");
var sb = new StringBuilder();

string Short(object v)
{
    if (v == null) return "null";
    if (v is string) return "\"" + v + "\"";
    if (v is IEnumerable)
    {
        int c = 0;
        try { foreach (object _ in (IEnumerable)v) { c++; if (c > 99999) break; } }
        catch (Exception) { return "<enum?err>"; }
        return "<IEnumerable n=" + c + ">";
    }
    string s;
    try { s = v.ToString(); } catch (Exception) { return "<ToString?err>"; }
    return s.Length > 70 ? s.Substring(0, 70) + "…" : s;
}

string Props(object o, int max)
{
    if (o == null) return "(null)";
    Type t = o.GetType();
    var b = new StringBuilder(t.Name + " {");
    int n = 0;
    foreach (PropertyInfo p in t.GetProperties())
    {
        if (n++ >= max) { b.Append(" …"); break; }
        object v = null;
        try { v = p.GetValue(o); } catch (Exception) { v = "<err>"; }
        b.Append(" ").Append(p.Name).Append(":").Append(p.PropertyType.Name)
         .Append("=").Append(Short(v)).Append(";");
    }
    b.Append(" }");
    return b.ToString();
}

try
{
    // ---------- 0. Data 顶层集合（全反射） ----------
    var cols = new Dictionary<string, object>();
    sb.AppendLine("== [0] Data 集合 ==");
    foreach (PropertyInfo p in Data.GetType().GetProperties())
    {
        object v = null;
        try { v = p.GetValue(Data); } catch (Exception) { continue; }
        if (v == null) continue;
        if (v is IList)
        {
            cols[p.Name] = v;
            sb.AppendLine("  " + p.Name + " n=" + ((IList)v).Count);
        }
    }
    sb.AppendLine();

    IList rooms = cols.ContainsKey("Rooms") ? (IList)cols["Rooms"] : null;
    if (rooms == null) { sb.AppendLine("!! 没有 Rooms 集合"); }
    else
    {
        // ---------- 1. 挑样本房间 ----------
        int iTile = -1, iInst = -1, iBg = -1, iAsset = -1;
        for (int i = 0; i < rooms.Count; i++)
        {
            UndertaleRoom r = (UndertaleRoom)rooms[i];
            if (r.Layers == null) continue;
            foreach (UndertaleRoom.Layer ly in r.Layers)
            {
                string tn = ly.LayerType.ToString();
                if (iTile < 0 && tn == "Tiles") iTile = i;
                if (iInst < 0 && tn == "Instances") iInst = i;
                if (iBg < 0 && tn == "Background") iBg = i;
                if (iAsset < 0 && tn == "Assets") iAsset = i;
            }
        }
        sb.AppendLine("== [1] 样本房间: Tiles=" + iTile + " Instances=" + iInst
                      + " Background=" + iBg + " Assets=" + iAsset + " ==");
        sb.AppendLine();

        string DumpLayer(int ridx, string want)
        {
            if (ridx < 0) return "  (无 " + want + " 层样本)";
            UndertaleRoom r = (UndertaleRoom)rooms[ridx];
            var o = new StringBuilder();
            o.AppendLine("-- room[" + ridx + "] " + (r.Name == null ? "?" : r.Name.Content)
                         + " " + r.Width + "x" + r.Height + " , layer=" + want);
            foreach (UndertaleRoom.Layer ly in r.Layers)
            {
                if (ly.LayerType.ToString() != want) continue;
                o.AppendLine("   Layer : " + Props(ly, 40));
                foreach (string pn in new string[] { "TilesData", "InstancesData", "BackgroundData",
                                                     "AssetsData", "EffectData", "PathData" })
                {
                    PropertyInfo p = ly.GetType().GetProperty(pn);
                    if (p == null) { o.AppendLine("   (无属性 " + pn + ")"); continue; }
                    object inner = null;
                    try { inner = p.GetValue(ly); } catch (Exception) { inner = null; }
                    if (inner == null) { o.AppendLine("   ." + pn + " = null"); continue; }
                    o.AppendLine("   ." + pn + " : " + Props(inner, 30));
                    foreach (PropertyInfo q in inner.GetType().GetProperties())
                    {
                        object col = null;
                        try { col = q.GetValue(inner); } catch (Exception) { continue; }
                        if (!(col is IList)) continue;
                        IList li = (IList)col;
                        if (li.Count == 0) continue;
                        o.AppendLine("      ." + q.Name + " n=" + li.Count);
                        o.AppendLine("        first(" + li[0].GetType().Name + ") : " + Props(li[0], 50));
                        break;
                    }
                    break;
                }
                break;
            }
            return o.ToString();
        }

        sb.AppendLine("== [2] 层内部结构 ==");
        sb.Append(DumpLayer(iTile, "Tiles"));
        sb.AppendLine();
        sb.Append(DumpLayer(iInst, "Instances"));
        sb.AppendLine();
        sb.Append(DumpLayer(iBg, "Background"));
        sb.AppendLine();
        sb.Append(DumpLayer(iAsset, "Assets"));
        sb.AppendLine();

        // ---------- 3. Sprite / GameObject / Code ----------
        sb.AppendLine("== [3] Sprite / Object / Code ==");
        foreach (string key in new string[] { "Sprites", "GameObjects", "Objects", "Code", "Backgrounds", "Sequences" })
        {
            if (!cols.ContainsKey(key)) continue;
            IList li = (IList)cols[key];
            if (li.Count == 0) continue;
            sb.AppendLine("  ### " + key + " n=" + li.Count);
            sb.AppendLine("    [0] : " + Props(li[0], 30));
            foreach (PropertyInfo q in li[0].GetType().GetProperties())
            {
                object col = null;
                try { col = q.GetValue(li[0]); } catch (Exception) { continue; }
                if (!(col is IList)) continue;
                IList l2 = (IList)col;
                if (l2.Count == 0) continue;
                sb.AppendLine("      ." + q.Name + " n=" + l2.Count
                              + "  first=" + (l2[0] == null ? "null" : Props(l2[0], 18)));
            }
            sb.AppendLine();
        }

        // ---------- 3b. 含 fountain 的 Object ----------
        string objKey = cols.ContainsKey("GameObjects") ? "GameObjects"
                      : (cols.ContainsKey("Objects") ? "Objects" : null);
        if (objKey != null)
        {
            IList objs = (IList)cols[objKey];
            sb.AppendLine("== [3b] 含 fountain 的 " + objKey + " ==");
            int shown = 0;
            for (int i = 0; i < objs.Count && shown < 10; i++)
            {
                object go = objs[i];
                string nm = null;
                PropertyInfo np = go.GetType().GetProperty("Name");
                if (np != null)
                {
                    object nv = np.GetValue(go);
                    if (nv != null)
                    {
                        PropertyInfo cp = nv.GetType().GetProperty("Content");
                        if (cp != null) { object cv = cp.GetValue(nv); nm = cv == null ? null : cv.ToString(); }
                    }
                }
                if (nm == null || nm.IndexOf("fountain", StringComparison.OrdinalIgnoreCase) < 0) continue;
                sb.AppendLine("  " + nm + " : " + Props(go, 25));
                shown++;
            }
            sb.AppendLine();
        }

        // ---------- 4. 连接图原料 ----------
        sb.AppendLine("== [4] 连接图原料：Code 里搜 room_goto ==");
        if (cols.ContainsKey("Code"))
        {
            IList codes = (IList)cols["Code"];
            int nHi = 0, nOk = 0, total = 0;
            string sample = null;
            for (int i = 0; i < codes.Count; i++)
            {
                object cd = codes[i];
                string nm = null;
                PropertyInfo np = cd.GetType().GetProperty("Name");
                if (np != null) { object nv = np.GetValue(cd); if (nv != null) { PropertyInfo cp = nv.GetType().GetProperty("Content"); if (cp != null) { object cv = cp.GetValue(nv); nm = cv == null ? null : cv.ToString(); } } }
                string dis = null;
                foreach (MethodInfo m in cd.GetType().GetMethods())
                {
                    if (m.Name != "Disassemble") continue;
                    ParameterInfo[] ps = m.GetParameters();
                    object[] args = new object[ps.Length];
                    bool ok = true;
                    for (int k = 0; k < ps.Length; k++)
                    {
                        string tn2 = ps[k].ParameterType.Name;
                        if (tn2 == "UndertaleData") args[k] = Data;
                        else if (ps[k].ParameterType.IsGenericType) { ok = false; break; }
                        else if (ps[k].ParameterType.IsValueType) { ok = false; break; }
                        else args[k] = null;
                    }
                    if (!ok) continue;
                    try { dis = (string)m.Invoke(cd, args); } catch (Exception) { continue; }
                    if (dis != null) break;
                }
                if (dis == null) continue;
                nOk++;
                total += dis.Length;
                if (dis.IndexOf("room_goto", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    nHi++;
                    if (sample == null) sample = nm;
                }
            }
            sb.AppendLine("  Code n=" + codes.Count + "  反汇编成功=" + nOk
                          + "  合计字符=" + total);
            sb.AppendLine("  含 room_goto 的条目 = " + nHi + "  样例 = " + sample);
        }
        else sb.AppendLine("  (没有 Code 集合)");
    }
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outPath, sb.ToString(), new UTF8Encoding(false));
