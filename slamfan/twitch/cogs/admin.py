
from twitchio.ext.commands import Cog, Context, command
import asyncio

from .cogbase import CogBase, Permission

class Admin(CogBase):
    """
    Administrator cog. Contains functions to kill, restart
    and shutdown the hosting bot remotely.
    """
    def __init__(self, super_user):
        super().__init__(super_user)
        self.__restart = asyncio.Event()
        self.__die = asyncio.Event()

    @command()
    async def kill(self, ctx: Context) -> None:
        from sys import exit
        """
        Forcibly exit the server.
        """
        if not self._check_permission(Permission.BotHost, ctx.author):
            return

        exit(-1)

    @command(name="die")
    async def die_cmd(self, ctx: Context) -> None:
        """
        Gracefully signal the server to shutdown.
        """
        if not self._check_permission(Permission.Moderator, ctx.author):
            return

        self.__die.set()


    @command()
    async def restart(self, ctx: Context):
        """
        Gracefully signal the server to shutdown, and signal
        that the server should restart.
        """
        if not self._check_permission(Permission.Moderator, ctx.author):
            return

        self.__restart.set()
        self.__die.set()

    @property
    def die_event(self) -> asyncio.Event:
        return self.__die

    @property
    def restart_event(self) -> asyncio.Event:
        return self.__restart
