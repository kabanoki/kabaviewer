#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import hashlib
import shutil
from datetime import datetime
from PyQt5.QtCore import QSettings
import piexif
from PIL import Image
import json

# スキーマバージョン: テーブル/カラム追加のたびに +1 する
SCHEMA_VERSION = 2

# 「未分類」は仮想グループとして予約する（DB に実体を作らない）
UNCLASSIFIED_GROUP = "未分類"

# 廃止グループ → 統合先グループのマッピング
# ここに登録されたグループは add_group / analyzer シード でも再生成されず、
# _migrate_group_structure で既存タグが統合先へ移動される
_MERGED_INTO: dict = {
    "制服": "衣装",
}

# デフォルトのタグタクソノミー定義
# キー = グループ名、値 = そのグループに初期割当するタグのリスト
# 既に手動でグループ割当済みのタグは上書きしない
# auto_tag_analyzer.get_default_mapping_rules() の具体値タグ（チャイナドレス/ツインテール/
# ぱっつん 等）を網羅する形で整備している
DEFAULT_TAG_GROUPS = {
    "性的ポーズ": ["性的ポーズ", "体位",
                   "騎乗位", "背面騎乗位", "アマゾン体位", "背後位", "フェラチオ",
                   "足コキ", "手コキ", "側位", "正常位", "パイズリ", "寝バック",
                   "立ちバック", "座位", "太ももで締め付ける", "触手", "スライム"],
    "成人向け":   ["成人向け", "R-18", "ヌード"],
    "キャラクター":   [],
    "作品":   [],
    "表情":       ["表情", "笑顔", "泣き顔", "怒り顔", "照れ顔", "驚き顔", "真顔", "ウィンク"],
    "髪色":       ["髪色",
                   "金髪", "茶髪", "黒髪", "白髪", "銀髪", "赤髪", "青髪", "緑髪",
                   "ピンク髪", "紫髪", "黄髪", "灰髪", "オレンジ髪", "ブロンズ髪",
                   "マルチカラー髪"],
    "髪型":       ["髪型", "ロングヘア", "ショートヘア", "ツインテール", "ポニーテール",
                   "三つ編み", "ストレートヘア", "ウェーブヘア",
                   # 長さ
                   "ベリーショート", "ピクシーカット", "ボブカット", "セミロング",
                   "ベリーロング", "超ロング",
                   # ポニーテール
                   "ハイポニー", "ローポニー", "サイドポニー", "編み込みポニー",
                   # ツインテール
                   "ショートツイン", "ハイツイン", "ローツイン", "サイドツイン", "おさげ",
                   # お団子
                   "お団子", "ヘアバン", "ハイバン", "ローバン", "サイドバン",
                   "ダブルバン", "編み込みバン",
                   # 編み込み
                   "編み込み", "クラウンブレイド", "フレンチブレイド",
                   "三つ編みツインテール", "四つ編み", "両サイドに編み込み",
                   "サイドブレイド", "編み込みリング",
                   "低い位置で結んだ長い三つ編み",
                   # アレンジ
                   "ハーフアップ", "ハーフアップブレイド", "ツーサイドアップ",
                   # 質感
                   "ドリルヘア", "リングレット", "ドレッドロック", "コーンロウ",
                   # 特殊部位
                   "アホ毛", "染めアホ毛", "ハートアホ毛", "動くアホ毛",
                   "アンテナヘア", "もみあげ", "頭の側面から伸びる毛束",
                   "外はね", "レイヤード",
                   # 前髪
                   "前髪", "ぱっつん", "姫カット", "斜めの前髪", "アーチ状の前髪",
                   "アシンメトリ", "交差した前髪", "はねた前髪", "編み込み前髪",
                   "長い前髪", "短い前髪", "シースルーバング", "センター分け",
                   "2ヶ所で分けた前髪", "両目の間の髪", "センターに垂れた前髪",
                   "流した前髪", "ピン留め前髪", "後ろに流した髪", "後ろにまとめる",
                   "目にかかる髪", "片目にかかる髪", "両目にかかる髪"],
    "目の色":     ["目の色", "青い目", "緑の目", "茶色い目", "赤い目", "紫の目",
                   "金色の目", "黒い目", "ピンクの目"],
    "肌の色":     ["肌の色", "色白", "褐色肌", "日焼け肌", "浅黒い肌",
                   "白肌", "黒肌", "茶肌"],
    "衣装":       ["衣装", "ファッション", "ドレス", "着物", "水着", "ビキニ",
                   "ランジェリー", "アーマー", "コスプレ",
                   # 水着
                   "Oリングビキニ", "スポーツブラビキニ", "ホルタービキニ",
                   "フラウンスビキニ", "スクール水着", "レーシングスタイル水着",
                   "ラッシュガード",
                   # ドレス・ワンピース系
                   "背中開きドレス", "黒ドレス", "ショートドレス", "セータードレス",
                   "チャイナドレス", "中国風衣装",
                   # トップス
                   "白シャツ", "黒ジャケット", "ジャージ上", "タートルネック",
                   "リブセーター", "童貞を殺す服", "セーター", "キャミソール",
                   # ボトムス・スカート
                   "ハイウエストスカート", "プリーツスカート", "ショートパンツ", "ブルマ",
                   # 靴・レッグウェア
                   "ブーツ", "編み上げブーツ", "ニーハイブーツ", "ハイヒール",
                   "ローファー", "靴",
                   "黒パンティストッキング", "パンティストッキング",
                   "ニーソックス", "ソックス", "絶対領域ソックス", "ニーソ",
                   # 部位・特徴
                   "肩出し", "胸元カット", "フリル", "ゴシック", "長袖", "半袖",
                   "ノースリーブ", "アームレス", "袖まくり", "リボン", "ネクタイ",
                   # コスチューム
                   "メイド", "メイドヘッドドレス", "ナース", "ナースキャップ",
                   "巫女", "修女", "体操服", "裸",
                   # 制服
                   "制服", "セーラー服", "ブレザー", "ブレザー制服", "学生服"],
    "身体":       ["身体", "体型", "巨乳", "貧乳", "大きい胸", "小さい胸", "乳首",
                   "平らな胸", "普通の胸", "巨胸"],
    "屋外":       ["屋外", "自然", "公園", "街", "ビーチ", "森", "山", "空",
                   "村", "自然の背景", "街から遠く離れた草原",
                   "プール", "海", "庭", "屋上", "花の前景", "メタバース"],
    "屋内":       ["屋内", "建物", "部屋", "寝室", "キッチン", "リビング"],
    "学校":       ["学校", "教育", "教室", "体育館"],
    "ポーズ":     ["ポーズ", "動作", "立ち", "座り", "寝そべり", "歩く", "走る"],
    "アニメ":     ["アニメ", "二次元"],
    "リアル":     ["リアル", "写実的"],
    "AI生成":     ["AI生成", "人工知能"],
    "季節":       ["季節", "春", "夏", "秋", "冬", "花見", "クリスマス"],
    "時間":       ["時間帯", "朝", "昼", "夕方", "夜"],
}


