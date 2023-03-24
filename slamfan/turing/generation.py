from enum import Enum
from re import compile, sub
from markovify import NewlineText as MarkovDataset, combine as MergeDatasets
import asyncio

class TextGenerator(object):
    """
    Abstract class representing a method of
    text generation.
    """

    def __init__(self) -> None:
        pass

    def add_data(self, corpus: str) -> None:
        raise NotImplementedError()

    async def generate_text(self):
        raise NotImplementedError()

    def fmt(self, str_: str) -> str:
        raise NotImplementedError()

    @property
    def type(self) -> 'GeneratorBackend':
        return self

class MarkovifyGenerator(TextGenerator):
    """
    Class representing generating text via Markovify,
    a library for using markov chains to generate text.
    """

    def __init__(self, **kwargs):
        super().__init__()

        self.__model: MarkovDataset | None = None
        self.__chain_length = kwargs.get('chain', 2)

    def add_data(self, corpus: str) -> None:
        if self.__model is None:
            self.__model = MarkovDataset(corpus, state_size=self.__chain_length)
        else:
            self.__model = MergeDatasets([self.__model,
                                          MarkovDataset(corpus,
                                                        state_size=self.__chain_length)])

    async def generate_text(self):
        from functools import partial

        if self.__model is None:
            return None

        fn = partial(self.__model.make_sentence, state_size=self.__chain_length, test_output=False)
        return await asyncio.get_running_loop().run_in_executor(None, fn)

    def fmt(self, str_: str) -> str:
        if not isinstance(str_, str):
            raise TypeError()

        repl = { "(", ")", "[", "]", "{", "}", "'", '"', ":", ";", "<", ">", "*" }

        ret: str = str_
        for x in repl:
            ret = ret.replace(x, "")

        return ret


class GeneratorBackend(Enum):
    """
    Enumerators describing the generators - should
    generally use this class for assignment.
    """
    UNDEFINED = TextGenerator()
    MARKOVIFY = MarkovifyGenerator()
