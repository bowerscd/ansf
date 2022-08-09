#!/usr/bin/python3
from datetime import datetime
from typing import List, Set
from collections import Counter
from markovify import NewlineText as markovifyDataset

class DataLine:

    def __init__(self, line : str):
        x = { k: v for k, v in enumerate(line.split(sep=',')) }
        self._channel = x.get(0)
        self._author = x.get(1)
        self._msg_id = x.get(2)
        self.__raw_string = x.get(3)
        self._msg = self.__normalize(x.get(3))
        self._timestamp = x.get(4)

    @property
    def msg_id(self) -> str:
        return self._msg_id

    @property
    def author(self) -> str:
        return self._author

    @property
    def message(self) -> str:
        return self._msg

    def timestamp(self) -> datetime | None:
        return self._timestamp

    def __str__(self) -> str:
        return f"[{self.author}]{self.message}"

    def __normalize(self, st: str) -> str:
        from re import sub
        nospace = st.strip()
        for x in {"(", ")", "[", "]", "'", '"'}:
            nospace = nospace.replace(x, "")
        return sub(r"\s\s+", " ", nospace)

    @property
    def _raw_string(self):
        return self.__raw_string

class DataSet:

    def __init__(self, data: List[DataLine]):
        self._data = data
        self._lengths = Counter()
        self._corpus = ""
        for x in data:
            words = x.message.split()
            if len(x.message) == 0 or len(words) == 0:
                continue
            self._corpus += x.message + "\n"
        self.lengths.update([len(x.message.split()) for x in data if len(x.message.split()) > 0])


    @property
    def corpus(self) -> str:
        return self._corpus

    @property
    def unique_words(self) -> Set[str]:
        return set(self._corpus.split())

    @property
    def lengths(self) -> Counter:
        return self._lengths

    @property
    def _raw(self) -> List[DataLine]:
        return self._data

    def merge(self, other: 'DataSet'):
        return DataSet(self._raw + other._raw)

def generate_sentence(datasets_to_use: List[str], weights: List[float] = [1.0]) -> str:
    if len(datasets_to_use) == 0:
        raise ValueError()

    data: DataSet
    with open(f"{datasets_to_use[0]}.data.log", 'r') as f:
        data = DataSet([DataLine(x) for x in f.readlines()])

    for i in range(1, len(datasets_to_use)):
        dataset = datasets_to_use[i]
        with open(f"{dataset}.data.log", 'r') as f:
            data.merge(DataSet([DataLine(x) for x in f.readlines()]))

    markov_data = markovifyDataset(data.corpus)

    x = None
    while x is None:
        x = markov_data.make_sentence(tries=100, min_words=min(data.lengths), max_words=max(data.lengths))

    return x