import json
import bcrypt
from datetime import datetime
from db.database import get_conn


# ── Users ──────────────────────────────────────────────────────────────────

def create_user(username: str, password: str) -> int:
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, pw_hash)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def verify_user(username: str, password: str):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return row["id"]
        return None
    finally:
        conn.close()


def username_exists(username: str) -> bool:
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone() is not None
    finally:
        conn.close()


# ── Sessions ───────────────────────────────────────────────────────────────

def create_session(user_id: int, name: str = "未命名研究", mode: str = "practice") -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO sessions (user_id, session_name, mode) VALUES (?, ?, ?)",
            (user_id, name, mode)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_sessions(user_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session(session_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_session_state(session_id: int, state: dict):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE sessions SET state_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(state, ensure_ascii=False), datetime.now().isoformat(), session_id)
        )
        conn.commit()
    finally:
        conn.close()


def rename_session(session_id: int, new_name: str):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE sessions SET session_name = ?, updated_at = ? WHERE id = ?",
            (new_name, datetime.now().isoformat(), session_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_session(session_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM analysis_results WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM uploaded_files WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


# ── Uploaded Files ─────────────────────────────────────────────────────────

def save_uploaded_file(session_id: int, filename: str, file_path: str,
                        columns_json: dict, classification_json: dict = None) -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO uploaded_files
               (session_id, filename, file_path, columns_json, classification_json)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, filename, file_path,
             json.dumps(columns_json, ensure_ascii=False),
             json.dumps(classification_json, ensure_ascii=False) if classification_json else None)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_file_classification(file_id: int, classification: dict):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE uploaded_files SET classification_json = ? WHERE id = ?",
            (json.dumps(classification, ensure_ascii=False), file_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_uploaded_files(session_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM uploaded_files WHERE session_id = ? ORDER BY uploaded_at",
            (session_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["columns_json"] = json.loads(d["columns_json"]) if d["columns_json"] else {}
            d["classification_json"] = json.loads(d["classification_json"]) if d["classification_json"] else {}
            result.append(d)
        return result
    finally:
        conn.close()


# ── Analysis Results ───────────────────────────────────────────────────────

def save_analysis_result(session_id: int, analysis_type: str,
                          parameters: dict, results: dict,
                          interpretation: str = "") -> int:
    conn = get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO analysis_results
               (session_id, analysis_type, parameters_json, results_json, interpretation)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, analysis_type,
             json.dumps(parameters, ensure_ascii=False),
             json.dumps(results, ensure_ascii=False),
             interpretation)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_analysis_results(session_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM analysis_results WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["parameters_json"] = json.loads(d["parameters_json"]) if d["parameters_json"] else {}
            d["results_json"] = json.loads(d["results_json"]) if d["results_json"] else {}
            result.append(d)
        return result
    finally:
        conn.close()


def toggle_in_paper(result_id: int, in_paper: bool):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE analysis_results SET in_paper = ? WHERE id = ?",
            (1 if in_paper else 0, result_id)
        )
        conn.commit()
    finally:
        conn.close()


# ── Chat History ───────────────────────────────────────────────────────────

def add_chat_message(session_id: int, role: str, content: str):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(session_id: int, limit: int = 50) -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT role, content FROM chat_history
               WHERE session_id = ? ORDER BY created_at DESC LIMIT ?""",
            (session_id, limit)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()


def clear_chat_history(session_id: int):
    conn = get_conn()
    try:
        conn.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()
