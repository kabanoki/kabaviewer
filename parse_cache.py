"""一括タグ付け用のパース結果キャッシュ。

各画像の (mtime, file_size) をキーに、解析で得たタグリストを SQLite に
保存しておき、次回同じファイル（変更なし）の解析時はディスク読み込み +
プロンプト解析をまるごとスキップする。

スレッドセーフのため、Python の sqlite3 はスレッドごとに connection を作る。
"""

import os
import json
import sqlite3
import threading


_DEFAULT_DIR = os.path.expanduser("~/.kabaviewer")
_DB_NAME = "parse_cache.db"


def _db_path():
    return os.path.join(_DEFAULT_DIR, _DB_NAME)


class ParseCache:
    """画像パース結果のローカルキャッシュ。"""

    def __init__(self, path=None):
        os.makedirs(_DEFAULT_DIR, exist_ok=True)
        self.db_path = path or _db_path()
        # スレッドごとに connection を保持（sqlite3 はデフォルトでスレッド共有 NG）
        self._local = threading.local()
        self._init_schema()

    def _conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.db_path)
            # キャッシュは丈夫さよりスピード優先
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = c
        return c

    def _init_schema(self):
        c = self._conn()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS parse_cache (
                file_path TEXT PRIMARY KEY,
                mtime    REAL NOT NULL,
                file_size INTEGER NOT NULL,
                tags_json TEXT NOT NULL,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.commit()

    def get(self, file_path):
        """キャッシュヒットならタグリストを返す。それ以外は None。

        mtime と file_size が両方一致する場合のみヒットとみなす。
        """
        try:
            st = os.stat(file_path)
        except OSError:
            return None
        c = self._conn()
        row = c.execute(
            "SELECT mtime, file_size, tags_json FROM parse_cache WHERE file_path=?",
            (file_path,),
        ).fetchone()
        if not row:
            return None
        cached_mtime, cached_size, tags_json = row
        if abs(cached_mtime - st.st_mtime) < 1e-6 and cached_size == st.st_size:
            try:
                return json.loads(tags_json)
            except Exception:
                return None
        return None

    def set(self, file_path, tags):
        try:
            st = os.stat(file_path)
        except OSError:
            return
        try:
            c = self._conn()
            c.execute(
                "INSERT OR REPLACE INTO parse_cache (file_path, mtime, file_size, tags_json, cached_at)"
                " VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (file_path, st.st_mtime, st.st_size, json.dumps(list(tags), ensure_ascii=False)),
            )
            c.commit()
        except Exception as e:
            print(f"[ParseCache.set] {file_path}: {e}")

    def set_many(self, entries):
        """[(file_path, tags), ...] を 1 トランザクションで書き込む。"""
        c = self._conn()
        c.execute("BEGIN")
        try:
            for file_path, tags in entries:
                try:
                    st = os.stat(file_path)
                except OSError:
                    continue
                c.execute(
                    "INSERT OR REPLACE INTO parse_cache (file_path, mtime, file_size, tags_json, cached_at)"
                    " VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (file_path, st.st_mtime, st.st_size, json.dumps(list(tags), ensure_ascii=False)),
                )
            c.commit()
        except Exception as e:
            c.rollback()
            print(f"[ParseCache.set_many]: {e}")

    def clear(self):
        c = self._conn()
        c.execute("DELETE FROM parse_cache")
        c.commit()
