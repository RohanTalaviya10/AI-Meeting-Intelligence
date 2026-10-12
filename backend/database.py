import sqlite3
import json
from typing import List, Optional, Dict, Any
from backend.config import DB_PATH


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_path TEXT,
            file_size INTEGER DEFAULT 0,
            transcript TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meeting_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            speaker TEXT,
            text TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def save_meeting(filename: str, file_path: str, file_size: int, transcript: str, analysis: dict) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO meetings (filename, file_path, file_size, transcript, analysis_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (filename, file_path, file_size, transcript, json.dumps(analysis))
    )
    meeting_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return meeting_id


def list_meetings() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, file_size, created_at, analysis_json FROM meetings ORDER BY id DESC")
    rows = cursor.fetchall()
    results = []
    for row in rows:
        analysis_data = {}
        try:
            analysis_data = json.loads(row["analysis_json"])
        except Exception:
            pass
        results.append({
            "id": row["id"],
            "filename": row["filename"],
            "file_size_bytes": row["file_size"],
            "created_at": row["created_at"],
            "summary": analysis_data.get("summary", ""),
            "action_item_count": len(analysis_data.get("action_items", [])),
            "decision_count": len(analysis_data.get("decisions", []))
        })
    conn.close()
    return results


def get_meeting(meeting_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, file_path, file_size, transcript, analysis_json, created_at FROM meetings WHERE id = ?", (meeting_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    try:
        analysis = json.loads(row["analysis_json"])
    except Exception:
        analysis = {}
    result = {
        "id": row["id"],
        "filename": row["filename"],
        "file_path": row["file_path"],
        "file_size_bytes": row["file_size"],
        "transcript": row["transcript"],
        "analysis": analysis,
        "created_at": row["created_at"]
    }
    conn.close()
    return result


def delete_meeting(meeting_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    cursor.execute("DELETE FROM queries WHERE meeting_id = ?", (meeting_id,))
    cursor.execute("DELETE FROM meeting_chunks WHERE meeting_id = ?", (meeting_id,))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def save_query_record(meeting_id: int, query: str, answer: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO queries (meeting_id, query, answer) VALUES (?, ?, ?)",
        (meeting_id, query, answer)
    )
    conn.commit()
    conn.close()


def save_meeting_chunks(meeting_id: int, chunks: List[Dict[str, Any]]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meeting_chunks WHERE meeting_id = ?", (meeting_id,))
    for c in chunks:
        cursor.execute(
            """
            INSERT INTO meeting_chunks (meeting_id, chunk_index, speaker, text, embedding_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                meeting_id,
                c.get("chunk_index", 0),
                c.get("speaker", ""),
                c.get("text", ""),
                json.dumps(c.get("embedding", []))
            )
        )
    conn.commit()
    conn.close()


def get_meeting_chunks(meeting_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT chunk_index, speaker, text, embedding_json FROM meeting_chunks WHERE meeting_id = ? ORDER BY chunk_index ASC",
        (meeting_id,)
    )
    rows = cursor.fetchall()
    results = []
    for r in rows:
        emb = []
        try:
            emb = json.loads(r["embedding_json"])
        except Exception:
            pass
        results.append({
            "chunk_index": r["chunk_index"],
            "speaker": r["speaker"],
            "text": r["text"],
            "embedding": emb
        })
    conn.close()
    return results

