# -*- coding: utf-8 -*-
"""sprite_loader.py 修复（第2区块）：占位帧混入动画、自动分组帧号去重、候选路径去重"""
P = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\modules\sprite_loader.py"

with open(P, "rb") as f:
    raw = f.read()
crlf = b"\r\n" in raw
src = raw.decode("utf-8").replace("\r\n", "\n")

def patch(old, new):
    global src
    assert old in src, f"NOT FOUND:\n{old[:200]}"
    assert src.count(old) == 1, f"NOT UNIQUE:\n{old[:200]}"
    src = src.replace(old, new, 1)

# 1) load_frame 增加 placeholder_on_missing 参数：
#    缺图时是否返回占位图。素材加载路径传 False（缺帧就跳过该帧，
#    不让灰色"?"占位帧混入动画）；其他调用点保持默认行为不变。
patch(
"""    def load_frame(self, filename):
        \"\"\"加载单个帧，参考niko_desktop_pet优化：支持多种文件命名格式\"\"\"
        # 检查缓存中是否已经有该文件""",
"""    def load_frame(self, filename, placeholder_on_missing=True):
        \"\"\"加载单个帧，参考niko_desktop_pet优化：支持多种文件命名格式。

        修复：原实现缺图时一律返回灰色"?"占位图，而调用方以
        `if frame:` 判断（QPixmap 对象恒真），导致素材缺失时占位帧
        混进动画序列，Ralsei 动画中周期性闪出灰块。现在调用方可传
        placeholder_on_missing=False 让缺帧返回 None（由调用方决定
        跳过或兜底），保证正常动画序列里永不出现占位帧。
        \"\"\"
        # 检查缓存中是否已经有该文件""")

# 2) 文件候选去重（.png→.jpg 再 .jpg→.png 会重复）
patch(
"""        # 参考niko_desktop_pet，支持多种文件命名格式
        file_candidates = [
            filename,  # 优先：原始文件名
            filename.replace('.png', '.jpg'),  # 次选：jpg格式
            filename.replace('.jpg', '.png'),  # 次选：png格式
        ]""",
"""        # 参考niko_desktop_pet，支持多种文件命名格式
        # 修复：.png→.jpg 与 .jpg→.png 在特定文件名下会生成重复候选，
        # 白白多做一次磁盘探测；用有序去重保留语义。
        file_candidates = list(dict.fromkeys([
            filename,  # 优先：原始文件名
            filename.replace('.png', '.jpg'),  # 次选：jpg格式
            filename.replace('.jpg', '.png'),  # 次选：png格式
        ]))""")

# 3) 缺图时按参数决定返回
patch(
"""        if not loaded_ok:
            # 文件缺失：返回占位图但不缓存，避免后续补上真实文件后仍显示占位图
            pixmap = self.create_placeholder_image()
            return pixmap""",
"""        if not loaded_ok:
            # 文件缺失：不缓存（避免后续补上真实文件后仍显示占位图）；
            # 是否返回占位图由调用方决定。
            if placeholder_on_missing:
                return self.create_placeholder_image()
            return None""")

# 4) load_sprites 缺帧不再用占位图填充
patch(
"""            # 加载所有帧
            for i, file in enumerate(files):
                frame = self.load_frame(file)
                if frame:
                    frames_reserved[i] = frame""",
"""            # 加载所有帧（修复：缺帧返回 None 并跳过，不把占位帧混入动画；
            # 仅当整个关键动画无帧时才由下方兜底逻辑创建占位帧）
            for i, file in enumerate(files):
                frame = self.load_frame(file, placeholder_on_missing=False)
                if frame is not None:
                    frames_reserved[i] = frame""")

# 5) 自动分组帧号去重 + 稳定排序：
#    dance2.png 与 dance_2.png 同帧号 → 只保留一个；顺序不再依赖 os.listdir。
patch(
"""        # 对每个前缀组内的帧按帧号排序
        for prefix, frames in prefix_groups.items():
            # 按帧号排序
            sorted_frames = sorted(frames, key=lambda x: x[0])
            # 只保留文件名
            self.auto_scanned_animations[prefix] = [frame_info[1] for frame_info in sorted_frames]""",
"""        # 对每个前缀组内的帧按帧号排序
        for prefix, frames in prefix_groups.items():
            # 修复：dance2.png 与 dance_2.png 会被解析成同一帧号，原实现全部
            # 保留 → 动画出现重复帧；且同帧号顺序依赖 os.listdir（不稳定）。
            # 现在按 (帧号, 文件名) 稳定排序后按帧号去重，只保留每帧第一个。
            sorted_frames = sorted(frames, key=lambda x: (x[0], x[1]))
            seen_frames = set()
            deduped = []
            for frame_number, filename in sorted_frames:
                if frame_number in seen_frames:
                    _log.debug("动画 %s 帧号 %d 重复，忽略 %s", prefix, frame_number, filename)
                    continue
                seen_frames.add(frame_number)
                deduped.append(filename)
            # 只保留文件名
            self.auto_scanned_animations[prefix] = deduped""")

out = src.replace("\n", "\r\n") if crlf else src
with open(P, "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("sprite_loader.py patched OK")
