# -*- coding: utf-8 -*-
"""
ArchiveFileManager - GUI メインアプリケーション
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

try:
    from config import APP_NAME, APP_VERSION, validate_environment
except ImportError:
    from ..config import APP_NAME, APP_VERSION, validate_environment

from .convert_tab import ConvertTab
from .empty_tab import EmptyTab
from .log_handler import GuiLogHandler

logger = logging.getLogger(__name__)

class ArchiveFileManagerGUI:
    """
    アプリケーションのメインウィンドウとタブ管理を担当するクラス。
    """
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("640x720")
        self.root.minsize(600, 650)
        
        # スタイル設定
        self.style = ttk.Style()
        self.style.configure("TButton", padding=5)
        self.style.configure("Header.TLabel", font=("MS Gothic", 12, "bold"))
        self.style.configure("Status.TLabel", font=("MS Gothic", 9))
        
        self._setup_ui()
        self._setup_logging()
        # 起動時には警告を表示するが、アプリは閉じない
        self._check_env_init()

    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # タブコントロール
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # タブ1: 圧縮変換
        self.tab_convert = ConvertTab(self.notebook, log_callback=self._log_direct)
        self.notebook.add(self.tab_convert, text=" 📦 圧縮変換 ")

        # タブ2: 空フォルダ
        self.tab_empty = EmptyTab(self.notebook, log_callback=self._log_direct)
        self.notebook.add(self.tab_empty, text=" 🗂 空フォルダ ")

    def _setup_logging(self):
        """
        GUIへのログ出力をセットアップ。
        ConvertTab 内のテキストウィジェットをターゲットにします。
        """
        self.gui_handler = GuiLogHandler(self.tab_convert.log_text)
        self.gui_handler.setFormatter(logging.Formatter('%(message)s'))
        logging.getLogger().addHandler(self.gui_handler)

    def _log_direct(self, message):
        """各タブからの直接ログ（必要に応じて）"""
        logger.info(message)

    def _check_env_init(self):
        """起動時の環境チェック（警告のみ）"""
        errors = validate_environment()
        if errors:
            logger.warning("環境に問題が見つかりました（起動は続行します）: " + ", ".join(errors))
            # タブ内のUIが既に警告を表示しているため、ここでは通知のみ
