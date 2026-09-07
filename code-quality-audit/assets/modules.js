// 各模块详细问题数据
(function() {
  var modules = [
    {
      name: 'desktop_interaction.py',
      critical: 5,
      high: 9,
      medium: 12,
      low: 6,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: 'clean_temp_files 删除系统TEMP所有文件', desc: '无差别遍历删除，可能损坏其他应用数据', lines: '第 493-516 行' },
            { title: 'cut_file 剪切失败变复制', desc: '先复制后删除，删除失败时源文件残留', lines: '第 1394-1465 行' },
            { title: 'Office COM 进程泄漏', desc: '异常路径不释放COM对象，残留Office进程', lines: 'ppt_control/create_new_excel 等' },
            { title: '桌面图标位置与文件匹配错位', desc: '文件夹和文件独立分配位置导致重叠', lines: '第 706-776 行' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '文件操作前未检查权限', desc: '复制/移动/删除前不检查是否有足够权限', lines: '多处文件操作函数' },
            { title: '路径包含特殊字符处理', desc: '路径含空格、中文等特殊字符时可能出错', lines: '多处路径拼接' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '异常重试循环重复', desc: '多个函数都有类似的try-except-retry模式', lines: '多处' },
            { title: 'COM对象创建释放重复', desc: '每个Office函数都重复创建和释放逻辑', lines: 'Office相关函数' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '上帝类 2300+ 行', desc: '10+种职责耦合，违反单一职责原则', lines: '整个文件' },
            { title: '硬编码延迟值', desc: '0.5、0.3等魔法数字散落各处', lines: '多处' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '大量 except: pass', desc: '错误被完全静默吞噬，无法排查', lines: '数十处' },
            { title: '缺少错误恢复策略', desc: '操作失败后没有回滚或补偿机制', lines: '多处文件操作' }
          ]
        }
      ]
    },
    {
      name: 'sprite_loader.py',
      critical: 1,
      high: 4,
      medium: 10,
      low: 6,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '假 LRU 缓存（实际是FIFO）', desc: '命中时不更新顺序，淘汰取最早插入项', lines: '第 403-406 行' },
            { title: 'QPixmap加载失败完全静默', desc: '异常被吞噬，无法排查图片加载问题', lines: 'load_frame 方法' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '动画帧索引越界', desc: 'current_frame超过帧数时无保护', lines: 'get_current_frame' },
            { title: '空动画名称处理', desc: '传入空字符串或不存在的动画名' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '80+ 动画映射硬编码', desc: '大量动画名称到文件列表的映射手写', lines: 'animation_mapping' },
            { title: 'position_offset 100+ 全零条目', desc: '默认值就是(0,0)，这些条目完全冗余', lines: 'position_offset 字典' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '硬编码绝对路径', desc: '使用 c:/Users/... 绝对路径，无法跨平台', lines: 'sprite_dir/face_dir' },
            { title: '缓存非线程安全', desc: '多线程访问缓存可能出现竞态', lines: 'image_cache 操作' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: 'load_frame 捕获所有异常但不打印', desc: 'except Exception: pass 完全静默', lines: 'load_frame 方法' },
            { title: 'scan_and_group_assets 正则覆盖不全', desc: '复杂命名的精灵图可能无法正确分组' }
          ]
        }
      ]
    },
    {
      name: 'emotion_system.py',
      critical: 2,
      high: 3,
      medium: 6,
      low: 4,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '复合情绪衰减完全失效', desc: '衰减后立即被_update_complex_emotions重算覆盖', lines: '情绪更新循环' },
            { title: '个性调整累积缩放', desc: '每次事件情绪值乘系数，指数级偏离', lines: '_adjust_emotion_by_personality' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '情绪值上下限边界', desc: '情绪变化后可能超出0-100范围', lines: '情绪值修改处' },
            { title: '空事件类型处理', desc: '传入未知事件类型无默认行为' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '各情绪衰减逻辑重复', desc: '每种情绪都有类似的衰减计算代码' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '情绪规则硬编码', desc: '事件-情绪映射写死在代码中', lines: '事件处理逻辑' },
            { title: '个性系统扩展性差', desc: '新增个性维度需要改多处代码' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '核心方法几乎无异常保护', desc: '情绪计算出错可能导致整个系统崩溃', lines: 'update_emotions 等' },
            { title: '缺少日志输出', desc: '情绪状态变化无记录，调试困难' }
          ]
        }
      ]
    },
    {
      name: 'config_manager.py',
      critical: 1,
      high: 2,
      medium: 7,
      low: 4,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: 'is_encryption_enabled 永远返回False', desc: '与配置项完全脱节，开启加密无效', lines: '第 347-350 行' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '空字符串 key_path 产生垃圾数据', desc: 'config[""] 被创建', lines: 'set() 方法' },
            { title: 'UnicodeDecodeError 未捕获', desc: '非UTF-8配置文件导致崩溃', lines: '_load_config' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '6个配置get/update方法模式重复', desc: 'api/privacy/security各有一对get/update', lines: 'get_api_config等6个方法' },
            { title: 'key_path逐级创建字典逻辑重复', desc: 'set()和update()中各写了一遍' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '配置路径硬编码', desc: '不支持%APPDATA%和可移植模式', lines: '配置文件路径' },
            { title: '列表配置合并策略问题', desc: '列表型配置升级时用户自定义会被覆盖', lines: '_merge_configs' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '裸 except: pass 吞噬所有异常', desc: '备份失败不留痕，包括KeyboardInterrupt', lines: '第 130 行' },
            { title: '配置保存失败无回滚', desc: '内存已修改但磁盘保存失败，状态不一致', lines: 'update() 方法' }
          ]
        }
      ]
    },
    {
      name: 'api_client.py',
      critical: 0,
      high: 3,
      medium: 8,
      low: 6,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: 'agent_id 加到payload顶层', desc: '标准OpenAI API不认识，可能返回400', lines: 'chat() 方法' },
            { title: 'Logger只设level无handler', desc: '日志会丢失，用户看不到警告', lines: '日志初始化' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: 'temperature/max_tokens无范围校验', desc: '传入负数或超大值可能导致API错误', lines: 'chat() 参数处理' },
            { title: 'base_url为空时生成相对路径', desc: '请求发往错误地址', lines: 'chat_endpoint 属性' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: 'HTTP POST调用逻辑重复', desc: 'chat()和_post_json()中有重复的请求构造', lines: '两个方法' },
            { title: '三个command方法结构相同', desc: 'get_commands/send_status/execute_command几乎逐行相同' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '全局单例 _provider_factory', desc: '无法同时连接多个不同后端', lines: '全局变量' },
            { title: '认证方式只有Bearer Token', desc: '新增认证方式需改核心代码' },
            { title: 'stream硬编码为False', desc: '支持流式输出需要较大重构' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '所有失败统一返回None', desc: '无法区分超时/鉴权/限流/服务端错误', lines: '所有except分支' },
            { title: 'ABC抽象方法有默认空实现', desc: '子类漏实现不会报错，削弱了抽象约束', lines: 'HTTPLocalAI 类' }
          ]
        }
      ]
    },
    {
      name: 'autonomous_agent.py',
      critical: 1,
      high: 2,
      medium: 7,
      low: 6,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '暂停=取消 bug', desc: '冲突解除后任务被丢弃，不恢复执行', lines: '冲突处理逻辑' },
            { title: '整理桌面冷却逻辑缺陷', desc: '安全实现返回(0,0)仍消耗30分钟冷却', lines: '整理桌面任务' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '空任务队列处理', desc: '没有可执行任务时的状态处理' },
            { title: '任务执行超时保护', desc: '某个任务卡住会阻塞整个代理' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '状态判断逻辑重复', desc: '多处if-elif链判断当前状态' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '状态机硬编码在if-elif链', desc: '新增状态需要改动大量代码', lines: 'update 方法' },
            { title: '情绪系统访问路径脆弱', desc: 'desktop.parent.emotion_system 深层依赖', lines: '情绪访问处' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '6处 except Exception: pass', desc: '任务执行失败完全静默，调试困难', lines: '多处' },
            { title: '任务失败无重试机制', desc: '一次失败就放弃，没有重试策略' }
          ]
        }
      ]
    },
    {
      name: 'social_growth_system.py',
      critical: 1,
      high: 2,
      medium: 5,
      low: 4,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '成就随机解锁', desc: '10%概率随机解锁，与条件描述完全无关', lines: '第 474 行' },
            { title: '进化阶段计算错误', desc: '第一次进化(5级)阶段值不变，落后一个阶段', lines: '第 455-456 行' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '经验值溢出', desc: '升级后剩余经验值处理不当', lines: 'add_exp 方法' },
            { title: '等级上限处理', desc: '达到最高等级后经验值继续增长' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '数据保存/加载模式重复', desc: '多个系统都有类似的JSON读写模式' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '成就配置硬编码', desc: '新增成就需要改源码', lines: '成就定义' },
            { title: '等级曲线不可配置', desc: '经验需求公式写死在代码中' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '文件路径无目录存在检查', desc: '保存目录不存在时会报错', lines: 'save/load 方法' },
            { title: '数据损坏无降级', desc: '存档文件损坏后无法启动' }
          ]
        }
      ]
    },
    {
      name: 'pet_ai.py',
      critical: 0,
      high: 3,
      medium: 8,
      low: 5,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: 'energy和hunger调整用elif互斥', desc: '同一帧只能处理一个，另一个被忽略', lines: 'update_state 方法' },
            { title: '直接修改parent属性绕过状态机', desc: '多处直接设置parent的状态变量', lines: '多处parent.xxx = ...' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '随机概率边界', desc: '概率值可能超出0-1范围' },
            { title: '状态切换无冷却', desc: '可能在短时间内频繁切换状态' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '行为决策逻辑重复', desc: '多处类似的随机选择+概率判断模式' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '行为概率硬编码', desc: '调整行为频率需要改源码', lines: '各处random判断' },
            { title: '高度耦合parent对象', desc: '父类API改动影响整个AI', lines: 'self.parent 访问' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '主循环无外层异常保护', desc: 'AI更新出错可能导致整个程序崩溃', lines: 'update_state 方法' },
            { title: '无异步/非阻塞设计', desc: '复杂计算可能拖慢UI线程', lines: '主线程中运行' }
          ]
        }
      ]
    },
    {
      name: 'dialogue_system.py',
      critical: 0,
      high: 3,
      medium: 6,
      low: 5,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '死代码分支', desc: '部分条件分支永远不会执行到', lines: '多处' },
            { title: '对话模板三处重复', desc: '1000+行对话文本分散在三处', lines: '模板定义处' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '空输入处理', desc: '用户输入空字符串时的行为' },
            { title: '超长输入处理', desc: '输入超过模型限制时无截断' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '对话模板重复定义', desc: '三处相似的对话模板数据', lines: '模板定义' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '对话文本硬编码', desc: '修改回复内容需要改源码', lines: '对话模板' },
            { title: '多语言支持困难', desc: '所有文本写死，国际化成本高' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: 'generate_response无外层兜底', desc: '任何分支异常都会导致对话系统崩溃', lines: 'generate_response 方法' },
            { title: 'AI调用失败无降级', desc: 'API不可用时无本地备选回复' }
          ]
        }
      ]
    },
    {
      name: 'sound_manager.py',
      critical: 0,
      high: 2,
      medium: 6,
      low: 6,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '_media_player 定义但从未使用', desc: '死代码变量，可能导致混淆', lines: '实例变量定义' },
            { title: 'WAV和OGG播放失败完全静默', desc: 'except Exception: pass 零日志', lines: '播放方法' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '音量范围无校验', desc: '传入负数或超大值可能出错' },
            { title: '音频文件不存在处理', desc: '播放不存在的音效无友好提示' }
          ]
        },
        {
          title: '🔄 重复编码',
          issues: [
            { title: '各音效播放方法模式重复', desc: '每个音效都有类似的加载+播放逻辑' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '音频后端硬编码为PyQt5', desc: '没有抽象接口，难以更换后端', lines: '整个类' },
            { title: '音量硬编码为80', desc: '无全局音量控制配置', lines: '音量设置' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '整个类零日志', desc: '播放成功失败都没有任何记录', lines: '所有方法' },
            { title: '音频格式不兼容无降级', desc: '格式不支持时静默失败' }
          ]
        }
      ]
    },
    {
      name: 'weather_system.py',
      critical: 1,
      high: 1,
      medium: 3,
      low: 2,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '夜间概率不归一', desc: '调整后概率和<1，多余概率全fallback到sunny', lines: '第 84-104 行' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '天气API调用失败无缓存降级', desc: '网络异常时天气数据为空' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '天气API硬编码', desc: '更换天气服务商需要改代码', lines: 'API调用处' },
            { title: '更新间隔硬编码', desc: '刷新频率不可配置' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '阻塞请求无超时保护', desc: '网络慢时可能卡住UI', lines: 'update_weather 方法' }
          ]
        }
      ]
    },
    {
      name: 'search_summarizer.py',
      critical: 1,
      high: 1,
      medium: 2,
      low: 2,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '查询未URL编码', desc: '含特殊字符的查询会导致请求失效', lines: '第 16、60 行' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '搜索引擎硬编码', desc: '只支持Bing，难以扩展其他引擎', lines: '搜索URL构造' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '网络请求异常处理不足', desc: '超时、404等情况处理不完善' }
          ]
        }
      ]
    },
    {
      name: 'dialogue_ui.py',
      critical: 1,
      high: 2,
      medium: 3,
      low: 2,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: 'AI回调线程安全问题', desc: '非UI线程直接操作Qt控件', lines: '第 807-834 行' }
          ]
        },
        {
          title: '⚠️ 边界条件',
          issues: [
            { title: '超长文本显示', desc: '对话文本过长时UI布局问题' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: 'UI样式硬编码', desc: '主题、字体大小等不可配置' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: 'UI更新异常无保护', desc: '绘制异常可能导致整个窗口崩溃' }
          ]
        }
      ]
    },
    {
      name: 'main.py (主程序)',
      critical: 1,
      high: 3,
      medium: 5,
      low: 3,
      categories: [
        {
          title: '🐛 隐藏 Bug',
          issues: [
            { title: '单实例检查在模块顶层执行', desc: 'import就可能触发退出', lines: '第 6-96 行' },
            { title: '多定时器状态竞态', desc: '10+ QTimer并发修改状态变量', lines: '各处timer' }
          ]
        },
        {
          title: '🚀 拓展坑点',
          issues: [
            { title: '主文件 8000+ 行', desc: '上帝类，所有系统耦合在一起', lines: '整个文件' },
            { title: '状态变量散落', desc: '大量布尔和枚举分散，缺少统一管理' }
          ]
        },
        {
          title: '💥 异常处理',
          issues: [
            { title: '116+处 print 替代日志', desc: '无级别控制、无文件输出', lines: '各处print' },
            { title: 'PerformanceMonitor空实现', desc: 'print_stats什么都不做，装饰器未应用', lines: '性能监控类' }
          ]
        }
      ]
    }
  ];

  // 渲染模块列表
  var container = document.getElementById('module-list');
  if (!container) return;

  modules.forEach(function(mod, idx) {
    var section = document.createElement('div');
    section.className = 'module-section';

    var header = document.createElement('div');
    header.className = 'module-header';
    header.innerHTML = '\
      <div class="module-name">\
        <span>📄</span>\
        ' + mod.name + '\
      </div>\
      <div class="module-stats">\
        <span class="module-stat c">严 ' + mod.critical + '</span>\
        <span class="module-stat h">高 ' + mod.high + '</span>\
        <span class="module-stat m">中 ' + mod.medium + '</span>\
        <span class="module-stat l">低 ' + mod.low + '</span>\
        <span class="arrow">▼</span>\
      </div>\
    ';

    var body = document.createElement('div');
    body.className = 'module-body';

    mod.categories.forEach(function(cat) {
      var catDiv = document.createElement('div');
      catDiv.className = 'issue-category';
      catDiv.innerHTML = '<h5>' + cat.title + '（' + cat.issues.length + '）</h5>';

      cat.issues.forEach(function(issue) {
        var issueDiv = document.createElement('div');
        issueDiv.className = 'issue-item';
        issueDiv.innerHTML = '\
          <div class="issue-item-title">\
            <span>' + issue.title + '</span>\
          </div>\
          <div class="issue-item-desc">' + issue.desc + '</div>\
          <div class="issue-item-lines">' + (issue.lines || '') + '</div>\
        ';
        catDiv.appendChild(issueDiv);
      });

      body.appendChild(catDiv);
    });

    section.appendChild(header);
    section.appendChild(body);
    container.appendChild(section);
  });
})();
