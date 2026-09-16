import copy
import json
import os
import time

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入
    import logging

    def get_logger(name):
        return logging.getLogger(name)

_log = get_logger(__name__)


def _resolve_config_path(config_file):
    """配置文件的**正式位置**：最终存储（E 盘优先）→ 程序目录。

    历史遗留：旧版本把 `config.json` 直接写在程序目录，而那份在仓库里是**被跟踪的
    默认模板**。所以这里只**复制一份**到正式位置（`data_store.ensure_artifact`），
    绝不搬走或删除程序目录那份，免得 git 显示"默认配置被删了"。
    """
    if os.path.isabs(config_file):
        return config_file
    try:
        import data_store
        return data_store.app_file(config_file)
    except Exception:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", config_file)


class ConfigManager:
    """配置文件管理类，用于加载和保存配置"""
    
    def __init__(self, config_file="config.json"):
        # 获取配置文件的完整路径
        self.config_file = _resolve_config_path(config_file)
        self.config_version = "1.0"
        self.last_save_time = time.time()
        self.observers = []
        self.config = self._load_config()
        # 修复：备份清理原来只在"新建备份"时触发，而 _backup_config 仅在配置结构
        # 发生大变动时才被调用 —— 于是历史遗留的备份文件永远不会被收敛
        # （本机实测程序目录里积压了 106 个 config.json.backup.*，纯垃圾）。
        # 启动时主动剪枝一次，保证"最多保留 MAX_CONFIG_BACKUPS 个"这一承诺成立。
        try:
            self._prune_old_backups()
        except Exception as e:
            _log.debug("启动时清理历史配置备份失败（已忽略）: %s", e)
    
    @staticmethod
    def _default_config():
        return {
            "version": "1.0",
            "api": {
                "enabled": False,
                "api_key": "",
                "base_url": "http://localhost:8000",
                "model": "local-model",
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
                # 修复：加密功能尚未实现（api_key 等仍明文落盘），默认值改为
                # False 以避免"已启用加密"的虚假安全感；待实现 DPAPI/Fernet 后再开启。
                "enable_encryption": False,
                "encryption_key": "",
                "auto_lock": False,
                "lock_timeout": 300
            },
            "animation": {
                # 2026-09-13 用户反馈"动画播放太快"：默认帧率从 30 降回 6
                # （即 167ms/帧，与早期固定 167ms 的手感一致）。30fps 只适合游戏原速，
                # 桌宠逐帧播放会显得"抽搐式快进"。
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

    def _load_config(self):
        """加载配置文件"""
        default_config = self._default_config()
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(self.config_file):
            self._save_config(default_config)
            return default_config
        
        # 加载配置文件
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            # 修复：config.json 可能是合法 JSON 但非 dict（[]/null/数字/字符串），
            # 之后 .get("version") 会抛未捕获 AttributeError 导致启动即崩（无备份无回退）。
            # 非 dict 一律按损坏处理：备份后回退默认配置。
            if not isinstance(loaded_config, dict):
                _log.warning("配置文件根节点不是对象（%s），按损坏处理",
                             type(loaded_config).__name__)
                raise json.JSONDecodeError("config root is not dict", "", 0)

            # 配置版本检查和自动升级
            config_version = loaded_config.get("version", "0.0")
            if config_version != self.config_version:
                _log.info("配置版本升级: %s -> %s", config_version, self.config_version)
                # 创建配置备份
                self._backup_config(loaded_config)
                # 合并默认配置和加载的配置，确保所有必要的键都存在
                merged_config = self._merge_configs(default_config, loaded_config)
                # 更新版本号
                merged_config["version"] = self.config_version
            else:
                # 正常合并配置
                merged_config = self._merge_configs(default_config, loaded_config)

            # 自动迁移旧版云服务商配置到本地 AI 默认值
            api_section = merged_config.get("api", {})
            if not isinstance(api_section, dict):
                # 兜底：无论如何都不能让一个非 dict 的 api 节走到 .get() 上
                _log.warning("配置节 'api' 类型异常（%s），已重置为默认值", type(api_section).__name__)
                api_section = {}
                merged_config["api"] = api_section
            needs_migration = False
            _legacy_cloud_urls = ("https://api.doubao.com",
                                  "https://ark.cn-beijing.volces.com",
                                  "https://ark.cn-beijing.volces.com/api/v3")
            if api_section.get("base_url", "").lower() in _legacy_cloud_urls:
                api_section["base_url"] = "http://localhost:8000"
                needs_migration = True
            if api_section.get("model", "").lower().startswith("doubao"):
                api_section["model"] = "local-model"
                needs_migration = True
            if needs_migration:
                _log.info("检测到旧版云服务配置，已自动迁移为本地 AI 默认值")

            # 如果合并后的配置与加载的配置不同，保存更新后的配置
            if merged_config != loaded_config:
                self._save_config(merged_config)

            return merged_config
        # 修复：原先只捕获 (JSONDecodeError, IOError)，编码错误（UnicodeDecodeError）
        # 不在 IOError 体系内，会让启动直接崩溃；一并捕获并走"备份损坏文件→回退默认"流程。
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError,
                AttributeError, OSError) as e:
            # 修复：TypeError/AttributeError 也要接住——配置结构被写坏时它们会在
            # 合并/迁移阶段抛出，漏掉就会让"备份损坏文件→回退默认配置"这条兜底失效。
            _log.error("加载配置文件失败: %s", e)
            # 创建配置备份
            try:
                with open(self.config_file, 'r', encoding='utf-8', errors='replace') as f:
                    corrupt_config = f.read()
                backup_path = f"{self.config_file}.corrupt.{int(time.time())}"
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(corrupt_config)
                _log.info("已备份损坏的配置文件到: %s", backup_path)
            except OSError as backup_err:
                # 修复：原先裸 except 静默吞噬备份失败，现在至少留一条日志
                _log.warning("备份损坏配置失败: %s", backup_err)
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
            elif key in merged and isinstance(merged[key], dict) and not isinstance(value, dict):
                # 修复：用户手改配置 / 同步工具写坏时，可能把整"节"写成标量或数组
                # （如 "api": "oops"）。原实现直接用这个标量覆盖字典节，紧接着
                # _load_config 里就对它调用 .get()，抛出的 AttributeError 又不在
                # 捕获列表内 → 桌宠双击启动后完全不出现（只在控制台留一句"按回车键退出"）。
                # 这里保留默认节，只记录一条 warning。
                _log.warning("配置节 %r 应为 dict，实际是 %s，已忽略并保留默认值",
                             key, type(value).__name__)
            else:
                # 否则直接替换
                merged[key] = value
        
        return merged
    
    def _save_config(self, config) -> bool:
        """保存配置文件（原子写入）。修复：返回是否成功，供 update() 做失败回滚。"""
        try:
            temp_file = f"{self.config_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            os.replace(temp_file, self.config_file)
            self.last_save_time = time.time()
            return True
        except (OSError, TypeError, ValueError) as e:
            _log.error("保存配置文件失败: %s", e)
            if os.path.exists(f"{self.config_file}.tmp"):
                try:
                    os.remove(f"{self.config_file}.tmp")
                except OSError:
                    pass
            return False

    def get(self, key_path, default=None):
        """获取配置值"""
        if not isinstance(key_path, str) or not key_path:
            return default
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

    @staticmethod
    def _split_key_path(key_path):
        """校验并切分 key_path；非法（空串/None/含空段）返回 None。

        修复：原先 "a..b"/""/None 会创建 config[""] 垃圾数据。
        """
        if not isinstance(key_path, str) or not key_path:
            return None
        keys = key_path.split('.')
        if any(k == "" for k in keys):
            return None
        return keys

    @staticmethod
    def _ensure_nested(config, keys):
        """逐级确保嵌套字典存在，返回最内层字典。

        修复：原先 set() 与 update() 各写一份逐级建字典的循环（重复编码），收敛于此。
        收尾修复：遇到中间节点不是 dict 时记 warning，避免静默覆盖导致数据丢失。
        """
        for key in keys:
            if key not in config:
                config[key] = {}
            elif not isinstance(config[key], dict):
                _log.warning(
                    "配置节点 %r 原值类型为 %s 而非 dict，将被覆盖为空字典（数据可能丢失）",
                    key, type(config[key]).__name__,
                )
                config[key] = {}
            config = config[key]
        return config

    def set(self, key_path, value):
        """设置配置值"""
        # 修复：空/非法 key_path 原先会创建 config[""] 垃圾数据，现在直接拒绝
        keys = self._split_key_path(key_path)
        if keys is None:
            _log.warning("set() 拒绝非法 key_path: %r", key_path)
            return False

        # 保存快照，写盘失败时回滚内存状态（与 update() 一致）
        snapshot = copy.deepcopy(self.config)

        # 保存旧值用于通知观察者
        old_value = self.get(key_path)

        try:
            # 遍历除最后一个键之外的所有键，确保嵌套字典存在
            config = self._ensure_nested(self.config, keys[:-1])

            # 设置最后一个键的值
            config[keys[-1]] = value
        except (TypeError, AttributeError) as e:
            _log.error("set() 失败，已回滚: %s", e)
            self.config = snapshot
            return False

        # 保存配置文件；失败则回滚内存并放弃通知
        if not self._save_config(self.config):
            self.config = snapshot
            _log.error("set() 写盘失败，已回滚内存配置: %s", key_path)
            return False

        # 通知观察者配置变更
        self._notify_observers(key_path, old_value, value)
        return True

    def update(self, updates):
        """批量更新配置"""
        if not isinstance(updates, dict):
            return False

        # 修复：先校验全部 key_path 合法，避免半途插入垃圾数据后再回滚的复杂态
        valid_updates = {}
        for key_path, value in updates.items():
            if self._split_key_path(key_path) is not None:
                valid_updates[key_path] = value
            else:
                _log.warning("update() 跳过非法 key_path: %r", key_path)
        if not valid_updates:
            return False

        # 修复：保存快照，写盘失败时回滚内存状态（原先保存失败时内存与磁盘不一致）
        snapshot = copy.deepcopy(self.config)

        # 记录变更信息
        changes = []

        try:
            for key_path, value in valid_updates.items():
                old_value = self.get(key_path)
                keys = key_path.split('.')

                # 遍历创建嵌套字典
                config = self._ensure_nested(self.config, keys[:-1])

                # 设置值
                config[keys[-1]] = value
                changes.append((key_path, old_value, value))
        except (TypeError, AttributeError) as e:
            _log.error("批量更新配置失败，已回滚: %s", e)
            self.config = snapshot
            return False

        # 一次性保存配置；失败则回滚内存并放弃通知
        if not self._save_config(self.config):
            self.config = snapshot
            _log.error("批量更新写盘失败，已回滚内存配置")
            return False

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
                _log.warning("通知观察者失败: %s", e)

    # 修复：配置备份此前没有任何保留上限，配置版本一旦反复演进，备份文件会在
    # 程序目录里无限堆积（实测已累积 100+ 个 config.json.backup.*，纯垃圾文件）。
    # 保留最近 MAX_CONFIG_BACKUPS 个，其余自动清理。
    MAX_CONFIG_BACKUPS = 10

    def _backup_config(self, config):
        """创建配置备份"""
        try:
            backup_path = f"{self.config_file}.backup.{int(time.time())}"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            _log.info("已创建配置备份: %s", backup_path)
            self._prune_old_backups()
        except (OSError, TypeError, ValueError) as e:
            _log.warning("创建配置备份失败: %s", e)

    def _prune_old_backups(self, keep=None):
        """只保留最近 keep 个配置备份，删除更早的（按文件名时间戳排序）。"""
        if keep is None:
            keep = self.MAX_CONFIG_BACKUPS
        prefix = f"{self.config_file}.backup."
        try:
            files = [os.path.join(os.path.dirname(self.config_file), n)
                     for n in os.listdir(os.path.dirname(self.config_file))
                     if n.startswith(os.path.basename(prefix))]
        except OSError as e:
            _log.debug("枚举配置备份失败（已忽略）: %s", e)
            return

        def _ts(path):
            # 兼容 hash 后缀之外的非数字文件名：解析失败视为最旧
            try:
                return int(os.path.basename(path).rsplit('.', 1)[-1])
            except (ValueError, IndexError):
                return 0

        files.sort(key=_ts, reverse=True)
        for old in files[keep:]:
            try:
                os.remove(old)
                _log.info("已清理过期配置备份: %s", os.path.basename(old))
            except OSError as e:
                # 单个文件删不掉不影响主流程（可能被占用/无权限）
                _log.debug("清理配置备份失败（已忽略）: %s", e)
    
    def reset_config(self, section=None):
        """重置配置到默认值"""
        defaults = self._default_config()

        if section:
            # 按 section 重置：复用 update() 的回滚与通知逻辑
            if section not in defaults:
                return False
            section_defaults = defaults[section]
            if not isinstance(section_defaults, dict):
                return False
            updates = {f"{section}.{key}": value for key, value in section_defaults.items()}
            return self.update(updates)
        else:
            # 全量重置：保存快照，写盘失败时回滚
            snapshot = copy.deepcopy(self.config)
            self.config = copy.deepcopy(defaults)

            if not self._save_config(self.config):
                self.config = snapshot
                _log.error("全量重置配置写盘失败，已回滚内存配置")
                return False

            # 为每个顶级 section 发送变更通知
            for key in defaults:
                if isinstance(defaults[key], dict):
                    self._notify_observers(key, snapshot.get(key), self.config.get(key))
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

        # AI 配置验证（修复：手改配置缺键时直接 [] 索引会 KeyError，改用 .get）
        api_config = self.config.get("api", {}) or {}
        if api_config.get("enabled"):
            if not api_config.get("api_key"):
                return False, "AI已启用但未设置API密钥"
            if not api_config.get("base_url"):
                return False, "AI已启用但未设置基础URL"

        # ---- 数值范围校验 ----
        # 合理范围说明：
        #   animation.fps:  1 ~ 120 fps（<=0 会导致除零错误；过高无实际意义且占用性能）
        #   movement.speed: > 0（负数会导致移动方向反转等异常）
        #   ui.dialogue_duration: >= 1000 ms（即至少 1 秒，否则对话瞬间消失用户无法阅读）
        # 发现非法值时：记录 warning 日志并回退到默认值，不影响整体验证结果。

        defaults = self._default_config()

        # animation.fps 校验
        anim_config = self.config.get("animation", {})
        if isinstance(anim_config, dict):
            fps = anim_config.get("fps")
            if not isinstance(fps, (int, float)) or fps <= 0 or fps > 120:
                default_fps = defaults["animation"]["fps"]
                _log.warning(
                    "配置 animation.fps = %r 非法（合理范围: 1~120），已回退为默认值 %s",
                    fps, default_fps)
                anim_config["fps"] = default_fps

        # movement.speed 校验
        move_config = self.config.get("movement", {})
        if isinstance(move_config, dict):
            speed = move_config.get("speed")
            if not isinstance(speed, (int, float)) or speed <= 0:
                default_speed = defaults["movement"]["speed"]
                _log.warning(
                    "配置 movement.speed = %r 非法（必须 > 0），已回退为默认值 %s",
                    speed, default_speed)
                move_config["speed"] = default_speed

        # ui.dialogue_duration 校验
        ui_config = self.config.get("ui", {})
        if isinstance(ui_config, dict):
            duration = ui_config.get("dialogue_duration")
            if not isinstance(duration, (int, float)) or duration < 1000:
                default_duration = defaults["ui"]["dialogue_duration"]
                _log.warning(
                    "配置 ui.dialogue_duration = %r 非法（必须 >= 1000 毫秒），已回退为默认值 %s",
                    duration, default_duration)
                ui_config["dialogue_duration"] = default_duration

        return True, "配置验证通过"
    
    def get_api_config(self):
        """获取 AI 相关配置"""
        return self.config.get("api", {})
    
    def update_api_config(self, api_config):
        """更新 AI 相关配置"""
        updates = {f"api.{key}": value for key, value in api_config.items()}
        self.update(updates)
    
    def is_api_enabled(self):
        """检查API是否启用"""
        return self.config.get("api", {}).get("enabled", False)
    
    def enable_api(self, enabled=True):
        """启用或禁用API"""
        self.set("api.enabled", enabled)
    
    def get_privacy_config(self):
        """获取隐私相关配置"""
        return self.config.get("privacy", {})
    
    def update_privacy_config(self, privacy_config):
        """更新隐私相关配置"""
        updates = {f"privacy.{key}": value for key, value in privacy_config.items()}
        self.update(updates)
    
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
        updates = {f"security.{key}": value for key, value in security_config.items()}
        self.update(updates)
    
    def is_encryption_enabled(self):
        """检查是否启用加密。注意：当前版本加密功能尚未实现，
        无论配置如何都返回 False，避免上层产生"已加密"的错觉。"""
        return False
