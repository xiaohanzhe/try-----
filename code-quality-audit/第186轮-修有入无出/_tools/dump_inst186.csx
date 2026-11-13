using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第186轮取证 d：直接要 5 间房的**实例表**（object 名 + 坐标）。
// 为什么不用 115 轮的 rooms_map：那份 ch1 是修正前导的（已知问题），
// 而"房里到底有没有门"是本轮的判定前提，必须用一手数据。
EnsureDataLoaded();

string dir = @"__OUTDIR__";
var utf8 = new UTF8Encoding(false);

var want = new Dictionary<string, string>();
want.Add("room_cc_fountain", "ch1.card_castle.cc_fountain");
want.Add("room_alphysclass", "ch1.hometown.alphysclass");
want.Add("room_dark_chase2", "ch1.dark_world.dark_chase2");
want.Add("room_forest_maze_susie", "ch1.forest.forest_maze_susie");
want.Add("room_cc_prisonelevator", "ch1.card_castle.cc_prisonelevator");

var sb = new StringBuilder();
int nRoom = 0;

for (int i = 0; i < Data.Rooms.Count; i++)
{
    var r = Data.Rooms[i];
    if (r == null || r.Name == null) continue;
    string rn = r.Name.Content;
    if (!want.ContainsKey(rn)) continue;

    var rows = new List<string>();
    int nObj = 0;
    // ★ 第186轮修：UndertaleRoom 上**没有** `Instances`（`error CS1061`），
    //   权威属性名是 `GameObjects`（见 UndertaleModLib.xml：
    //   `P:UndertaleModLib.Models.UndertaleRoom.GameObjects` = "The list of game objects this room uses."），
    //   单项类型 `UndertaleRoom.GameObject` 的对象引用是 `ObjectDefinition` 而非 `Object`。
    if (r.GameObjects != null)
    {
        foreach (var inst in r.GameObjects)
        {
            if (inst == null) continue;
            string on = (inst.ObjectDefinition != null && inst.ObjectDefinition.Name != null)
                ? inst.ObjectDefinition.Name.Content : "?";
            bool pc = inst.PreCreateCode != null;
            rows.Add("    { \"obj\": " + JsonStr(on) + ", \"x\": " + inst.X + ", \"y\": " + inst.Y
                     + ", \"pc\": " + (pc ? "true" : "false") + " }");
            nObj++;
        }
    }

    if (nRoom > 0) sb.Append(",\n");
    sb.Append("  { \"room\": ").Append(JsonStr(rn));
    sb.Append(", \"scene\": ").Append(JsonStr(want[rn]));
    sb.Append(", \"index\": ").Append(i);
    sb.Append(", \"width\": ").Append(r.Width).Append(", \"height\": ").Append(r.Height);
    sb.Append(", \"n\": ").Append(nObj);
    // ★ 自证：若 n==0 而 n_layers>0，就说明这份 data.win 是 GMS2 分层结构、
    //   `GameObjects` 没被填（xml 原话："are empty and Layers are used instead"），
    //   那时 n=0 不能当成"房间里没有对象"。
    sb.Append(", \"n_layers\": ").Append(r.Layers == null ? -1 : r.Layers.Count);
    sb.Append(", \"instances\": [\n").Append(string.Join(",\n", rows.ToArray())).Append("\n  ]}");
    nRoom++;
    Console.WriteLine("  " + rn + " n=" + nObj);
    Console.Out.Flush();
}

File.WriteAllText(Path.Combine(dir, "rooms_inst186.json"),
    "{\n \"n_rooms\": " + nRoom + ",\n \"rooms\": [\n" + sb.ToString() + "\n ]\n}\n", utf8);

ScriptMessage("R186-INST rooms=" + nRoom);

string JsonStr(string s)
{
    if (s == null) return "null";
    var b = new StringBuilder("\"");
    foreach (char ch in s)
    {
        if (ch == '"') b.Append("\\\"");
        else if (ch == '\\') b.Append("\\\\");
        else if (ch == '\n') b.Append("\\n");
        else if (ch == '\r') b.Append("\\r");
        else if (ch == '\t') b.Append("\\t");
        else if (ch < 32) b.Append("\\u").Append(((int)ch).ToString("x4"));
        else b.Append(ch);
    }
    b.Append("\"");
    return b.ToString();
}
