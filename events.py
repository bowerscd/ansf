from asyncio import PriorityQueue, AbstractEventLoop
from time import sleep
from enum import Enum, auto
from typing import Any, Tuple
from twitchio import Message, Channel
from twitchio.chatter import PartialChatter


class ChatEventType(Enum):
    Ban = 0
    Censor = 1
    Message = 2

    def __lt__(self, other):
        if not isinstance(other, ChatEventType):
            raise TypeError()

        return self.value < other.value

    def __gt__(self, other):
        if not isinstance(other, ChatEventType):
            raise TypeError()

        return self.value > other.value

    def __eq__(self, other):
        if not isinstance(other, ChatEventType):
            raise TypeError()

        return self.value == other.value

class ChatEvent:
    """
    """
    def __init__(self, type : ChatEventType, *args) -> None:
        """
        """
        self.__type : ChatEventType = type
        self.__data : None | Message | Tuple[PartialChatter, Channel, dict] | Tuple[PartialChatter, Channel, str, dict]
        self.__tags : None | dict
        match type:
            case ChatEventType.Ban:
                self.__data = (args[0], args[1], args[2])
            case ChatEventType.Censor:
                self.__data = (args[0], args[1], args[2], args[3])
            case ChatEventType.Message:
                self.__data = args[0]
            case _:
                raise NotImplementedError()

    def __lt__(self, other: Any) -> int:
        if not isinstance(other, ChatEvent):
            raise TypeError()
        return self.__type < other.__type

    def __gt__(self, other: Any) -> int:
        if not isinstance(other, ChatEvent):
            raise TypeError()
        return self.__type > other.__type

    def __eq__(self, other) -> bool:
        if not isinstance(other, ChatEvent):
            return False
        return self.__type == other.__type and self.__data == other.__data

    @property
    def event_type(self) -> ChatEventType:
        return self.__type

    @property
    def payload(self) -> Message | Tuple[PartialChatter, Channel] | Tuple[PartialChatter, Channel, str]:
        return self.__data

class DelayedPriorityQueue(PriorityQueue):
    """
    """

    def __init__(self, maxsize: int = ..., *, delay: int = ...) -> None:
        """
        """
        super().__init__(maxsize)
        self.__delay = delay

    def _get(self):
        """
        """
        try:
            sleep(self.__delay / 1000)
            return super()._get()
        except KeyboardInterrupt:
            return None
