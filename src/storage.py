# -*- coding: utf-8 -*-
"""
ArchiveFileManager - 設定・履歴・お気に入りの永続化
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.expanduser("~/.archive_file_manager_settings.json")

class Storage:
    def __init__(self):
        self.data = {
            "winrar_dir": "",
            "history": [],
            "favorites": []
        }
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except Exception as e:
                logger.error(f"設定の読み込みに失敗: {e}")

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"設定の保存に失敗: {e}")

    def get_winrar_dir(self):
        return self.data.get("winrar_dir", "")

    def set_winrar_dir(self, path):
        self.data["winrar_dir"] = path
        self.save()

    def add_history(self, path):
        if not path: return
        history = self.data.get("history", [])
        if path in history:
            history.remove(path)
        history.insert(0, path)
        self.data["history"] = history[:10]  # 直近10件
        self.save()

    def add_favorite(self, path):
        if not path: return
        favorites = self.data.get("favorites", [])
        if path not in favorites:
            favorites.append(path)
            self.save()

    def remove_favorite(self, path):
        favorites = self.data.get("favorites", [])
        if path in favorites:
            favorites.remove(path)
            self.save()
