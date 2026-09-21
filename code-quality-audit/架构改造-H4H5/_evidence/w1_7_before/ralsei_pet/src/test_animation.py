import sys
import os

# 添加项目根目录到搜索路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from modules.sprite_loader import SpriteLoader

# 测试加载jump_ball动画
sprite_loader = SpriteLoader()
try:
    sprite_loader.load_sprites()
    print("所有动画:")
    for anim in sorted(sprite_loader.sprites.keys()):
        print(f"  - {anim}")
    
    # 检查jump相关动画
    print("\nJump相关动画:")
    for anim in sprite_loader.sprites.keys():
        if 'jump' in anim.lower():
            print(f"  - {anim}")
            # 打印动画的帧信息
            frames = sprite_loader.sprites[anim]
            print(f"    帧数: {len(frames)}")
            for i, frame in enumerate(frames[:3]):  # 只显示前3帧
                print(f"    帧{i}: {frame}")
except Exception as e:
    print(f"加载精灵资源失败: {e}")
    import traceback
    traceback.print_exc()