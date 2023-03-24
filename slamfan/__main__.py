#!/usr/bin/python3
from argparse import ArgumentParser, Namespace
from enum import Enum
import asyncio


def __add_bot_args(parser: ArgumentParser) -> ArgumentParser:
    from os import getenv
    parser.add_argument("--channel", "-c",
                        dest="channels",
                        action="append", type=str,
                        required=True,
                        help="channels to watch")

    parser.add_argument("--robo-access-token", "-rat",
                        action="store", type=str, dest='robo_token',
                        required=getenv("ROBO_TOKEN") is None, 
                        default=getenv("ROBO_TOKEN"),
                        help='twitch access token for the obvious robot account')

    parser.add_argument("--turing-access-token", "-tat",
                        action="store", type=str, dest='turing_token',
                        required=getenv("ANSF_TOKEN") is None, 
                        default=getenv("ANSF_TOKEN"),
                        help='twitch access token for the nonobvious robot account')

    parser.add_argument("--database", "-db",
                        action="store", type=str, dest='database',
                        required=getenv("DATABASE") is None,
                        default=getenv("DATABASE"),
                        help='database to operate using')

    parser.add_argument("--super-user", "-su",
                        action="store", type=str, dest='superuser',
                        required=getenv("SUPER_USER") is None,
                        default=getenv("SUPER_USER"),
                        help='the super user account for the bots')

    return parser

async def __bot_main(argv: Namespace):
    from brokers import DatabaseBroker
    from twitch import Admin, Turing
    from twitch import TwitchBot
    try:
        async with asyncio.TaskGroup() as tg: #, DashboardBroker() as dash:
            su = argv.superuser.lower()
            dbm = DatabaseBroker(tg, argv.database)
            await dbm.connect()

            while True:
                am = Admin(su)

                # Turing Bot
                ansf: TwitchBot = TwitchBot(argv.turing_token, '$', [su] + argv.channels)
                ansf.add_cog(am)
                ansf.add_cog(Turing(su, dbm, tg))

                async with ansf:
                    await am.die_event.wait()

                    if am.restart_event.is_set():
                        continue

                    return

    except asyncio.CancelledError:
        print("cancelled")

def __main():
    from argparse import ArgumentParser as ap
    arg = ap(description="")
    __add_bot_args(arg)
    argv = arg.parse_args()

    print("crtl+c to exit")
    asyncio.run(__bot_main(argv))

if __name__ == "__main__":
    __main()