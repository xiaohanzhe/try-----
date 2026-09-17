# -*- coding: utf-8 -*-
"""H5 §4.1 —— 素材分组「补漏报告器」（只读，不修改任何配置）

职责（严格限定）：
  1. 扫描 deltarune_ralsei/*.png，按命名格式 `spr_<base>_<seq>.png` 归组；
  2. 与 ralsei_pet/assets/animations.json 对账，给每个磁盘组打三态标签：
       已登记 / 部分引用 / 未引用
  3. 反向检查「配置引用了但磁盘没有」的帧；
  4. 产出 UTF-8 证据文件 + 单文件 HTML 图库（内联 base64，无需服务器）。

本脚本**绝不**回写 animations.json，也绝不删任何素材 —— 按 H5 §4.1，
分组结果只作为「给人确认」的报告，是否收编由用户决定。
"""
import os
import re
import json
import base64
import time
import collections

HERE = os.path.dirname(os.path.abspath(__file__))          # .../code-quality-audit/架构改造-H4H5
AUDIT = os.path.dirname(HERE)                              # .../code-quality-audit
ROOT = os.path.dirname(AUDIT)                              # 工程根
ASSET_DIR = os.path.join(ROOT, "deltarune_ralsei")
JSON_PATH = os.path.join(ROOT, "ralsei_pet", "assets", "animations.json")
OUT_DIR = os.path.join(HERE, "_evidence")
TODAY = time.strftime("%Y-%m-%d")
GALLERY_PATH = os.path.join(ROOT, "素材分组总览_%s.html" % TODAY)
RUN_LOG = os.path.join(OUT_DIR, "scan_asset_groups.run.txt")

LOG = []


def log(msg):
    LOG.append(str(msg))


# ---------------------------------------------------------------- 命名解析
SEQ_RE = re.compile(r"^(?P<base>.+)_(?P<seq>\d+)$")
PREFIX = "spr_"


def parse_stem(filename):
    """spr_foo_bar_3.png -> ('foo_bar', 3)；无数字后缀 -> ('foo_bar', None)"""
    stem = filename
    if stem.lower().endswith(".png"):
        stem = stem[:-4]
    if stem.startswith(PREFIX):
        stem = stem[len(PREFIX):]
    m = SEQ_RE.match(stem)
    if m:
        return m.group("base"), int(m.group("seq"))
    return stem, None


def unparse(base, seq):
    """parse_stem 的逆运算，用于 X5 自检。"""
    stem = base if seq is None else "%s_%d" % (base, seq)
    return PREFIX + stem + ".png"


def family_of(base):
    """家族 = 首 token（ralsei / board / susie / cutscene ...）"""
    return base.split("_", 1)[0]


