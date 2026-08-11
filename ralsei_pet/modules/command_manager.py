import json
import logging
from typing import Dict, Any, Callable
from PyQt5.QtCore import QPoint

class CommandManager:
    def __init__(self, ralsei_pet):
        self.ralsei = ralsei_pet
        self.logger = logging.getLogger('CommandManager')
        self.logger.setLevel(logging.INFO)
        
        # 命令映射表，将API命令映射到对应的方法
        self.command_handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            'move': self.handle_move_command,
            'jump': self.handle_jump_command,
            'change_animation': self.handle_animation_command,
            'say': self.handle_say_command,
            'follow_mouse': self.handle_follow_mouse_command,
            'stop_following': self.handle_stop_following_command,
            'sleep': self.handle_sleep_command,
            'wake_up': self.handle_wake_up_command,
            'set_mood': self.handle_set_mood_command,

            'play_game': self.handle_play_game_command,
            'idle': self.handle_idle_command,
            'run': self.handle_run_command
        }
    
    def execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """执行来自API的命令"""
        try:
            command_type = command.get('type')
            if not command_type:
                return {'status': 'error', 'message': '缺少命令类型'}
            
            handler = self.command_handlers.get(command_type)
            if not handler:
                return {'status': 'error', 'message': f'未知命令类型: {command_type}'}
            
            # 执行命令
            result = handler(command)
            self.logger.info(f"命令执行成功: {command_type}, 结果: {result}")
            return {'status': 'success', 'result': result}
        except Exception as e:
            self.logger.error(f"命令执行失败: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def handle_move_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理移动命令"""
        x = command.get('x', 0)
        y = command.get('y', 0)
        speed = command.get('speed', self.ralsei.speed)
        
        self.ralsei.target_pos = QPoint(x, y)
        self.ralsei.speed = speed
        self.ralsei.is_moving = True
        
        return {'message': f'正在移动到位置 ({x}, {y})', 'speed': speed}
    
    def handle_jump_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理跳跃命令"""
        x = command.get('x')
        y = command.get('y')
        
        if x is not None and y is not None:
            target_pos = QPoint(x, y)
            self.ralsei.start_jump(target_pos)
        else:
            # 原地跳跃
            current_pos = self.ralsei.pos()
            self.ralsei.start_jump(current_pos)
        
        return {'message': '开始跳跃'}
    
    def handle_animation_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理动画切换命令"""
        animation_name = command.get('animation', 'idle')
        force = command.get('force', False)
        
        self.ralsei.change_animation(animation_name, force=force)
        
        return {'message': f'切换动画到 {animation_name}'}
    
    def handle_say_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理对话命令"""
        text = command.get('text', '')
        emotion = command.get('emotion', 'normal')
        
        if text:
            self.ralsei.dialogue_ui.add_dialogue("ralsei", text, emotion)
            self.ralsei.dialogue_ui.show_dialogue()
            
        return {'message': f'Ralsei说: {text}', 'emotion': emotion}
    
    def handle_follow_mouse_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理跟随鼠标命令"""
        self.ralsei.is_following_mouse = True
        
        return {'message': '开始跟随鼠标'}
    
    def handle_stop_following_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理停止跟随命令"""
        self.ralsei.is_following_mouse = False
        
        return {'message': '停止跟随鼠标'}
    
    def handle_sleep_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理睡眠命令"""
        self.ralsei.is_sleeping = True
        self.ralsei.current_activity = "sleeping"
        
        return {'message': '开始睡眠'}
    
    def handle_wake_up_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理唤醒命令"""
        self.ralsei.wake_up()
        
        return {'message': '已唤醒'}
    
    def handle_set_mood_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理设置心情命令"""
        mood = command.get('mood', 'normal')
        self.ralsei.mood = mood
        
        return {'message': f'心情已设置为 {mood}'}
    

    
    def handle_play_game_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理游戏命令"""
        game_type = command.get('game_type', 'rock_paper_scissors')
        
        # 这里可以扩展不同游戏的处理逻辑
        if game_type == 'rock_paper_scissors':
            import random
            choice = random.choice(self.ralsei.rock_paper_scissors_options)
            return {'message': f'开始石头剪刀布游戏', 'choice': choice}
        elif game_type == 'guess_number':
            import random
            target = random.randint(1, 100)
            self.ralsei.guess_number_game['target_number'] = target
            return {'message': '开始猜数字游戏', 'target_number': target}
        
        return {'message': f'开始游戏: {game_type}'}
    
    def handle_idle_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理空闲命令"""
        self.ralsei.is_moving = False
        self.ralsei.current_activity = "idle"
        self.ralsei.change_animation("idle")
        
        return {'message': '进入空闲状态'}
    
    def handle_run_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """处理奔跑命令"""
        x = command.get('x', self.ralsei.target_pos.x())
        y = command.get('y', self.ralsei.target_pos.y())
        self.ralsei.target_pos = QPoint(x, y)
        self.ralsei.speed = self.ralsei.max_speed
        self.ralsei.is_moving = True
        
        # 根据方向设置奔跑动画
        current_pos = self.ralsei.pos()
        dx = x - current_pos.x()
        dy = y - current_pos.y()
        
        if abs(dx) > abs(dy):
            direction = "right" if dx > 0 else "left"
        else:
            direction = "down" if dy > 0 else "up"
        
        self.ralsei.change_animation(f"run_{direction}")
        
        return {'message': f'正在奔跑向位置 ({x}, {y})', 'direction': direction}
    
    def get_status(self) -> Dict[str, Any]:
        """获取Ralsei的当前状态"""
        return {
            'position': {
                'x': self.ralsei.pos().x(),
                'y': self.ralsei.pos().y()
            },
            'activity': self.ralsei.current_activity,
            'animation': self.ralsei.current_animation,
            'mood': self.ralsei.mood,
            'emotions': self.ralsei.emotions,
            'is_moving': self.ralsei.is_moving,
            'is_following_mouse': self.ralsei.is_following_mouse,
            'is_sleeping': self.ralsei.is_sleeping,
            'speed': self.ralsei.speed,
            'time_of_day': self.ralsei.time_of_day,
            'weather': self.ralsei.weather,
            'temperature': self.ralsei.temperature
        }