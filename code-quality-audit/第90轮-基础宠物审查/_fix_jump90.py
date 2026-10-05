# -*- coding: utf-8 -*-
u"""第90轮 P0 修复：`handle_jump` 竖直方向坐标系（Y 向下）。

纪律：
  · **二进制精确替换**，保持文件原有的 **CRLF**（main.py 实测 14400 CRLF / 0 裸 LF）；
  · 替换前**断言唯一命中**，不唯一就中止（绝不模糊替换）；
  · 替换后立即复读并用 AST 断言：`vy0` 公式与 `y` 公式都变成新形式、旧式已消失。
"""
import ast
import io
import os
import sys

MAIN = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\src\main.py"

OLD_VY0 = (
    "# 计算初始垂直速度：使用抛物线公式 dy = vy0 * t - 0.5 * g * t\u00b2\r\n"
    "        vy0 = (delta_y + 0.5 * g * self.jump_duration * self.jump_duration + 50)"
    " / self.jump_duration  # \u589e\u52a050\u50cf\u7d20\u7684\u989d\u5916\u9ad8\u5ea6\r\n"
)

NEW_VY0 = (
    "# \u2605\u2605 \u7b2c90\u8f6e\u4fee\u590d\uff08P0\uff09\uff1a**\u7ad6\u76f4\u65b9\u5411\u7684\u5750\u6807\u7cfb**\u3002\r\n"
    "        #   `self.jump_start_pos` \u662f Qt \u5c4f\u5e55\u5750\u6807 \u2014\u2014 **Y \u5411\u4e0b\u589e\u5927**\u3002\r\n"
    "        #   \u65e7\u5199\u6cd5 `y = y0 + vy0*t - 0.5*g*t\u00b2`\uff08\u914d `vy0 = (\u0394y + 0.5gT\u00b2 + 50)/T`\uff09\r\n"
    "        #   \u662f\u6807\u51c6 **Y-up** \u5f39\u9053\u516c\u5f0f \u21d2 \u7ad6\u76f4\u52a0\u901f\u5ea6 `-0.5g t\u00b2` \u6052\u671d**\u5c4f\u5e55\u4e0a\u65b9**\r\n"
    "        #   \uff08\u7b49\u4e8e\u53cd\u91cd\u529b\uff09\uff0c\u6570\u5b66\u4e0a**\u6c38\u8fdc\u4ea7\u751f\u4e0d\u4e86\u201c\u5148\u4e0a\u540e\u4e0b\u201d\u7684\u629b\u7269\u7ebf**\uff1a\r\n"
    "        #     \u00b7 \u0394y > -0.5gT\u00b2 \u21d2 vy0 > 0\uff0c\u5ba0\u7269\u5148\u671d\u5c4f\u5e55**\u4e0b\u65b9**\u6c89\uff08\u540c\u9ad8\u8df3\u5148\u6c89 90px\uff09\uff1b\r\n"
    "        #     \u00b7 \u0394y \u2264 -0.5gT\u00b2 \u21d2 vy0 \u2264 0\uff0c\u5168\u7a0b\u5355\u8c03\u52a0\u901f\u4e0a\u5347\uff0c\u9876\u70b9\u538b\u6839\u4e0d\u5b58\u5728\uff1b\r\n"
    "        #     \u00b7 `+50` \u8ba9\u516c\u5f0f\u843d\u70b9**\u6052\u5b9a**\u6bd4\u76ee\u6807\u4f4e 50px\uff0c\u518d\u9760\u672b\u5e27\u786c\u5438\u9644\u8865 \u21d2 \u843d\u5730\u8df3\u53d8 50px\u3002\r\n"
    "        #   \uff08\u6570\u503c\u4eff\u771f\uff1acode-quality-audit/\u7b2c90\u8f6e-\u57fa\u7840\u5ba0\u7269\u5ba1\u67e5/_evidence/sim_jump90.py\uff09\r\n"
    "        #   \u6539\u4e3a\u5c4f\u5e55\u5750\u6807\u4e0b\u7684\u6b63\u786e\u5f62\u5f0f\uff0c`vy0` **\u8d1f = \u521d\u901f\u671d\u4e0a**\uff08\u4e0e `handle_fall` \u7684\r\n"
    "        #   `_vy0` \u540c\u4e00\u7ea6\u5b9a\uff09\uff1a\u6b64\u65f6 y(T) == y0 + \u0394y **\u6070\u597d\u6210\u7acb**\uff0c\u4e0d\u518d\u9700\u8981\u9b54\u6570\uff0c\r\n"
    "        #   \u4e5f\u4e0d\u518d\u9700\u8981\u672b\u5e27\u5438\u9644\u6765\u201c\u8865\u201d\u843d\u70b9\u3002\r\n"
    "        vy0 = (delta_y - 0.5 * g * self.jump_duration * self.jump_duration)"
    " / self.jump_duration\r\n"
)

OLD_Y = ("        y = self.jump_start_pos.y() + vy0 * elapsed"
         " - 0.5 * g * elapsed * elapsed\r\n")
NEW_Y = ("        y = self.jump_start_pos.y() + vy0 * elapsed"
         " + 0.5 * g * elapsed * elapsed\r\n")


def main():
    with open(MAIN, "rb") as f:
        raw = f.read()
    before_crlf = raw.count(b"\r\n")
    before_lf = raw.count(b"\n") - before_crlf
    print("改前：CRLF=%d  裸LF=%d  字节=%d" % (before_crlf, before_lf, len(raw)))

    nb = raw.count(OLD_VY0.encode("utf-8"))
    ny = raw.count(OLD_Y.encode("utf-8"))
    print("OLD_VY0 命中 = %d    OLD_Y 命中 = %d" % (nb, ny))
    if nb != 1 or ny != 1:
        print("!! 命中数不为 1，**中止**（绝不模糊替换）")
        return 2

    new = raw.replace(OLD_VY0.encode("utf-8"), NEW_VY0.encode("utf-8"))
    new = new.replace(OLD_Y.encode("utf-8"), NEW_Y.encode("utf-8"))

    # 语法自检（ast.parse，不产 .pyc）
    ast.parse(new.decode("utf-8"))
    print("AST 语法自检：OK")

    after_crlf = new.count(b"\r\n")
    after_lf = new.count(b"\n") - after_crlf
    print("改后：CRLF=%d  裸LF=%d  字节=%d" % (after_crlf, after_lf, len(new)))
    if after_lf != 0:
        print("!! 出现裸 LF，**中止**（EOL 被破坏）")
        return 3

    with open(MAIN, "wb") as f:
        f.write(new)

    # 复读核验
    with open(MAIN, "rb") as f:
        chk = f.read()
    print("复读：旧 vy0 残留 = %d（须 0）" % chk.count(b"+ 50) / self.jump_duration"))
    print("复读：新 vy0 出现 = %d（须 1）"
          % chk.count(b"vy0 = (delta_y - 0.5 * g * self.jump_duration"))
    print("复读：旧 y 式残留 = %d（须 0）"
          % chk.count(b"vy0 * elapsed - 0.5 * g * elapsed * elapsed"))
    print("复读：新 y 式出现 = %d（须 1）"
          % chk.count(b"vy0 * elapsed + 0.5 * g * elapsed * elapsed"))
    print("复读：CRLF=%d  裸LF=%d"
          % (chk.count(b"\r\n"), chk.count(b"\n") - chk.count(b"\r\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
