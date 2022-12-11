from asyncio import Task, gather, get_running_loop, sleep
from csv import writer
from datetime import datetime, timezone
from json import dumps, load, loads
from os.path import exists
from shutil import move
from typing import Dict, Iterable, List, Set
from re import compile

from text import generate_sentence
from twitchio import Channel, Message, PartialChatter
from twitchio.ext.commands import Bot, Cog, Context, command

_GLOBALLY_IGNORED={
    100135110, # StreamElements
    19264788,  # Nightbot
    786049415, # SpectatorDashboard
    95174992,  # MembTVBot
}

_FEATURE_CHATTER = 'chatter'

_DEFAULT_FEATURES = {
    _FEATURE_CHATTER
}

_SAVE_INTERVAL = 30
_REMOVE_MENTION = compile(r"\s*@[A-Z0-9a-z_]+\s*")

class ChannelSetting:

    @staticmethod
    def from_json_file(f: str, dataroot: str) -> 'ChannelSetting':
        j: Dict
        with open(f, 'r') as f:
            j = load(f)
        j['dataroot'] = dataroot
        return ChannelSetting(**j)

    def __init__(self, channel, dataroot, **kwargs):
        self.__channel_name = channel
        self.__die = False

        # ignored stuff
        self.__ignored_users: Set[int] = set(kwargs.get('ignored_users', []))
        self.__ignored_users.update(_GLOBALLY_IGNORED)
        self.__censored_messages = set()
        self.__bad_words = kwargs.get('bad_words', set())

        # set to avoid sending same message twice
        self.__messages_sent = set()

        self.__dataroot = dataroot

        # markov model options
        # channel influences
        self.__influences : Dict[str, float] = kwargs.get('model_influences', { channel: 1.0 })
        # chain size (each selection has x words)
        self.__chain_size = kwargs.get('model_chain_size', 2)

        # message delay, in seconds
        self.__msg_delay = kwargs.get('msg_delay', 10 * 60)

        # process delay, in seconds
        self.__process_delay = kwargs.get('process_delay', 60 * 5)

        # feature
        self.__features = kwargs.get('features', { x for x in _DEFAULT_FEATURES })

    def add_influence(self, channel: str, weight: float) -> None:
        self.__influences[channel] = weight

    def remove_influence(self, channel: str) -> None:
        del self.__influences[channel]
        self.__save()

    def clear_sent_messages(self) -> None:
        self.__messages_sent.clear()

    def add_bad_word(self, word: str) -> None:
        self.__bad_words.add(word)

    def remove_bad_word(self, word: str) -> None:
        self.__bad_words.remove(word)

    def add_ignored_user(self, id: int) -> None:
        self.__ignored_users.add(id)

    def remove_ignored_user(self, id: int) -> None:
        self.__ignored_users.remove(id)

    def change_message_delay(self, new_delay: int) -> None:
        self.__msg_delay = new_delay

    def enable_feature(self, feature: str) -> None:
        """
        Enable a feature for this channel
        """
        self.__features.add(feature)

    def disable_feature(self, feature: str) -> None:
        """
        Disable a feature from this channel
        """
        self.__features.remove(feature)

    def feature_is_enabled(self, feature: str) -> bool:
        """
        Returns whether a feature is enabled in this channel
        """
        return feature in self.__features

    def tune_chain_size(self, new_size: int) -> None:
        self.__chain_size = new_size

    @property
    def message_delay(self) -> int:
        return self.__msg_delay

    @property
    def channel(self):
        return self.__channel_name

    @property
    def influences(self) -> Iterable[str]:
        return self.__influences.keys()

    def __message_is_banned(self, msg: Message) -> bool:
        """
        Determine if a message is banned and should be ignored for processing.
        This prevents the message from being added to the dataset, preventing
        sentence generation using its content.

        The intention for this is to remove malicious entities, prevent
        risque messages, or respect moderator bans/clear messages,
        as well as prevent feedback from itself.
        """
        return msg.echo \
           or any(map(lambda x: x in self.__bad_words, msg.content.split())) \
           or msg.id in self.__censored_messages \
           or int(msg.author.id) in self.__ignored_users

    def __record_message(self, msg: Message) -> None:
        """
        Write a line of the data set, represented by msg.

        This is run synchronously.
        """
        from os.path import join
        with open(join(self.__dataroot, f"{self.__channel_name}.data.csv"), 'a') as f:
            csv = writer(f)
            csv.writerow([msg.channel.name,
                          msg.author.id,
                          msg.id,
                          msg.timestamp.replace(tzinfo=timezone.utc).isoformat(),
                          _REMOVE_MENTION.sub("", msg.content)])

    async def enqueue_message(self, msg: Message) -> None:
        """
        Enqueue a message to be recorded in the dataset to be consumed
        by the markov model.

        The first thing this function does is wait __process_delay seconds,
        then checks if the message is banned, before recording the message.
        """
        await sleep(self.__process_delay)

        if self.__message_is_banned(msg):
            return

        await get_running_loop().run_in_executor(None, self.__record_message, msg)

    async def enqueue_censor(self, msg_id: str) -> None:
        """
        Record a message id as a censored message. Any message pending to be
        recorded by enqueue_message will be ignored. If the message has
        been recorded, this does nothing.
        """
        self.__censored_messages.add(msg_id)

    async def enqueue_ban(self, banned_user: int) -> None:
        """
        Record a user id as an ignored user. Any message pending to be
        recorded by enqueue_message will be ignored, when authored
        by the user passed here. If the message has been recorded,
        this does nothing.
        """
        self.__ignored_users.add(banned_user)

    def generate_msg(self) -> str:
        """
        Generate a message using the markov chain and the configured
        options
        """
        msg = generate_sentence(self.__influences,
                                self.__chain_size)

        while msg not in self.__messages_sent and any(map(lambda x: x in self.__bad_words, msg.split())):
            msg = generate_sentence(self.__influences, self.__chain_size)
        self.__messages_sent.add(msg)

        return msg

    def __str__(self) -> str:
        return dumps({
            "channel": self.__channel_name,
            "ignored_users": list(self.__ignored_users),
            "bad_words" : list(self.__bad_words),
            "model_influences": self.__influences,
            "model_chain_size": self.__chain_size,
            "msg_delay": self.__msg_delay,
            "process_delay": self.__process_delay,
            "features": list(self.__features)
        }, sort_keys=True, indent=2)

    async def save(self) -> None:
        while not self.__die:
            await sleep(_SAVE_INTERVAL)

            current = f"{self.__channel_name}.settings.json"
            new = current + ".tmp"

            with open(new, 'w+') as n:
                n.write(str(self))

            move(new, current)

    async def close(self) -> None:
        self.__die = True


