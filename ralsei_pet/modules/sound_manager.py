# -*- coding: utf-8 -*-
"""
声音管理器。
支持 WAV（QSound）和 OGG（QMediaPlayer）。缺少文件或播放失败时静默降级。
"""

import os
from PyQt5.QtCore import QObject, QUrl


class SoundManager(QObject):
    """管理桌宠音效。所有方法都做了容错，无音频文件时静默。"""

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
        # QSound（WAV）
        try:
            from PyQt5.QtMultimedia import QSound
            self._QSound = QSound
        except Exception:
            self._QSound = None
        # QMediaPlayer（OGG 等）
        self._media_player = None
        try:
            from PyQt5.QtMultimedia import QMediaPlayer
            self._QMediaPlayer = QMediaPlayer
        except Exception:
            self._QMediaPlayer = None

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)

    def _resolve_path(self, filename: str) -> str:
        """解析音效文件路径，支持直接传绝对路径或文件名。"""
        if os.path.isabs(filename) and os.path.isfile(filename):
            return filename
        for d in self._candidate_dirs:
            path = os.path.join(d, filename)
            if os.path.isfile(path):
                return path
        return None

    def _play_wav(self, path: str):
        """用 QSound 播放 WAV。"""
        if not self._enabled or self._QSound is None:
            return
        try:
            self._QSound.play(path)
        except Exception:
            pass

    def _play_ogg(self, path: str):
        """用 QMediaPlayer 播放 OGG（每次新建 player 避免重叠冲突）。"""
        if not self._enabled or self._QMediaPlayer is None:
            return
        try:
            player = self._QMediaPlayer(self)
            player.setMedia(QUrl.fromLocalFile(path))
            player.setVolume(80)
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
        except Exception:
            pass

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
