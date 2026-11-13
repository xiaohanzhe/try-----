using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第186轮取证 e：**全 147 间房**的实例表（obj 名 + 坐标 + 是否有 PreCreate）。
// 为什么全导：`rooms_map.json`（115 轮）ch1 是修正前导的，而"房里有没有门/有没有
// 负责换房的对象"是本轮全部判定的前提；一次导全，后面不再反复问 UTMT。
EnsureDataLoaded();

string dir = @"__OUTDIR__";
var utf8 = new UTF8Encoding(false);

var sb = new StringBuilder();
int nRoom = 0;

for (int i = 0; i < Data.Rooms.Count; i++)
{
    var r = Data.Rooms[i];
    if (r == null || r.Name == null) continue;
    string rn = r.Name.Content;

    var rows = new List<string>();
    int nObj = 0;
    // ★ UndertaleRoom 没有 `Instances`（error CS1061），权威属性是 `GameObjects`；
    //   单项 `UndertaleRoom.GameObject` 的对象引用是 `ObjectDefinition`。
    if (r.GameObjects != null)
    {
        foreach (var inst in r.GameObjects)
        {
            if (inst == null) continue;
            string on = (inst.ObjectDefinition != null && inst.ObjectDefinition.Name != null)
                ? inst.ObjectDefinition.Name.Content : "?";
            bool pc = inst.PreCreateCode != null;
            rows.Add("   [" + JsonStr(on) + "," + inst.X + "," + inst.Y + "," + (pc ? 1 : 0) + "]");
            nObj++;
        }
    }

    if (nRoom > 0) sb.Append(",\n");
    sb.Append(" {\"room\":").Append(JsonStr(rn));
    sb.Append(",\"index\":").Append(i);
    sb.Append(",\"w\":").Append(r.Width).Append(",\"h\":").Append(r.Height);
    sb.Append(",\"n_layers\":").Append(r.Layers == null ? -1 : r.Layers.Count);
    sb.Append(",\"n\":").Append(nObj);
    sb.Append(",\"inst\":[\n").Append(string.Join(",\n", rows.ToArray())).Append("\n ]}");
    nRoom++;
}
Console.WriteLine("  rooms=" + nRoom);
Console.Out.Flush();

File.WriteAllText(Path.Combine(dir, "all_rooms186.json"),
    "{\n\"n_rooms\":" + nRoom + ",\n\"rooms\":[\n" + sb.ToString() + "\n]\n}\n", utf8);

ScriptMessage("R186-ALLROOMS rooms=" + nRoom);

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
