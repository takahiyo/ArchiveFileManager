"""実行ファイル横に保存する画面設定。"""
import configparser
import logging
import os
import config


def load_settings():
    """INI の UI セクションを辞書で返す。欠落・破損時は空辞書。"""
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(os.path.join(config.get_exe_dir(), config.UI_SETTINGS_FILE), encoding='utf-8')
        return dict(parser['UI']) if parser.has_section('UI') else {}
    except (OSError, configparser.Error, UnicodeError):
        logging.exception('画面設定の読み込み失敗。初期値を使用します')
        return {}


def save_settings(values):
    """設定辞書を一時ファイル経由で保存し、途中終了による破損を防ぐ。"""
    path = os.path.join(config.get_exe_dir(), config.UI_SETTINGS_FILE)
    parser = configparser.ConfigParser(interpolation=None)
    parser['UI'] = {key: str(value) for key, value in values.items()}
    try:
        with open(path + '.tmp', 'w', encoding='utf-8') as stream:
            parser.write(stream)
        os.replace(path + '.tmp', path)
    except OSError:
        logging.exception('画面設定の保存失敗: %s', path)
