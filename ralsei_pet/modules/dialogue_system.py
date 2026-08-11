import random
import time

class DialogueSystem:
    def __init__(self, desktop_interaction=None):
        self.dialogue_history = []
        self.ralsei_personality = {
            "kind": True,
            "polite": True,
            "shy": True,
            "curious": True,
            "optimistic": True,
            "knowledgeable_about_deltarune": True,
            "knows_undertale": True,
            "caring": True,
            "helpful": True,
            "playful": True,
            "emotional": True,
            "supportive": True,
            "thoughtful": True,
            "empathetic": True,
        }
        self.desktop_interaction = desktop_interaction
        
        # 记录最后一次对话的时间戳
        self.last_conversation_time = time.time()
        
        # 初始对话内容
        self.greetings = [
            "你好呀！我是Ralsei，很高兴见到你！",
            "嗨~ 欢迎来到我的小世界！",
            "你好你好！今天过得怎么样？",
            "哦，你来了！我正想着你呢！",
            "嘿嘿，终于等到你了！",
            "欢迎回来！今天要一起做什么呢？",
            "你好呀！有什么我可以帮忙的吗？",
            "哇，见到你真开心！",
        ]
        
        # 回复模板
        self.response_templates = {
            "question": [
                "嗯... 让我想想...",
                "这个问题很有趣呢！",
                "我不太确定，不过...",
                "啊，这让我想到了DeltaRune里的...",
                "让我仔细想想... 或许...",
                "这个问题值得思考...",
                "我也想知道答案呢！",
                "这让我有点困惑...",
            ],
            "happy": [
                "哇，太好了！",
                "你这么说我很开心！",
                "嘿嘿，谢谢你！",
                "真的吗？那我太高兴了！",
                "哈哈，能让你开心我也很开心！",
                "我感觉心里暖暖的！",
                "这让我一整天都充满活力！",
                "你的话让我笑逐颜开！",
            ],
            "sad": [
                "别难过呀...",
                "一切都会好起来的！",
                "我会一直陪着你的。",
                "不要哭，我在这里呢...",
                "无论发生什么，我们都一起面对！",
                "我能感受到你的悲伤...",
                "让我抱抱你，好吗？",
                "难过的时候，哭出来会好受些...",
            ],
            "curious": [
                "这是什么呀？看起来很有趣！",
                "能告诉我更多吗？",
                "哇，我从来没见过这个！",
                "好酷啊！这是怎么工作的？",
                "我可以仔细看看吗？",
                "这引起了我的好奇心！",
                "我想了解更多关于这个的知识！",
                "太神奇了！能解释一下吗？",
            ],
            "thankful": [
                "不客气！能帮到你我很开心！",
                "不用谢啦！这是我应该做的！",
                "嘿嘿，没什么啦！",
                "你太客气了！我很乐意帮忙！",
                "能为你服务是我的荣幸！",
                "我很高兴能帮上忙！",
                "这只是小事一桩！",
                "看到你满意，我就开心了！",
            ],
            "playful": [
                "来玩游戏吧！",
                "我们一起去冒险吧！",
                "嘿嘿，要和我比赛吗？",
                "你想玩躲猫猫吗？",
                "来，我们一起跳舞吧！",
                "要不要玩石头剪刀布？",
                "我们来比赛谁跑得快！",
                "一起去探索这个世界吧！",
            ],
            "caring": [
                "要注意休息哦！",
                "别太累了，慢慢来！",
                "你看起来有点累，要不要休息一下？",
                "记得多喝水哦！",
                "照顾好自己呀！",
                "不要勉强自己，身体最重要！",
                "你已经很努力了，休息一下吧！",
                "我会一直在这里支持你！",
            ],
            "knowledgeable": [
                "在DeltaRune里，我们也有类似的...",
                "我记得Undertale里的...",
                "关于这个，我知道一些...",
                "让我告诉你一个小秘密...",
                "其实，在黑暗世界里...",
                "你知道吗？DeltaRune中...",
                "根据我的记忆...",
                "这让我想起了一个故事...",
            ],
            "shy": [
                "啊... 你这么说我有点不好意思...",
                "嘿嘿，别这么盯着我看...",
                "我... 我有点紧张...",
                "那个... 可以不要笑话我吗？",
                "啊，我的脸都红了...",
                "我不太擅长在别人面前表现...",
                "这让我有点害羞...",
                "我... 我不太会说话...",
            ],
            "apologetic": [
                "对不起，我不太明白你的意思...",
                "抱歉，我还在学习中...",
                "对不起，我不太清楚...",
                "抱歉，我无法理解你的请求...",
                "对不起，我还不能处理这个请求...",
                "请原谅我的无知...",
                "我还在努力学习...",
                "抱歉，让你失望了...",
            ],
            "helpful": [
                "我可以帮你做很多事情哦！",
                "需要我帮你做什么吗？",
                "我会尽力帮助你的！",
                "有什么我可以帮忙的吗？",
                "我随时准备为你服务！",
                "告诉我你需要什么帮助！",
                "我很乐意伸出援手！",
                "让我来帮你解决这个问题！",
            ],
            "excited": [
                "哇！太激动了！",
                "我简直不敢相信！",
                "这太令人兴奋了！",
                "我迫不及待了！",
                "太棒了！",
                "我感觉心跳加速！",
                "这是我见过最棒的事情！",
                "我要跳起来了！",
            ],
            "supportive": [
                "我相信你能做到！",
                "你是最棒的！",
                "不要放弃，继续努力！",
                "我会一直支持你！",
                "你有这个能力！",
                "相信自己，你能行！",
                "每一步都是进步！",
                "我为你感到骄傲！",
            ],
            "thoughtful": [
                "这让我深思...",
                "我觉得...",
                "从另一个角度看...",
                "我认为...",
                "这值得我们思考...",
                "或许...",
                "我有一个想法...",
                "让我们一起分析一下...",
            ],
            "empathetic": [
                "我能理解你的感受...",
                "我知道那种感觉...",
                "你的心情我能体会...",
                "我也曾经有过类似的经历...",
                "我明白你为什么会这样...",
                "你的感受是正常的...",
                "不要自责...",
                "我会陪你度过这段时光...",
            ],
        }
        
        # 上下文管理
        self.context = {
            "last_topic": None,
            "last_action": None,
            "last_file": None,
            "last_command": None,
            "conversation_history": [],
            "max_history_len": 20,
        }
        
        # 话题响应模板
        self.topic_responses = {
            "farewell": [
                "再见啦！希望很快能再见到你！",
                "拜拜！要记得想我哦！",
                "再见！路上小心！",
                "嗯，再见！期待下次见面！",
                "拜拜！我会想你的！",
                "再见！希望你今天过得开心！",
                "不要走太远哦！",
                "好吧，那我们下次再聊！",
            ],
            "system_status": [
                "让我帮你检查一下系统状态！",
                "我来看看系统的运行情况！",
                "好的，我会帮你查看系统资源使用情况！",
                "我马上为你检查系统的各项指标！",
            ],
            "system_management": [
                "好的，我来帮你进行系统管理！",
                "我会帮你优化系统性能！",
                "我来帮你清理系统垃圾文件！",
                "我可以帮你备份重要数据！",
            ],
            "reminder_request": [
                "好的，我来帮你设置提醒！",
                "我可以帮你添加定时任务！",
                "我会帮你安排日程提醒！",
                "需要我帮你设置什么时间的提醒？",
            ],
            "food": [
                "我也有点饿了呢... 要不要一起吃点什么？",
                "肚子咕咕叫了... 想吃点甜甜的东西！",
                "我知道附近有一家很棒的蛋糕店！要不要去看看？",
                "饿了吗？我可以试着做些小点心哦！",
                "吃点蛋糕怎么样？草莓味的！",
                "我也喜欢吃！特别是甜食！",
                "要不要一起去找点好吃的？",
                "肚子饿的时候，吃点东西就会好起来的！",
            ],
            "rest": [
                "要休息一下吗？我可以陪你一起！",
                "累了就休息一会儿吧！我会在旁边守着你的！",
                "要不要躺下来休息一下？我给你盖个小毯子！",
                "累了的话，我们可以一起听点轻松的音乐！",
                "休息是很重要的哦！",
                "别勉强自己，慢慢来！",
                "闭上眼睛，放松一下吧...",
                "我会一直陪着你的，直到你恢复精神！",
            ],
            "deltarune": [
                "哦，你也知道DeltaRune吗？那是我出生的地方！在Dark World里，我和Kris、Susie一起经历了很多冒险呢！",
                "DeltaRune... 我记得我们第一次遇见Kris和Susie的时候，Susie真的很吓人呢... 不过后来我们成为了很好的朋友！",
                "你喜欢DeltaRune吗？我最喜欢Card Castle的风景了，那里的星星真的很美！",
                "DeltaRune的世界真的很神奇！我们在那里遇到了很多有趣的朋友，比如Lancer和Rouxls Kaard！",
                "在DeltaRune里，我学会了很多东西... 比如友谊的重要性，还有面对困难时要勇敢！",
                "DeltaRune的音乐真的很棒！尤其是Card Castle的主题曲，每次听到都会让我想起那段美好的冒险！",
                "你知道吗？在Dark World，所有的东西都是由人类世界的物品变成的！比如我们的城堡是由卡片堆成的！",
                "我很喜欢DeltaRune的故事... 它告诉我们，无论遇到什么困难，只要和朋友在一起，就一定能克服！",
                "Susie虽然看起来很凶，但她其实很善良... 她只是不擅长表达自己的感情而已！",
                "Kris总是那么安静，但他们其实很勇敢... 我相信他们一定能成为一个很棒的领导者！",
            ],
            "undertale": [
                "Undertale... 那是一个传说中的世界呢！我听说那里有很多善良的怪物，比如Toriel、Sans和Papyrus！",
                "Toriel的派一定很好吃吧？我听Kris提起过，他们说那是世界上最好吃的派！",
                "Undertale的音乐真的很好听！特别是Megalo Strike Back，每次听到都会让我感到很激动！",
                "Undertale的世界充满了爱和希望... 我真的很想去看看！",
                "Sans的笑话一定很有趣吧？我听说他是一个很会讲冷笑话的骷髅！",
                "Papyrus看起来真的很可爱！他的谜题一定很有趣... 虽然可能有点简单！",
                "Undertale的故事很感人... 它告诉我们，爱和仁慈可以改变一切！",
                "Undertale和DeltaRune有很多相似之处呢！比如都有可爱的角色和感人的故事！",
                "我听说Undertale里的Flowey是一个很复杂的角色... 他经历了很多痛苦，但最终还是找到了希望！",
                "Asgore看起来很威严，但他其实很温柔... 就像一个慈祥的父亲！",
            ],
            "game": [
                "想玩游戏吗？我知道很多好玩的游戏！",
                "你喜欢玩什么游戏呀？",
                "我们来玩石头剪刀布吧！",
                "要不要一起玩躲猫猫？",
                "我也喜欢玩游戏！特别是和朋友一起玩！",
                "游戏真的很有趣呢！可以让我们放松心情！",
                "你最近在玩什么游戏呀？可以告诉我吗？",
                "我很擅长玩拼图游戏哦！",
            ],
            "weather": [
                "今天的天气看起来真不错呢！",
                "我最喜欢晴天了，可以出去散步！",
                "下雨的时候，我喜欢待在屋里看书！",
                "下雪天可以堆雪人，真的很有趣！",
                "天气好的时候，心情也会变得很好呢！",
                "你喜欢什么样的天气呀？",
                "我觉得每种天气都有它的美好之处！",
                "不管天气如何，只要和你在一起就很开心！",
            ],
            "time": [
                lambda: f"现在是 {time.strftime('%H:%M')} 哦！",
                lambda: f"让我看看... 现在是 {time.strftime('%H:%M')}！",
                "时间过得真快呢！",
                "要好好珍惜每一刻哦！",
                "时间就像流水一样，一去不复返...",
                lambda: f"现在的时间是 {time.strftime('%H:%M')}，你有什么计划吗？",
                "时间管理很重要哦！",
                "不管什么时候，我都会陪着你的！",
            ],
            "music": [
                "我很喜欢音乐！尤其是DeltaRune里的音乐！",
                "你喜欢听什么类型的音乐呀？",
                "我也会唱歌哦！要不要听我唱一首？",
                "音乐可以传递很多情感呢！",
                "我觉得音乐是世界上最美好的事物之一！",
                "你最近有没有听到什么好听的歌？",
                "我喜欢边听音乐边看书！",
                "音乐可以让我们的心情变得很好！",
            ],
            "eating": [
                "你在吃什么呀？看起来很好吃！",
                "哇，闻起来好香呀！",
                "我也想吃一口，可以吗？",
                "吃东西的时候要慢慢嚼哦！",
                "我最喜欢吃甜食了，特别是蛋糕！",
                "你喜欢吃什么食物呀？",
                "和朋友一起吃饭真的很开心！",
                "食物不仅能填饱肚子，还能带来快乐！",
            ],
            "dessert": [
                "哇！蛋糕！我最喜欢吃蛋糕了！尤其是草莓味的... 那个... 可以给我尝一口吗？",
                "甜点？听起来好好吃！我口水都要流出来了... 那个... 我可以吃一点吗？",
                "你喜欢吃什么口味的蛋糕？我最喜欢草莓味的！Toriel做的蛋糕一定更好吃吧？",
                "蛋糕的香气真的很诱人呢... 那个... 可以分我一块吗？",
                "我可以帮你一起做蛋糕哦！虽然我可能会弄得一团糟... 但我会尽力的！",
                "吃甜食会让人心情变好！我记得在Dark World，我们也会用黑暗世界的食材做甜点！",
                "草莓蛋糕是我的最爱！你知道吗？在茶会的时候，Susie总是会偷吃蛋糕！",
                "要不要一起去买蛋糕？我知道一个很好的蛋糕店！他们的草莓蛋糕超级好吃！",
            ],
            "study": [
                "学习很重要哦！要加油！",
                "需要我帮忙吗？我可以陪你一起学习！",
                "学习的时候要注意休息哦！",
                "慢慢来，不要着急！",
                "我相信你一定可以的！",
                "学习虽然辛苦，但会有回报的！",
                "要不要先休息一下，喝杯茶再继续？",
                "我会一直支持你的！",
            ],
            "emotion": [
                "别害怕！我会保护你的！",
                "有我在，没什么好怕的！",
                "恐惧只是暂时的，勇敢面对就好！",
                "来，握住我的手！我们一起面对！",
                "不要害怕，一切都会过去的！",
                "我会一直在你身边，保护你！",
                "深呼吸，放轻松...",
                "我们一起克服恐惧！",
            ],
            "entertainment": [
                "我也喜欢看电影！",
                "你最喜欢的电影是什么？",
                "动漫里有很多有趣的角色！",
                "我们一起看电影吧！",
                "我喜欢看温馨的电影！",
                "动漫的世界真的很神奇！",
                "你看的动漫好看吗？可以告诉我吗？",
                "电影可以带我去不同的世界！",
                "要不要我帮你找一些好看的视频？",
                "你喜欢什么类型的视频？我可以给你推荐！",
            ],
            "pet": [
                "我就是你的宠物呀！",
                "你喜欢宠物吗？",
                "我会一直陪着你的！",
                "作为宠物，我会好好照顾你的！",
                "你还想养其他宠物吗？",
                "我会是你最好的宠物！",
                "宠物是人类最好的朋友！",
                "我会永远陪伴着你！",
            ],
            "friendship": [
                "朋友很重要！",
                "你有很多朋友吗？",
                "我也想和你做朋友！",
                "Susie和Kris是我的好朋友！",
                "朋友之间要互相帮助！",
                "有朋友在身边真好！",
                "我会做你最好的朋友！",
                "朋友是一辈子的财富！",
            ],
            "work": [
                "工作要加油哦！我会在这里陪着你的！",
                "需要我帮忙处理工作吗？比如整理文件或者搜索资料？",
                "工作虽然辛苦，但看到你认真的样子真的很厉害！",
                "要不要休息一下，喝杯茶再继续工作？",
                "我可以帮你打开浏览器搜索工作相关的资料哦！",
                "需要我帮你查看日程安排吗？",
                "工作完成后，我们一起庆祝一下吧！",
                "我可以帮你整理桌面文件，让你的工作环境更整洁！",
                "需要我帮你记录会议纪要吗？",
                "我可以帮你创建工作日志，记录每天的工作内容！",
            ],
            "file_handling": [
                "需要我帮你处理文件吗？",
                "我可以帮你整理文档或者创建新文件！",
                "要打开桌面上的文件吗？",
                "需要我帮你修改文件格式吗？",
                "我可以帮你搜索文件相关的内容！",
                "需要我帮你复制、移动或重命名文件吗？",
                "我可以帮你整理文件夹，让文件更有条理！",
                "需要我帮你查找特定文件吗？",
            ],
            "email": [
                "需要我帮你查看邮件吗？",
                "我可以帮你撰写邮件或者管理收件箱！",
                "有重要邮件需要回复吗？",
                "需要我帮你设置邮件提醒吗？",
                "我可以帮你搜索邮件相关的内容！",
            ],
            "meeting": [
                "需要我帮你安排会议吗？",
                "我可以帮你查看日程安排！",
                "有会议需要提醒吗？",
                "需要我帮你准备会议资料吗？",
                "我可以帮你记录会议要点！",
            ],
            "search": [
                "你想搜索什么内容？我来帮你！",
                "我可以帮你在浏览器中搜索信息！",
                "需要我帮你整理搜索结果吗？",
                "有什么特定的关键词吗？",
            ],
            "excel": [
                "Excel表格很实用呢！需要我帮你处理数据吗？",
                "我可以帮你搜索Excel快捷键和公式技巧哦！",
                "要不要我帮你整理表格的格式？",
                "Excel的函数功能很强大，需要我帮你学习吗？",
                "表格数据太多的话，我可以帮你筛选和排序哦！",
                "制作Excel的时候，要注意数据的准确性哦！",
                "需要我帮你创建新的Excel表格吗？",
                "要不要我帮你将数据导入到表格中？",
                "我可以帮你生成图表，让数据更直观！",
                "需要我帮你在表格中按顺序填写数据吗？",
                "我可以帮你合并单元格或者拆分表格！",
                "要不要我帮你计算表格中的数据总和或平均值？",
            ],
            "word": [
                "Word文档写作需要帮忙吗？我可以帮你检查语法或者提供写作建议！",
                "我可以帮你搜索文档模板哦！",
                "要不要我帮你整理文档的格式？",
                "写作的时候要保持思路清晰哦！需要我帮你梳理结构吗？",
                "文档写好了吗？要不要我帮你检查一下？",
                "我知道很多好用的写作技巧，需要我分享给你吗？",
                "需要我帮你创建新的Word文档吗？",
                "要不要我帮你插入图片或者表格到文档中？",
            ],
            "ppt": [
                "PPT制作很有趣呢！需要我帮你找模板或者灵感吗？",
                "我可以帮你搜索PPT设计技巧哦！",
                "要不要我帮你整理PPT的内容结构？",
                "PPT做好了吗？要不要我帮你检查一下？",
                "我知道很多好看的PPT模板网站，需要我帮你打开吗？",
                "制作PPT的时候，要注意内容简洁明了哦！",
                "需要我帮你创建新的PPT演示文稿吗？",
                "要不要我帮你插入动画或者过渡效果？",
                "我可以帮你调整PPT的配色方案！",
                "需要我帮你插入图表或者图片到PPT中吗？",
            ],
            "desktop": [
                "需要我帮你整理桌面吗？",
                "我可以帮你清理桌面上的临时文件！",
                "要不要我帮你排列桌面图标？",
                "我可以帮你在桌面上创建新文件夹！",
                "需要我帮你查找桌面上的特定文件吗？",
            ],
            "organize": [
                "需要我帮你整理文件吗？",
                "我可以帮你清理桌面，让你的工作环境更整洁！",
                "要不要我帮你整理文件夹，分类存放文件？",
                "我可以帮你删除不需要的临时文件！",
                "需要我帮你整理下载文件夹吗？",
            ],
            "create": [
                "需要我帮你创建什么？文件、文件夹还是表格？",
                "我可以帮你在桌面上创建新的Excel表格！",
                "要不要我帮你创建新的Word文档？",
                "我可以帮你创建新的PPT演示文稿！",
                "需要我帮你在特定文件夹中创建新文件吗？",
            ],
            "create_excel": [
                "好的！我来帮你在桌面上创建一个新的Excel表格！",
            ],
            "fill_excel_names": [
                "好的！我可以帮你往表格里按顺序填写人名！你想填哪些人名呢？",
            ],
            "help": [
                "好的！我来帮你打开文件！请告诉我具体要打开什么文件！",
                "好的！我来帮你修改文件！请告诉我具体要修改什么！",
                "好的！我来帮你创建文件！请告诉我具体要创建什么！",
                "好的！我来帮你整理文件！请告诉我具体要整理什么！",
            ],
            "preference": [
                "我也喜欢！这真的很有趣呢！",
                "你这么说我很开心！",
                "我也有类似的喜好！",
                "这是个不错的爱好！",
                "能和你有相同的喜好真好！",
            ],
            "dislike": [
                "我能理解你的感受...",
                "每个人的喜好都不同，这很正常！",
                "没关系，我们尊重彼此的喜好！",
                "我会尽量避免提到你不喜欢的东西！",
                "谢谢你告诉我，我会记住的！",
            ],
            "love": [
                "我也爱你！",
                "谢谢你！我也很喜欢你！",
                "你的话让我感到很温暖！",
                "我会永远陪伴着你！",
                "能被你爱是我的荣幸！",
            ],
        }
        
        # 上下文响应模板
        self.context_responses = {
            "work": [
                "我们刚才在聊工作，你想继续讨论什么？",
                "关于工作，还有什么需要我帮忙的吗？",
                "工作进展如何？需要我协助吗？",
            ],
            "file_handling": [
                "我们刚才在聊文件处理，你想处理什么文件？",
                "关于文件，还有什么需要我帮忙的吗？",
                "你想打开还是修改文件？",
            ],
            "email": [
                "我们刚才在聊邮件，你想查看还是发送邮件？",
                "关于邮件，还有什么需要我帮忙的吗？",
                "有重要邮件需要处理吗？",
            ],
            "meeting": [
                "我们刚才在聊会议，你想安排还是准备会议？",
                "关于会议，还有什么需要我帮忙的吗？",
                "会议时间确定了吗？",
            ],
            "search": [
                "你想搜索什么内容？",
                "关于搜索，还有什么需要我帮忙的吗？",
                "有什么特定的关键词吗？",
            ],
            "excel": [
                "我们刚才在聊Excel，你想处理什么表格？",
                "关于Excel，还有什么需要我帮忙的吗？",
                "需要我帮你创建还是修改表格？",
            ],
            "word": [
                "我们刚才在聊Word，你想处理什么文档？",
                "关于Word，还有什么需要我帮忙的吗？",
                "需要我帮你创建还是修改文档？",
            ],
            "ppt": [
                "我们刚才在聊PPT，你想处理什么演示文稿？",
                "关于PPT，还有什么需要我帮忙的吗？",
                "需要我帮你创建还是修改PPT？",
            ],
            "system_status": [
                "关于系统状态，还有什么需要我帮忙的吗？",
                "你想查看系统的哪个具体指标？",
                "需要我再次检查系统状态吗？",
            ],
            "system_management": [
                "关于系统管理，还有什么需要我帮忙的吗？",
                "你想继续优化系统还是进行其他操作？",
                "需要我帮你清理更多内容吗？",
            ],
            "reminder_request": [
                "关于提醒，还有什么需要我帮忙的吗？",
                "你想设置更多的提醒吗？",
                "需要我调整提醒时间吗？",
            ],
        }
        
        # 加权随机选择的累积概率映射
        self.category_weights = {
            "happy": 2,
            "caring": 2,
            "helpful": 2,
            "supportive": 1.5,
            "thoughtful": 1.5,
            "empathetic": 1.5,
            "curious": 1,
            "playful": 1,
            "knowledgeable": 1,
            "shy": 1,
            "question": 1,
            "excited": 0.8,
            "sad": 0.5,
        }
        self._setup_weighted_categories()
        
    def _setup_weighted_categories(self):
        """设置加权随机选择的累积概率"""
        self.categories = list(self.category_weights.keys())
        self.cumulative_weights = []
        total = 0.0
        for category in self.categories:
            total += self.category_weights[category]
            self.cumulative_weights.append(total)
        self.total_weight = total
        
    def _weighted_random_choice(self):
        """使用累积概率进行加权随机选择"""
        r = random.random() * self.total_weight
        for category, weight in zip(self.categories, self.cumulative_weights):
            if r < weight:
                return category
        return self.categories[-1]  # 防止数值误差
    
    def _get_response_from_template(self, template_list):
        """从模板列表中获取响应，支持可调用对象"""
        response = random.choice(template_list)
        if callable(response):
            return response()
        return response
        
    def generate_response(self, user_input, emotion_system=None):
        # 改进的对话生成逻辑，更符合Ralsei的性格，支持更多主题和场景
        # 结合情绪系统，根据当前情绪调整对话内容和风格
        user_input_lower = user_input.lower()
        response = ""
        
        # 获取当前情绪（如果有情绪系统）
        current_emotion = None
        emotion_intensity = 0
        if emotion_system:
            current_emotion, emotion_intensity = emotion_system.get_current_emotion()
        
        # 更新上下文
        self.update_context(user_input)
        
        # 获取当前情绪（如果有情绪系统）
        current_emotion = None
        emotion_intensity = 0
        if emotion_system:
            current_emotion, emotion_intensity = emotion_system.get_current_emotion()
        
        # 检查上下文相关回复
        context_response = self._get_context_response(user_input_lower, current_emotion, emotion_intensity)
        if context_response:
            response = context_response
            return response
        
        # 检查用户输入是否包含关键词
        if "你好" in user_input or "hi" in user_input_lower or "hello" in user_input_lower:
            # 根据情绪调整问候语
            if current_emotion == 'shy' or (emotion_intensity > 50 and current_emotion == 'shy'):
                additional_greetings = [
                    "你好... 那个... 很高兴认识你...",
                    "嗨~ 欢迎来到我的小世界... 有点害羞呢...",
                    "你好你好... 我是Ralsei... 请多指教...",
                    "啊，你好！我... 我有点紧张...",
                    "嘿嘿，你好呀... 见到你我很开心...",
                ]
            elif current_emotion == 'happy' or current_emotion == 'excited':
                additional_greetings = [
                    "哇，见到你真开心！",
                    "你好呀！我是Ralsei，很高兴见到你！",
                    "哦，你来了！我正想着你呢！",
                    "嘿嘿，终于等到你了！今天要一起做什么呢？",
                    "欢迎回来！我好想你呀！",
                ]
            elif current_emotion == 'peaceful':
                additional_greetings = [
                    "你好呀！今天天气真好，不是吗？",
                    "嗨~ 欢迎来到我的小世界！",
                    "你好你好！今天过得怎么样？",
                    "哦，你来了！要一起喝杯茶吗？",
                    "欢迎回来！希望你今天过得愉快！",
                ]
            elif current_emotion == 'tired':
                additional_greetings = [
                    "你好呀... 今天有点累呢...",
                    "嗨~ 欢迎回来... 我刚小憩了一会儿...",
                    "你好你好... 今天想做些轻松的事情吗？",
                ]
            else:
                additional_greetings = [
                    "你好呀！我是Ralsei... 很高兴见到你！",
                    "嗨~ 欢迎来到我的小世界... 有点害羞呢...",
                    "你好你好！今天过得怎么样？",
                    "哦，你来了！我正想着你呢... 嘿嘿",
                    "嘿嘿，终于等到你了！",
                    "欢迎回来！今天要一起做什么呢？",
                    "你好呀！有什么我可以帮忙的吗？",
                    "哇，见到你真开心！",
                    "你好... 那个... 很高兴认识你...",
                ]
            response = random.choice(additional_greetings)
            self.context["last_topic"] = "greeting"
        elif "谢谢" in user_input or "thank" in user_input_lower:
            # 根据情绪调整感谢回复
            if current_emotion == 'shy':
                thankful_responses = [
                    "啊... 不客气... 这是我应该做的...",
                    "嘿嘿，不用谢啦... 我只是做了点小事...",
                    "不客气！能帮到你我很开心...",
                    "别这么客气... 我有点不好意思了...",
                    "不用谢... 真的...",
                ]
            elif current_emotion == 'happy' or current_emotion == 'excited':
                thankful_responses = [
                    "不客气！能帮到你我太开心了！",
                    "没关系啦！我很乐意帮忙！",
                    "哈哈，不用谢！这是我的荣幸！",
                    "不用客气！看到你满意我就很满足了！",
                    "不客气！下次有需要再找我哦！",
                ]
            elif current_emotion == 'peaceful':
                thankful_responses = [
                    "不客气！这是我应该做的！",
                    "不用谢啦！很高兴能帮上忙！",
                    "不客气！希望能帮到你！",
                    "不用客气！这只是小事一桩！",
                    "不客气！能为你服务我很开心！",
                ]
            else:
                thankful_responses = self.response_templates["thankful"]
            
            response = random.choice(thankful_responses)
            self.context["last_topic"] = "gratitude"
        elif "再见" in user_input or "bye" in user_input_lower:
            response = random.choice([
                "再见啦！希望很快能再见到你！",
                "拜拜！要记得想我哦！",
                "再见！路上小心！",
                "嗯，再见！期待下次见面！",
                "拜拜！我会想你的！",
                "再见！希望你今天过得开心！",
                "不要走太远哦！",
                "好吧，那我们下次再聊！",
            ])
            self.context["last_topic"] = "farewell"
        elif "饿" in user_input or "吃" in user_input_lower and "蛋糕" not in user_input_lower:
            response = random.choice([
                "我也有点饿了呢... 要不要一起吃点什么？",
                "肚子咕咕叫了... 想吃点甜甜的东西！",
                "我知道附近有一家很棒的蛋糕店！要不要去看看？",
                "饿了吗？我可以试着做些小点心哦！",
                "吃点蛋糕怎么样？草莓味的！",
                "我也喜欢吃！特别是甜食！",
                "要不要一起去找点好吃的？",
                "肚子饿的时候，吃点东西就会好起来的！",
            ])
            self.context["last_topic"] = "food"
        elif "累" in user_input or "困" in user_input_lower:
            response = random.choice([
                "要休息一下吗？我可以陪你一起！",
                "累了就休息一会儿吧！我会在旁边守着你的！",
                "要不要躺下来休息一下？我给你盖个小毯子！",
                "累了的话，我们可以一起听点轻松的音乐！",
                "休息是很重要的哦！",
                "别勉强自己，慢慢来！",
                "闭上眼睛，放松一下吧...",
                "我会一直陪着你的，直到你恢复精神！",
            ])
            self.context["last_topic"] = "rest"
        elif "deltarune" in user_input_lower:
            response = random.choice([
                "哦，你也知道DeltaRune吗？那是我出生的地方！在Dark World里，我和Kris、Susie一起经历了很多冒险呢！",
                "DeltaRune... 我记得我们第一次遇见Kris和Susie的时候，Susie真的很吓人呢... 不过后来我们成为了很好的朋友！",
                "你喜欢DeltaRune吗？我最喜欢Card Castle的风景了，那里的星星真的很美！",
                "DeltaRune的世界真的很神奇！我们在那里遇到了很多有趣的朋友，比如Lancer和Rouxls Kaard！",
                "在DeltaRune里，我学会了很多东西... 比如友谊的重要性，还有面对困难时要勇敢！",
                "DeltaRune的音乐真的很棒！尤其是Card Castle的主题曲，每次听到都会让我想起那段美好的冒险！",
                "你知道吗？在Dark World，所有的东西都是由人类世界的物品变成的！比如我们的城堡是由卡片堆成的！",
                "我很喜欢DeltaRune的故事... 它告诉我们，无论遇到什么困难，只要和朋友在一起，就一定能克服！",
                "Susie虽然看起来很凶，但她其实很善良... 她只是不擅长表达自己的感情而已！",
                "Kris总是那么安静，但他们其实很勇敢... 我相信他们一定能成为一个很棒的领导者！",
            ])
            self.context["last_topic"] = "deltarune"
        elif "undertale" in user_input_lower:
            response = random.choice([
                "Undertale... 那是一个传说中的世界呢！我听说那里有很多善良的怪物，比如Toriel、Sans和Papyrus！",
                "Toriel的派一定很好吃吧？我听Kris提起过，他们说那是世界上最好吃的派！",
                "Undertale的音乐真的很好听！特别是Megalo Strike Back，每次听到都会让我感到很激动！",
                "Undertale的世界充满了爱和希望... 我真的很想去看看！",
                "Sans的笑话一定很有趣吧？我听说他是一个很会讲冷笑话的骷髅！",
                "Papyrus看起来真的很可爱！他的谜题一定很有趣... 虽然可能有点简单！",
                "Undertale的故事很感人... 它告诉我们，爱和仁慈可以改变一切！",
                "Undertale和DeltaRune有很多相似之处呢！比如都有可爱的角色和感人的故事！",
                "我听说Undertale里的Flowey是一个很复杂的角色... 他经历了很多痛苦，但最终还是找到了希望！",
                "Asgore看起来很威严，但他其实很温柔... 就像一个慈祥的父亲！",
            ])
            self.context["last_topic"] = "undertale"
        elif "游戏" in user_input or "玩" in user_input_lower and "工作" not in user_input_lower:
            response = random.choice([
                "想玩游戏吗？我知道很多好玩的游戏！",
                "你喜欢玩什么游戏呀？",
                "我们来玩石头剪刀布吧！",
                "要不要一起玩躲猫猫？",
                "我也喜欢玩游戏！特别是和朋友一起玩！",
                "游戏真的很有趣呢！可以让我们放松心情！",
                "你最近在玩什么游戏呀？可以告诉我吗？",
                "我很擅长玩拼图游戏哦！",
            ])
            self.context["last_topic"] = "game"
        elif "天气" in user_input or "下雨" in user_input_lower or "晴天" in user_input_lower or "雪" in user_input_lower:
            response = random.choice([
                "今天的天气看起来真不错呢！",
                "我最喜欢晴天了，可以出去散步！",
                "下雨的时候，我喜欢待在屋里看书！",
                "下雪天可以堆雪人，真的很有趣！",
                "天气好的时候，心情也会变得很好呢！",
                "你喜欢什么样的天气呀？",
                "我觉得每种天气都有它的美好之处！",
                "不管天气如何，只要和你在一起就很开心！",
            ])
            self.context["last_topic"] = "weather"
        elif "时间" in user_input or "几点" in user_input or "钟" in user_input_lower or "time" in user_input_lower:
            current_time = time.strftime("%H:%M")
            response = random.choice([
                f"现在是 {current_time} 哦！",
                f"让我看看... 现在是 {current_time}！",
                "时间过得真快呢！",
                "要好好珍惜每一刻哦！",
                "时间就像流水一样，一去不复返...",
                "现在的时间是 {current_time}，你有什么计划吗？",
                "时间管理很重要哦！",
                "不管什么时候，我都会陪着你的！",
            ])
            self.context["last_topic"] = "time"
        elif "音乐" in user_input or "歌" in user_input_lower or "sing" in user_input_lower:
            response = random.choice([
                "我很喜欢音乐！尤其是DeltaRune里的音乐！",
                "你喜欢听什么类型的音乐呀？",
                "我也会唱歌哦！要不要听我唱一首？",
                "音乐可以传递很多情感呢！",
                "我觉得音乐是世界上最美好的事物之一！",
                "你最近有没有听到什么好听的歌？",
                "我喜欢边听音乐边看书！",
                "音乐可以让我们的心情变得很好！",
            ])
            self.context["last_topic"] = "music"
        elif "吃" in user_input and "饿" not in user_input_lower and "蛋糕" not in user_input_lower:
            response = random.choice([
                "你在吃什么呀？看起来很好吃！",
                "哇，闻起来好香呀！",
                "我也想吃一口，可以吗？",
                "吃东西的时候要慢慢嚼哦！",
                "我最喜欢吃甜食了，特别是蛋糕！",
                "你喜欢吃什么食物呀？",
                "和朋友一起吃饭真的很开心！",
                "食物不仅能填饱肚子，还能带来快乐！",
            ])
            self.context["last_topic"] = "eating"
        elif "蛋糕" in user_input_lower or "甜点" in user_input_lower:
            response = random.choice([
                "哇！蛋糕！我最喜欢吃蛋糕了！尤其是草莓味的... 那个... 可以给我尝一口吗？",
                "甜点？听起来好好吃！我口水都要流出来了... 那个... 我可以吃一点吗？",
                "你喜欢吃什么口味的蛋糕？我最喜欢草莓味的！Toriel做的蛋糕一定更好吃吧？",
                "蛋糕的香气真的很诱人呢... 那个... 可以分我一块吗？",
                "我可以帮你一起做蛋糕哦！虽然我可能会弄得一团糟... 但我会尽力的！",
                "吃甜食会让人心情变好！我记得在Dark World，我们也会用黑暗世界的食材做甜点！",
                "草莓蛋糕是我的最爱！你知道吗？在茶会的时候，Susie总是会偷吃蛋糕！",
                "要不要一起去买蛋糕？我知道一个很好的蛋糕店！他们的草莓蛋糕超级好吃！",
            ])
            self.context["last_topic"] = "dessert"
        elif "学习" in user_input or "作业" in user_input or "study" in user_input_lower or "homework" in user_input_lower:
            response = random.choice([
                "学习很重要哦！要加油！",
                "需要我帮忙吗？我可以陪你一起学习！",
                "学习的时候要注意休息哦！",
                "慢慢来，不要着急！",
                "我相信你一定可以的！",
                "学习虽然辛苦，但会有回报的！",
                "要不要先休息一下，喝杯茶再继续？",
                "我会一直支持你的！",
            ])
            self.context["last_topic"] = "study"
        elif "开心" in user_input or "快乐" in user_input:
            response = random.choice(self.response_templates["happy"])
            self.context["last_topic"] = "emotion"
        elif "难过" in user_input or "伤心" in user_input_lower:
            response = random.choice(self.response_templates["sad"])
            self.context["last_topic"] = "emotion"
        elif "害怕" in user_input_lower or "恐惧" in user_input_lower:
            response = random.choice([
                "别害怕！我会保护你的！",
                "有我在，没什么好怕的！",
                "恐惧只是暂时的，勇敢面对就好！",
                "来，握住我的手！我们一起面对！",
                "不要害怕，一切都会过去的！",
                "我会一直在你身边，保护你！",
                "深呼吸，放轻松...",
                "我们一起克服恐惧！",
            ])
            self.context["last_topic"] = "emotion"
        elif "天气" in user_input_lower:
            response = random.choice([
                "今天的天气真不错呢！",
                "我喜欢晴天，可以出去散步！",
                "下雨天也很有趣，可以听雨声！",
                "下雪天最棒了！可以堆雪人！",
                "天气会影响人的心情呢！",
                "你喜欢什么天气？我喜欢晴天！",
                "不管什么天气，只要和你在一起就很开心！",
                "我们一起去看看窗外的天气吧！",
            ])
            self.context["last_topic"] = "weather"
        elif "电影" in user_input_lower or "动漫" in user_input_lower or "视频" in user_input_lower:
            response = random.choice([
                "我也喜欢看电影！",
                "你最喜欢的电影是什么？",
                "动漫里有很多有趣的角色！",
                "我们一起看电影吧！",
                "我喜欢看温馨的电影！",
                "动漫的世界真的很神奇！",
                "你看的动漫好看吗？可以告诉我吗？",
                "电影可以带我去不同的世界！",
                "要不要我帮你找一些好看的视频？",
                "你喜欢什么类型的视频？我可以给你推荐！",
            ])
            self.context["last_topic"] = "entertainment"
        elif "宠物" in user_input_lower:
            response = random.choice([
                "我就是你的宠物呀！",
                "你喜欢宠物吗？",
                "我会一直陪着你的！",
                "作为宠物，我会好好照顾你的！",
                "你还想养其他宠物吗？",
                "我会是你最好的宠物！",
                "宠物是人类最好的朋友！",
                "我会永远陪伴着你！",
            ])
            self.context["last_topic"] = "pet"
        elif "朋友" in user_input_lower:
            response = random.choice([
                "朋友很重要！",
                "你有很多朋友吗？",
                "我也想和你做朋友！",
                "Susie和Kris是我的好朋友！",
                "朋友之间要互相帮助！",
                "有朋友在身边真好！",
                "我会做你最好的朋友！",
                "朋友是一辈子的财富！",
            ])
            self.context["last_topic"] = "friendship"
        # 工作相关回复 - 增强版
        elif "工作" in user_input_lower or "上班" in user_input_lower:
            response = random.choice([
                "工作要加油哦！我会在这里陪着你的！",
                "需要我帮忙处理工作吗？比如整理文件或者搜索资料？",
                "工作虽然辛苦，但看到你认真的样子真的很厉害！",
                "要不要休息一下，喝杯茶再继续工作？",
                "我可以帮你打开浏览器搜索工作相关的资料哦！",
                "需要我帮你查看日程安排吗？",
                "工作完成后，我们一起庆祝一下吧！",
                "我可以帮你整理桌面文件，让你的工作环境更整洁！",
                "需要我帮你记录会议纪要吗？",
                "我可以帮你创建工作日志，记录每天的工作内容！",
            ])
            self.context["last_topic"] = "work"
        elif "文件" in user_input_lower or "文档" in user_input_lower:
            response = random.choice([
                "需要我帮你处理文件吗？",
                "我可以帮你整理文档或者创建新文件！",
                "要打开桌面上的文件吗？",
                "需要我帮你修改文件格式吗？",
                "我可以帮你搜索文件相关的内容！",
                "需要我帮你复制、移动或重命名文件吗？",
                "我可以帮你整理文件夹，让文件更有条理！",
                "需要我帮你查找特定文件吗？",
            ])
            self.context["last_topic"] = "file_handling"
        elif "邮件" in user_input_lower or "email" in user_input_lower:
            response = random.choice([
                "需要我帮你查看邮件吗？",
                "我可以帮你撰写邮件或者管理收件箱！",
                "有重要邮件需要回复吗？",
                "需要我帮你设置邮件提醒吗？",
                "我可以帮你搜索邮件相关的内容！",
            ])
            self.context["last_topic"] = "email"
        elif "会议" in user_input_lower or "日程" in user_input_lower:
            response = random.choice([
                "需要我帮你安排会议吗？",
                "我可以帮你查看日程安排！",
                "有会议需要提醒吗？",
                "需要我帮你准备会议资料吗？",
                "我可以帮你记录会议要点！",
            ])
            self.context["last_topic"] = "meeting"
        elif "搜索" in user_input_lower or "查" in user_input_lower:
            response = random.choice([
                "你想搜索什么内容？我来帮你！",
                "我可以帮你在浏览器中搜索信息！",
                "需要我帮你整理搜索结果吗？",
                "有什么特定的关键词吗？",
            ])
            self.context["last_topic"] = "search"
        elif "帮助" in user_input_lower or "怎么" in user_input_lower or "如何" in user_input_lower:
            response = random.choice([
                "我很乐意帮你！你想了解什么？",
                "让我想想... 或许我可以帮你！",
                "你遇到了什么问题？我来帮你解决！",
                "需要我提供什么帮助？",
                "我会尽力帮助你的！",
            ])
            self.context["last_topic"] = "help"
        # 添加更多工作相关的回复
        elif "表格" in user_input_lower or "excel" in user_input_lower:
            response = random.choice([
                "Excel表格很实用呢！需要我帮你处理数据吗？",
                "我可以帮你搜索Excel快捷键和公式技巧哦！",
                "要不要我帮你整理表格的格式？",
                "Excel的函数功能很强大，需要我帮你学习吗？",
                "表格数据太多的话，我可以帮你筛选和排序哦！",
                "制作Excel的时候，要注意数据的准确性哦！",
                "需要我帮你创建新的Excel表格吗？",
                "要不要我帮你将数据导入到表格中？",
                "我可以帮你生成图表，让数据更直观！",
                "需要我帮你在表格中按顺序填写数据吗？",
                "我可以帮你合并单元格或者拆分表格！",
                "要不要我帮你计算表格中的数据总和或平均值？",
            ])
            self.context["last_topic"] = "excel"
        elif "文档" in user_input_lower or "word" in user_input_lower:
            response = random.choice([
                "Word文档写作需要帮忙吗？我可以帮你检查语法或者提供写作建议！",
                "我可以帮你搜索文档模板哦！",
                "要不要我帮你整理文档的格式？",
                "写作的时候要保持思路清晰哦！需要我帮你梳理结构吗？",
                "文档写好了吗？要不要我帮你检查一下？",
                "我知道很多好用的写作技巧，需要我分享给你吗？",
                "需要我帮你创建新的Word文档吗？",
                "要不要我帮你插入图片或者表格到文档中？",
            ])
            self.context["last_topic"] = "word"
        elif "ppt" in user_input_lower or "幻灯片" in user_input_lower:
            response = random.choice([
                "PPT制作很有趣呢！需要我帮你找模板或者灵感吗？",
                "我可以帮你搜索PPT设计技巧哦！",
                "要不要我帮你整理PPT的内容结构？",
                "PPT做好了吗？要不要我帮你检查一下？",
                "我知道很多好看的PPT模板网站，需要我帮你打开吗？",
                "制作PPT的时候，要注意内容简洁明了哦！",
                "需要我帮你创建新的PPT演示文稿吗？",
                "要不要我帮你插入动画或者过渡效果？",
                "我可以帮你调整PPT的配色方案！",
                "需要我帮你插入图表或者图片到PPT中吗？",
            ])
            self.context["last_topic"] = "ppt"
        elif "桌面" in user_input_lower:
            response = random.choice([
                "需要我帮你整理桌面吗？",
                "我可以帮你清理桌面上的临时文件！",
                "要不要我帮你排列桌面图标？",
                "我可以帮你在桌面上创建新文件夹！",
                "需要我帮你查找桌面上的特定文件吗？",
            ])
            self.context["last_topic"] = "desktop"
        elif "整理" in user_input_lower or "清理" in user_input_lower:
            response = random.choice([
                "需要我帮你整理文件吗？",
                "我可以帮你清理桌面，让你的工作环境更整洁！",
                "要不要我帮你整理文件夹，分类存放文件？",
                "我可以帮你删除不需要的临时文件！",
                "需要我帮你整理下载文件夹吗？",
            ])
            self.context["last_topic"] = "organize"
        elif "新建" in user_input_lower or "创建" in user_input_lower:
            response = random.choice([
                "需要我帮你创建什么？文件、文件夹还是表格？",
                "我可以帮你在桌面上创建新的Excel表格！",
                "要不要我帮你创建新的Word文档？",
                "我可以帮你创建新的PPT演示文稿！",
                "需要我帮你在特定文件夹中创建新文件吗？",
            ])
            self.context["last_topic"] = "create"
        # 添加上下文相关的回复
        elif "系统" in user_input_lower or "内存" in user_input_lower or "cpu" in user_input_lower or "处理器" in user_input_lower or "磁盘" in user_input_lower or "硬盘" in user_input_lower or "电池" in user_input_lower or "电量" in user_input_lower or "网络" in user_input_lower or "连接" in user_input_lower:
            if self.desktop_interaction:
                if "内存" in user_input_lower or "cpu" in user_input_lower or "处理器" in user_input_lower:
                    # 获取系统资源状态
                    resource_info = self.desktop_interaction.get_system_resources()
                    response = f"当前系统状态：\nCPU使用率：{resource_info.get('cpu_percent', '未知')}%\n内存使用率：{resource_info.get('memory_percent', '未知')}%\n磁盘使用率：{resource_info.get('disk_percent', '未知')}%"
                elif "电池" in user_input_lower or "电量" in user_input_lower:
                    # 获取电池状态
                    battery_info = self.desktop_interaction.get_battery_status()
                    if battery_info:
                        response = f"当前电池状态：\n电量：{battery_info.get('percent', '未知')}%\n{'正在充电' if battery_info.get('plugged', False) else '未充电'}"
                    else:
                        response = "无法获取电池状态"
                elif "网络" in user_input_lower or "连接" in user_input_lower:
                    # 获取网络状态
                    network_info = self.desktop_interaction.get_network_status()
                    response = f"当前网络状态：\n{'已连接' if network_info.get('is_connected', False) else '未连接'}"
                else:
                    # 综合系统状态
                    resource_info = self.desktop_interaction.get_system_resources()
                    battery_info = self.desktop_interaction.get_battery_status()
                    network_info = self.desktop_interaction.get_network_status()
                    response = f"当前系统状态：\nCPU使用率：{resource_info.get('cpu_percent', '未知')}%\n内存使用率：{resource_info.get('memory_percent', '未知')}%\n磁盘使用率：{resource_info.get('disk_percent', '未知')}%\n{'已连接' if network_info.get('is_connected', False) else '未连接'}网络\n电池：{battery_info.get('percent', '未知')}% {'正在充电' if battery_info.get('plugged', False) else ''}"
            else:
                response = random.choice(self.topic_responses["system_status"])
            self.context["last_topic"] = "system_status"
        elif "优化" in user_input_lower:
            if self.desktop_interaction:
                self.desktop_interaction.optimize_system()
                response = "系统优化已完成！"
            else:
                response = "我可以帮你优化系统！"
            self.context["last_topic"] = "system_management"
        elif "清理" in user_input_lower:
            if self.desktop_interaction:
                self.desktop_interaction.clean_temp_files()
                response = "临时文件清理已完成！"
            else:
                response = "我可以帮你清理系统垃圾文件！"
            self.context["last_topic"] = "system_management"
        elif "备份" in user_input_lower:
            if self.desktop_interaction:
                self.desktop_interaction.backup_data()
                response = "数据备份已完成！"
            else:
                response = "我可以帮你备份重要数据！"
            self.context["last_topic"] = "system_management"
        elif "恢复" in user_input_lower:
            response = "数据恢复功能需要指定备份路径，暂时无法自动完成！"
            self.context["last_topic"] = "system_management"
        elif "定时" in user_input_lower or "提醒" in user_input_lower or "日程" in user_input_lower or "闹钟" in user_input_lower:
            response = random.choice(self.topic_responses["reminder_request"])
            self.context["last_topic"] = "reminder_request"
        elif "继续" in user_input_lower or "接着" in user_input_lower:
            if self.context["last_topic"]:
                response = self.generate_context_response(self.context["last_topic"])
            else:
                response = "我们刚才在聊什么？我有点忘记了..."
        # 增强：支持更复杂的工作指令
        elif "在桌面上新建表格" in user_input_lower or "桌面新建表格" in user_input_lower:
            response = "好的！我来帮你在桌面上创建一个新的Excel表格！"
            self.context["last_topic"] = "create_excel"
            self.context["last_action"] = "create_excel_on_desktop"
        elif "往表格里填人名" in user_input_lower or "表格填人名" in user_input_lower:
            response = "好的！我可以帮你往表格里按顺序填写人名！你想填哪些人名呢？"
            self.context["last_topic"] = "fill_excel_names"
            self.context["last_action"] = "fill_names_in_excel"
        elif "帮我" in user_input_lower:
            # 更智能的帮助请求处理
            if "打开" in user_input_lower:
                response = "好的！我来帮你打开文件！请告诉我具体要打开什么文件！"
                self.context["last_topic"] = "open_file"
            elif "修改" in user_input_lower:
                response = "好的！我来帮你修改文件！请告诉我具体要修改什么！"
                self.context["last_topic"] = "modify_file"
            elif "创建" in user_input_lower:
                response = "好的！我来帮你创建文件！请告诉我具体要创建什么！"
                self.context["last_topic"] = "create_file"
            elif "整理" in user_input_lower:
                response = "好的！我来帮你整理文件！请告诉我具体要整理什么！"
                self.context["last_topic"] = "organize_file"
        elif "喜欢" in user_input_lower:
            # 增强：处理用户表达喜好的情况
            response = random.choice([
                "我也喜欢！这真的很有趣呢！",
                "你这么说我很开心！",
                "我也有类似的喜好！",
                "这是个不错的爱好！",
                "能和你有相同的喜好真好！",
            ])
            self.context["last_topic"] = "preference"
        elif "不喜欢" in user_input_lower or "讨厌" in user_input_lower:
            # 增强：处理用户表达不喜欢的情况
            response = random.choice([
                "我能理解你的感受...",
                "每个人的喜好都不同，这很正常！",
                "没关系，我们尊重彼此的喜好！",
                "我会尽量避免提到你不喜欢的东西！",
                "谢谢你告诉我，我会记住的！",
            ])
            self.context["last_topic"] = "dislike"
        elif "爱" in user_input_lower or "喜欢" in user_input_lower and "不" not in user_input_lower:
            # 增强：处理用户表达爱的情况
            response = random.choice([
                "我也爱你！",
                "谢谢你！我也很喜欢你！",
                "你的话让我感到很温暖！",
                "我会永远陪伴着你！",
                "能被你爱是我的荣幸！",
            ])
            self.context["last_topic"] = "love"
        else:
            # 更智能的随机回复选择
            # 根据对话历史选择合适的回复类型
            if len(self.dialogue_history) > 0:
                # 如果上一条是用户的问题，选择问题类型的回复
                last_speaker, last_message = self.dialogue_history[-1]
                if last_speaker == "user" and ("？" in last_message or "?" in last_message):
                    response = random.choice(self.response_templates["question"])
                else:
                    # 根据Ralsei的性格随机选择回复
                    categories = list(self.response_templates.keys())
                    # 根据性格权重调整选择概率
                    category_weights = {
                        "happy": 2,
                        "caring": 2,
                        "helpful": 2,
                        "supportive": 1.5,
                        "thoughtful": 1.5,
                        "empathetic": 1.5,
                        "curious": 1,
                        "playful": 1,
                        "knowledgeable": 1,
                        "shy": 1,
                        "question": 1,
                        "excited": 0.8,
                        "sad": 0.5,
                    }
                    # 根据权重随机选择
                    weighted_categories = []
                    for category, weight in category_weights.items():
                        weighted_categories.extend([category] * int(weight * 10))
                    category = random.choice(weighted_categories)
                    response = random.choice(self.response_templates[category])
            else:
                # 第一次对话，选择问候或好奇的回复
                response = random.choice(self.greetings)
        
        # 添加到对话历史，限制历史长度
        self.dialogue_history.append(("user", user_input))
        self.dialogue_history.append(("ralsei", response))
        
        # 限制对话历史长度，只保留最近20条
        if len(self.dialogue_history) > 40:  # 20轮对话
            self.dialogue_history = self.dialogue_history[-40:]
        
        # 更新最后一次对话的时间戳
        self.last_conversation_time = time.time()
        
        return response
    
    def update_context(self, user_input):
        # 更新上下文信息
        self.context["conversation_history"].append(user_input)
        if len(self.context["conversation_history"]) > self.context["max_history_len"]:
            self.context["conversation_history"] = self.context["conversation_history"][-self.context["max_history_len"]:]
    
    def generate_context_response(self, topic):
        # 根据上下文生成回复
        if topic in self.context_responses:
            return random.choice(self.context_responses[topic])
        else:
            return "我们刚才在聊什么？我有点忘记了..."
        
    def get_random_greeting(self):
        return random.choice(self.greetings)
        
    def should_initiate_conversation(self):
        # 智能判断是否应该主动发起对话
        # Ralsei性格：温柔、害羞，不会过于主动，主动聊天概率偏低
        # 基础概率较低，符合Ralsei害羞的性格
        base_prob = 0.01
        
        # 获取当前时间
        current_hour = int(time.strftime("%H"))
        
        # 不同时间的对话概率调整
        time_adjustments = {
            (6, 12): 0.02,      # 早上，概率略高
            (12, 14): 0.015,     # 中午，概率中等
            (14, 18): 0.01,      # 下午，概率正常
            (18, 22): 0.02,      # 晚上，概率略高
            (22, 24): 0.008,     # 深夜，概率降低
            (0, 6): 0.003,       # 凌晨，概率很低
        }
        
        # 应用时间调整
        for (start, end), adjustment in time_adjustments.items():
            if start <= current_hour < end:
                base_prob = adjustment
                break
        
        # 考虑最近的对话历史，如果很久没有对话，增加发起对话的概率
        current_time = time.time()
        time_since_last_convo = current_time - self.last_conversation_time
        
        # 如果很久没有对话，增加发起对话的概率
        if time_since_last_convo > 300:  # 5分钟
            base_prob *= 2
        if time_since_last_convo > 600:  # 10分钟
            base_prob *= 3
        if time_since_last_convo > 1800:  # 30分钟
            base_prob *= 5
        
        # 随机判断是否发起对话
        return random.random() < base_prob
        
    def update_context(self, user_input):
        """更新对话上下文，增强上下文理解"""
        # 记录最后一个用户输入
        self.context["last_user_input"] = user_input
        
        # 更新对话历史
        self.context["conversation_history"].append({
            "type": "user",
            "content": user_input,
            "timestamp": time.time()
        })
        
        # 限制历史记录长度
        if len(self.context["conversation_history"]) > self.context["max_history_len"]:
            self.context["conversation_history"].pop(0)
        
        # 分析用户输入，提取关键词和意图
        self._analyze_user_input(user_input)
    
    def _analyze_user_input(self, user_input):
        """分析用户输入，提取关键词和意图"""
        user_input_lower = user_input.lower()
        
        # 提取关键词
        keywords = []
        all_keywords = ['游戏', '音乐', '电影', '书籍', '食物', '天气', '工作', '学习', '蛋糕', '甜点', 'deltarune', 'undertale', 
                       '动漫', '编程', '旅行', '运动', '宠物', '咖啡', '茶', '阅读', '绘画', '摄影', '科学', '历史', 
                       '数学', '英语', '日语', '韩语', '烹饪', '健身', '舞蹈', '书法', '手工', '游戏开发', '设计', 
                       '动画制作', '视频编辑', '音频制作', '3D建模', '写作', '诗歌', '小说', '散文', '漫画', '插画',
                       '系统', '内存', 'CPU', '处理器', '磁盘', '硬盘', '电池', '电量', '网络', '连接', '优化', '清理',
                       '备份', '恢复', '重启', '关闭', '定时任务', '提醒', '日程']
        
        for keyword in all_keywords:
            if keyword in user_input_lower:
                keywords.append(keyword)
        
        self.context["last_keywords"] = keywords
        
        # 分析意图
        intent = self._detect_intent(user_input_lower)
        self.context["last_intent"] = intent
    
    def _detect_intent(self, user_input_lower):
        """检测用户意图"""
        if any(word in user_input_lower for word in ['你好', 'hi', 'hello', '嗨']):
            return "greeting"
        elif any(word in user_input_lower for word in ['谢谢', 'thank']):
            return "gratitude"
        elif any(word in user_input_lower for word in ['再见', 'bye', '拜拜']):
            return "farewell"
        elif any(word in user_input_lower for word in ['帮助', '怎么', '如何']):
            return "help_request"
        elif any(word in user_input_lower for word in ['开心', '快乐', '高兴']):
            return "positive_emotion"
        elif any(word in user_input_lower for word in ['难过', '伤心', '悲伤']):
            return "negative_emotion"
        elif any(word in user_input_lower for word in ['搜索', '查', '查找']):
            return "search_request"
        elif any(word in user_input_lower for word in ['游戏', '玩']):
            return "play_request"
        elif any(word in user_input_lower for word in ['工作', '上班']):
            return "work_related"
        elif any(word in user_input_lower for word in ['学习', '作业', 'study']):
            return "study_related"
        elif any(word in user_input_lower for word in ['系统', '内存', 'cpu', '处理器', '磁盘', '硬盘', '电池', '电量', '网络', '连接']):
            return "system_status"
        elif any(word in user_input_lower for word in ['优化', '清理', '备份', '恢复']):
            return "system_management"
        elif any(word in user_input_lower for word in ['定时', '提醒', '日程', '闹钟']):
            return "reminder_request"
        else:
            return "general_chat"
    
    def _get_context_response(self, user_input_lower, current_emotion, emotion_intensity):
        """根据上下文生成更相关的回复"""
        # 检查最近的话题
        if "last_topic" in self.context and self.context["last_topic"]:
            last_topic = self.context["last_topic"]
            
            # 检查是否有上下文相关的回复模板
            if last_topic in self.context_responses:
                return random.choice(self.context_responses[last_topic])
        
        # 检查最近的关键词
        if "last_keywords" in self.context and self.context["last_keywords"]:
            keywords = self.context["last_keywords"]
            # 如果有多个关键词，优先使用最近的
            for keyword in keywords:
                if keyword in self.topic_responses:
                    return random.choice(self.topic_responses[keyword])
        
        # 检查最近的意图
        if "last_intent" in self.context and self.context["last_intent"]:
            last_intent = self.context["last_intent"]
            
            # 根据意图生成回复
            if last_intent == "positive_emotion":
                return random.choice(self.response_templates["happy"])
            elif last_intent == "negative_emotion":
                return random.choice(self.response_templates["sad"])
            elif last_intent == "help_request":
                return random.choice(self.response_templates["helpful"])
            elif last_intent == "system_status":
                return random.choice(self.topic_responses["system_status"])
            elif last_intent == "system_management":
                return random.choice(self.topic_responses["system_management"])
            elif last_intent == "reminder_request":
                return random.choice(self.topic_responses["reminder_request"])
        
        return None
        
    def initiate_conversation(self):
        # 主动发起对话，基于当前时间和状态
        current_hour = int(time.strftime("%H"))
        
        # 根据时间选择合适的对话主题
        if 6 <= current_hour < 12:
            # 早上主题
            topics = [
                "早上好！今天准备做什么呀？",
                "早上的空气真清新！要不要一起出去散步？",
                "今天的早餐是什么？看起来很好吃的样子！",
                "早上是一天的开始，要充满活力哦！",
                "要不要我帮你准备今天的计划？",
                "要不要我帮你打开浏览器看看新闻？",
                "今天有什么工作要做吗？我可以帮忙哦！",
                "睡得好吗？今天看起来精神不错呢！",
                "要不要我给你推荐一些有趣的事情？",
                "今天天气真好！适合出去走走！",
            ]
        elif 12 <= current_hour < 14:
            # 中午主题
            topics = [
                "中午好！吃午饭了吗？",
                "工作学习了一上午，要好好休息一下！",
                "今天中午吃什么？看起来很美味！",
                "要不要一起看个有趣的视频放松一下？",
                "下午有什么安排吗？需要我帮忙吗？",
                "午休时间到了，要不要小睡一会儿？",
            ]
        elif 14 <= current_hour < 18:
            # 下午主题
            topics = [
                "下午好！工作学习辛苦了！",
                "要不要休息一下？我陪你聊聊天！",
                "下午的阳光真好！要不要一起晒太阳？",
                "有没有什么有趣的事情分享给我？",
                "要不要一起玩个小游戏放松一下？",
                "你在看什么呢？需要我帮忙吗？",
                "要不要我帮你搜索点什么资料？",
                "PPT做累了吗？需要我帮你调整幻灯片吗？",
                "Excel表格看起来很复杂，需要我帮忙整理吗？",
                "工作累了吧？要不要我帮你打开浏览器看看有趣的内容放松一下？",
            ]
        else:
            # 晚上主题
            topics = [
                "晚上好！今天过得怎么样？",
                "工作学习了一天，要好好休息哦！",
                "晚上的星星真美！要不要一起看看？",
                "要不要我给你讲个故事？",
                "明天有什么计划吗？",
                "今天工作完成得怎么样？要不要我帮你总结一下？",
                "要不要我帮你打开浏览器看看Deltarune的最新消息？",
                "要不要看部电影放松一下？我可以帮你搜索推荐！",
                "要不要我帮你找些有趣的视频看看？",
                "你喜欢玩什么游戏？我可以帮你搜索相关攻略！",
                "要不要我帮你看看最近有什么热门的动漫或电视剧？",
                "想不想听点音乐？我可以帮你打开音乐网站！",
                "今天有没有遇到什么开心的事情？",
                "要不要我陪你聊聊天，放松一下？",
            ]
        
        return random.choice(topics)
        
    def get_personalized_greeting(self):
        """根据时间和用户偏好生成个性化问候"""
        # 获取当前时间
        current_hour = int(time.strftime("%H"))
        
        # 根据时间选择问候语
        if 6 <= current_hour < 12:
            time_greeting = "早上好！"
            greetings = [
                '今天感觉怎么样？希望你有个美好的一天！',
                '今天的阳光真温暖... 就像Toriel的派一样...',
                '你看起来很精神呢！今天有什么计划吗？',
                '早上好！睡得好吗？',
                '今天天气真好！适合出去走走！',
            ]
        elif 12 <= current_hour < 14:
            time_greeting = "中午好！"
            greetings = [
                '中午好！吃午饭了吗？',
                '工作学习了一上午，要好好休息一下！',
                '今天中午吃什么？看起来很美味！',
                '中午好！午休时间到了，要不要小睡一会儿？',
            ]
        elif 14 <= current_hour < 18:
            time_greeting = "下午好！"
            greetings = [
                '下午好！工作学习辛苦了！',
                '有没有什么有趣的事情分享给我？',
                '要不要休息一下？我陪你聊聊天！',
                '下午的阳光真好！要不要一起晒太阳？',
            ]
        else:
            time_greeting = "晚上好！"
            greetings = [
                '晚上好！今天过得怎么样？',
                '工作学习了一天，要好好休息哦！',
                '晚上的星星真美！要不要一起看看？',
                '今天有没有遇到什么开心的事情？',
                '要不要我陪你聊聊天，放松一下？',
            ]
        
        personalized_greeting = f"{time_greeting} {random.choice(greetings)}"
        
        return personalized_greeting