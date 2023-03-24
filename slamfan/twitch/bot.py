from twitchio.ext.commands import Bot, Context
from twitchio.ext.commands.errors import CommandNotFound
from datetime import datetime
from twitchio import User, Channel, Chatter, Message
from uuid import UUID
from typing import Dict, Any, List

from .cogs.cogbase import CogBase

class TwitchBot(Bot):
    """
    Base Class for Twitch Bots. Contains additional events
    that are extensions for the base `Bot` class provided
    by twitchio.

    Additionally provides __aenter__ and __aexit__ context
    managers.
    """
    def __init__(self, access_token: str, prefix: str, channels: List[str] = []):
        """
        Base Class for Twitch Bots. Contains additional events
        that are extensions for the base `Bot` class provided
        by twitchio.

        :paramref:`access_token`:
            Twitch OAUTH Token To use for this bot instance
        :paramref:`prefix`:
            Prefix to use for commands
        :paramref:`channels`:
            List of channels to watch initially.
        """
        super().__init__(access_token, prefix=prefix, initial_channels=channels)

    async def __aenter__(self):
        """
        Context manager allowing `async with` statements: connects the bot
        asynchronously on start of statement
        """
        await self.connect()
        await self.wait_for_ready()

    async def __aexit__(self, *args):
        """
        Context manager allowing `async with` statements: disconnects the bot
        on end of statement.
        """
        await self.close()

        for v in self.cogs.values():
            if isinstance(v, CogBase):
                v.die()

    async def event_raw_data(self, data: str) -> None:
        """
        Processes raw event data. This is used to fill in the gaps
        that exist in TwitchIO, like for ban/timeout events (clearchat),
        message removal (clearmsg), and the actual usernotice events,
        including the message.

        :paramref:`data`:
            raw event data passed by twitchio

        """
        SPECIAL_ACTIONS = { "PING" }
        MODERATOR_ACTIONS = { "CLEARCHAT", "CLEARMSG" }
        ADVANCED_ACTIONS = { "USERNOTICE" }

        action: str
        groups = data.strip().split(maxsplit=5)

        if groups[0] in SPECIAL_ACTIONS:
            await super().event_raw_data(data)
            return

        if groups[1] == "JOIN":
            action = groups[1]
        elif groups[2] in MODERATOR_ACTIONS:
            action = groups[2]
        else:
            action = groups[-2]

        if action in MODERATOR_ACTIONS:
            await self.__process_moderator_action(action, groups)
            return

        if action in ADVANCED_ACTIONS:
            await self.__process_advanced_action(action, groups)
            return

        await super().event_raw_data(data)

    async def __process_moderator_action(self, action: str, data: List[str]) -> None:
        """
        Process a message that is typically associated with a moderator action,
        like a user being banned, timed-out, or a message being deleted.

        :paramref:`action`:
            the action being taken. Can be one of `CLEARMSG` or `CLEARCHAT`.
        :paramref:`data`:
            the event data for the action

        """
        user_moderated: User | Chatter | None = None
        channel: Channel = self.get_channel(data[3][1:])
        metadata: Dict[str, str] = dict([tuple(x.split("=")) for x in data[0][1:].split(";")])
        timestamp: datetime = datetime.utcfromtimestamp(int(metadata['tmi-sent-ts']) / 1000)

        if 'login' in metadata:
            user_moderated = channel.get_chatter(metadata['login'])
        elif len(data) > 4:
            user_moderated = await self.fetch_users(names=[data[4][1:]])

        match action:
            case "CLEARCHAT":
                if len(data) > 4:
                    if 'ban-duration' in metadata:
                        self.run_event("user_timeout", user_moderated, channel, timestamp, int(metadata['ban-duration']), metadata)
                    else:
                        self.run_event('user_banned')
                else:
                    self.run_event("clearchat", channel, timestamp, metadata)
            case "CLEARMSG":
                self.run_event("clearmsg", user_moderated, channel, UUID(metadata['target-msg-id']), timestamp, metadata)
            case _:
                raise NotImplementedError


    async def __process_advanced_action(self, _: str, data: List[str]) -> None:
        """
        Process a message that is considered 'advanced' by TwitchIO (or not
        processed correctly - most of the time, the message content is actually
        dropped). These are all USERNOTICE events.

        :paramref:`_`:
            the action being taken. Always `USERNOTICE`.
        :paramref:`data`:
            the event data for the action

        """
        metadata: Dict[str, str] = dict([tuple(x.split("=")) for x in data[0][1:].split(";")])
        channel : Channel = self.get_channel(data[3][1:])
        user: Chatter = channel.get_chatter(metadata['login'])
        msg_type: str = metadata['msg-id']
        message: Message = Message(
            raw_data=" ".join(data),
            content=data[-1][1:],
            author=user,
            channel=channel,
            tags=metadata)

        match msg_type:
            case 'sub'|'resub'|'rewardgift'|'giftpaidupgrade'|'submysterygift'|'anongiftpaidupgrade':
                if len(data) == 5:
                    self.run_event("subscription_message", message, msg_type)
            case _:
                raise NotImplementedError

    async def event_command_error(self, context: Context, error: Exception) -> None:
        if isinstance(error, CommandNotFound):
            return

        return await super().event_command_error(context, error)

    async def event_subscription_message(self, message: Message, msg_type: str) -> None:
        """
        Event raised when a subscription event occurs - of any type.

        :paramref:`message`:
            the message associated with the subscription
        :paramref:`msg_type`:
            the type of subscription - can be one of::

                - sub
                - resub
                - rewardgift
                - giftpaidupgrade
                - submysterygift
                - anongiftpaidupgrade

        The raw form of these events are::

            [@<key>=<value>[;<key>=<value>]*] :tmi.twitch.tv USERNOTICE #<channel> [:<message>]

        """
        pass

    async def event_user_banned(self, banned_user: User, channel: Channel, timestamp: datetime, metadata: Dict[str, str]):
        """
        Event raised when a user is banned.

        :paramref:`User`:
            the user recieving the action. This isn't a chatter because
            the subject would not be a chatter after the action occurs.

        :paramref:`channel`:
            the channel in which the action occurs

        :paramref:`timestamp`:
            the server timestamp for the action.

        :paramref:`metadata`:
            dictionary for various metadata associated with the message.

        The raw form of these events are::

            [@<key>=<value>[;<key>=<value>]*] :tmi.twitch.tv CLEARCHAT #<channel> :<user>
        """
        pass

    async def event_user_timeout(self, timed_out: User, channel: Channel, timestamp: datetime, duration: int, metadata: Dict[str, str]):
        """
        Event raised when a user is timed out.

        :paramref:`User`:
            the user recieving the action. This isn't a chatter because
            the subject would not be a chatter after the action occurs.

        :paramref:`channel`:
            the channel in which the action occurs

        :paramref:`timestamp`:
            the server timestamp for the action.

        :paramref:`duration`:
            the timeout duration, in seconds

        :paramref:`metadata`:
            dictionary for various metadata associated with the message.

        The raw form of these events are::

            [@<key>=<value>[;<key>=<value>]*] :tmi.twitch.tv CLEARCHAT #<channel> :<user>
        """
        pass

    async def event_clearchat(self, channel: Channel, timestamp: datetime, metadata: Dict[str, Any]):
        """
        Event raised when a chat is cleared entirely by a moderator.

        :paramref:`channel`:
            the channel in which the action occurs

        :paramref:`timestamp`:
            the server timestamp for the action.

        :paramref:`metadata`:
            dictionary for various metadata associated with the message.

        The raw form of these events are::

            [@<key>=<value>[;<key>=<value>]*] :tmi.twitch.tv CLEARCHAT #<channel>
        """
        pass

    async def event_clearmsg(self, user: Chatter, channel: Channel, msg_id: UUID, timestamp: datetime, metadata: Dict[str, Any]):
        """
        Event raised when an individual message is removed by a moderator.

        :paramref:`user`:
            the user whose message is deleted

        :paramref:`channel`:
            the channel in which the action occurs

        :paramref:`msg_id`:
            the identifier for the message being removed

        :paramref:`timestamp`:
            the timestamp when the message occurs

        :paramref:`metadata`:
            dictionary for various metadata associated with the message.

        The raw form of these events are::

            [@<key>=<value>[;<key>=<value>]*] :tmi.twitch.tv CLEARCHAT #<channel> :<message>
        """
        pass
