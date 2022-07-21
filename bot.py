from copy import deepcopy
from os.path import exists
from typing import Iterable
from logging import debug, error
from datetime import datetime

from events import ChatEvent, ChatEventType, DelayedPriorityQueue
from text import generate_sentence
from twitchio import Channel, Message, PartialChatter, User, channel
from twitchio.ext.commands import Bot
from twitchio.ext.routines import routine
from twitchio.notice import UserNotice

_GLOBALLY_IGNORED={
    100135110, # StreamElements
    19264788,  # Nightbot
    786049415, # SpectatorDashboard
    95174992,  # MembTVBot
}

__BAD_WORDS={
}

class __Bot(Bot):

    def __init__(self, twitch_access_token, channels: Iterable[str]):
        self._msg_queue: DelayedPriorityQueue = DelayedPriorityQueue(maxsize=0, delay=1000 * 4)
        self.__ignored_users = { x.lower(): deepcopy(_GLOBALLY_IGNORED) for x in channels }
        self.__censored_messages = {x.lower(): set() for x in channels }
        for x in channels:
            fn = f"{x}.ban.log"
            if exists(fn):
                with open(fn, "r") as f:
                    for ln in f:
                        self.__ignored_users[x].add(ln)

        super().__init__(twitch_access_token, prefix='$', initial_channels=channels)

    def run(self):
        from asyncio import all_tasks
        try:
            self.loop.create_task(self.connect())
            self._emit_msg.start()
            self._record_chats.start()
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            for t in all_tasks(self.loop):
                t.cancel()
            self.loop.run_until_complete(self.close())
            self.loop.close()

    async def event_ready(self) -> None:
        print(f"Logged in as {self.nick}")

    async def event_message(self, msg: Message) -> None:
        await self._msg_queue.put(ChatEvent(ChatEventType.Message, msg))

    async def event_usernotice_subscription(self, notice: UserNotice) -> None:
        if len(notice.message.content) > 0:
            await self._msg_queue.put(ChatEvent(ChatEventType.Message, notice.message))

    async def event_clearchat(self, chatter: PartialChatter, channel: Channel, tags: dict):
        await self._msg_queue.put(ChatEvent(ChatEventType.Ban, chatter, channel, tags))

    async def event_clearmsg(self, chatter: PartialChatter, channel: Channel, msg_id: str, tags: dict):
        await self._msg_queue.put(ChatEvent(ChatEventType.Censor, chatter, channel, msg_id, tags))

    @routine(minutes=10, wait_first=True)
    async def _emit_msg(self) -> None:
        for x in self.connected_channels:
            try:
                fmt = generate_sentence([x.name])
                streams = (await self.fetch_streams(user_logins=[x.name]))
                if len(streams) > 0:
                    await self.get_channel(x.name).send(fmt)
            except Exception as e:
                error(f"{e}")

    @routine(iterations=1, seconds=10, wait_first=True)
    async def _record_chats(self):
        while True:
            item: ChatEvent = await self._msg_queue.get()
            match item.event_type:
                case ChatEventType.Ban:
                    chatter: User = await item.payload[0].user()
                    channel: Channel = item.payload[1] 

                    self.__ignored_users[channel.name].add(chatter.id)
                    with open(f"{channel.name}.bans.log", "a") as f:
                        f.write(f"{chatter.id}\n")

                case ChatEventType.Censor:
                    channel: Channel = item.payload[1]
                    msg_id: str = item.payload[2]
                    self.__censored_messages[channel.name].add(msg_id)

                case ChatEventType.Message:
                    msg: Message = item.payload
                    if msg.echo or msg.author.id in self.__ignored_users:
                        continue
                    if msg.id in self.__censored_messages:
                        self.__censored_messages.pop(msg.id)
                        self._msg_queue.task_done()
                        continue
                    with open(f"{msg.channel.name}.data.log", 'a') as f:
                        f.write(f"{msg.channel.name},{msg.author.id},{msg.id},{msg.content}\n")
                        f.flush()
                case _:
                    self._msg_queue.task_done()
                    continue
            self._msg_queue.task_done()


def start_bot(access_token, channels):
    bot = __Bot(access_token, channels)
    bot.run()
