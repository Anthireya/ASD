"""Tiny SQLite helper: creates the database the first time the site starts."""
import os
import sqlite3
from flask import g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(DATA_DIR, "deepface_asd.sqlite3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    age           INTEGER NOT NULL,
    gender        TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    mobile        TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screenings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at     TEXT NOT NULL,
    subject_name   TEXT,
    subject_age    TEXT,
    -- status values: analysed | demo | not_provided | error
    image_status   TEXT NOT NULL,
    image_label    TEXT,
    image_prob     REAL,
    audio_status   TEXT NOT NULL,
    audio_label    TEXT,
    audio_prob     REAL,
    combined_status TEXT NOT NULL DEFAULT 'not_available',
    mode           TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.commit()
    con.close()
