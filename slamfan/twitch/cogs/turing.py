
from twitchio.ext.commands import Cog, Context, command
from twitchio import Message, Chatter, Channel, User
from typing import Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, UTC
from re import compile as regex

from brokers import DatabaseBroker

from .cogbase import CogBase, Permission
from aiorwlock import RWLock
import asyncio

_GLOBALLY_IGNORED_={
    "100135110", # StreamElements
    "19264788",  # Nightbot
    "786049415", # SpectatorDashboard
    "95174992",  # MembTVBot
    "854854747", # RoboAOE
}

class Turing(CogBase):
    """
    Base class for the turing-test extension for the bot.

    This extension records messages emitted into a database, and then
    emits messages in attempt to mimic the average chatter, hence
    the 'turing' name.
    """

    __SAVE_INTERVAL__ = 60
    __REMOVE_MENTION__ = regex(r"\s*@[A-Z0-9a-z_]+\s*")

    def __init__(self, super_user: str, dbm: DatabaseBroker, tg: asyncio.TaskGroup):
        """
        Initialization. 

        :paramref: `super_user`: the username of the super user who
                    will be used for 'BotHost' permissions.

        :paramref: `dbm`: the database manager object to control reading
                          and querying the database.
        """
        from random import seed

        super().__init__(super_user)
        seed()
        self.__dbm = dbm
        self.__tasks = tg
        self.__msg_delay: Tuple[float, float] = (300.0, 600.0)

    @command()
    async def ignore(self, ctx: Context, *args):
        """
        Ignore command, i.e. `!ignore @username`

        Adds the listed user to the database as a banned user.
        Anyone can opt-out by ignoring themselves (`!ignore`).

        This users' messages will be deliberately ignored.
        For privacy, maliciousness, whatever.

        Moderator-level permission is required to ignore someone
        _else_.
        """
        target_id: int

        if len(args) == 1:
            target = args[0]
            if target.startswith("@"):
                target = target[1:]

            target = await self._bot.fetch_users(names=[target])
            if len(target) < 1:
                raise ValueError()

            target_id = target[0].id
        else:
            target_id = ctx.author.id

        # Banning someone else requires mod level
        if target_id != ctx.author.id and not self._check_permission(Permission.Moderator, ctx.author):
            raise PermissionError()

        await self.__dbm.twitch_ban(ctx.channel.name, target_id, ctx.message.timestamp)

    @command()
    async def listen(self, ctx: Context, *args):
        """
        Listen command, i.e. `!listen @username`

        Removes the listed user from the database as a banned user.
        Anyone can opt-in by listening themselves (`!listen`).

        This users' messages will be now be recorded.

        Moderator-level permission is required to listen to
        someone _else_.
        """
        if len(args) == 1:
            target = args[0]
            if target.startswith("@"):
                target = target[1:]

            target = await self._bot.fetch_users(names=[target])
            if len(target) < 1:
                raise ValueError()

            target_id = target[0].id
        else:
            target_id = ctx.author.id

        # Listening to someone else requires mod level
        if target_id != ctx.author.id and not self._check_permission(Permission.Moderator, ctx.author):
            raise PermissionError()

        await self.__dbm.twitch_unban(ctx.channel.name, ctx.author.id, ctx.message.timestamp)

    @command()
    async def bad(self, ctx: Context):
        """
        bad command, i.e. `!bad <word>`

        Adds a word to the list of words that messages cannot
        contain. Any messages with this word will be ignored,
        and the extension will not generate sentences with this
        word.

        NOTE: this will trigger a complete rebuild of the dataset,
        so it's perf will be pretty horrendous.
        """
        raise NotImplementedError()

    @command()
    async def good(self, ctx: Context):
        """
        good command, i.e. `!good <word>`

        Removes a word to the list of words that messages cannot
        contain. Any messages with this word will no longer
        be ignored, and the extension will now generate sentences
        with this word.

        NOTE: this will trigger a complete rebuild of the dataset,
        so it's perf will be pretty horrendous.
        """
        raise NotImplementedError()

    async def __save_message(self, channel: str, uid: int, msg: str, msg_id: UUID, msg_time: datetime):
        """
        Internal function for saving messages to the database. Shortcuts out
        if the user is a well-known bot.
        """
        msg_time = msg_time.replace(tzinfo=UTC)

        if uid in _GLOBALLY_IGNORED_:
            return

        await self.__dbm.add_twitch_message(channel, uid, msg, msg_id, msg_time)


    async def turing_main(self, channel: Channel):
        """
        The main function that interacts with users. This is the
        function that emits a message to the end user by generating
        a message via the collected data.

        It will only emit a message while alive, and the interval is
        random in a range.
        """
        from random import randint
        try:
            messages = set()

            while not self._die.is_set():
                delay = 0.0

                rnd_delay = randint(self.__msg_delay[0], self.__msg_delay[1])

                while delay < rnd_delay:

                    if self._die.is_set():
                        return

                    await asyncio.sleep(1.0)
                    delay += 1.0

                for i in range(20):
                    text = await self.__dbm.generate_text(channel.name)

                if text is None:
                    continue

                # block until stream is live
                while len(await self._bot.fetch_streams(user_logins=[channel.name])) == 0:
                    # ...except if we're dying
                    if self._die.is_set():
                        return

                    messages.clear()
                    await asyncio.sleep(0.1)

                messages.add(text)  
                await channel.send(text)
        except asyncio.CancelledError:
            pass

    @Cog.event("event_channel_joined")
    async def on_join_channel(self, channel: Channel) -> None:
        await self.__dbm.init_corpus(channel.name)
        self.__tasks.create_task(self.turing_main(channel))

    @Cog.event("event_message")
    async def on_message(self, msg: Message) -> None:
        if msg.echo or msg.content.startswith(self._bot._prefix):
            return

        await self.__save_message(msg.channel.name,
                                  msg.author.id,
                                  msg.content,
                                  UUID(msg.id),
                                  msg.timestamp)

    @Cog.event("event_subscription")
    async def on_subscription(self, msg: Message, msg_type: str) -> None:
        await self.__save_message(msg.channel.name,
                                  msg.author.id,
                                  msg.content,
                                  UUID(msg.id),
                                  msg.timestamp)

    @Cog.event("event_user_banned")
    async def on_banned(self, banned_user: User, channel: Channel, timestamp: datetime, metadata: Dict[str, str]) -> None:
        await self.__dbm.twitch_ban(channel.name, banned_user.id, timestamp)

    @Cog.event("event_user_timeout")
    async def on_timeout(self, timed_out: User, channel: Channel, timestamp: datetime, duration: int, metadata: Dict[str, str]) -> None:
        await self.__dbm.twitch_timeout(channel.name, timed_out.id, timestamp, duration)

    @Cog.event("event_clearmsg")
    async def on_message_removed(self, _: Chatter, channel: Channel, msg_id: UUID, __: datetime, ___: Dict[str, Any]) -> None:
        await self.__dbm.twitch_remove_message(channel.name, msg_id)