class ChatterModule(Cog):

    def __init__(self, bot: '__Bot'):
        super().__init__()

        self.__bot = bot
        self.__die = False
        self._chat_tasks : Set[Task] = set()
        for setting in self.__bot.settings.values():
            if setting.feature_is_enabled(_FEATURE_CHATTER):
                tsk: Task = get_running_loop().create_task(self.__chat(setting), name=f'{setting.channel}_chat')
                self._chat_tasks.add(tsk)
                tsk.add_done_callback(self._chat_tasks.discard)

    async def __chat(self, setting: ChannelSetting) -> None:
        while not self.__die:
            await sleep(setting.message_delay)
            st = await self.__bot.fetch_streams(user_logins=[setting.channel])
            if len(st) != 1:
                setting.clear_sent_messages()
                continue

            msg = setting.generate_msg()
            print(f"< c=\"{setting.channel}\" t=\"{datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()}\" m=\"{msg}\" >")
            await st[0].user.channel.send(msg)

    async def cog_unload(self) -> None:
        self.__die = True
        gather(*self._chat_tasks)

    def sudo(self, ctx: Context):
        """
        Determine if a context belongs to a super user as author
        """
        return int(ctx.author.id) == self.__bot._host.id

    @command(name='ignore')
    async def ignore(self, ctx: Context) -> None:
        """
        Ignore a user
        """
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or self.sudo(ctx)):
            return

        cli : List[str] = ctx.message.content.split()
        if len(cli) < 2:
            return

        user_to_ignore = await ctx.bot.fetch_users([cli[1].replace('@', '')])
        if len(user_to_ignore) == 0:
            return

        self.__bot.setting(ctx.channel.name).add_ignored_user(int(user_to_ignore[0].id))

    @command(name="listen")
    async def listen(self, ctx: Context) -> None:
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or self.sudo(ctx)):
            return

        cli : List[str] = ctx.message.content.split()
        if len(cli) < 2:
            return

        user_to_ignore = await ctx.bot.fetch_users([cli[1].replace('@', '')])
        if len(user_to_ignore) == 0:
            return

        await self.__bot.setting(ctx.channel.name).remove_ignored_user(user_to_ignore[0].id)

    @command(name="tune")
    async def tune(self, ctx: Context) -> None:
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or self.sudo(ctx)):
            return

        cli : List[str] = ctx.message.content.split()
        if len(cli) < 2:
            return

        new_size = int(cli[1])

        self.__bot.setting(ctx.channel.name).tune_chain_size(new_size)

    @command(name="delay")
    async def delay(self, ctx: Context) -> None:
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or self.sudo(ctx)):
            return

        cli : List[str] = ctx.message.content.split()
        if len(cli) < 2:
            return

        new_delay = int(cli[1])

        self.__bot.setting(ctx.channel.name).change_message_delay(new_delay)

    @command(name="add-influence")
    async def add_influence(self, ctx: Context) -> None:
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or self.sudo(ctx)):
            return

        cli : List[str] = ctx.message.content.split()
        if len(cli) < 3:
            return

        ch = cli[1].replace('@', '')

        await self.__bot.join_channels([ch])
        self.__bot.setting(ctx.channel.name).add_influence(ch, float(cli[2]))

    @command(name="del-influence")
    async def del_influence(self, ctx: Context) -> None:
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or self.sudo(ctx)):
            return

        cli : List[str] = ctx.message.content.split()
        if len(cli) < 2:
            return

        ch = cli[1].replace('@', '')

        await self.__bot.part_channels([ch])
        self.__bot.setting(ctx.channel.name).remove_influence(ch)

    @command(name="bad-word")
    async def bad_word(self, ctx: Context) -> None:
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or self.sudo(ctx)):
            return

        cli : List[str] = ctx.message.content.split()
        if len(cli) < 2:
            return

        self.__bot.setting(ctx.channel.name).add_bad_word(cli[1])

    @command(name="good-word")
    async def good_word(self, ctx: Context) -> None:
        if not (ctx.author.is_mod or ctx.author.is_broadcaster or self.sudo(ctx)):
            return

        cli : List[str] = ctx.message.content.split()
        if len(cli) < 2:
            return

        self.__bot.setting(ctx.channel.name).remove_bad_word(cli[1])

