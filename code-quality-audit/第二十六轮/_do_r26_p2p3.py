# -*- coding: utf-8 -*-
"""第26轮 P2/P3 处置 —— 定点修复（白名单改写 + 逐项命中计数断言 + 编译校验）。

清单：
  P2-a  memory_system.py:508-509  except:pass  →  补 debug（next_id 兜底失败）
  P2-b  memory_system.py:981-982  except:pass  →  补 debug（extract_keywords 失败，
                                                   随后走退化实现）
  P2-c  memory_system.py:1196-1197 except:pass →  补 debug（node_weight 失败 → skip）
  P2-d  memory_store.py:324-325   except:pass  →  补 debug（删空目录失败）
  P2-e  desktop_interaction.py:123-124  except:pass → 补 debug（DWM 取窗口边框失败）
  P2-f  desktop_interaction.py:1342-1343 except:pass → 补 debug（EnumWindows 回调单窗失败）
  P3-a  main.py 自主开口链路 _clean_ai_reply 补传 recent
  P3-b  main.py:4961 paintEvent 的 QPainter 加 try/finally

纪律：逐条替换必须命中**恰好 1 次**；失败即整体中止（不写盘）；
      改完 ast.parse + compileall；反向归一证明（把新串换回旧串 == 原文）。
"""
import ast
import hashlib
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EVID = os.path.join(HERE, "_evidence")

TARGETS = {
    "memory_system": os.path.join(ROOT, "ralsei_pet", "modules", "memory_system.py"),
    "memory_store": os.path.join(ROOT, "ralsei_pet", "modules", "memory_store.py"),
    "desktop_interaction": os.path.join(ROOT, "ralsei_pet", "modules", "desktop_interaction.py"),
    "main": os.path.join(ROOT, "ralsei_pet", "src", "main.py"),
}

# (键, 文件, 旧串, 新串, 期望命中数, 备注)
EDITS = []

# ---------- P2-a ----------
EDITS.append((
    "P2-a", "memory_system",
    """            if _mx >= self._next_id:
                self._next_id = _mx + 1
        except Exception:
            pass
""",
    """            if _mx >= self._next_id:
                self._next_id = _mx + 1
        except Exception as e:  # 修复：原先静默吞噬
            _log.debug("memory_system 防御性异常（已忽略）: %s", e)
""",
    1, "next_id 兜底失败 → _next_id 留在文件值，可能导致 id 复用"))

# ---------- P2-b ----------
EDITS.append((
    "P2-b", "memory_system",
    """            try:
                return list(_cf.extract_keywords(text))[:limit]
            except Exception:
                pass
""",
    """            try:
                return list(_cf.extract_keywords(text))[:limit]
            except Exception as e:  # 修复：原先静默吞噬
                _log.debug("memory_system 防御性异常（已忽略）: %s", e)
""",
    1, "抽词失败 → 静默回落退化实现，无痕迹"))

# ---------- P2-c ----------
EDITS.append((
    "P2-c", "memory_system",
    """                    try:
                        if graph.node_weight(tgt) < self.MIN_PAGE_W:
                            continue
                    except Exception:
                        pass
""",
    """                    try:
                        if graph.node_weight(tgt) < self.MIN_PAGE_W:
                            continue
                    except Exception as e:  # 修复：原先静默吞噬
                        _log.debug("memory_system 防御性异常（已忽略）: %s", e)
""",
    1, "node_weight 失败 → 该路径被跳过，无痕迹"))

# ---------- P2-d ----------
# 注意：L316-317 那处是清理 tmp 的 pass（真实原因已在 L308/309 记录 → 正确模式，不动）。
# 这里只改 L324-325 —— 删"确实空了"的回落目录失败。
EDITS.append((
    "P2-d", "memory_store",
    """    try:
        if not os.listdir(fb):
            os.rmdir(fb)
            result['removed_fallback_dir'] = True
    except Exception:
        pass
""",
    """    try:
        if not os.listdir(fb):
            os.rmdir(fb)
            result['removed_fallback_dir'] = True
    except Exception as e:  # 修复：原先静默吞噬
        _log.debug("memory_store 防御性异常（已忽略）: %s", e)
""",
    1, "删空回落目录失败（非递归），影响面小但应留痕"))

# ---------- P2-e ----------
EDITS.append((
    "P2-e", "desktop_interaction",
    """            if hr == 0 and (r.right - r.left) > 0 and (r.bottom - r.top) > 0:
                return (r.left, r.top, r.right, r.bottom)
        except Exception:
            pass
""",
    """            if hr == 0 and (r.right - r.left) > 0 and (r.bottom - r.top) > 0:
                return (r.left, r.top, r.right, r.bottom)
        except Exception as e:  # 修复：原先静默吞噬
            log.debug("desktop_interaction 防御性异常（已忽略）: %s", e)
""",
    1, "DWM 取窗口边框失败 → 回落 GetWindowRect，应有痕迹"))

# ---------- P2-f ----------
EDITS.append((
    "P2-f", "desktop_interaction",
    """                        if app_name.lower() in title.lower() or app_name.lower() in class_name.lower():
                            hwnds.append(hwnd)
                except Exception:
                    pass
""",
    """                        if app_name.lower() in title.lower() or app_name.lower() in class_name.lower():
                            hwnds.append(hwnd)
                except Exception as e:  # 修复：原先静默吞噬
                    log.debug("desktop_interaction 防御性异常（已忽略）: %s", e)
""",
    1, "窗口枚举回调单窗失败 → 该窗口漏标，应有痕迹"))

