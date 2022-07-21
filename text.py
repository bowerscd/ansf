#!/usr/bin/python3
from typing import List, Set
from enum import Enum, auto
from functools import reduce

from numpy import bincount, add
from numpy.random import choice
from scipy.sparse import csr_matrix, dok_matrix

class ModelType(Enum):
    MarkovChain = auto()

class ChatLine:

    @classmethod
    def from_csv_line(cls, msg: str) -> 'ChatLine':
        ctx = msg.split(",", maxsplit=3)
        return ChatLine(ctx[3], ctx[1], ctx[2])

    def __init__(self, msg : str, author_id : str, msg_id : str):
        self._msg = msg.strip()
        self._author = author_id
        self._msg_id = msg_id

    @property
    def msg_id(self) -> str:
        return self._msg_id

    @property
    def author(self) -> str:
        return self._author

    @property
    def message(self) -> str:
        return self._msg

    @property
    def words(self) -> List[str]:
        normalized = self.message.replace('’', '\'').replace('”', '"').replace('“', '"').encode('utf8', errors='replace').decode('utf8', errors='replace')
        for spaced in ['.','-',',','!','?','(','—',')', ';', ':']:
            msg = normalized.replace(spaced, ' {0} '.format(spaced))
        return msg.split()

    def __str__(self) -> str:
        return f"[{self.author}]{self.message}"

class TwitchDataSet:

    def __init__(self, data: List[ChatLine]):
        self._chats = data
        words = []
        for x in self._chats:
            words = words + x.words
        self._corpus = words
        self.__markov_k = None

    @classmethod
    def from_file(cls, streamer: str):
        with open(f"{streamer}.data.log", "r") as f:
            return TwitchDataSet([ChatLine.from_csv(x) for x in f.readlines()])

    @property
    def dataset(self) -> List[str]:
        return self._corpus

    @property
    def unique_words(self) -> Set[str]:
        return set(self._corpus)

    @property
    def chats(self) -> List[ChatLine]:
        return self._chats

    @property
    def stats(self):
        return {
            "lines": len(self._chats),
            "unique_words": len(list(self.unique_words)),
            "characters": reduce(lambda x, y: x + y, [len(x) for x in self._corpus]),
            "histogram": bincount([len(x.message.split()) for x in self._chats])
        }

    def _create_markov_dataset(self, k = 2):
        corpus_words = self.dataset
        distinct_words = list(self.unique_words)
        word_idx_dict = {word: i for i, word in enumerate(distinct_words)}
    
        sets_of_k_words = [ ' '.join(corpus_words[i:i+k]) for i, _ in enumerate(corpus_words[:-k]) ]
        sets_count = len(list(set(sets_of_k_words)))
        next_after_k_words_matrix = dok_matrix((sets_count, len(distinct_words)))
        distinct_sets_of_k_words = list(set(sets_of_k_words))
        k_words_idx_dict = {word: i for i, word in enumerate(distinct_sets_of_k_words)}

        for i, word in enumerate(sets_of_k_words[:-k]):

            word_sequence_idx = k_words_idx_dict[word]
            next_word_idx = word_idx_dict[corpus_words[i+k]]
            next_after_k_words_matrix[word_sequence_idx, next_word_idx] +=1

        self.__markov_k = k
        self.__markov_distinct_sets_of_k_words = distinct_sets_of_k_words
        self.__markov_distinct_words = distinct_words
        self.__makrov_matrix = next_after_k_words_matrix
        self.__markov_k_words_idx_dict = k_words_idx_dict

    def __sample(self, word_sequence, variability: float = 0):
        next_word_vector = self.__makrov_matrix[self.__markov_k_words_idx_dict[word_sequence]] + variability
        likelihoods = csr_matrix(next_word_vector)/next_word_vector.sum()
        weights = likelihoods.toarray().flatten()
        # if no words possible - terminate
        if weights.sum() == 0.0:
            return ""
        return choice(self.__markov_distinct_words, p=weights)

    def __stochastic_chain(self, chain_len: int, k: int=2, variability: float=0, regen: bool = False):

        if regen or not self.__markov_k or self.__markov_k != k:
            self._create_markov_dataset(k)

        seed = choice(self.__markov_distinct_sets_of_k_words)

        current_words = seed.split(' ')
        sentence = seed

        for _ in range(chain_len):
            sentence+=' '
            next_word = self.__sample(' '.join(current_words), variability=variability)
            sentence+=next_word
            current_words = current_words[1:]+[next_word]
        return sentence

    def _generate_sentence(self, _type : ModelType=ModelType.MarkovChain, **kwargs):
        match _type:
            case ModelType.MarkovChain:
                return self.__stochastic_chain(**kwargs)
            case _:
                raise NotImplementedError()

def generate_sentence(channels: List[str],  _type : ModelType=ModelType.MarkovChain, **kwargs) -> str:
    all_data = []
    for ch in channels:
        with open(f"{ch}.data.log", 'r') as f:
            all_data += [ChatLine.from_csv_line(x) for x in f.readlines()]

    dataset = TwitchDataSet(all_data)
    stats = dataset.stats

    chain_len = choice(a=[x for x in range(len(stats['histogram']))], p=(stats['histogram'] / add.accumulate(stats['histogram'])[-1]))
    if chain_len <= 2:
        k = 1
    elif chain_len <= 5:
        k = 2
    else:
        k = 3

    sentence = dataset._generate_sentence(chain_len=chain_len, k=k)
    print(f"< K={k} Chain={chain_len} Msg='{sentence}' >")
    return sentence
