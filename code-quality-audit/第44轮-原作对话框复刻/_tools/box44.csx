// box44.csx —— 第44轮 侦测：原作对话框（textbox）相关 Sprite / Font / Object / Code
// 判据锚点（3 个已知真值，全命中才允许采信本脚本输出）：
//   A1 spr_pixel_white 必须存在（第43轮淡入淡出用它）
//   A2 字体总数必须 > 0
//   A3 obj_writer 必须存在（第43轮 obj_dialogueobj 里出现过的打字机对象）

using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using UndertaleModLib;
using UndertaleModLib.Models;

Func<object, string, object> GO = (o, p) => {
    if (o == null) return null;
    var pi = o.GetType().GetProperty(p);
    return pi == null ? null : pi.GetValue(o);
};
Func<object, string> S = (o) => {
    if (o == null) return null;
    if (o is UndertaleString us) return us.Content;
    return o.ToString();
};
Func<object, string> ResName = (o) => S(GO(o, "Name"));

string OUT = Path.Combine(Path.GetDirectoryName(FilePath), "box44.txt");
var sb = new StringBuilder();

string[] KW = new string[] { "textbox", "text_box", "box", "border", "dialog", "window",
                             "bubble", "frame", "panel", "text", "msg", "speech" };

// ---------- 锚点 ----------
var sprites = (IList)GO(Data, "Sprites");
string a1 = null, a3 = null;
foreach (var s in sprites) { if (ResName(s) == "spr_pixel_white") { a1 = "spr_pixel_white@idx"; break; } }
var objs = (IList)GO(Data, "GameObjects");
foreach (var o in objs) { if (ResName(o) == "obj_writer") { a3 = "obj_writer"; break; } }
var fonts = (IList)GO(Data, "Fonts");
sb.AppendLine("=== 锚点 ===");
sb.AppendLine("A1 spr_pixel_white = " + (a1 != null));
sb.AppendLine("A2 Fonts.Count = " + fonts.Count);
sb.AppendLine("A3 obj_writer = " + (a3 != null));

// ---------- [A] Sprite ----------
sb.AppendLine();
sb.AppendLine("=== [A] Sprite（总 " + sprites.Count + "）命中关键词 ===");
foreach (var s in sprites) {
    string n = ResName(s);
    if (n == null) continue;
    string ln = n.ToLower();
    bool hit = false; foreach (var k in KW) if (ln.Contains(k)) { hit = true; break; }
    if (!hit) continue;
    var tex = (IList)GO(s, "Textures");
    string dim = "";
    try {
        if (tex != null && tex.Count > 0) {
            var t0 = tex[0];
            dim = " w=" + S(GO(t0, "Width")) + " h=" + S(GO(t0, "Height"))
                + " sprW=" + S(GO(t0, "TargetX")) // 占位，后面用 sprite 自身字段
                + " tex=" + ResName(GO(t0, "Texture"));
        }
    } catch (Exception e) { dim = " ERR " + e.Message; }
    sb.AppendLine(n + "  frames=" + (tex == null ? -1 : tex.Count)
                  + "  L=" + S(GO(s, "Width")) + " R=" + S(GO(s, "Height"))
                  + " ox=" + S(GO(s, "OriginX")) + " oy=" + S(GO(s, "OriginY")) + dim);
}

// ---------- [B] Font ----------
sb.AppendLine();
sb.AppendLine("=== [B] Font（总 " + fonts.Count + "）===");
foreach (var f in fonts) {
    sb.AppendLine("font: " + ResName(f)
                  + "  display=" + S(GO(f, "DisplayName"))
                  + "  em=" + S(GO(f, "EmSize"))
                  + "  bold=" + S(GO(f, "Bold"))
                  + "  range=" + S(GO(f, "RangeStart")) + ".." + S(GO(f, "RangeEnd"))
                  + "  glyphs=" + ((IList)GO(f, "Glyphs") == null ? -1 : ((IList)GO(f, "Glyphs")).Count));
}

// ---------- [C] Object ----------
sb.AppendLine();
sb.AppendLine("=== [C] Object（总 " + objs.Count + "）命中关键词 ===");
foreach (var o in objs) {
    string n = ResName(o);
    if (n == null) continue;
    string ln = n.ToLower();
    bool hit = false; foreach (var k in KW) if (ln.Contains(k)) { hit = true; break; }
    if (!hit) continue;
    sb.AppendLine(n + "  sprite=" + ResName(GO(o, "Sprite")) + "  visible=" + S(GO(o, "Visible")));
}

// ---------- [D] Code ----------
var codes = (IList)GO(Data, "Code");
sb.AppendLine();
sb.AppendLine("=== [D] Code（总 " + codes.Count + "）命中关键词 ===");
foreach (var c in codes) {
    string n = ResName(c);
    if (n == null) continue;
    string ln = n.ToLower();
    bool hit = false; foreach (var k in KW) if (ln.Contains(k)) { hit = true; break; }
    if (!hit) continue;
    sb.AppendLine(n + "  ins=" + S(GO(c, "Length")));
}

// ---------- [E] 字符串池里带 textbox/dialog 的 ----------
var strs = (IList)GO(Data, "Strings");
sb.AppendLine();
sb.AppendLine("=== [E] Strings 命中（总 " + strs.Count + "）===");
int cnt = 0;
foreach (var st in strs) {
    string v = S(st);
    if (v == null) continue;
    string lv = v.ToLower();
    if (lv.Contains("textbox") || lv.Contains("dialoguebox") || lv.Contains("dialogbox")) {
        sb.AppendLine("str: " + v);
        if (++cnt > 200) { sb.AppendLine("... (截断)"); break; }
    }
}

File.WriteAllText(OUT, sb.ToString());
