from twitchio.ext.commands import Cog, command
from twitchio.ext.commands.bot import Bot
from twitchio import Chatter
from enum import Enum

import asyncio

class Permission(Enum):

    BotHost = 0,
    Broadcaster = 1,
    Moderator = 2,
    VIP = 3,
    Subscriber = 4,
    Anonymous = 5

    def __lt__(self, other) -> bool:
        if not isinstance(other, Permission):
            raise TypeError()

        return self.value < other.value

    def __gt__(self, other) -> bool:
        if not isinstance(other, Permission):
            raise TypeError()

        return self.value > other.value

    def __eq__(self, other) -> bool:
        if not isinstance(other, Permission):
            raise TypeError()

        return self.value == other.value

    def __le__(self, other) -> bool:
        return self < other or self == other

    def __ge__(self, other) -> bool:
        return self > other or self == other

class CogBase(Cog):
    """
    Extended base class for all cogs. Instantiates
    with a super user host, and allows for a consistent
    method to check permissions of users.

    Additionally automatically associates the bot instance
    with the extended cog.
    """

    def __init__(self, super_user: str):
        self._sudo = super_user
        self._die = asyncio.Event()

    def _load_methods(self, bot: Bot) -> None:
        self._bot = bot
        return super()._load_methods(bot)

    def cog_unload(self) -> None:
        self.die()
        return super().cog_unload()

    def die(self):
        self._die.set()

    @Cog.event("event_ready")
    async def on_ready(self):
        print(f"{self._bot.nick}.{self.name} ready")

    def _check_permission(self, required: Permission, person: Chatter) -> bool:
        got: Permission = Permission.Anonymous

        if self._sudo.lower() == person.name.lower():
            got = Permission.BotHost
        elif person.is_broadcaster:
            got = Permission.Broadcaster
        elif person.is_mod:
            got = Permission.Moderator
        elif person.is_vip:
            got = Permission.VIP
        elif person.is_subscriber:
            got = Permission.Subscriber

        return got <= required
