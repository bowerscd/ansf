#!/usr/bin/python3
from datetime import datetime
from functools import reduce
from os.path import exists
from typing import Any, Dict, List, Set
from collections import Counter
from markovify import NewlineText as MarkovDataset, combine as markov_combine
from csv import reader

class DataLine:

    def __init__(self, line : List[str]):
        x = { k: v for k, v in enumerate(line) }
        self._channel = x.get(0)
        self._author = x.get(1)
        self._msg_id = x.get(2)
        self._timestamp = x.get(3)
        self.__raw_string = x.get(4)
        self._msg = self.__normalize(x.get(4))

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
        self.__occurrences = Counter()
        self._corpus = ""
        for x in data:
            words = x.message.split()
            if len(x.message) == 0 or len(words) == 0:
                continue
            self._corpus += x.message + "\n"
            self.__occurrences.update(words)
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
    def occurrences(self) -> Counter:
        return self.__occurrences

    @property
    def _raw(self) -> List[DataLine]:
        return self._data

    def merge(self, other: 'DataSet'):
        return DataSet(self._raw + other._raw)

def generate_sentence(datasets: Dict[str, float],
                      chain_length = 1) -> str:
    if len(datasets) == 0:
        raise ValueError()

    data: List[DataSet] = []
    weights: List[float] = []
    for s, w in datasets.items():
        if exists(f"{s}.data.csv"):
            with open(f"{s}.data.csv", 'r') as f:
                data.append(DataSet([DataLine(x) for x in reader(f.readlines())]))
                weights.append(w)

    big_data = reduce(lambda x, y: x.merge(y), data)
    markov_data = markov_combine(models=[MarkovDataset(x.corpus, state_size=chain_length) for x in data], weights=weights)

    return markov_data.make_sentence(tries=10000,
                                     min_words=min(big_data.lengths),
                                     max_words=max(big_data.lengths),
                                     test_output=False)
