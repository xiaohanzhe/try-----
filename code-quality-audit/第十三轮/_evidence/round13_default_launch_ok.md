第十三轮：默认启动方式复跑结论（关闭第十二轮补丁 §六-1）
================================================================
命令（就是用户日常的启动方式）：
    Set-Location ralsei_pet
    & C:\Python311\python.exe src\main.py

结果：进程存活（psutil 实测 pid 2116），日志无 [safe-delete] 行、无 traceback。
      （随后由我主动 kill，故 EXIT=15。）

启动会话关键行（E:\RalseiMemory\logs\ralsei_pet.log）：
    2026-09-16 22:54:12 [INFO] ralsei_pet.text_segmenter - 已启用 jieba 分词（用户词表: 无）
    Loading model from cache E:\RalseiMemory\cache\jieba.cache
    2026-09-16 22:54:12 [INFO] ...sprite_loader - [anim-config] 已从 animations.json 加载 109 组动画（legacy 28 组，schema=1）
    Loading model cost 0.981 seconds.
    Prefix dict has been built successfully.

为什么这次能起来（第十二轮补丁时不能）：
    memory_store._is_writable_dir 改了零副作用快路径 —— 健康盘上不再 建/写/删 .write_probe，
    于是不再累积撞上沙箱的"同轮同路径删除配额"（SAFE_DELETE_BULK_CONFIRM_REQUIRED）。
    第十二轮补丁把这条判成"确定性拦截、换轮次复跑照样拦"，第十三轮证伪：
    它是**按目标路径累计的删除计数**（本轮实测 count=51 / threshold=50 / targetCount=1），
    真正的触发源是应用自己每次启动十几次的探针写删。