def _migrate(conn, db_path):
    """SQLiteスキーマのマイグレーション処理"""
    current = conn.execute("PRAGMA user_version").fetchone()[0]

    if current < 1:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS image_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT UNIQUE NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                tags TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_modified_at TIMESTAMP,
                is_favorite BOOLEAN DEFAULT 0
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON image_tags(file_hash)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON image_tags(file_path)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_tags ON image_tags(tags)')

    if current < 2:
        # v1.10.0: タググループ管理テーブルを追加
        if os.path.exists(db_path):
            shutil.copy2(db_path, db_path + ".bak")
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tag_groups (
                group_id   TEXT PRIMARY KEY,
                sort_order INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tag_group_members (
                tag      TEXT PRIMARY KEY,
                group_id TEXT NOT NULL
            )
        ''')

    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


class TagManager:
    """
    KabaViewer用スマート・ハイブリッドタグ管理システム
    
    - 高速検索用SQLiteインデックス
    - ポータブル性のためのEXIF埋め込み
    - 障害時復旧用QSettingsバックアップ
    """
    
    def __init__(self, app_data_dir="~/.kabaviewer"):
        self.app_data_dir = os.path.expanduser(app_data_dir)
        os.makedirs(self.app_data_dir, exist_ok=True)
        
        self.db_path = os.path.join(self.app_data_dir, "tags.db")
        self.settings = QSettings("MyCompany", "ImageViewerApp")

        # お気に入り状態変更時の通知リスナー（callable(file_path: str, is_favorite: bool)）
        self._favorite_listeners: list = []

        self.init_database()
        self._migrate_group_structure()
        self.seed_default_tag_groups()
        self.seed_groups_from_analyzer_defaults()

    def add_favorite_listener(self, callback):
        """お気に入り状態が変更された際に呼ばれるコールバックを登録する。

        callback(file_path: str, is_favorite: bool) はメインスレッドから呼び出される前提
        （SQLite 書き込み直後）。listener から例外が出ても他リスナーに影響しないよう握りつぶす。
        """
        if callback not in self._favorite_listeners:
            self._favorite_listeners.append(callback)

    def remove_favorite_listener(self, callback):
        if callback in self._favorite_listeners:
            self._favorite_listeners.remove(callback)

    def _notify_favorite_changed(self, file_path, is_favorite):
        for cb in list(self._favorite_listeners):
            try:
                cb(file_path, is_favorite)
            except Exception as e:
                print(f"favorite listener error: {e}")
    
    def init_database(self):
        """SQLiteデータベースの初期化・マイグレーション"""
        conn = sqlite3.connect(self.db_path)
        try:
            _migrate(conn, self.db_path)
        finally:
            conn.close()
    
    # ─────────────────────────────────────────
    # タググループ管理
    # ─────────────────────────────────────────

    def _migrate_group_structure(self):
        """DEFAULT_TAG_GROUPS の構造変更に追従するためのグループ統合マイグレーション。

        _MERGED_INTO に登録されたグループを統合先へ移動し、旧グループを削除する。
        フラグにより既存ユーザーに対して1回だけ実行される。
        """
        for old_group, new_group in _MERGED_INTO.items():
            key = f"tag_group_migrate_{old_group}_to_{new_group}_v1"
            if self.settings.value(key, False, type=bool):
                continue
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    "UPDATE tag_group_members SET group_id = ? WHERE group_id = ?",
                    (new_group, old_group)
                )
                conn.execute("DELETE FROM tag_groups WHERE group_id = ?", (old_group,))
                conn.commit()
            finally:
                conn.close()
            self.settings.setValue(key, True)

    def seed_default_tag_groups(self, force=False):
        """DEFAULT_TAG_GROUPS に基づきグループ作成＋未分類タグの自動割当を行う。

        既に手動でグループ割当済みのタグは上書きしない。
        force=True でも手動変更済みタグは維持される。

        グループが既存の場合でも sort_order を DEFAULT_TAG_GROUPS の定義順で上書きする
        （既存ユーザーで analyzer シードが先に走っていた場合も順序を統一するため）。
        """
        if not force and self.settings.value("tag_default_groups_seeded_v3", False, type=bool):
            return
        conn = sqlite3.connect(self.db_path)
        try:
            for idx, (group_name, tags) in enumerate(DEFAULT_TAG_GROUPS.items()):
                if group_name == UNCLASSIFIED_GROUP:
                    continue
                # INSERT OR IGNORE ではなく UPSERT で sort_order も更新する
                conn.execute(
                    "INSERT INTO tag_groups (group_id, sort_order) VALUES (?, ?) "
                    "ON CONFLICT(group_id) DO UPDATE SET sort_order = excluded.sort_order",
                    (group_name, idx * 10)
                )
            conn.commit()
        finally:
            conn.close()
        # タグ割当（手動変更済みは維持）
        for group_name, tags in DEFAULT_TAG_GROUPS.items():
            for tag in tags:
                if self.get_group_of(tag) is None:
                    self.set_tag_group(tag, group_name)
        self.settings.setValue("tag_default_groups_seeded_v3", True)

    def seed_groups_from_analyzer_defaults(self, force=False):
        """auto_tag_analyzer のカテゴリから初期グループとメンバーをシード（初回起動時に1回だけ実行）"""
        if not force and self.settings.value("tag_groups_seeded_v1", False, type=bool):
            return
        try:
            from auto_tag_analyzer import AutoTagAnalyzer
            analyzer = AutoTagAnalyzer()
            for idx, (group_name, spec) in enumerate(analyzer.category_rules.items()):
                # _MERGED_INTO に登録されたグループはスキップし、タグを統合先へ振り向ける
                effective_group = _MERGED_INTO.get(group_name, group_name)
                self.add_group(effective_group, sort_order=idx * 10)
                for tag in spec.get("tags", []):
                    if self.get_group_of(tag) is None:
                        self.set_tag_group(tag, effective_group)
            self.settings.setValue("tag_groups_seeded_v1", True)
        except Exception as e:
            print(f"[TagManager] seed_groups_from_analyzer_defaults failed: {e}")

    def get_all_groups(self):
        """グループ一覧を sort_order 昇順で返す"""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT group_id FROM tag_groups ORDER BY sort_order ASC, group_id ASC"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()

    def add_group(self, group_id, sort_order=100):
        """グループを追加する（既存の場合は何もしない / sort_order は新規作成時のみ適用）。
        UNCLASSIFIED_GROUP および _MERGED_INTO に登録済みの廃止グループは DB への作成を拒否する。
        """
        if group_id == UNCLASSIFIED_GROUP:
            return
        if group_id in _MERGED_INTO:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO tag_groups (group_id, sort_order) VALUES (?, ?)",
                (group_id, sort_order)
            )
            conn.commit()
        finally:
            conn.close()

    def rename_group(self, old_id, new_id):
        """グループ名を変更する（メンバーの参照も更新）。
        UNCLASSIFIED_GROUP を含む変更は拒否する。
        """
        if old_id == new_id:
            return
        if old_id == UNCLASSIFIED_GROUP or new_id == UNCLASSIFIED_GROUP:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO tag_groups (group_id, sort_order) "
                "SELECT ?, sort_order FROM tag_groups WHERE group_id = ?",
                (new_id, old_id)
            )
            conn.execute(
                "UPDATE tag_group_members SET group_id = ? WHERE group_id = ?",
                (new_id, old_id)
            )
            conn.execute("DELETE FROM tag_groups WHERE group_id = ?", (old_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_group(self, group_id):
        """グループを削除する（所属タグは未分類に退避）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "DELETE FROM tag_group_members WHERE group_id = ?", (group_id,)
            )
            conn.execute("DELETE FROM tag_groups WHERE group_id = ?", (group_id,))
            conn.commit()
        finally:
            conn.close()

    def get_group_of(self, tag):
        """タグが属するグループを返す（未所属の場合は None）"""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT group_id FROM tag_group_members WHERE tag = ?", (tag,)
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def set_tag_group(self, tag, group_id):
        """タグを指定グループに割り当てる（グループが存在しない場合は自動作成）。
        group_id に UNCLASSIFIED_GROUP を指定した場合はグループ割り当てを解除する。
        """
        if group_id == UNCLASSIFIED_GROUP:
            return self.remove_tag_from_group(tag)
        self.add_group(group_id)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO tag_group_members (tag, group_id) VALUES (?, ?)",
                (tag, group_id)
            )
            conn.commit()
        finally:
            conn.close()

    def set_tags_group(self, tags, group_id):
        """複数タグをまとめて指定グループに割り当てる。
        group_id に UNCLASSIFIED_GROUP を指定した場合は各タグのグループ割り当てを解除する。
        """
        if group_id == UNCLASSIFIED_GROUP:
            for tag in tags:
                self.remove_tag_from_group(tag)
            return
        self.add_group(group_id)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO tag_group_members (tag, group_id) VALUES (?, ?)",
                [(tag, group_id) for tag in tags]
            )
            conn.commit()
        finally:
            conn.close()

    def remove_tag_from_group(self, tag):
        """タグのグループ割り当てを解除する（未分類へ）"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM tag_group_members WHERE tag = ?", (tag,))
            conn.commit()
        finally:
            conn.close()

    def get_tags_grouped(self):
        """タグをグループ別に整理した辞書を返す。
        戻り値: OrderedDict 順 (sort_order 昇順のグループ → タグリスト)
        グループ未割当のタグは "未分類" キーの末尾に追加される。
        """
        groups = self.get_all_groups()
        all_tags = self.get_all_tags()

        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT tag, group_id FROM tag_group_members"
            ).fetchall()
        finally:
            conn.close()

        tag_to_group = {row[0]: row[1] for row in rows}

        result = {g: [] for g in groups}
        unclassified = []

        for tag in all_tags:
            group = tag_to_group.get(tag)
            if group and group in result:
                result[group].append(tag)
            else:
                unclassified.append(tag)

        # 空グループも保持（ユーザーが作ったグループは空でも表示する）
        result[UNCLASSIFIED_GROUP] = unclassified

        return result

    def calculate_file_hash(self, file_path):
        """ファイルの一意性確認用ハッシュ計算"""
        try:
            with open(file_path, 'rb') as f:
                # ファイル全体ではなく、先頭と末尾の一部をハッシュ化（高速化）
                f.seek(0)
                start_chunk = f.read(8192)  # 先頭8KB
                f.seek(-min(8192, os.path.getsize(file_path)), 2)
                end_chunk = f.read(8192)    # 末尾8KB
                
            hash_md5 = hashlib.md5()
            hash_md5.update(start_chunk)
            hash_md5.update(end_chunk)
            hash_md5.update(str(os.path.getsize(file_path)).encode())  # ファイルサイズも含める
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"Hash calculation failed for {file_path}: {e}")
            return None
    
    def add_tags(self, file_path, tags, write_to_file=True):
        """
        画像にタグを追加
        
        Args:
            file_path (str): 画像ファイルのパス
            tags (list): 追加するタグのリスト
            write_to_file (bool): EXIFにも書き込むかどうか
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_hash = self.calculate_file_hash(file_path)
        if not file_hash:
            return False
        
        # 既存タグを取得
        existing_tags = self.get_tags(file_path)
        
        # 新しいタグを追加（重複除去）
        all_tags = list(set(existing_tags + tags))
        all_tags.sort()  # ソートして一貫性を保つ
        
        # SQLiteに保存
        self._save_to_database(file_path, file_hash, all_tags)
        
        # EXIFに埋め込み（オプション）
        if write_to_file:
            self._save_to_exif(file_path, all_tags)
        
        # QSettingsにバックアップ
        self._save_to_qsettings_backup(file_path, all_tags)
        
        return True
    
    def save_tags(self, file_path, tags):
        """
        画像のタグを完全に置き換える（上書き保存）
        
        Args:
            file_path (str): 画像ファイルのパス
            tags (list): 保存するタグのリスト（既存タグを完全に置き換え）
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_hash = self.calculate_file_hash(file_path)
        if not file_hash:
            return False
        
        # タグリストを整理（重複除去・ソート）
        clean_tags = sorted(list(set(tags))) if tags else []
        
        # SQLiteに保存（上書き）
        self._save_to_database(file_path, file_hash, clean_tags)
        
        # EXIFに埋め込み（上書き）
        self._save_to_exif(file_path, clean_tags)
        
        # QSettingsにバックアップ（上書き）
        self._save_to_qsettings_backup(file_path, clean_tags)
        
        return True
    
    def remove_tags(self, file_path, tags):
        """画像からタグを削除"""
        if not os.path.exists(file_path):
            return False
        
        existing_tags = self.get_tags(file_path)
        remaining_tags = [tag for tag in existing_tags if tag not in tags]
        
        file_hash = self.calculate_file_hash(file_path)
        if file_hash:
            self._save_to_database(file_path, file_hash, remaining_tags)
            self._save_to_exif(file_path, remaining_tags)
            self._save_to_qsettings_backup(file_path, remaining_tags)
        
        return True
    
    def get_tags(self, file_path):
        """画像のタグを取得（複数ソースから統合）"""
        # 1. SQLiteから取得（最も高速）
        db_tags = self._get_tags_from_database(file_path)
        if db_tags:
            return db_tags
        
        # 2. EXIFから取得
        exif_tags = self._get_tags_from_exif(file_path)
        if exif_tags:
            # 発見したタグをSQLiteにキャッシュ
            file_hash = self.calculate_file_hash(file_path)
            if file_hash:
                self._save_to_database(file_path, file_hash, exif_tags)
            return exif_tags
        
        # 3. QSettingsバックアップから取得
        backup_tags = self._get_tags_from_qsettings_backup(file_path)
        return backup_tags or []
    
    # お気に入り機能
    def get_favorite_status(self, file_path):
        """画像のお気に入り状態を取得（3層ハイブリッド取得）"""
        # 1. SQLiteから取得（最も高速）
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT is_favorite FROM image_tags WHERE file_path = ? ORDER BY updated_at DESC LIMIT 1', (file_path,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row is not None:
            return bool(row[0])
        
        # 2. EXIFから取得
        exif_favorite = self._get_favorite_from_exif(file_path)
        if exif_favorite is not None:
            # EXIFで見つかった場合はデータベースに直接キャッシュ（再帰を避ける）
            if exif_favorite:  # お気に入りが True の場合のみキャッシュ
                file_hash = self.calculate_file_hash(file_path)
                if file_hash:
                    existing_tags = self.get_tags(file_path)
                    self._save_to_database(file_path, file_hash, existing_tags, exif_favorite)
            return exif_favorite
        
        # 3. QSettingsバックアップから取得
        return self._get_favorite_from_qsettings(file_path)
    
    def set_favorite_status_fast(self, file_path, is_favorite):
        """SQLite + QSettings への書き込みを行う高速版（メインスレッド用）。

        QSettings は軽量かつスレッドセーフでないためメインスレッド側で確定する。
        EXIF 書き込み（piexif）のみ呼び出し側でワーカーに逃がす想定。
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_hash = self.calculate_file_hash(file_path)
        if not file_hash:
            return False

        existing_tags = self.get_tags(file_path)
        self._save_to_database(file_path, file_hash, existing_tags, is_favorite)
        # QSettings はメインスレッドでのみ更新する
        self._save_favorite_to_qsettings(file_path, is_favorite)
        self._notify_favorite_changed(file_path, bool(is_favorite))
        return True

    def _write_favorite_side_effects(self, file_path, is_favorite):
        """EXIF への書き込みのみ（ワーカースレッドから呼ぶ想定）。

        QSettings は set_favorite_status_fast でメインスレッドから既に書き込まれている。
        """
        self._save_favorite_to_exif(file_path, is_favorite)

    def set_favorite_status(self, file_path, is_favorite):
        """画像のお気に入り状態を設定（SQLite + QSettings + EXIF の完全版・同期）"""
        if not self.set_favorite_status_fast(file_path, is_favorite):
            return False
        self._write_favorite_side_effects(file_path, is_favorite)
        return True

    def toggle_favorite(self, file_path):
        """画像のお気に入り状態をトグル（SQLite のみ即時; EXIF/QSettings は呼び出し側で非同期化すること）"""
        current_status = self.get_favorite_status(file_path)
        new_status = not current_status
        return self.set_favorite_status_fast(file_path, new_status), new_status

    def get_favorite_map(self, file_paths):
        """複数ファイルパスのお気に入り状態を一括取得して dict で返す。

        DB に存在しないパスは False 扱い。500 件ずつ IN 句に分割してクエリを実行する。
        """
        if not file_paths:
            return {}

        result = {}
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        chunk_size = 500
        for i in range(0, len(file_paths), chunk_size):
            chunk = file_paths[i:i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(f"""
                SELECT file_path, is_favorite
                FROM image_tags
                WHERE file_path IN ({placeholders})
                  AND (file_path, updated_at) IN (
                      SELECT file_path, MAX(updated_at)
                      FROM image_tags
                      GROUP BY file_path
                  )
            """, chunk)
            for row in cursor.fetchall():
                result[row[0]] = bool(row[1])
        conn.close()

        for path in file_paths:
            if path not in result:
                result[path] = False
        return result
    
    def get_favorite_images(self):
        """お気に入り画像のリストを取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT file_path, file_name, updated_at 
            FROM image_tags 
            WHERE is_favorite = 1 
            ORDER BY updated_at DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return [(row[0], row[1], row[2]) for row in results]
    
    def search_by_tags(self, tags, match_all=True, exclude_tags=None, only_favorites=False):
        """タグで画像を検索（JSON配列内の完全一致）
        
        Args:
            tags: 検索対象のタグリスト
            match_all: True=すべてのタグにマッチ, False=いずれかのタグにマッチ
            exclude_tags: 除外するタグのリスト（このタグを持つ画像は結果から除外）
            only_favorites: True=お気に入り画像のみを検索対象にする
        """
        if exclude_tags is None:
            exclude_tags = []
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # SQLクエリにお気に入りフィルターを追加
        if only_favorites:
            # お気に入りのみを取得（最新のレコードのみ）
            cursor.execute('''
                SELECT DISTINCT file_path, tags 
                FROM image_tags 
                WHERE (file_path, updated_at) IN (
                    SELECT file_path, MAX(updated_at) 
                    FROM image_tags 
                    GROUP BY file_path
                ) AND is_favorite = 1
            ''')
        else:
            # 最新のレコードのみを取得（重複を避ける）
            cursor.execute('''  
                SELECT DISTINCT file_path, tags 
                FROM image_tags 
                WHERE (file_path, updated_at) IN (
                    SELECT file_path, MAX(updated_at) 
                    FROM image_tags 
                    GROUP BY file_path
                )
            ''')
        all_records = cursor.fetchall()
        conn.close()
        
        matching_files = []
        
        for file_path, tags_json in all_records:
            # ファイルが存在するかチェック
            if not os.path.exists(file_path):
                continue
                
            try:
                # JSONをパースしてタグリストを取得
                file_tags = json.loads(tags_json) if tags_json else []
                
                # 除外タグチェック - 除外タグが含まれている場合はスキップ
                if exclude_tags and any(exclude_tag in file_tags for exclude_tag in exclude_tags):
                    continue
                
                # マッチング判定
                is_match = False
                if not tags:  # 検索タグが空の場合は除外タグのチェックのみ
                    is_match = True
                elif match_all:
                    # すべての検索タグが画像のタグに含まれているかチェック
                    is_match = all(tag in file_tags for tag in tags)
                else:
                    # いずれかの検索タグが画像のタグに含まれているかチェック
                    is_match = any(tag in file_tags for tag in tags)
                
                if is_match:
                    matching_files.append(file_path)
                        
            except (json.JSONDecodeError, TypeError):
                # JSONの解析に失敗した場合はスキップ
                continue
        
        return matching_files
    
    def get_all_tags(self):
        """すべてのユニークタグを取得（優先順序付き）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 最新のレコードのみを取得（重複を避ける）
        cursor.execute('''
            SELECT DISTINCT file_path, tags 
            FROM image_tags 
            WHERE (file_path, updated_at) IN (
                SELECT file_path, MAX(updated_at) 
                FROM image_tags 
                GROUP BY file_path
            )
        ''')
        
        all_tags_set = set()
        
        all_records = cursor.fetchall()
        
        for row in all_records:
            try:
                tags_list = json.loads(row[1]) if row[1] else []
                all_tags_set.update(tags_list)
            except (json.JSONDecodeError, TypeError):
                continue
        
        conn.close()
        return self._sort_tags_with_priority(list(all_tags_set))
    
    def _sort_tags_with_priority(self, tags_list):
        """タグを優先順位付きでソート"""
        # 優先タグを定義（順序も重要）
        priority_tags = [
            "騎乗位",
            "背面騎乗位", 
            "アマゾン体位",
            "背後位",
            "フェラチオ",
            "足コキ",
            "手コキ",
            "側位",
            "正常位",
            "パイズリ",
            "寝バック",
            "立ちバック"
        ]
        
        # 優先タグとその他のタグに分離
        priority_found = []
        other_tags = []
        
        for tag in tags_list:
            if tag in priority_tags:
                priority_found.append(tag)
            else:
                other_tags.append(tag)
        
        # 優先タグは指定順序でソート
        priority_sorted = sorted(priority_found, key=lambda x: priority_tags.index(x))
        
        # その他のタグは五十音順でソート
        other_sorted = sorted(other_tags)
        
        # 優先タグ + その他のタグの順で結合
        return priority_sorted + other_sorted
    
    def migrate_file_paths(self, old_prefix, new_prefix):
        """
        データベースおよび設定内のファイルパスを一括置換する（移行用）
        
        Args:
            old_prefix (str): 置換前のパスの接頭辞
            new_prefix (str): 置換後のパスの接頭辞
        Returns:
            dict: 影響を受けた各項目の件数
        """
        results = {"database": 0, "history": 0, "favorites": 0}
        
        # 1. SQLiteデータベースの更新
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE image_tags 
                SET file_path = REPLACE(file_path, ?, ?)
                WHERE file_path LIKE ?
            ''', (old_prefix, new_prefix, f"{old_prefix}%"))
            results["database"] = cursor.rowcount
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Database migration failed: {e}")
        finally:
            conn.close()
            
        # 2. QSettings (履歴と登録リスト) の更新
        # 履歴 (folder_history)
        history = self.settings.value("folder_history", [])
        if history:
            new_history = []
            changed = False
            for path in history:
                if path.startswith(old_prefix):
                    new_history.append(path.replace(old_prefix, new_prefix, 1))
                    changed = True
                    results["history"] += 1
                else:
                    new_history.append(path)
            if changed:
                self.settings.setValue("folder_history", new_history)
                
        # 登録リスト (新フォーマット: favorite_entries)
        entries = self.settings.value("favorite_entries", None)
        entries_updated = False
        entries_replaced = 0
        if isinstance(entries, list) and entries:
            new_entries = []
            changed = False
            for entry in entries:
                if (isinstance(entry, dict)
                        and entry.get("type") == "folder"
                        and isinstance(entry.get("path"), str)
                        and entry["path"].startswith(old_prefix)):
                    new_entry = dict(entry)
                    new_entry["path"] = entry["path"].replace(old_prefix, new_prefix, 1)
                    new_entries.append(new_entry)
                    changed = True
                    entries_replaced += 1
                    results["favorites"] += 1
                else:
                    new_entries.append(entry)
            if changed:
                self.settings.setValue("favorite_entries", new_entries)
            entries_updated = True

        # 登録リスト (旧フォーマット: favorite_folders) - 旧データが残っている環境も更新
        favorites = self.settings.value("favorite_folders", [])
        legacy_count = 0
        if favorites:
            new_favorites = []
            changed = False
            for path in favorites:
                if isinstance(path, str) and path.startswith(old_prefix):
                    new_favorites.append(path.replace(old_prefix, new_prefix, 1))
                    changed = True
                    legacy_count += 1
                else:
                    new_favorites.append(path)
            if changed:
                self.settings.setValue("favorite_folders", new_favorites)
                if not entries_updated:
                    results["favorites"] += legacy_count
        
        return results
    
    # プライベートメソッド
    def _get_tags_from_database(self, file_path):
        """SQLiteデータベースから特定画像のタグを取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 最新のレコードを取得
        cursor.execute('''
            SELECT tags FROM image_tags 
            WHERE file_path = ? 
            ORDER BY updated_at DESC 
            LIMIT 1
        ''', (file_path,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            try:
                tags = json.loads(result[0])
                return tags
            except (json.JSONDecodeError, TypeError):
                return []
        
        return []
    
    def _get_tags_from_qsettings_backup(self, file_path):
        """QSettingsバックアップからタグを取得"""
        settings_key = f"tags/{file_path}"
        tags_json = self.settings.value(settings_key, "[]")
        
        try:
            tags = json.loads(tags_json) if tags_json else []
            return tags
        except (json.JSONDecodeError, TypeError):
            return []
    
    def _save_to_qsettings_backup(self, file_path, tags):
        """QSettingsにタグをバックアップ保存"""
        settings_key = f"tags/{file_path}"
        tags_json = json.dumps(tags, ensure_ascii=False)
        self.settings.setValue(settings_key, tags_json)
    
    def _save_to_database(self, file_path, file_hash, tags, is_favorite=None):
        """SQLiteデータベースに保存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        tags_json = json.dumps(tags, ensure_ascii=False)
        file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        # 既存のお気に入り状態を取得（指定されていない場合）
        if is_favorite is None:
            cursor.execute('SELECT is_favorite FROM image_tags WHERE file_path = ? ORDER BY updated_at DESC LIMIT 1', (file_path,))
            row = cursor.fetchone()
            is_favorite = row[0] if row else 0
        
        # 古い重複レコードを削除（同じfile_pathの古いレコードを削除）
        cursor.execute('DELETE FROM image_tags WHERE file_path = ?', (file_path,))
        
        # 新しいレコードを挿入
        cursor.execute('''
            INSERT INTO image_tags 
            (file_hash, file_path, file_name, tags, is_favorite, updated_at, file_modified_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (file_hash, file_path, os.path.basename(file_path), tags_json, is_favorite, file_mod_time))
        
        conn.commit()
        conn.close()
    
    def _get_tags_from_database(self, file_path):
        """SQLiteデータベースからタグを取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT tags FROM image_tags WHERE file_path = ? ORDER BY updated_at DESC LIMIT 1', (file_path,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            try:
                return json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def _save_to_exif(self, file_path, tags):
        """EXIFにタグを埋め込み"""
        try:
            # JPEGファイルのみ対応
            if not file_path.lower().endswith(('.jpg', '.jpeg')):
                return
            
            # 既存のEXIFデータを読み取り
            try:
                exif_dict = piexif.load(file_path)
            except:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            
            # Keywords フィールドにタグを設定
            keywords = ', '.join(tags).encode('utf-8')
            exif_dict["0th"][piexif.ImageIFD.XPKeywords] = keywords
            
            # EXIFデータをバイナリに変換
            exif_bytes = piexif.dump(exif_dict)
            
            # 画像に書き込み
            img = Image.open(file_path)
            img.save(file_path, "JPEG", exif=exif_bytes, quality=95)
            
        except Exception as e:
            print(f"Failed to write EXIF tags to {file_path}: {e}")
    
    def _get_tags_from_exif(self, file_path):
        """EXIFからタグを取得"""
        try:
            if not file_path.lower().endswith(('.jpg', '.jpeg')):
                return []
            
            exif_dict = piexif.load(file_path)
            
            if piexif.ImageIFD.XPKeywords in exif_dict["0th"]:
                keywords_bytes = exif_dict["0th"][piexif.ImageIFD.XPKeywords]
                keywords_str = keywords_bytes.decode('utf-8', errors='ignore')
                return [tag.strip() for tag in keywords_str.split(',') if tag.strip()]
                
        except Exception as e:
            print(f"Failed to read EXIF tags from {file_path}: {e}")
        
        return []
    
    def _save_favorite_to_exif(self, file_path, is_favorite):
        """EXIFにお気に入り状態を埋め込み"""
        try:
            # file_pathの型チェック
            if not isinstance(file_path, str) or not file_path:
                return
                
            # JPEGファイルのみ対応
            if not file_path.lower().endswith(('.jpg', '.jpeg')):
                return
                
            # 既存のEXIFを読み込み
            try:
                exif_dict = piexif.load(file_path)
            except:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            
            # ImageDescriptionフィールドにお気に入り情報を埋め込み
            favorite_marker = "KABAVIEWER_FAVORITE:1" if is_favorite else "KABAVIEWER_FAVORITE:0"
            
            # 既存のImageDescriptionがある場合は保持
            existing_desc = ""
            if piexif.ImageIFD.ImageDescription in exif_dict["0th"]:
                try:
                    existing_desc = exif_dict["0th"][piexif.ImageIFD.ImageDescription].decode('utf-8', errors='ignore')
                    # 既存のお気に入りマーカーを削除
                    import re
                    existing_desc = re.sub(r'KABAVIEWER_FAVORITE:[01]\s*', '', existing_desc).strip()
                except:
                    existing_desc = ""
            
            # 新しいImageDescriptionを作成
            new_desc = f"{favorite_marker} {existing_desc}".strip()
            exif_dict["0th"][piexif.ImageIFD.ImageDescription] = new_desc.encode('utf-8')
            
            # EXIFを保存
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, file_path)
            
        except Exception as e:
            print(f"Failed to save favorite status to EXIF for '{file_path}' (type: {type(file_path)}): {e}")
    
    def _get_favorite_from_exif(self, file_path):
        """EXIFからお気に入り状態を取得"""
        try:
            # file_pathの型チェック
            if not isinstance(file_path, str) or not file_path:
                return False
                
            if not file_path.lower().endswith(('.jpg', '.jpeg')):
                return False
                
            exif_dict = piexif.load(file_path)
            
            if piexif.ImageIFD.ImageDescription in exif_dict["0th"]:
                desc = exif_dict["0th"][piexif.ImageIFD.ImageDescription].decode('utf-8', errors='ignore')
                if "KABAVIEWER_FAVORITE:1" in desc:
                    return True
                elif "KABAVIEWER_FAVORITE:0" in desc:
                    return False
                    
        except Exception as e:
            print(f"Failed to read favorite status from EXIF for '{file_path}' (type: {type(file_path)}): {e}")
        
        return False
    
    def _save_to_qsettings_backup(self, file_path, tags):
        """QSettingsにバックアップ保存"""
        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        folder_tags = self.settings.value(f"tags/{folder_path}", {}, type=dict)
        folder_tags[file_name] = tags
        self.settings.setValue(f"tags/{folder_path}", folder_tags)
    
    def _get_tags_from_qsettings_backup(self, file_path):
        """QSettingsバックアップからタグを取得"""
        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        folder_tags = self.settings.value(f"tags/{folder_path}", {}, type=dict)
        return folder_tags.get(file_name, [])
    
    def _save_favorite_to_qsettings(self, file_path, is_favorite):
        """QSettingsにお気に入り状態をバックアップ保存"""
        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        favorites_key = f"favorites/{folder_path}"
        folder_favorites = self.settings.value(favorites_key, {}, type=dict)
        folder_favorites[file_name] = is_favorite
        self.settings.setValue(favorites_key, folder_favorites)
    
    def _get_favorite_from_qsettings(self, file_path):
        """QSettingsバックアップからお気に入り状態を取得"""
        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        favorites_key = f"favorites/{folder_path}"
        folder_favorites = self.settings.value(favorites_key, {}, type=dict)
        return folder_favorites.get(file_name, False)


# 使用例
if __name__ == "__main__":
    tag_manager = TagManager()
    
    # サンプル使用方法
    sample_image = "/path/to/your/image.jpg"
    
    # タグを追加
    tag_manager.add_tags(sample_image, ["風景", "夕日", "海"])
    
    # タグを取得
    tags = tag_manager.get_tags(sample_image)
    print(f"Tags for {sample_image}: {tags}")
    
    # タグで検索
    results = tag_manager.search_by_tags(["風景"])
    print(f"Images with '風景' tag: {results}")
    
    # すべてのタグを取得
    all_tags = tag_manager.get_all_tags()
    print(f"All unique tags: {all_tags}")