# ---------- P3-a ----------
# 自主开口链路：原先调 _clean_ai_reply(reply_text) 未传 recent →
# 第 2 步『车轱辘话』整步被跳过 → 自主开口**永远不会**被判退重采样。
# 与对话链路（L6796 传 recent）不一致。此处补传，来源 = dialogue_ui 的 AI 历史
# 里 role=='assistant' 的文本（与对话链路 L6780 的取法同源）。
EDITS.append((
    "P3-a", "main",
    """            try:
                text = self._clean_ai_reply(reply_text) or ""
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)
""",
    """            try:
                # 修复：原先未传 recent → _clean_ai_reply 第 2 步（车轱辘话判定）
                # 整步跳过，自主开口永远不会被判退重采样，与对话链路不一致。
                # 取法与对话链路同源：AI 历史里 role=='assistant' 的文本。
                _rec = []
                try:
                    _dui = getattr(self, 'dialogue_ui', None)
                    _hist = _dui.get_ai_history() if _dui is not None else []
                    _rec = [c for _r, c in _hist if _r == 'assistant']
                except Exception:
                    _rec = []
                text = self._clean_ai_reply(reply_text, recent=_rec) or ""
            except Exception as e:
                _log.debug("main 防御性异常（已忽略）: %s", e)
""",
    1, "自主开口补传 recent（对齐对话链路）"))

# ---------- P3-b ----------
EDITS.append((
    "P3-b", "main",
    """    def paintEvent(self, event):
        # 绘制透明背景
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QBrush(QColor(0, 0, 0, 0)))
""",
    """    def paintEvent(self, event):
        # 绘制透明背景
        # 修复：原先无显式 end()，中途抛异常会留下 active painter，
        # Qt 会打印 "QPainter::begin: Painter already active"。
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QBrush(QColor(0, 0, 0, 0)))
        finally:
            painter.end()
""",
    1, "paintEvent 无 end() → 异常时 painter 残留"))


def md5b(b):
    return hashlib.md5(b).hexdigest()


raw = {}
text = {}
for k, p in TARGETS.items():
    with io.open(p, "rb") as f:
        raw[k] = f.read()
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        text[k] = f.read()

log = []
log.append("第26轮 P2/P3 定点修复记录")
log.append("")
log.append("### 改前哈希")
for k in TARGETS:
    log.append("  %-22s md5=%s bytes=%d" % (k, md5b(raw[k]), len(raw[k])))
log.append("")

# --- 逐条替换（命中数必须精确匹配） ---
applied = []
for key, fkey, old, new, expect, note in EDITS:
    cnt = text[fkey].count(old)
    if cnt != expect:
        log.append("  !! [%s] 命中 %d（期望 %d）→ 中止，未写任何文件" % (key, cnt, expect))
        with io.open(os.path.join(EVID, "r26_p2p3_fix_FAILED.txt"), "w",
                     encoding="utf-8", newline="\n") as f:
            f.write("\n".join(log) + "\n")
        raise SystemExit("命中数不符 [%s]: %d != %d" % (key, cnt, expect))
    text[fkey] = text[fkey].replace(old, new, 1)
    applied.append((key, fkey, old, new, note))
    log.append("  OK [%s] %s  命中=%d  %s" % (key, fkey, cnt, note))
log.append("")

# --- 反向归一证明：逐条换回 → 等于原文 ---
norm = dict(text)
for key, fkey, old, new, _note in reversed(applied):
    assert norm[fkey].count(new) >= 1, "反向归一：找不到新串 [%s]" % key
    norm[fkey] = norm[fkey].replace(new, old, 1)
for k in TARGETS:
    original = raw[k].decode("utf-8")
    assert norm[k] == original, "反向归一失败 [%s]" % k
log.append("### 反向归一证明：通过（逐条换回 == 原文，逐字符相等）")
log.append("")

# --- 写盘 ---
for k in TARGETS:
    with io.open(TARGETS[k], "w", encoding="utf-8", newline="") as f:
        f.write(text[k])

# --- 编译校验 ---
log.append("### AST / compileall 校验")
for k in TARGETS:
    try:
        ast.parse(text[k])
        log.append("  %-22s AST OK" % k)
    except SyntaxError as e:
        log.append("  %-22s AST FAIL: %s" % (k, e))
        raise
rc = subprocess.call([sys.executable, "-m", "compileall", "-q",
                      os.path.join(ROOT, "ralsei_pet")])
log.append("  compileall 退出码：%d" % rc)
log.append("")

log.append("### 改后哈希")
for k in TARGETS:
    with io.open(TARGETS[k], "rb") as f:
        nb = f.read()
    log.append("  %-22s md5=%s bytes=%d (Δ=%+d)" % (
        k, md5b(nb), len(nb), len(nb) - len(raw[k])))

with io.open(os.path.join(EVID, "r26_p2p3_fix.txt"), "w",
             encoding="utf-8", newline="\n") as f:
    f.write("\n".join(log) + "\n")

sys.stdout.write("OK %d edits applied, compileall=%d\n" % (len(applied), rc))
