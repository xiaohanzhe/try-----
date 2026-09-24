原作 Deltarune 对话框素材（第44轮）

来源：UndertaleModTool CLI v0.9.2.0 反编译 chapter1_windows/data.win 后，
      用 `UndertaleModCli dump <data.win> -o <outdir> --sprites` 导出，文件名原样保留。

用途：modules/dr_textbox.py 复刻原作 scr_darkbox() 的 32px 边框带 + 32x32 动画角。
- spr_textbox_topleft_0..7.png  16x16  四角（8 帧动画，帧号 = cur_jewel/10）
- spr_textbox_top_0.png          1x16  上/下边剖条（下边垂直翻转）
- spr_textbox_left_0.png        16x1   左/右边剖条（右边水平翻转）

版权：素材版权归 Deltarune / Toby Fox 所有，本项目为个人同人用途。
