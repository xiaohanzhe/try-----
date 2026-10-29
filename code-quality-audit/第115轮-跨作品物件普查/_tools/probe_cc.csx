// probe_cc.csx —— 探测「实例创建代码（CreationCode）」是否可取
// 只统计，不导出内容：每间房里有多少实例带创建代码、其中 door 类的有多少、
// 以及（关键）创建代码里的指令是否含「Push 常量 + Pop 变量」这种 `target = N` 形态。
// 输出 probe_cc.txt（UTF-8 无 BOM）
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
string outTxt = Path.Combine(dir, "probe_cc.txt");
var so = new StringBuilder();

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

try
{
    var rooms = (IList)GO(Data, "Rooms");
    int nInst = 0, nWithCC = 0, nDoor = 0, nDoorWithCC = 0;
    int nCCConst = 0, nCCVar = 0;
    var samples = new List<string>();

    for (int ri = 0; ri < rooms.Count && ri < 400; ri++)
    {
        object room = rooms[ri];
        string rname = ResName(room);
        IEnumerable gosEn = GO(room, "GameObjects") as IEnumerable;
        if (gosEn == null) continue;
        foreach (object inst in gosEn)
        {
            nInst++;
            object odef = GO(inst, "ObjectDefinition");
            string on = ResName(odef);
            bool isDoor = on != null && on.IndexOf("door", StringComparison.OrdinalIgnoreCase) >= 0;
            if (isDoor) nDoor++;

            object cc = GO(inst, "CreationCode");
            if (cc == null) continue;
            nWithCC++;
            if (isDoor) nDoorWithCC++;

            // 看创建代码里有没有 Push 常量 / Pop 变量
            IEnumerable insEn = GO(cc, "Instructions") as IEnumerable;
            if (insEn == null) continue;
            var toks = new List<string>();
            foreach (object x in insEn)
            {
                string kind = GO(x, "Kind") == null ? null : GO(x, "Kind").ToString();
                if (kind == null) continue;
                if (kind.StartsWith("Push"))
                {
                    string vv = ResName(GO(x, "ValueVariable"));
                    string fn = ResName(GO(x, "ValueFunction"));
                    string sh = GO(x, "ValueShort") == null ? null : GO(x, "ValueShort").ToString();
                    string iv = GO(x, "ValueInt") == null ? null : GO(x, "ValueInt").ToString();
                    if (vv != null) { toks.Add("V:" + vv); nCCVar++; }
                    else if (fn != null) toks.Add("F:" + fn);
                    else if (iv != null) { toks.Add("I:" + iv); nCCConst++; }
                    else if (sh != null) { toks.Add("S:" + sh); nCCConst++; }
                }
                if (toks.Count > 12) break;
            }
            if (isDoor && samples.Count < 25 && toks.Count > 0)
                samples.Add(rname + " / " + on + "  创建代码: " + String.Join(" ", toks.ToArray()));
        }
    }

    so.AppendLine("rooms_total = " + rooms.Count);
    so.AppendLine("instances_scanned = " + nInst);
    so.AppendLine("instances_with_creationcode = " + nWithCC);
    so.AppendLine("doorish_instances = " + nDoor);
    so.AppendLine("doorish_with_creationcode = " + nDoorWithCC);
    so.AppendLine("cc_push_const = " + nCCConst);
    so.AppendLine("cc_push_var = " + nCCVar);
    so.AppendLine();
    so.AppendLine("== 样例（door 实例的创建代码指令前 12 个）==");
    foreach (string s in samples) so.AppendLine(s);

    File.WriteAllText(outTxt, so.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_cc OK inst=" + nInst + " withCC=" + nWithCC
        + " door=" + nDoor + " doorCC=" + nDoorWithCC);
}
catch (Exception ex)
{
    File.WriteAllText(outTxt, "FAILED: " + ex.ToString(), new UTF8Encoding(false));
    Console.WriteLine("probe_cc FAILED: " + ex.Message);
}