class __Bot(Bot):

    def __init__(self, twitch_access_token, approot: str, dataroot:str , participants: Iterable[str], host: str):
        from os.path import join

        super().__init__(twitch_access_token, prefix='$', initial_channels=participants)
        self._host = host

        setting_files = { x: join(approot, f'{x}.settings.json') for x in participants }
        self._settings = { channel: ChannelSetting.from_json_file(setting, dataroot) if exists(setting) else ChannelSetting(channel, dataroot) for channel, setting in setting_files.items() }

    def setting(self, channel: str) -> ChannelSetting:
        return self._settings[channel]

    @property
    def settings(self) -> Dict[str, ChannelSetting]:
        return self._settings

    async def event_ready(self) -> None:
        self._host = (await self.fetch_users(names=[self._host]))[0]
        channels = set()
        self.__save_tasks: Set[Task] = set()
        for setting in self._settings.values():
            tsk: Task = self.loop.create_task(setting.save(), name=f"{setting.channel}_save")
            self.__save_tasks.add(tsk)
            tsk.add_done_callback(self.__save_tasks.discard)
            channels.update(setting.influences)

        await self.join_channels(list(channels))
        self.add_cog(ChatterModule(self))

        print(dumps({
            "bot_name": self.nick,
            "super_user": self._host.name,
            "channels": { ch: loads(str(s)) for ch, s in self._settings.items() },
            "watched": list(channels),
            "modules": list(self.cogs.keys())
        }, indent=2, sort_keys=True))

    async def event_message(self, msg: Message) -> None:
        if msg.content[0] == self._prefix:
            return await super().event_message(msg)

        await self.setting(msg.channel.name).enqueue_message(msg)

    async def event_usernotice_subscription(self, metadata) -> None:
        print(metadata)

    async def event_clearchat(self, chatter: PartialChatter, channel: Channel, tags: dict):
        await self.setting(channel.name).enqueue_ban((await chatter.user()).id)

    async def event_clearmsg(self, chatter: PartialChatter, channel: Channel, msg_id: str, tags: dict):
        await self.setting(channel.name).enqueue_censor(msg_id)

    async def close(self) -> None:
        [ await x.cog_unload() for x in self.cogs.values() ]
        [ await x.close() for x in self.settings.values() ]
        await gather(*self.__save_tasks)
        await super().close()

def start_bot(approot: str, dataroot: str, access_token: str, channels: List[str], super_user : str) -> None:
    bot = __Bot(access_token, approot, dataroot, channels, super_user)
    bot.run()
