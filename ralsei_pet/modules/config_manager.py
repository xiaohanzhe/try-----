import json
import os
import time

class ConfigManager:
    """配置文件管理类，用于加载和保存配置"""
    
    def __init__(self, config_file="config.json"):
        # 获取配置文件的完整路径
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", config_file)
        self.config_version = "1.0"  # 配置版本
        self.last_save_time = time.time()
        self.save_delay = 0.5  # 保存延迟，避免频繁写入
        self.observers = []  # 配置变更观察者
        self.config = self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        default_config = {
            "version": self.config_version,
            "api": {
                "enabled": False,
                "api_key": "",
                "base_url": "https://api.doubao.com",
                "model": "doubao-pro",
                "agent_id": "",
                "api_version": "v1",
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 1.0
            },
            "privacy": {
                "enable_usage_data": False,
                "enable_daily_report": False,
                "enable_activity_tracking": False,
                "enable_api_data_logging": False,
                "clear_data_on_exit": False,
                "data_retention_days": 30
            },
            "security": {
                "enable_encryption": True,
                "encryption_key": "",
                "auto_lock": False,
                "lock_timeout": 300
            },
            "animation": {
                "fps": 6,
                "frame_delay": 166
            },
            "movement": {
                "speed": 5.0,
                "min_speed": 3.0,
                "max_speed": 8.0
            },
            "ui": {
                "dialogue_duration": 5000,
                "typing_speed": 50
            },
            "behavior": {
                "energy_recovery_rate": 1.0,
                "hunger_increase_rate": 0.5
            }
        }
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(self.config_file):
            self._save_config(default_config)
            return default_config
        
        # 加载配置文件
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            # 配置版本检查和自动升级
            config_version = loaded_config.get("version", "0.0")
            if config_version != self.config_version:
                print(f"配置版本升级: {config_version} -> {self.config_version}")
                # 创建配置备份
                self._backup_config(loaded_config)
                # 合并默认配置和加载的配置，确保所有必要的键都存在
                merged_config = self._merge_configs(default_config, loaded_config)
                # 更新版本号
                merged_config["version"] = self.config_version
            else:
                # 正常合并配置
                merged_config = self._merge_configs(default_config, loaded_config)
            
            # 如果合并后的配置与加载的配置不同，保存更新后的配置
            if merged_config != loaded_config:
                self._save_config(merged_config)
            
            return merged_config
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载配置文件失败: {e}")
            # 创建配置备份
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    corrupt_config = f.read()
                backup_path = f"{self.config_file}.corrupt.{int(time.time())}"
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(corrupt_config)
                print(f"已备份损坏的配置文件到: {backup_path}")
            except:
                pass
            # 如果加载失败，使用默认配置
            self._save_config(default_config)
            return default_config
    
    def _merge_configs(self, default, loaded):
        """递归合并配置"""
        merged = default.copy()
        
        for key, value in loaded.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # 如果是嵌套字典，递归合并
                merged[key] = self._merge_configs(merged[key], value)
            else:
                # 否则直接替换
                merged[key] = value
        
        return merged
    
    def _save_config(self, config):
        """保存配置文件"""
        # 延迟保存机制，避免频繁写入
        current_time = time.time()
        if current_time - self.last_save_time < self.save_delay:
            return
        
        try:
            # 创建临时文件，写入成功后再替换原文件，提高安全性
            temp_file = f"{self.config_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            # 替换原文件
            os.replace(temp_file, self.config_file)
            
            # 更新最后保存时间
            self.last_save_time = current_time
        except IOError as e:
            print(f"保存配置文件失败: {e}")
            # 清理临时文件
            if os.path.exists(f"{self.config_file}.tmp"):
                try:
                    os.remove(f"{self.config_file}.tmp")
                except:
                    pass
    
    def get(self, key_path, default=None):
        """获取配置值"""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            return value
        except (TypeError, AttributeError):
            return default
    
    def set(self, key_path, value):
        """设置配置值"""
        keys = key_path.split('.')
        config = self.config
        
        # 保存旧值用于通知观察者
        old_value = self.get(key_path)
        
        # 遍历除最后一个键之外的所有键，确保嵌套字典存在
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        
        # 设置最后一个键的值
        config[keys[-1]] = value
        
        # 保存配置文件
        self._save_config(self.config)
        
        # 通知观察者配置变更
        self._notify_observers(key_path, old_value, value)
    
    def update(self, updates):
        """批量更新配置"""
        if not isinstance(updates, dict):
            return False
        
        # 记录变更信息
        changes = []
        
        for key_path, value in updates.items():
            old_value = self.get(key_path)
            keys = key_path.split('.')
            config = self.config
            
            # 遍历创建嵌套字典
            for key in keys[:-1]:
                if key not in config or not isinstance(config[key], dict):
                    config[key] = {}
                config = config[key]
            
            # 设置值
            config[keys[-1]] = value
            changes.append((key_path, old_value, value))
        
        # 一次性保存配置
        self._save_config(self.config)
        
        # 通知所有变更
        for change in changes:
            self._notify_observers(*change)
        
        return True
    
    def add_observer(self, observer):
        """添加配置变更观察者"""
        if observer not in self.observers:
            self.observers.append(observer)
    
    def remove_observer(self, observer):
        """移除配置变更观察者"""
        if observer in self.observers:
            self.observers.remove(observer)
    
    def _notify_observers(self, key_path, old_value, new_value):
        """通知观察者配置变更"""
        for observer in self.observers:
            try:
                observer.on_config_change(key_path, old_value, new_value)
            except Exception as e:
                print(f"通知观察者失败: {e}")
    
    def _backup_config(self, config):
        """创建配置备份"""
        try:
            backup_path = f"{self.config_file}.backup.{int(time.time())}"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print(f"已创建配置备份: {backup_path}")
        except Exception as e:
            print(f"创建配置备份失败: {e}")
    
    def reset_config(self, section=None):
        """重置配置到默认值"""
        """重置配置到默认值"""
        default_config = self._load_config()
        
        if section:
            # 只重置特定部分
            if section in default_config:
                self.config[section] = default_config[section]
                self._save_config(self.config)
                self._notify_observers(section, None, self.config[section])
                return True
            return False
        else:
            # 重置所有配置
            self.config = default_config
            self._save_config(self.config)
            self._notify_observers("*")
            return True
    
    def get_full_config(self):
        """获取完整配置"""
        return self.config.copy()
    
    def validate_config(self):
        """验证配置的完整性和正确性"""
        # 基础验证：检查必要的配置部分是否存在
        required_sections = ["api", "privacy", "security", "animation", "movement", "ui", "behavior"]
        for section in required_sections:
            if section not in self.config:
                return False, f"缺少必要的配置部分: {section}"
        
        # API配置验证
        api_config = self.config["api"]
        if api_config["enabled"]:
            if not api_config["api_key"]:
                return False, "API已启用但未设置API密钥"
            if not api_config["base_url"]:
                return False, "API已启用但未设置基础URL"
        
        return True, "配置验证通过"
    
    def get_api_config(self):
        """获取API相关配置"""
        return self.config.get("api", {})
    
    def update_api_config(self, api_config):
        """更新API相关配置"""
        self.config["api"].update(api_config)
        self._save_config(self.config)
    
    def is_api_enabled(self):
        """检查API是否启用"""
        return self.config.get("api", {}).get("enabled", False)
    
    def enable_api(self, enabled=True):
        """启用或禁用API"""
        self.config["api"]["enabled"] = enabled
        self._save_config(self.config)
    
    def get_privacy_config(self):
        """获取隐私相关配置"""
        return self.config.get("privacy", {})
    
    def update_privacy_config(self, privacy_config):
        """更新隐私相关配置"""
        self.config["privacy"].update(privacy_config)
        self._save_config(self.config)
    
    def is_usage_data_enabled(self):
        """检查是否启用使用数据收集"""
        return self.config.get("privacy", {}).get("enable_usage_data", False)
    
    def is_activity_tracking_enabled(self):
        """检查是否启用活动跟踪"""
        return self.config.get("privacy", {}).get("enable_activity_tracking", False)
    
    def get_security_config(self):
        """获取安全相关配置"""
        return self.config.get("security", {})
    
    def update_security_config(self, security_config):
        """更新安全相关配置"""
        self.config["security"].update(security_config)
        self._save_config(self.config)
    
    def is_encryption_enabled(self):
        """检查是否启用加密"""
        return self.config.get("security", {}).get("enable_encryption", True)
