import asyncio

from twitchio.ext.commands import Cog, Context, command
from twitchio import Message, Chatter, Channel, User
from typing import Dict, Any, List, Set
from re import compile as regex
from random import shuffle, choice
from aiohttp import ClientSession
from math import ceil
from html import unescape as htmlunescape

from brokers import DashboardBroker, DatabaseBroker

from .cogbase import CogBase, Permission

__TWITCH_TO_DASHBOARD_NAME__ = {
    "slamjam_": "slam"
}

class TriviaQuestion(object):

    def __init__(self, q: str, a : str, incorrect: List[str]):
        a = htmlunescape(a)
        q = htmlunescape(q)
        incorrect = [htmlunescape(x) for x in incorrect]
        a_pool = incorrect + [a]
        self.__q = q
        self.__multiple_choice = len(a_pool) > 2
        self.__formatted: Dict[str, str] | None = None
        self.__answerers: Set[int] = set()

        if self.__multiple_choice:
            shuffle(a_pool)
            self.__formatted = { a_pool[i]: chr(ord('A') + i) for i in range(len(a_pool)) }
            self.__answer = self.__formatted[a]
        else:
            self.__answer = a

    def is_correct(self, answer: str, answerer: int) -> bool:
        if answerer in self.__answerers:
            pass

        self.__answerers.add(answerer)

        if self.__multiple_choice:
            return answer.lower() == self.__answer.lower()

        return self.__answer.lower().startswith(answer.lower())

    @property
    def answer(self) -> str:
        return self.__answer

    @property
    def question(self) -> str:
        return self.__q

    def __str__(self) -> str:
        if self.__multiple_choice:
            q = self.__q
            # if not self.__q.endswith('?'):
            #     q += '?'
            s = ". ".join([f"{l}. {a}" for a, l in self.__formatted.items()])
            return f"{q} {s}"
        else:
            return f"True or False? {self.__q}"

class _TriviaSource(object):
    def __init__(self, source):
        self.__source = source

    async def question(self) -> TriviaQuestion:
        pass

    async def dispute(self) -> str:
        return f"Dispute the answer at {self.__source}"

class _WebTriviaSource(_TriviaSource):

    def __init__(self, url) -> None:
        from urllib.parse import urlparse
        self.__session = ClientSession()
        self.__url = url
        parsed = urlparse(self.__url)
        super().__init__(f"{parsed.scheme}://{parsed.netloc}")

    async def _fetch(self) -> Dict[str, Any]:
        req = await self.__session.get(self.__url)
        return await req.json(content_type=None)

    async def __aenter__(self) -> '_WebTriviaSource':
        await self.__session.__aenter__()
        return self

    async def __aexit__(self, *a) -> None:
        await self.__session.__aexit__(*a)

class OpenTrivia(_WebTriviaSource):

    def __init__(self) -> None:
        super().__init__("https://opentdb.com/api.php?amount=1")

    async def question(self) -> TriviaQuestion:
        r = await self._fetch()

        if r['response_code'] != 0:
            # TODO Logging
            pass

        r = r['results'][0]

        return TriviaQuestion(r['question'], r['correct_answer'], r["incorrect_answers"])

class TriviaApi(_WebTriviaSource):

    def __init__(self) -> None:
        super().__init__("https://the-trivia-api.com/api/questions?limit=1")

    async def question(self) -> TriviaQuestion:
        r = (await self._fetch())[0]
        return TriviaQuestion(r['question'], r['correctAnswer'], r["incorrectAnswers"])

class GithubSource(_WebTriviaSource):

    def __init__(self) -> None:
        super().__init__("https://raw.githubusercontent.com/bowerscd/aoe2trivia/main/data.json")

    async def question(self) -> TriviaQuestion:

        r = await self._fetch()
        q = choice(r)
        return TriviaQuestion(q['question'], q['answer'], q['options'] + q['answer'])


