import asyncio
from typing import Dict, Awaitable
from aoe2dashboard import Client
from aoe2dashboard.packets import PlayerUpdate, PlayerStatusType

class DashboardBroker(Client):
    """
    Class controlling access to the spectator dashboard
    """

    def __init__(self, tg, **kwargs) -> None:
        """
        TODO
        """
        self.__player_states = {}
        self.__task_group = tg
        super().__init__()

    async def event_player_update(self, packet: PlayerUpdate) -> None:
        if getattr(packet, 'name', None) == None:
            return

        if packet.name not in self.__player_states:
            self.__player_states[packet.name] = -1

        if packet.status != self.__player_states[packet.name]:
            self.__player_states[packet.name] = packet.status

    def player_is_idle(self, player: str) -> bool:
        match self.__player_states.get(player, -1):
            case PlayerStatusType.UNDEFINED \
               | PlayerStatusType.BANNED    \
               | PlayerStatusType.LOBBY     \
               | PlayerStatusType.QUEUING   \
               | PlayerStatusType.DASHBOARD:
                return True
            case _:
                return False