# -*- coding: utf-8 -*-
u"""第90轮：把 check90 注册进 G2 的 SUITES（二进制精确插入，保持 CRLF）。"""
import ast
import sys

RUN = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\regress\run_all.py"

ANCHOR = (
    "                'G \u5224\u636e\u81ea\u8eab\u4f53\u68c0\uff08\u88ab\u6d4b\u6587\u4ef6\u5728\u76d8"
    " \u00b7 \u8ba1\u6570\u5b88\u6052\uff09',\r\n    },\r\n]\r\n"
)

ENTRY = (
    "    # \u7b2c90\u8f6e \u00b7 `handle_jump` \u7684**\u7ad6\u76f4\u65b9\u5411\u5750\u6807\u7cfb**"
    "\uff08\u5c4f\u5e55 Y \u5411\u4e0b\uff09\u3002\r\n"
    "    # \u2605 \u7528\u6237\u53e3\u5f84\uff1a\u300c\u8df3\u8dc3\u7684\u629b\u7269\u7ebf\u4e5f\u4e0d\u5bf9\u300d"
    "\u300c\u8df3\u4e0a\u53bb\u7a97\u53e3\u4e5f\u53ea\u6709\u8df3\u6ca1\u6709\u4e0a\u53bb\u300d\u3002\r\n"
    "    # \u65e7\u5199\u6cd5\u7528\u7684\u662f Y-up \u5f39\u9053\u516c\u5f0f \u21d2 \u7ad6\u76f4\u52a0\u901f\u5ea6\u6052"
    "\u671d\u5c4f\u5e55\u4e0a\u65b9\uff08\u53cd\u91cd\u529b\uff09\uff0c\u6c38\u8fdc\u753b\u4e0d\u51fa\u201c\u5148\u4e0a"
    "\u540e\u4e0b\u201d\u7684\u629b\u7269\u7ebf\u3002\r\n"
    "    # \u2605\u2605 \u672c\u5957\u4ef6\u7684 C \u6bb5\u662f\u201c\u9274\u522b\u529b\u81ea\u8bc1\u201d\uff1a"
    "\u628a\u65e7\u516c\u5f0f**\u72ec\u7acb\u91cd\u7b97**\u4e00\u904d\uff0c\u5fc5\u987b\u8fc7\u4e0d\u4e86 B \u6bb5\u5224\u636e\u3002\r\n"
    "    # \u96f6\u7f51\u7edc / \u96f6 UI / \u4e0d\u9700\u8981\u663e\u793a\u5668 / \u96f6\u5916\u90e8\u76d8\u3002\r\n"
    "    {\r\n"
    "        'id': 'check90',\r\n"
    "        'script': os.path.join(ROOT, 'code-quality-audit',\r\n"
    "                               '\u7b2c90\u8f6e-\u57fa\u7840\u5ba0\u7269\u5ba1\u67e5', '_tools', 'check90.py'),\r\n"
    "        'offscreen': True,\r\n"
    "        'desc': '\u7b2c\u4e5d\u5341\u8f6e\uff1a`handle_jump` \u7ad6\u76f4\u65b9\u5411\u5750\u6807\u7cfb"
    "\uff08\u629b\u7269\u7ebf\uff09\u4e0d\u8bb8\u9759\u9ed8\u56de\u9000 \u2014\u2014 '\r\n"
    "                'A \u2605\u2605 \u516c\u5f0f\u7ed3\u6784\uff08AST \u9010\u5f0f\u5168\u7b49\uff1a`vy0` \u65e0 "
    "+50 \u9b54\u6570 \u00b7 `y` \u7684\u7ad6\u76f4\u52a0\u901f\u5ea6\u4e3a **+0.5gt\u00b2**\u00b7 '\r\n"
    "                '\u4e24\u6761\u7ed3\u6784\u5c42\u8d1f\u63a7\u5236\uff09 / '\r\n"
    "                'B \u2605\u2605\u2605 \u884c\u4e3a\uff08\u771f\u8c03 `RalseiPet.handle_jump`\uff08\u8f7b\u91cf"
    "\u6869\uff09\uff1a\u540c\u9ad8\u8df3\u5fc5\u987b\u662f**\u5148\u4e0a\u540e\u4e0b**\u7684\u771f\u5f27 \u00b7 '\r\n"
    "                '\u4e0a\u8df3\u4e0d\u8bb8\u201c\u5148\u5f80\u4e0b\u6c89\u201d \u00b7 \u843d\u70b9\u7cbe\u786e == "
    "\u76ee\u6807\uff08\u65e0\u672b\u5e27\u786c\u5438\u9644\u6b8b\u91cf\uff09\u00b7 '\r\n"
    "                '\u4e0b\u8df3\u4e0d\u8bb8\u8d8a\u8fc7\u76ee\u6807\u7ebf \u00b7 \u62ac\u5347\u968f\u8de8\u5ea6\u5355\u8c03\uff09 / '\r\n"
    "                'C \u2605\u2605\u2605 \u9274\u522b\u529b\u81ea\u8bc1\uff08\u65e7\u516c\u5f0f**\u72ec\u7acb\u91cd\u7b97**"
    "\u5fc5\u987b\u8fc7\u4e0d\u4e86 B1/B4/B5 + \u6b63\u63a7\u5236 C4\uff09 / '\r\n"
    "                'D \u2605\u2605 \u540c\u6587\u4ef6\u53e3\u5f84\u4e00\u81f4\uff08`handle_jump` \u4e0e "
    "`handle_fall` \u7684\u91cd\u529b\u5fc5\u987b\u540c\u53f7 \u00b7 '\r\n"
    "                '\u5168\u6587\u4ef6\u65e0\u7b2c\u4e8c\u4efd\u771f\u76f8\u6b8b\u7559\uff09 / '\r\n"
    "                'E \u5224\u636e\u81ea\u8eab\u4f53\u68c0\uff08\u88ab\u6d4b\u6587\u4ef6\u5728\u76d8 \u00b7 "
    "\u6807\u8bb0\u6253\u5370\u70b9 \u00b7 \u72ec\u7acb\u8ba1\u6570\u5668\u5b88\u6052 + \u6f0f\u8bb0\u8d1f\u63a7\u5236\uff09',\r\n"
    "    },\r\n"
    "]\r\n"
)


def main():
    with open(RUN, "rb") as f:
        raw = f.read()
    n = raw.count(ANCHOR.encode("utf-8"))
    print("锚点命中 = %d（须 1）" % n)
    if n != 1:
        print("!! 中止")
        return 2
    prefix = ("                'G \u5224\u636e\u81ea\u8eab\u4f53\u68c0\uff08\u88ab\u6d4b\u6587\u4ef6\u5728\u76d8"
              " \u00b7 \u8ba1\u6570\u5b88\u6052\uff09',\r\n    },\r\n")
    new = raw.replace(ANCHOR.encode("utf-8"), (prefix + ENTRY).encode("utf-8"))
    ast.parse(new.decode("utf-8"))
    print("AST 语法自检：OK")
    crlf = new.count(b"\r\n")
    print("改后 CRLF=%d 裸LF=%d" % (crlf, new.count(b"\n") - crlf))
    if new.count(b"\n") - crlf:
        print("!! EOL 被破坏，中止")
        return 3
    with open(RUN, "wb") as f:
        f.write(new)
    print("已写入。check90 出现次数 =", new.count(b"'check90'"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
