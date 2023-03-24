from sys import argv
from csv import reader
from sqlite3 import connect
from hashlib import sha384
from json import load
from datetime import datetime
from zoneinfo import ZoneInfo

def create_tables(db):
    db.execute("""
    CREATE TABLE IF NOT EXISTS TwitchMessages(
        Id          INTEGER PRIMARY KEY AUTOINCREMENT,
        Channel     TEXT,
        User        TEXT,
        Message     TEXT,
        MessageTime DATETIME
    )""")
    db.execute("""
    CREATE TABLE IF NOT EXISTS TwitchBannedWords(
        Id          INTEGER PRIMARY KEY AUTOINCREMENT,
        Word        TEXT,
        AddTime     DATETIME
    )""")
    db.execute("""
    CREATE TABLE IF NOT EXISTS TwitchBanned(
        Id          INTEGER PRIMARY KEY AUTOINCREMENT,
        Channel     TEXT,
        User        TEXT,
        BanTime     DATETIME,
        UnbanTime   DATETIME
    )""")
    db.execute("""
    CREATE TABLE IF NOT EXISTS TwitchStreams(
        Id          INTEGER PRIMARY KEY AUTOINCREMENT,
        VOD         TEXT,
        Channel     TEXT,
        StartTime   DATETIME,
        EndTime     DATETIME
    )
    """)
    db.execute("""
    CREATE TABLE IF NOT EXISTS TwitchClips(
        Id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ClipLink    TEXT,
        Channel     TEXT,
        StartTime   DATETIME,
        EndTime     DATETIME
    )
    """)
    db.commit()

def insert_msg(db, it):

    channel, user_id, msg_id, time, msg = it
    if len(msg) == 0:
        return
    db.execute("""
        INSERT INTO TwitchMessages
            (
                Channel,
                User,
                Message,
                MessageTime
            )
        VALUES (?, ?, ?, ?)
            """,
            (
                channel,
                sha384(user_id.encode()).hexdigest(),
                msg,
                datetime.fromisoformat(time)
            )
        )

with connect(f"{argv[1].split('.')[0]}.sqlite") as db:
    create_tables(db)
    with open(argv[1], "r") as f:
        csv = reader(f) 
        for row in csv:
            insert_msg(db, row)

    with open(argv[2], "r") as f:
        settings = load(f)
        bans = settings["ignored_users"]
        channel = settings["channel"]
        for ban in bans:
            db.execute("""
                INSERT INTO TwitchBanned(
                    Channel,
                    User,
                    BanTime
                ) VALUES (?, ?, ?)
            """, (channel, sha384(f"{ban}".encode()).hexdigest(), datetime.fromtimestamp(0, ZoneInfo("UTC"))))


