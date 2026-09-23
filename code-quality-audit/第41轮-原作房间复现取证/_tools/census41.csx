using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第41轮 · 普查：房间层几何 / 瓦片与帧原料 / 房间连接图（room_goto）
// 产出 <data.win 同级>/census41.txt  与  room_edges41.json
EnsureDataLoaded();

string dir = Path.GetDirectoryName(FilePath);
string outTxt = Path.Combine(dir, "census41.txt");
string outJson = Path.Combine(dir, "room_edges41.json");
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

try
{
    // ===== 1. 房间 / 层 普查 =====
    var rooms = (IList)GO(Data, "Rooms");
    sb.AppendLine("== [1] 房间与层 ==");
    sb.AppendLine("Rooms=" + rooms.Count);
    var byType = new Dictionary<string, int>();
    var byDepthNonZero = new Dictionary<string, int>();
    int geoLayers = 0, layersTotal = 0;
    int roomsWithTiles = 0, roomsWithInst = 0, roomsWithAssets = 0, roomsWithBg = 0;
    long tileCellTotal = 0;
    var tilesetUse = new Dictionary<string, int>();
    for (int i = 0; i < rooms.Count; i++)
    {
        UndertaleRoom r = (UndertaleRoom)rooms[i];
        bool hT = false, hI = false, hA = false, hB = false;
        if (r.Layers != null)
            foreach (UndertaleRoom.Layer ly in r.Layers)
            {
                layersTotal++;
                string tn = ly.LayerType.ToString();
                if (!byType.ContainsKey(tn)) byType[tn] = 0;
                byType[tn]++;
                if (ly.XOffset != 0 || ly.YOffset != 0 || ly.HSpeed != 0 || ly.VSpeed != 0) geoLayers++;
                if (tn == "Tiles")
                {
                    hT = true;
                    if (ly.TilesData != null)
                    {
                        string ts = ResName(ly.TilesData.Background);
                        if (ts != null) { if (!tilesetUse.ContainsKey(ts)) tilesetUse[ts] = 0; tilesetUse[ts]++; }
                        tileCellTotal += (long)ly.TilesData.TilesX * ly.TilesData.TilesY;
                    }
                }
                if (tn == "Instances") hI = true;
                if (tn == "Assets") hA = true;
                if (tn == "Background") hB = true;
            }
        if (hT) roomsWithTiles++;
        if (hI) roomsWithInst++;
        if (hA) roomsWithAssets++;
        if (hB) roomsWithBg++;
    }
    sb.AppendLine("层总数=" + layersTotal + " ；几何非零(有视差/偏移)的层=" + geoLayers);
    sb.AppendLine("层 type 分布: ");
    foreach (var kv in byType) sb.AppendLine("   " + kv.Key + " = " + kv.Value);
    sb.AppendLine("有 Tiles 层的房间=" + roomsWithTiles + " ；有 Instances 层=" + roomsWithInst
                  + " ；有 Assets 层=" + roomsWithAssets + " ；有 Background 层=" + roomsWithBg);
    sb.AppendLine("瓦片格总量(TilesX*TilesY 求和)=" + tileCellTotal);
    sb.AppendLine("用到的 tileset 数=" + tilesetUse.Count);
    int k2 = 0;
    foreach (var kv in tilesetUse) { sb.AppendLine("   " + kv.Key + " 用于 " + kv.Value + " 层"); if (++k2 > 25) { sb.AppendLine("   …"); break; } }
    sb.AppendLine();

    // ===== 2. Sprite 帧 / tileset 动画 =====
    sb.AppendLine("== [2] Sprite 帧 与 tileset 动画 ==");
    var sprites = (IList)GO(Data, "Sprites");
    int multi = 0, totalFrames = 0, animated = 0;
    var frameHist = new Dictionary<int, int>();
    for (int i = 0; i < sprites.Count; i++)
    {
        object sp = sprites[i];
        object tex = GO(sp, "Textures");
        int n = 0;
        if (tex is IList) n = ((IList)tex).Count;
        totalFrames += n;
        if (n > 1) multi++;
        if (!frameHist.ContainsKey(n)) frameHist[n] = 0;
        frameHist[n]++;
        string st = GS(sp, "GMS2PlaybackSpeedType");
        if (n > 1 || (st != null && st != "FramesPerGameFrame")) animated++;
    }
    sb.AppendLine("Sprites=" + sprites.Count + " ；总帧数=" + totalFrames + " ；多帧 sprite=" + multi);
    sb.AppendLine("帧数分布(Top12): ");
    int k3 = 0;
    var sorted = new List<KeyValuePair<int, int>>(frameHist);
    sorted.Sort(delegate (KeyValuePair<int, int> a, KeyValuePair<int, int> b) { return b.Value.CompareTo(a.Value); });
    foreach (var kv in sorted) { sb.AppendLine("   frames=" + kv.Key + " → " + kv.Value + " 个精灵"); if (++k3 > 11) break; }
    sb.AppendLine();

    var bgs = (IList)GO(Data, "Backgrounds");
    sb.AppendLine("Backgrounds(tilesets)=" + bgs.Count);
    int animTs = 0;
    for (int i = 0; i < bgs.Count; i++)
    {
        object bg = bgs[i];
        object ids = GO(bg, "GMS2TileIds");
        int n = (ids is IList) ? ((IList)ids).Count : 0;
        if (n > 1) animTs++;
    }
    sb.AppendLine("  含多帧 GMS2TileIds 的 tileset = " + animTs + "（瓦片动画来源）");
    // 打印一个含多帧的 tileset
    for (int i = 0; i < bgs.Count; i++)
    {
        object bg = bgs[i];
        object ids = GO(bg, "GMS2TileIds");
        int n = (ids is IList) ? ((IList)ids).Count : 0;
        if (n > 1)
        {
            sb.AppendLine("  样例: " + ResName(bg) + "  tileW=" + GS(bg, "GMS2TileWidth")
                          + " tileH=" + GS(bg, "GMS2TileHeight")
                          + " cols=" + GS(bg, "GMS2TileColumns")
                          + " count=" + GS(bg, "GMS2TileCount")
                          + " frameLen=" + GS(bg, "GMS2FrameLength")
                          + " frames=" + n);
            break;
        }
    }
    sb.AppendLine();

    // ===== 3. 连接图：Code 里找 room_goto =====
    sb.AppendLine("== [3] 连接图（room_goto）==");
    var codes = (IList)GO(Data, "Code");
    var funcNames = new Dictionary<string, int>();
    int nInstr = 0;
    for (int i = 0; i < codes.Count; i++)
    {
        object cd = codes[i];
        object instrs = GO(cd, "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        for (int k = 0; k < li.Count; k++)
        {
            nInstr++;
            object ins = li[k];
            object fn = GO(ins, "ValueFunction");
            string fnn = ResName(fn);
            if (fnn == null) continue;
            if (fnn.IndexOf("room", StringComparison.OrdinalIgnoreCase) < 0) continue;
            if (!funcNames.ContainsKey(fnn)) funcNames[fnn] = 0;
            funcNames[fnn]++;
        }
    }
    sb.AppendLine("Code=" + codes.Count + " ；指令总数=" + nInstr);
    sb.AppendLine("ValueFunction 名含 'room' 的函数（出现次数）: ");
    int k4 = 0;
    foreach (var kv in funcNames) { sb.AppendLine("   " + kv.Key + " x" + kv.Value); if (++k4 > 40) { sb.AppendLine("   …"); break; } }
    sb.AppendLine();

    // 3b. 打印前 6 个含 room_goto 的 Code 的指令序列（确认提取规则）
    sb.AppendLine("== [3b] 含 room_goto 的 Code 指令序列（前 6 个，各最多 26 条）==");
    int shown = 0;
    for (int i = 0; i < codes.Count && shown < 6; i++)
    {
        object cd = codes[i];
        object instrs = GO(cd, "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        bool has = false;
        for (int k = 0; k < li.Count; k++)
        {
            string fnn = ResName(GO(li[k], "ValueFunction"));
            if (fnn != null && fnn.IndexOf("room_goto", StringComparison.OrdinalIgnoreCase) >= 0) { has = true; break; }
        }
        if (!has) continue;
        shown++;
        sb.AppendLine("-- " + ResName(cd) + "  (instr n=" + li.Count + ")");
        int m = 0;
        for (int k = 0; k < li.Count && m < 26; k++)
        {
            object ins = li[k];
            string fn2 = ResName(GO(ins, "ValueFunction"));
            string vn = ResName(GO(ins, "ValueVariable"));
            sb.AppendLine("     [" + k + "] " + GS(ins, "Kind")
                          + " T1=" + GS(ins, "Type1") + " T2=" + GS(ins, "Type2")
                          + " I=" + GS(ins, "ValueInt") + " S=" + GS(ins, "ValueShort")
                          + " L=" + GS(ins, "ValueLong") + " D=" + GS(ins, "ValueDouble")
                          + " fn=" + fn2 + " var=" + vn
                          + " refType=" + GS(ins, "ReferenceType"));
            m++;
        }
    }
    sb.AppendLine();

    // ===== 4. 尽力提取边（启发式：Push 常量 + room_goto 调用） =====
    var edges = new List<string>();
    var nextIds = new List<int>();
    int skipVar = 0;
    for (int i = 0; i < codes.Count; i++)
    {
        object cd = codes[i];
        object instrs = GO(cd, "Instructions");
        if (!(instrs is IList)) continue;
        IList li = (IList)instrs;
        string src = ResName(cd);
        int lastInt = -1; bool lastOk = false;
        for (int k = 0; k < li.Count; k++)
        {
            object ins = li[k];
            string kind = GS(ins, "Kind");
            if (kind == "Push" || kind == "Push.I" || kind == "Push.S" || kind == "Push.L" || kind == "Push.D")
            {
                lastInt = -1; lastOk = false;
                string i1 = GS(ins, "ValueInt");
                int v;
                if (i1 != null && Int32.TryParse(i1, out v)) { lastInt = v; lastOk = true; }
            }
            string fn = ResName(GO(ins, "ValueFunction"));
            if (fn == null) continue;
            if (fn.IndexOf("room_goto_next", StringComparison.OrdinalIgnoreCase) == 0) { nextIds.Add(i); }
            else if (fn.IndexOf("room_goto", StringComparison.OrdinalIgnoreCase) == 0)
            {
                string target = null;
                if (lastOk && lastInt >= 0 && lastInt < rooms.Count)
                    target = ((UndertaleRoom)rooms[lastInt]).Name == null ? null : ((UndertaleRoom)rooms[lastInt]).Name.Content;
                if (target == null) { skipVar++; target = "?" + (lastOk ? lastInt.ToString() : "var"); }
                edges.Add("{\"from_code\": " + JsonS(src) + ", \"to_room\": " + JsonS(target)
                          + ", \"to_index\": " + (lastOk ? lastInt.ToString() : "-1") + "}");
            }
        }
    }
    sb.AppendLine("== [4] 启发式提取 ==");
    sb.AppendLine("room_goto(常量) 边 = " + edges.Count + " ；其中目标非字面量(跳过) = " + skipVar);
    sb.AppendLine("room_goto_next() 出现 = " + nextIds.Count);

    jb.Append("{\"source\": ").Append(JsonS(FilePath)).Append(",\n");
    jb.Append(" \"n_edges\": ").Append(edges.Count).Append(",\n");
    jb.Append(" \"edges\": [\n  ").Append(String.Join(",\n  ", edges.ToArray())).Append("\n ]\n}\n");
    File.WriteAllText(outJson, jb.ToString(), new UTF8Encoding(false));
}
catch (Exception ex)
{
    sb.AppendLine("!! EXCEPTION: " + ex.ToString());
}

File.WriteAllText(outTxt, sb.ToString(), new UTF8Encoding(false));
