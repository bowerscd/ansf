from uuid import UUID
from typing import List, Iterable, Dict
from re import compile, sub
from hashlib import sha384
import asyncio

from .generation import GeneratorBackend, TextGenerator

_NOSPACE = compile(r"\s\s+")
_MENTION = compile(r"\s*@[A-Z0-9a-z_]+\s*")

class Corpus(object):
    """
    Represents a corpus, a dataset of large amounts of text. This
    is all in-memory.
    """

    def __init__(self,
                 data: Iterable[str] | None = None,
                 flavor: GeneratorBackend = GeneratorBackend.MARKOVIFY):
        self._raw_corpus: List[str] = []
        if data is None:
            data = []


        self._active_generator: TextGenerator = flavor.value
        if len(data) == 0:
            return

        self._raw_corpus += data
        self._real_dataset = "\n".join([self._active_generator.fmt(self.__normalize(x)) for x in data])
        self._active_generator.add_data(self._real_dataset)

    def __normalize(self, msg: str) -> str:
        return sub(_MENTION, "", sub(_NOSPACE, " ", msg))

    def add(self, msg: str) -> None:
        """
        Add a new message to the corpus (dataset)

        :paramref: `msg`: string to add
        """

        msg_ = self._active_generator.fmt(self.__normalize(msg))
        if len(msg_.strip()) == 0:
            return

        self._raw_corpus.append(msg_)
        self._real_dataset += "\n" + msg_
        self._active_generator.add_data(msg_)

    async def generate_text(self) -> str:
        return await self._active_generator.generate_text()