# ---------------------------------------------------------------- 读动画表
def load_json_groups():
    with open(JSON_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    groups = data["groups"]
    # 解析 alias_of 链，拿到每组真实帧列表
    resolved = {}
    visiting = set()

    def resolve(key):
        if key in resolved:
            return resolved[key]
        if key in visiting:
            log("[WARN] alias_of 存在循环引用：%s" % key)
            return []
        visiting.add(key)
        entry = groups.get(key) or {}
        frames = list(entry.get("frames") or [])
        alias = entry.get("alias_of")
        if alias:
            frames = frames + resolve(alias)
        visiting.discard(key)
        resolved[key] = frames
        return frames

    for k in groups:
        resolve(k)

    file_to_groups = collections.defaultdict(set)
    for k, frames in resolved.items():
        for fn in frames:
            file_to_groups[fn].add(k)
    return data, groups, resolved, file_to_groups


# ---------------------------------------------------------------- 主流程
def main():
    if not os.path.isdir(ASSET_DIR):
        log("[FATAL] 素材目录不存在：%s" % ASSET_DIR)
        write_all(None)
        return 2

    on_disk = sorted(
        n for n in os.listdir(ASSET_DIR)
        if n.lower().endswith(".png") and os.path.isfile(os.path.join(ASSET_DIR, n))
    )
    log("素材目录：%s" % ASSET_DIR)
    log("磁盘 PNG 总数：%d" % len(on_disk))

    data, json_groups, resolved, file_to_groups = load_json_groups()
    json_frames = set(file_to_groups.keys())
    log("配置：schema_version=%s，组数=%d，被引用帧数=%d"
        % (data.get("schema_version"), len(json_groups), len(json_frames)))

    # 磁盘 → 分组
    disk_groups = collections.OrderedDict()
    for fn in on_disk:
        base, seq = parse_stem(fn)
        g = disk_groups.setdefault(base, {"base": base, "frames": []})
        g["frames"].append({"file": fn, "seq": seq})

    # 打标签
    for base, g in disk_groups.items():
        frames = g["frames"]
        files = [x["file"] for x in frames]
        ref = {fn: sorted(file_to_groups.get(fn, ())) for fn in files}
        used = [fn for fn in files if ref[fn]]
        g["frame_count"] = len(files)
        g["used_count"] = len(used)
        g["referenced_by"] = sorted({k for fn in used for k in ref[fn]})
        g["frame_ref"] = ref
        if g["used_count"] == 0:
            g["status"] = "unused"
        elif g["used_count"] < g["frame_count"]:
            g["status"] = "partial"
        else:
            g["status"] = "registered"
        g["json_same_name"] = base in json_groups
        g["family"] = family_of(base)

    # 反向：配置引用但磁盘缺失
    missing = sorted(fn for fn in json_frames if not os.path.isfile(os.path.join(ASSET_DIR, fn)))
    orphan_groups = sorted(k for k, frames in resolved.items() if frames and all(
        not os.path.isfile(os.path.join(ASSET_DIR, fn)) for fn in frames))

    # ---- X 系列自检 ----
    checks = []
    summed = sum(g["frame_count"] for g in disk_groups.values())
    checks.append(("X1 分组帧数合计 == 磁盘文件数", summed == len(on_disk), "%d vs %d" % (summed, len(on_disk))))
    seen = collections.Counter()
    for g in disk_groups.values():
        for x in g["frames"]:
            seen[x["file"]] += 1
    dup = [f for f, c in seen.items() if c != 1]
    checks.append(("X2 每个文件恰好归属一组", not dup, "重复=%d" % len(dup)))
    checks.append(("X3 JSON 引用帧集合 ⊆ 磁盘（差集即缺失）",
                   len(set(json_frames) - set(on_disk)) == len(missing),
                   "缺失=%d" % len(missing)))
    stat = collections.Counter(g["status"] for g in disk_groups.values())
    checks.append(("X4 三态计数合计 == 组数",
                   sum(stat.values()) == len(disk_groups),
                   "%s 合计=%d 组数=%d" % (dict(stat), sum(stat.values()), len(disk_groups))))
    bad = [f for f in on_disk if unparse(*parse_stem(f)) != f]
    checks.append(("X5 命名解析可逆（parse→unparse 复原）", not bad, "不匹配=%d" % len(bad)))
    checks.append(("X6 状态标签取值合法",
                   set(stat) <= {"registered", "partial", "unused"}, str(set(stat))))
    checks.append(("X7 未引用组的 used_count 必为 0",
                   all(g["used_count"] == 0 for g in disk_groups.values() if g["status"] == "unused"),
                   "ok"))

    for name, ok, detail in checks:
        log("[%s] %s (%s)" % ("PASS" if ok else "FAIL", name, detail))

    result = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "asset_dir": ASSET_DIR,
        "animations_json": JSON_PATH,
        "totals": {
            "disk_png": len(on_disk),
            "disk_groups": len(disk_groups),
            "json_groups": len(json_groups),
            "json_frames": len(json_frames),
            "missing_on_disk": len(missing),
            "status": dict(stat),
            "families": len({g["family"] for g in disk_groups.values()}),
        },
        "missing_frames": missing,
        "orphan_json_groups": orphan_groups,
        "checks": [{"name": n, "pass": ok, "detail": d} for n, ok, d in checks],
        "families": {},
        "groups": {},
    }

    fam = collections.defaultdict(list)
    for base, g in disk_groups.items():
        fam[g["family"]].append(base)
        result["groups"][base] = {
            "family": g["family"],
            "frame_count": g["frame_count"],
            "used_count": g["used_count"],
            "status": g["status"],
            "json_same_name": g["json_same_name"],
            "referenced_by": g["referenced_by"],
            "frames": [{"file": x["file"], "seq": x["seq"],
                        "referenced_by": g["frame_ref"][x["file"]]} for x in g["frames"]],
        }
    for k, v in sorted(fam.items()):
        st = collections.Counter(disk_groups[b]["status"] for b in v)
        result["families"][k] = {"groups": len(v), "status": dict(st), "members": sorted(v)}

    write_all(result, disk_groups)
    return 0


