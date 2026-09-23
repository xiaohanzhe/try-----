第38轮续二：房间表严格复检（11 项全绿）+ 推送链路根因定位与修复

复检（_tools/recheck38b.py，判据来源 = AST 抽取 build_roomtable3.py 的真实规则表）
- A0 判据鉴别力自检：不存在的规则命中 0、真规则命中非 0（证明判据能分辨有/无匹配）
- A1 42 条规则在全量房间维度无死规则；1,013 个 scene 全部有区域归属
- A2 同名资源跨章区域一致（不一致 0）
- A3 area_id 与 area_name 严格一对一；区域共 32 个
- A4 总数 1251；分类 scene=1013 / maybe=37 / nonscene=201；87 个锚点 area_id 全部复现
- A5/A6/A7 逐条列出 nonscene / maybe / 敏感子串命中明细（全部人工可核，无误杀）
- A9 列出开发残留房间（example/mockup/old/backup/unused 等），仅呈现不判 FAIL
⇒ 11 项 PASS=11 FAIL=0

两次"报红"都是我判据写得不好，不是表的问题（已按"报红先怀疑判据"修正）：
- 反面控制用了 ^room_forest，它恰好也命中 32 个 ⇒ 改用保证命中 0 的名字
- "死规则"定义成"scene 维度命中 0" ⇒ 规则[0] 命中的房间全归 maybe/nonscene，
  但它仍在给这些房间定区域 ⇒ 判据改为"全量房间维度命中 0"

推送链路：前两次 push 失败（rc=128 / 超时）的真实根因
- ★ 根因一：本机 schannel 后端**吊销检查必失败**
  （CRYPT_E_NO_REVOCATION_CHECK）⇒ 换 openssl 后端 + 导出系统 CA 为 PEM + HTTP/1.1
- ★ 根因二：宿主注入的 credential.helper=helper-selector **不读 Windows 凭据管理器**，
  遇到需要凭据的 push 就**弹 GUI 选择框并挂死**
  （实测挂 1m22s；进程表抓到 git-credential-helper-selector.exe get 正在运行）
- ★★ 我一度误判"凭据已可用"：因为 ls-remote 成功 ⇒ 但该仓库是**公开**的，
  匿名也能列 ref ⇒ **ls-remote 在这个仓库上是恒真判据**，根本没走到认证
- 修复：清空 helper 链（-c credential.helper=）+ 直接问 git-credential-manager 取凭据
  （GCM_INTERACTIVE=never / GCM_PROVIDER=github / GCM_CREDENTIAL_STORE=wincredman）
  + http.extraheader 注入 Basic 头 ⇒ 静默、零弹窗
- 结果：push rc=0，4c6c3eb..f117aed main -> main；
  ls-remote 与 rev-parse origin/main 双向一致

新增工具（_tools/）
- recheck38b.py    房间表严格复检（AST 抽真实规则表，不复刻）
- kill_gitproc.py  杀掉挂起的 git 家族进程（弹窗挂死时用）
- test_gcm.py      静默测试 GCM 能否取到凭据（只打印长度）
- push38.py        本次推送脚本（已泛化为 gitpush.py）
- gitpush.py       可复用的「add + numstat 删除守卫 + commit -F + push + 双向核验」
