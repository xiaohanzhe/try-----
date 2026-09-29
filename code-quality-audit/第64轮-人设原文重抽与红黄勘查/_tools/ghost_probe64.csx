using System;
using System.IO;
using System.Text;
using System.Collections;
using System.Reflection;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

// 第64轮探针：为「Chara -> 红与黄.apk 里的幽灵」定位素材。
// 产出 3 个文件（写到 datafile 同级目录）：
//   r64_names.json   —— 全资源名清单（rooms/sprites/objects/bg/sounds/fonts/code）
//   r64_hits.json    —— 关键词命中（按资源类型分组）
//   r64_strhits.json —— Data.Strings 里关键词命中（带下标）

EnsureDataLoaded();
string dir = Path.GetDirectoryName(FilePath);
var utf8 = new UTF8Encoding(false);

string[] KW = new string[] {
    "ghost", "chara", "determin", "spirit", "phantom", "apparition",
    "soul", "napsta", "blooky", "monster_kid", "mk",
    "幽灵", "幽霊", "亡灵", "亡霊", "决心", "決意", "灵魂", "魂", "鬼"
};

var allNames = new List<string>();          // "type\tname"
var hits = new List<string>();              // "type\tname"
var strHits = new List<string>();           // "idx\ttext"  (text 前 200 字)

void AddRes(string type, string name)
{
    if (name == null) name = "";
    allNames.Add(type + "\t" + name);
    string low = name.ToLowerInvariant();
    foreach (string k in KW)
    {
        if (low.Contains(k.ToLowerInvariant())) { hits.Add(type + "\t" + name + "\t<=" + k); break; }
    }
}

for (int i = 0; i < Data.Rooms.Count; i++)
{
    var r = Data.Rooms[i];
    AddRes("room", r.Name == null ? "" : r.Name.Content);
}
for (int i = 0; i < Data.Sprites.Count; i++)
{
    var s = Data.Sprites[i];
    AddRes("sprite", s.Name == null ? "" : s.Name.Content);
}
for (int i = 0; i < Data.GameObjects.Count; i++)
{
    var o = Data.GameObjects[i];
    string nm = (o.Name == null) ? "" : o.Name.Content;
    string sp = (o.Sprite != null && o.Sprite.Name != null) ? o.Sprite.Name.Content : "";
    AddRes("object", nm + "  [sprite=" + sp + "]");
}
for (int i = 0; i < Data.Backgrounds.Count; i++)
{
    var b = Data.Backgrounds[i];
    AddRes("background", b.Name == null ? "" : b.Name.Content);
}
for (int i = 0; i < Data.Sounds.Count; i++)
{
    var s = Data.Sounds[i];
    AddRes("sound", s.Name == null ? "" : s.Name.Content);
}
for (int i = 0; i < Data.Fonts.Count; i++)
{
    var f = Data.Fonts[i];
    AddRes("font", f.Name == null ? "" : f.Name.Content);
}
for (int i = 0; i < Data.Code.Count; i++)
{
    var c = Data.Code[i];
    string nm = (c.Name == null) ? "" : c.Name.Content;
    // code 只做命中收集，不进 allNames（太长）
    if (nm != null)
    {
        string low = nm.ToLowerInvariant();
        foreach (string k in KW)
        {
            if (low.Contains(k.ToLowerInvariant())) { hits.Add("code\t" + nm + "\t<=" + k); break; }
        }
    }
}

for (int i = 0; i < Data.Strings.Count; i++)
{
    string t = Data.Strings[i].Content;
    if (t == null) continue;
    string low = t.ToLowerInvariant();
    foreach (string k in KW)
    {
        if (low.Contains(k.ToLowerInvariant()))
        {
            string cut = t.Length > 200 ? t.Substring(0, 200) : t;
            strHits.Add(i + "\t" + k + "\t" + cut);
            break;
        }
    }
}

// --- 写 names ---
var sbN = new StringBuilder();
sbN.Append("{\n  \"counts\": {");
sbN.Append("\"rooms\":").Append(Data.Rooms.Count);
sbN.Append(",\"sprites\":").Append(Data.Sprites.Count);
sbN.Append(",\"objects\":").Append(Data.GameObjects.Count);
sbN.Append(",\"backgrounds\":").Append(Data.Backgrounds.Count);
sbN.Append(",\"sounds\":").Append(Data.Sounds.Count);
sbN.Append(",\"fonts\":").Append(Data.Fonts.Count);
sbN.Append(",\"strings\":").Append(Data.Strings.Count);
sbN.Append(",\"code\":").Append(Data.Code.Count);
sbN.Append("},\n  \"names\": [");
for (int i = 0; i < allNames.Count; i++)
{
    if (i > 0) sbN.Append(",");
    sbN.Append("\n    ").Append(JsonStr(allNames[i]));
}
sbN.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "r64_names.json"), sbN.ToString(), utf8);

var sbH = new StringBuilder();
sbH.Append("{\n  \"hits\": [");
for (int i = 0; i < hits.Count; i++)
{
    if (i > 0) sbH.Append(",");
    sbH.Append("\n    ").Append(JsonStr(hits[i]));
}
sbH.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "r64_hits.json"), sbH.ToString(), utf8);

var sbS = new StringBuilder();
sbS.Append("{\n  \"strhits\": [");
for (int i = 0; i < strHits.Count; i++)
{
    if (i > 0) sbS.Append(",");
    sbS.Append("\n    ").Append(JsonStr(strHits[i]));
}
sbS.Append("\n  ]\n}\n");
File.WriteAllText(Path.Combine(dir, "r64_strhits.json"), sbS.ToString(), utf8);

ScriptMessage("R64PROBE-OK names=" + allNames.Count + " hits=" + hits.Count + " strhits=" + strHits.Count);

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