# ---------------------------------------------------------------- 输出
def write_all(result, disk_groups=None):
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    with open(os.path.join(OUT_DIR, "asset_groups.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    with open(RUN_LOG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG) + "\n")
    if result is None:
        return
    with open(os.path.join(OUT_DIR, "asset_groups.txt"), "w", encoding="utf-8") as fh:
        fh.write(render_txt(result))
    html_doc = render_html(result, disk_groups)
    with open(GALLERY_PATH, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    log("已写出：%s" % GALLERY_PATH)
    log("已写出：%s" % os.path.join(OUT_DIR, "asset_groups.txt"))
    with open(RUN_LOG, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG) + "\n")


def render_txt(r):
    L = []
    A = L.append
    A("素材分组补漏报告（只读扫描，未修改任何配置）")
    A("生成时间：%s" % r["generated_at"])
    A("素材目录：%s" % r["asset_dir"])
    A("动画表  ：%s" % r["animations_json"])
    A("")
    t = r["totals"]
    A("== 总量 ==")
    A("磁盘 PNG            : %d" % t["disk_png"])
    A("磁盘分组（命名族）  : %d" % t["disk_groups"])
    A("家族数              : %d" % t["families"])
    A("配置组数            : %d" % t["json_groups"])
    A("配置引用帧数        : %d" % t["json_frames"])
    A("三态：已登记 %d / 部分引用 %d / 未引用 %d"
      % (t["status"].get("registered", 0), t["status"].get("partial", 0), t["status"].get("unused", 0)))
    A("配置引用但磁盘缺失  : %d" % t["missing_on_disk"])
    A("")
    A("== 自检 ==")
    for c in r["checks"]:
        A("[%s] %s (%s)" % ("PASS" if c["pass"] else "FAIL", c["name"], c["detail"]))
    A("")

    def dump(title, pred):
        A("== %s ==" % title)
        rows = sorted((k, v) for k, v in r["groups"].items() if pred(v))
        if not rows:
            A("（无）")
        for k, v in rows:
            A("  %-42s 帧%-3d 已用%-3d 同名组=%-5s 引用=%s"
              % (k, v["frame_count"], v["used_count"],
                 "有" if v["json_same_name"] else "无",
                 ",".join(v["referenced_by"]) or "-"))
        A("  小计：%d 组" % len(rows))
        A("")

    dump("A. 未引用（磁盘有、配置零引用）", lambda v: v["status"] == "unused")
    dump("B. 部分引用（帧只被引用了一部分）", lambda v: v["status"] == "partial")
    reg = [k for k, v in r["groups"].items() if v["status"] == "registered"]
    A("== C. 已登记 ==")
    A("  共 %d 组（全部帧均被配置引用），明细见 asset_groups.json" % len(reg))
    A("")
    A("== D. 配置引用但磁盘缺失的帧 ==")
    A(("（无）" if not r["missing_frames"] else "\n".join("  " + x for x in r["missing_frames"])))
    A("")
    A("== E. 家族统计 ==")
    A("  %-16s %-6s %-8s %-10s %s" % ("家族", "组数", "已登记", "部分引用", "未引用"))
    for k, v in sorted(r["families"].items(), key=lambda kv: (-kv[1]["groups"], kv[0])):
        s = v["status"]
        A("  %-16s %-6d %-8d %-10d %d"
          % (k, v["groups"], s.get("registered", 0), s.get("partial", 0), s.get("unused", 0)))
    A("")
    return "\n".join(L)


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--line:#e2e5ea;--ink:#1f2430;--dim:#6b7280;
--reg:#137a4a;--regbg:#e6f5ed;--par:#9a6206;--parbg:#fdf3e0;--unu:#a3282c;--unubg:#fdeaea;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 "Segoe UI","Microsoft YaHei",system-ui,sans-serif}
header{position:sticky;top:0;z-index:9;background:#fff;border-bottom:1px solid var(--line);
padding:12px 20px;box-shadow:0 1px 6px rgba(0,0,0,.05)}
h1{margin:0 0 8px;font-size:18px}
.sum{display:flex;flex-wrap:wrap;gap:8px;font-size:12px;color:var(--dim)}
.sum b{color:var(--ink)}
.chipbar{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.chip{cursor:pointer;border:1px solid var(--line);background:#fff;border-radius:14px;
padding:3px 10px;font-size:12px;color:var(--dim)}
.chip.on{background:#1f2430;border-color:#1f2430;color:#fff}
nav{padding:10px 20px;border-bottom:1px solid var(--line);background:#fff;
display:flex;flex-wrap:wrap;gap:6px;font-size:12px}
nav a{color:#25507a;text-decoration:none;border:1px solid var(--line);border-radius:12px;padding:2px 8px}
main{padding:16px 20px 80px}
h2{font-size:15px;margin:22px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--line)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--dim);
border-radius:8px;padding:8px 9px}
.card.unused{border-left-color:var(--unu)}
.card.partial{border-left-color:var(--par)}
.card.registered{border-left-color:var(--reg)}
.card.hide{display:none}
.chead{display:flex;align-items:flex-start;gap:6px}
.chead input{margin-top:3px}
.gname{font-family:Consolas,monospace;font-size:12.5px;font-weight:600;word-break:break-all;flex:1}
.badge{font-size:10.5px;border-radius:9px;padding:1px 7px;white-space:nowrap}
.badge.unused{background:var(--unubg);color:var(--unu)}
.badge.partial{background:var(--parbg);color:var(--par)}
.badge.registered{background:var(--regbg);color:var(--reg)}
.meta{font-size:11px;color:var(--dim);margin:3px 0 6px}
.thumbs{display:flex;flex-wrap:wrap;gap:3px;background:#dfe3e8;border-radius:5px;padding:4px;
background-image:linear-gradient(45deg,#cbd1d8 25%,transparent 25%),linear-gradient(-45deg,#cbd1d8 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#cbd1d8 75%),linear-gradient(-45deg,transparent 75%,#cbd1d8 75%);
background-size:10px 10px;background-position:0 0,0 5px,5px -5px,-5px 0}
.thumbs img{height:58px;width:auto;image-rendering:pixelated}
.flist{font-family:Consolas,monospace;font-size:10.5px;color:var(--dim);margin-top:5px;
max-height:74px;overflow:auto;word-break:break-all}
.picker{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid var(--line);
padding:8px 20px;display:flex;gap:10px;align-items:center;box-shadow:0 -2px 8px rgba(0,0,0,.06);z-index:10}
.picker textarea{flex:1;height:46px;font-family:Consolas,monospace;font-size:11.5px;
border:1px solid var(--line);border-radius:6px;padding:5px;resize:none;color:var(--ink)}
.picker button{border:1px solid var(--line);background:#1f2430;color:#fff;border-radius:6px;
padding:7px 12px;cursor:pointer;font-size:12px}
.picker .cnt{font-size:12px;color:var(--dim);white-space:nowrap}
.warn{background:#fff8e6;border:1px solid #f0dca6;color:#7a5a06;border-radius:6px;
padding:8px 10px;margin:10px 0;font-size:12.5px}
"""

JS = """
var groups=document.querySelectorAll('.card');
var boxes=document.querySelectorAll('.card input');
var ta=document.getElementById('sel');
function refresh(){
  var on=[];var c={unused:0,partial:0,registered:0};
  boxes.forEach(function(b){
    var card=b.closest('.card');
    c[card.dataset.status]=(c[card.dataset.status]||0)+1;
    if(b.checked) on.push(card.dataset.base);
  });
  document.getElementById('cnt').textContent='选中 '+on.length+' 组　（未引用 '+c.unused+' / 部分引用 '+c.partial+' / 已登记 '+c.registered+'）';
  ta.value=on.join('\\n');
}
boxes.forEach(function(b){b.addEventListener('change',refresh)});
document.querySelectorAll('.chip').forEach(function(ch){
  ch.addEventListener('click',function(){
    document.querySelectorAll('.chip').forEach(function(x){x.classList.remove('on')});
    ch.classList.add('on');
    var f=ch.dataset.filter;
    groups.forEach(function(g){g.classList.toggle('hide', f!=='all' && g.dataset.status!==f)});
  });
});
document.getElementById('fUnused').addEventListener('click',function(){
  boxes.forEach(function(b){b.checked=(b.closest('.card').dataset.status==='unused')});
  refresh();
});
document.getElementById('cNone').addEventListener('click',function(){
  boxes.forEach(function(b){b.checked=false}); refresh();
});
document.getElementById('copy').addEventListener('click',function(){
  ta.select(); try{document.execCommand('copy');}catch(e){}
  this.textContent='已复制'; var s=this; setTimeout(function(){s.textContent='复制'},900);
});
refresh();
"""


def render_html(r, disk_groups):
    def b64(path):
        with open(path, "rb") as fh:
            return base64.b64encode(fh.read()).decode("ascii")

    gallery_dir = ASSET_DIR
    A = []
    A.append('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">')
    A.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A.append('<title>素材分组总览 %s</title>' % r["generated_at"])
    A.append("<style>%s</style></head><body>" % CSS)
    t = r["totals"]
    A.append("<header><h1>Ralsei 素材分组总览（只读补漏报告）</h1>")
    A.append('<div class="sum"><span>磁盘 PNG <b>%d</b></span><span>命名分组 <b>%d</b></span>'
             '<span>家族 <b>%d</b></span><span>配置组 <b>%d</b></span>'
             '<span>已登记 <b>%d</b></span><span style="color:#9a6206">部分引用 <b>%d</b></span>'
             '<span style="color:#a3282c">未引用 <b>%d</b></span>'
             '<span>配置引用但缺文件 <b>%d</b></span></div>'
             % (t["disk_png"], t["disk_groups"], t["families"], t["json_groups"],
                t["status"].get("registered", 0), t["status"].get("partial", 0),
                t["status"].get("unused", 0), t["missing_on_disk"]))
    A.append('<div class="chipbar">'
             '<span class="chip on" data-filter="all">全部</span>'
             '<span class="chip" data-filter="unused">只看未引用</span>'
             '<span class="chip" data-filter="partial">只看部分引用</span>'
             '<span class="chip" data-filter="registered">只看已登记</span>'
             '<span class="chip" id="fUnused">✓ 勾选全部未引用</span>'
             '<span class="chip" id="cNone">清空勾选</span></div>')
    A.append("</header>")
    A.append("<nav>" + "".join(
        '<a href="#fam-%s">%s (%d)</a>' % (k, k, v["groups"])
        for k, v in sorted(r["families"].items(), key=lambda kv: (-kv[1]["groups"], kv[0]))
    ) + "</nav><main>")
    A.append('<div class="warn">用法：勾选你<b>不需要</b>的分组，下方文本框会自动列出组名，'
             '点「复制」后粘贴给我即可；我会据此收编/清理配置，并再做一轮要求文件查缺补漏。</div>')

    order = {"unused": 0, "partial": 1, "registered": 2}
    for fam, v in sorted(r["families"].items(), key=lambda kv: (-kv[1]["groups"], kv[0])):
        A.append('<h2 id="fam-%s">%s <span style="font-size:12px;color:#6b7280">'
                 '%d 组 · 未引用 %d / 部分 %d / 已登记 %d</span></h2>'
                 % (fam, fam, v["groups"], v["status"].get("unused", 0),
                    v["status"].get("partial", 0), v["status"].get("registered", 0)))
        A.append('<div class="grid">')
        for base in sorted(v["members"], key=lambda b: (order[r["groups"][b]["status"]], b)):
            g = r["groups"][base]
            zh = {"unused": "未引用", "partial": "部分引用", "registered": "已登记"}[g["status"]]
            A.append('<div class="card %s" data-status="%s" data-base="%s">' % (g["status"], g["status"], base))
            A.append('<div class="chead"><input type="checkbox"><span class="gname">%s</span>'
                     '<span class="badge %s">%s</span></div>' % (base, g["status"], zh))
            A.append('<div class="meta">帧 %d · 已被引用 %d · 配置同名组：%s%s</div>'
                     % (g["frame_count"], g["used_count"],
                        "有" if g["json_same_name"] else "无",
                        ("　→ " + ",".join(g["referenced_by"])) if g["referenced_by"] else ""))
            A.append('<div class="thumbs">')
            for fr in g["frames"]:
                p = os.path.join(gallery_dir, fr["file"])
                try:
                    src = "data:image/png;base64," + b64(p)
                except OSError:
                    continue
                tip = fr["file"] + ("  [%s]" % ",".join(fr["referenced_by"]) if fr["referenced_by"] else "  [未引用]")
                A.append('<img alt="%s" title="%s" src="%s">' % (fr["file"], tip, src))
            A.append("</div>")
            A.append('<div class="flist">' + "<br>".join(
                f['file'] + (" ✔" if f["referenced_by"] else "") for f in g["frames"]) + "</div>")
            A.append("</div>")
        A.append("</div>")
    A.append("</main>")
    A.append('<div class="picker"><span class="cnt" id="cnt">—</span>'
             '<textarea id="sel" placeholder="勾选后这里会出现组名（每行一个）"></textarea>'
             '<button id="copy">复制</button></div>')
    A.append("<script>%s</script></body></html>" % JS)
    return "\n".join(A)


if __name__ == "__main__":
    raise SystemExit(main())
