# -*- coding: utf-8 -*-
"""
声音管理器。
支持 WAV（QSound）和 OGG（QMediaPlayer）。缺少文件或播放失败时静默降级。
"""

import os
from PyQt5.QtCore import QObject, QUrl

try:
    from logger_utils import get_logger
except ImportError:  # 允许被包外单独导入
    import logging

    def get_logger(name):
        return logging.getLogger(name)

_log = get_logger(__name__)


class SoundManager(QObject):
    """管理桌宠音效。所有方法都做了容错，无音频文件时静默。"""

    # 音量默认值（0-100）。模块级常量，方便统一调整；实例可经 set_volume 覆盖。
    DEFAULT_VOLUME = 80

    def __init__(self, sounds_dir=None, parent=None):
        super().__init__(parent)
        # 候选目录：优先 assets/sounds，其次仓库根目录（历史上音频曾放在根目录，
        # 兼容两种布局，避免音效"静默失效"）。
        self._candidate_dirs = []
        if sounds_dir:
            self._candidate_dirs.append(sounds_dir)
        else:
            _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ralsei_pet/
            self._candidate_dirs.append(os.path.join(_here, "assets", "sounds"))
            self._candidate_dirs.append(os.path.dirname(_here))  # 仓库根（与素材同级）
        self.sounds_dir = self._candidate_dirs[0]
        self._enabled = True
        # 音量（0-100），修复：原先硬编码在 _play_ogg 里不可配置
        self._volume = self.DEFAULT_VOLUME
        # QSound（WAV）
        try:
            from PyQt5.QtMultimedia import QSound
            self._QSound = QSound
        except Exception as e:
            self._QSound = None
            _log.debug("QSound 不可用（%s），WAV 音效将被跳过", e)
        # QMediaPlayer（OGG 等）
        try:
            from PyQt5.QtMultimedia import QMediaPlayer
            self._QMediaPlayer = QMediaPlayer
        except Exception as e:
            self._QMediaPlayer = None
            _log.debug("QMediaPlayer 不可用（%s），OGG/MP3 音效将被跳过", e)

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)

    def set_volume(self, volume: int):
        """设置音量（0-100），越界自动钳位。"""
        try:
            volume = int(volume)
        except (TypeError, ValueError):
            volume = self.DEFAULT_VOLUME
        self._volume = max(0, min(100, volume))

    def get_volume(self) -> int:
        return self._volume

    def _resolve_path(self, filename: str) -> str:
        """解析音效文件路径，支持直接传绝对路径或文件名。"""
        if not isinstance(filename, str) or not filename:
            return None
        if os.path.isabs(filename) and os.path.isfile(filename):
            return filename
        for d in self._candidate_dirs:
            path = os.path.join(d, filename)
            if os.path.isfile(path):
                return path
        # 修复：原先静默返回 None，音效缺失无从排查；现在留 debug 日志
        _log.debug("音效文件未找到: %s（候选目录: %s）", filename, self._candidate_dirs)
        return None

    def _play_wav(self, path: str):
        """用 QSound 播放 WAV。"""
        if not self._enabled or self._QSound is None:
            return
        try:
            self._QSound.play(path)
        except Exception as e:
            _log.debug("播放 WAV 失败 %s: %s", path, e)

    def _play_ogg(self, path: str):
        """用 QMediaPlayer 播放 OGG（每次新建 player 避免重叠冲突）。"""
        if not self._enabled or self._QMediaPlayer is None:
            return
        try:
            player = self._QMediaPlayer(self)
            player.setMedia(QUrl.fromLocalFile(path))
            # 修复：音量原先硬编码 80，现在走可配置的 set_volume
            player.setVolume(self._volume)
            player.play()
            # 播放结束后自动清理（避免内存泄漏）
            # 修复：原来只在 EndOfMedia 时 deleteLater——文件缺失/无音频设备/
            # 编码不支持时 mediaStatusChanged 会发 Error/InvalidMedia，player 永不
            # 释放（打字机每字一个 player，会持续累积泄漏）。现在终止/出错状态都清理。
            _finish_states = (self._QMediaPlayer.EndOfMedia,
                              self._QMediaPlayer.Error,
                              self._QMediaPlayer.InvalidMedia)
            player.mediaStatusChanged.connect(
                lambda status, p=player: p.deleteLater() if status in _finish_states else None
            )
        except Exception as e:
            _log.debug("播放音频失败 %s: %s", path, e)

    def play_file(self, filename: str):
        """播放指定音效文件（自动识别 wav/ogg）。文件不存在则静默。"""
        path = self._resolve_path(filename)
        if path is None:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".wav":
            self._play_wav(path)
        elif ext in (".ogg", ".mp3", ".m4a"):
            self._play_ogg(path)
        else:
            # 未知格式尝试 QMediaPlayer
            self._play_ogg(path)

    # ---- 常用音效 ----

    def play_typewriter(self):
        """打字机音效：txtralsei.ogg（每字一声）。"""
        self.play_file("txtralsei.ogg")

    def play_spell(self):
        """施法音效：snd_spellcast.wav。"""
        self.play_file("snd_spellcast.wav")

    def play_spellcast(self):
        """施法音效别名。"""
        self.play_file("snd_spellcast.wav")

    def play_splat(self):
        """被踩/摔扁音效：snd_splat.wav。"""
        self.play_file("snd_splat.wav")

    def play_click(self):
        self.play_file("click.wav")

    def play_happy(self):
        self.play_file("happy.wav")

    def play_sad(self):
        self.play_file("sad.wav")

    def play_jump(self):
        self.play_file("jump.wav")

    def play_footstep(self):
        self.play_file("footstep.wav")