class Trivia(CogBase):
    """
    Base class for the trivia extension for the bot.
    """

    def __init__(self, super_user: str, dashboard: DashboardBroker, dbm: DatabaseBroker, tg: asyncio.TaskGroup):
        """
        Initialization.

        :paramref: `super_user`: the username of the super user who
                    will be used for 'BotHost' permissions.

        """
        from random import seed

        super().__init__(super_user)
        seed()
        # GithubSource()
        self.__trivia_sources: tuple[_WebTriviaSource] = (TriviaApi(), OpenTrivia())
        self.__dash = dashboard
        self.__dbm = dbm
        self.__tasks = tg
        self.__active_messages: Dict[str, List[asyncio.Event, TriviaQuestion, float]] = {}
        self.__trivia_delay: float = 90.0
        self.__trivia_time: float = 15.0

    async def __aenter__(self) -> '_WebTriviaSource':
        [await x.__aenter__() for x in self.__trivia_sources]
        return self

    async def __aexit__(self, *a) -> None:
        [await x.__aexit__(*a) for x in self.__trivia_sources]

    async def emit_message(self, channel: Channel) -> str:
        """
        """
        source = choice(self.__trivia_sources)

        question = await source.question()

        self.__active_messages[channel.name] = [asyncio.Event(), question, 0.0]
        await channel.send(f"{self._bot._prefix}answer in {ceil(self.__trivia_time)}s: {question}")

    async def trivia_main(self, channel: Channel):
        """

        """
        try:
            player_name = __TWITCH_TO_DASHBOARD_NAME__.get(channel.name, channel.name)
            while not self._die.is_set():

                # If player is not idle, or is not live, spin
                while True:

                    if self.__dash.player_is_idle(player_name) and len(await self._bot.fetch_streams(user_logins=[channel.name])) != 0:
                        break

                    await asyncio.sleep(0.5)

                # ask the question
                await self.emit_message(channel)
                while self.__active_messages[channel.name][2] < self.__trivia_time:
                    if self._die.is_set():
                        return

                    if self.__active_messages[channel.name][0].is_set():
                        break

                    self.__active_messages[channel.name][2] += 0.1
                    await asyncio.sleep(0.1)

                # no one got the answer, report the right answer
                if not self.__active_messages[channel.name][0].is_set():
                    self.__active_messages[channel.name][0].set()
                    await channel.send(f"The correct answer was: {self.__active_messages[channel.name][1].answer}")

                # Wait until the next quesiton can be asked
                time_elapsed = 0.0
                while time_elapsed < self.__trivia_delay:
                    if self._die.is_set():
                        return

                    await asyncio.sleep(1.0)
                    time_elapsed += 1.0

        except asyncio.CancelledError:
            pass

    @Cog.event("event_channel_joined")
    async def on_join_channel(self, channel: Channel) -> None:
        self.__tasks.create_task(self.trivia_main(channel))

    async def __get_stats(self, uid: int) -> str:
        rank, score, questions = await self.__dbm.get_trivia_stats(uid)
        return f"You are currently rank {rank}, with {score} points, and {questions} correct answer(s)."

    @command()
    async def trivia_rank(self, ctx: Context):
        await ctx.reply(self.__get_stats(ctx.author.id))

    @command(name="a", aliases=["answer"])
    async def answer(self, ctx: Context) -> None:
        """
        """

        v = self.__active_messages[ctx.channel.name]
        if v[0].is_set():
            return

        args = tuple(filter(lambda x: len(x) > 0, ctx.message.content.split()))
        if len(args) < 2:
            return

        if v[1].is_correct(args[1], ctx.author.id):
            v[0].set()
            time_remaining = self.__trivia_delay - v[2]
            score_increase = round(5.0 * time_remaining)
            await self.__dbm.increment_trivia_score(ctx.author.id, score_increase)
            await ctx.reply(f"Correct! Your trivia score has increased by {score_increase}! {await self.__get_stats(ctx.author.id)}")
