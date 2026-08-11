# Ralsei Desktop Pet

一个基于PyQt5的《Deltarune》Ralsei桌面宠物应用。

## 项目特点

### 核心功能
1. **智能移动**：Ralsei会自动在屏幕上漫游，运动逻辑符合其温和的性格
2. **丰富的动画**：包含多种动画效果，如行走、站立、大笑、跳舞等
3. **对话系统**：可以与Ralsei进行对话交流
4. **天气响应**：根据天气条件做出不同的反应
5. **精力和饥饿度系统**：Ralsei会感到饥饿和疲惫，需要休息和食物
6. **桌面交互**：可以与桌面上的文件夹和文件进行交互
7. **游戏和活动**：包括跳舞、唱歌、追逐鼠标等游戏

### 技术架构
- **语言**：Python 3.8+
- **GUI框架**：PyQt5
- **模块结构**：模块化设计，便于扩展和维护

## 项目结构

```
ralsei_pet/
├── src/
│   ├── main.py              # 主程序入口
│   ├── main_simple.py       # 简化版主程序
│   ├── test_pyqt_simple.py  # PyQt5测试脚本
│   └── test_basic.py        # 基本功能测试脚本
├── modules/
│   ├── __init__.py          # 模块初始化
│   ├── sprite_loader.py     # 精灵资源加载
│   ├── dialogue_system.py   # 对话生成系统
│   ├── dialogue_ui.py       # 对话界面
│   ├── weather_system.py    # 天气响应系统
│   ├── pet_ai.py            # 宠物AI行为逻辑
│   ├── desktop_interaction.py  # 桌面交互功能
│   └── energy_hunger.py     # 精力和饥饿度系统
├── requirements.txt         # 项目依赖
└── README.md                # 项目说明文档
```

## 安装和运行

### 1. 安装Python
确保你的系统安装了Python 3.8或更高版本。你可以从[Python官网](https://www.python.org/)下载安装。

### 2. 安装依赖
打开终端，进入项目目录，运行以下命令安装依赖：

```bash
pip install -r requirements.txt
```

### 3. 准备资源文件
确保你已经准备好以下资源文件：

- **精灵图片**：将Ralsei的精灵图片放在`c:/Users/[你的用户名]/Documents/trae_projects/try/deltarune_ralsei/`目录下
- **表情图片**：将Ralsei的表情图片放在`c:/Users/[你的用户名]/Documents/trae_projects/try/ralsei_face/`目录下

### 4. 运行项目

#### 完整版本
```bash
cd src
python main.py
```

#### 简化版本（推荐用于测试）
```bash
cd src
python main_simple.py
```

## 功能说明

### 基本交互
- **双击Ralsei**：显示/隐藏对话框
- **点击Ralsei**：触发他的反应
- **拖动Ralsei**：移动他的位置

### 自动行为
- **漫游**：Ralsei会自动在屏幕上漫游，运动节奏符合其性格
- **对话**：Ralsei会在适当的时候主动发起对话
- **休息**：当精力不足时，Ralsei会自动休息
- **进食**：当饥饿时，Ralsei会请求食物
- **探索**：Ralsei会主动探索桌面上的文件夹和文件

### 游戏和活动
- **跳舞**：Ralsei会随机跳舞
- **唱歌**：Ralsei会随机唱歌
- **追逐鼠标**：Ralsei会追逐你的鼠标指针
- **躲猫猫**：Ralsei会玩躲猫猫游戏
- **猜谜**：Ralsei会出一些简单的谜语

## 配置和扩展

### 调整运动节奏
在`main.py`中修改`randomize_movement_pattern`方法，调整Ralsei的运动和停留时间：

```python
def randomize_movement_pattern(self):
    # 随机设置最大停留时间（5-20秒）
    self.max_idle_duration = randint(5000, 20000) / 1000  # 转换为秒
    
    # 随机设置最大移动时间（3-10秒）
    self.max_moving_duration = randint(3000, 10000) / 1000  # 转换为秒
    
    # 随机调整速度
    self.speed = uniform(1.5, 3.0)
```

### 添加新动画
在`sprite_loader.py`的`animation_mapping`字典中添加新的动画映射：

```python
self.animation_mapping = {
    # 现有动画...
    "new_animation": ["new_animation_file_0.png", "new_animation_file_1.png"],
}
```

### 扩展对话系统
在`dialogue_system.py`中添加更多的对话回复和触发条件：

```python
def generate_response(self, user_input):
    # 现有对话逻辑...
    elif "关键词" in user_input:
        response = "对应的回复"
    # 更多对话逻辑...
```

## 常见问题

### Q: 程序运行后立即退出
A: 这可能是由于以下原因：
- PyQt5没有正确安装：尝试重新安装PyQt5
- 资源文件路径不正确：检查精灵和表情图片的路径是否正确
- 环境不支持GUI应用：尝试在支持GUI的环境中运行

### Q: 看不到Ralsei的身影
A: 检查以下几点：
- 确保资源文件存在且路径正确
- 检查是否有错误信息输出
- 尝试运行简化版本`main_simple.py`

### Q: 无法与Ralsei对话
A: 双击Ralsei可以显示/隐藏对话框，确保对话框已经显示

## 项目扩展建议

1. **集成AI对话模型**：使用OpenAI API或其他AI模型，使Ralsei的对话更加智能
2. **添加声音效果**：为Ralsei添加各种音效和语音
3. **支持多角色**：添加其他《Deltarune》角色，如Susie、Kris等
4. **添加更多游戏**：扩展游戏种类，如拼图、记忆游戏等
5. **支持自定义皮肤**：允许用户自定义Ralsei的外观
6. **添加成就系统**：记录与Ralsei的互动成就
7. **支持云同步**：同步Ralsei的状态和互动记录
8. **添加节日主题**：根据节日变化Ralsei的外观和行为

## 许可证

本项目仅供学习和娱乐使用，请勿用于商业用途。

## 贡献

欢迎提交Issue和Pull Request，一起完善这个项目！

## 致谢

- 《Deltarune》和Ralsei的版权归Toby Fox所有
- 感谢所有为项目提供帮助和支持的人

---

希望你喜欢这个Ralsei桌面宠物！如果有任何问题或建议，欢迎随时反馈。