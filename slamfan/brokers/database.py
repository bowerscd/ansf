import asyncio
from hashlib import sha384
from uuid import UUID
from datetime import datetime, timedelta
from typing import Dict, Awaitable
from turing import Corpus

from aiorwlock import RWLock

class DatabaseBroker(object):
    """
    Class controlling access to the database, and keeping
    a cache of corpus objects for less queries.
    """

    def __init__(self, tg, db: str = ":memory:", save_delay=30, **kwargs) -> None:
        """
        TODO
        """
        self.__db_str = db
        self.__save_delay = save_delay
        self.__cache_lock = RWLock()
        self.__task_group = tg

    def __aenter__(self) -> 'DatabaseBroker':
        pass

    def __aexit__(self, *e) -> None:
        pass

    def __new_task(self, fn: Awaitable, name: str):
        self.__task_group.create_task(fn, name=f"db_{name}")

    async def __add_message(self, channel: str, uid: int, msg: str, msg_time: datetime):
        try:
            add_to_db = True
            delay = 0
            uid_hash = sha384(str(uid).encode()).hexdigest()
            while delay < self.__save_delay:
                await asyncio.sleep(1)
                delay += 1

            query = self.__conn.execute("""SELECT User
                                           FROM TwitchBanned
                                           WHERE
                                              Channel = ?
                                                AND
                                              User = ?
                                                AND
                                              (UnbanTime == NULL OR UnbanTime > ?)
                                                AND
                                              BanTime < ?
                                            """, (channel, uid_hash, msg_time, msg_time)).fetchall()
            if len(query) > 0:
                add_to_db = False

            if add_to_db:
                query = self.__conn.execute("""SELECT Word FROM TwitchBannedWords""").fetchall()
                for word in query:
                    if word in msg:
                        add_to_db = False

            self.__conn.execute("""INSERT INTO TwitchMessages(
                                            Channel,
                                            User,
                                            Message,
                                            MessageTime
                                        ) VALUES (?, ?, ?, ?)
                                    """, (channel, uid_hash, msg, msg_time))
            self.__conn.commit()

            if add_to_db:
                async with self.__cache_lock.writer_lock:
                    self.__datasets[channel].add(msg)

        except asyncio.CancelledError:
            return

    async def add_twitch_message(self, channel: str, uid: int, msg: str, msg_id: UUID, msg_time: datetime) -> None:
        self.__task_group.create_task(self.__add_message(channel, uid, msg, msg_time),
                                      name=f"twitch.{channel}.{uid}.{msg_id}")

    async def twitch_remove_message(self, channel: str, msg_id: UUID):
        map(lambda x: x.cancel(), filter(lambda x: f"twitch.{channel}" in x.get_name() and f"{msg_id}" in x.get_name(), asyncio.all_tasks()))

    async def twitch_ban(self, channel: str, uid: int, timestamp: datetime):
        self.__conn.execute("""
                INSERT INTO TwitchBanned(
                    Channel,
                    User,
                    BanTime
                ) VALUES (?, ?, ?)""", (channel, sha384(str(uid).encode()).hexdigest(), timestamp))

        self.__conn.commit()

        map(lambda x: x.cancel(), filter(lambda x: x.get_name().startswith(f"twitch.{channel}.{uid}"), asyncio.all_tasks()))

    async def twitch_timeout(self, channel: str, uid: int, timestamp: datetime, duration: int):
        self.__conn.execute("""INSERT INTO TwitchBanned(
                                    Channel,
                                    User,
                                    BanTime,
                                    UnbanTime
                                ) VALUES (?, ?, ?, ?)
                                """, (channel, sha384(str(uid).encode()).hexdigest(), timestamp, timestamp + timedelta(seconds=duration)))
        self.__conn.commit()

        map(lambda x: x.cancel(), filter(lambda x: x.get_name().startswith(f"twitch.{channel}.{uid}"), asyncio.all_tasks()))

    async def twitch_unban(self, channel: str, uid: int, timestamp: datetime):
        self.__conn.execute("""UPDATE TwitchBanned SET
                                    UnbanTime = ?
                                WHERE (
                                    Channel = ?,
                                    User = ?,
                                    UnbanTime = NULL
                                )
                                """, (timestamp, channel, sha384(str(uid).encode()).hexdigest()))
        self.__conn.commit()

    async def p(self):
        pass

    async def connect(self) -> None:
        from sqlite3 import connect
        from sqlite3 import PARSE_DECLTYPES

        self.__conn = connect(self.__db_str, detect_types=PARSE_DECLTYPES)

        self.__conn.execute("""
            CREATE TABLE IF NOT EXISTS TwitchMessages(
                Id          INTEGER PRIMARY KEY AUTOINCREMENT,
                Channel     TEXT,
                User        TEXT,
                Message     TEXT,
                MessageTime DATETIME
            )""")
        self.__conn.execute("""
            CREATE TABLE IF NOT EXISTS TwitchBannedWords(
                Id          INTEGER PRIMARY KEY AUTOINCREMENT,
                Word        TEXT,
                AddTime     DATETIME
            )""")
        self.__conn.execute("""
            CREATE TABLE IF NOT EXISTS TwitchBanned(
                Id          INTEGER PRIMARY KEY AUTOINCREMENT,
                Channel     TEXT,
                User        TEXT,
                BanTime     DATETIME,
                UnbanTime   DATETIME
            )""")
        self.__conn.execute("""
            CREATE TABLE IF NOT EXISTS TwitchStreams(
                Id          INTEGER PRIMARY KEY AUTOINCREMENT,
                VODURL      TEXT,
                Channel     TEXT,
                StartTime   DATETIME,
                EndTime     DATETIME
            )
            """)
        self.__conn.execute("""
            CREATE TABLE IF NOT EXISTS TwitchClips(
                Id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ClipLink    TEXT,
                Channel     TEXT,
                StartTime   DATETIME,
                EndTime     DATETIME
            )
            """)
        self.__conn.commit()

        # Load messages into memory
        self.__datasets: Dict[str, Corpus] = {}
        query = self.__conn.execute("SELECT DISTINCT Channel FROM TwitchMessages").fetchall()
        for row in query:
            messages = self.__conn.execute("""
                SELECT Message
                FROM TwitchMessages
                WHERE Channel = ?
                  AND
                User NOT IN (SELECT User FROM TwitchBanned WHERE UnbanTime < ?)
                  AND
                NOT EXISTS ( SELECT Word FROM TwitchBannedWords WHERE Message LIKE '%' || Word || '%' )
            """, (row[0], datetime.now())).fetchall()
            async with self.__cache_lock.writer_lock:
                if row[0] in self.__datasets:
                    return

                self.__datasets[row[0]] = Corpus([x[0] for x in messages])

    async def init_corpus(self, channel: str) -> None:
        async with self.__cache_lock.writer_lock:
            if channel in self.__datasets:
                return

            q2 = self.__conn.execute("SELECT Message FROM TwitchMessages WHERE Channel = ?", (channel,)).fetchall()
            async with self.__cache_lock.writer_lock:
                self.__datasets[channel] = Corpus([x[0] for x in q2])

    async def generate_text(self, channel: str) -> str:
        async with self.__cache_lock.reader_lock:
            return await self.__datasets[channel].generate_text()
