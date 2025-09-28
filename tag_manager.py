#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import hashlib
from datetime import datetime
from PyQt5.QtCore import QSettings
import piexif
from PIL import Image
import json

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
        
        self.init_database()
    
    def init_database(self):
        """SQLiteデータベースの初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS image_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT UNIQUE NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                tags TEXT NOT NULL,  -- JSON形式でタグ配列を保存
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_modified_at TIMESTAMP,
                is_favorite BOOLEAN DEFAULT 0  -- お気に入りフラグ
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_hash ON image_tags(file_hash)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_path ON image_tags(file_path)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_tags ON image_tags(tags)
        ''')
        
        conn.commit()
        conn.close()
    
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
    
    def set_favorite_status(self, file_path, is_favorite):
        """画像のお気に入り状態を設定"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_hash = self.calculate_file_hash(file_path)
        if not file_hash:
            return False
        
        # 既存のタグを取得
        existing_tags = self.get_tags(file_path)
        
        # お気に入り状態を指定してデータベースに保存
        self._save_to_database(file_path, file_hash, existing_tags, is_favorite)
        
        # EXIFにもお気に入り状態を埋め込み
        self._save_favorite_to_exif(file_path, is_favorite)
        
        # QSettingsにもバックアップ
        self._save_favorite_to_qsettings(file_path, is_favorite)
        
        return True
    
    def toggle_favorite(self, file_path):
        """画像のお気に入り状態をトグル"""
        current_status = self.get_favorite_status(file_path)
        new_status = not current_status
        return self.set_favorite_status(file_path, new_status)
    
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
    
    def search_by_tags(self, tags, match_all=True):
        """タグで画像を検索"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if match_all:
            # すべてのタグにマッチ
            query = '''
                SELECT file_path FROM image_tags 
                WHERE ''' + ' AND '.join(['tags LIKE ?' for _ in tags])
            params = [f'%"{tag}"%' for tag in tags]
        else:
            # いずれかのタグにマッチ
            query = '''
                SELECT file_path FROM image_tags 
                WHERE ''' + ' OR '.join(['tags LIKE ?' for _ in tags])
            params = [f'%"{tag}"%' for tag in tags]
        
        cursor.execute(query, params)
        results = [row[0] for row in cursor.fetchall() if os.path.exists(row[0])]
        
        conn.close()
        return results
    
    def get_all_tags(self):
        """すべてのユニークタグを取得"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT tags FROM image_tags')
        all_tags_set = set()
        
        for row in cursor.fetchall():
            try:
                tags_list = json.loads(row[0])
                all_tags_set.update(tags_list)
            except (json.JSONDecodeError, TypeError):
                continue
        
        conn.close()
        return sorted(list(all_tags_set))
    
    # プライベートメソッド
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
