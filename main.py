#!/usr/bin/python3

from os import getenv
from logging import debug, DEBUG, WARNING, basicConfig as setup_logging

from bot import start_bot
from text import generate_sentence

def __main():
    from argparse import ArgumentParser as ap
    arg = ap(description="")
    arg.add_argument("--channel", "-c", action="append", type=str, required=True)
    arg.add_argument("--verbose", "-v", action='store_const', required=False, default=WARNING, const=DEBUG)
    g1 = arg.add_mutually_exclusive_group(required=True)
    g1.add_argument("--text", "-t", action='store_true')
    g1.add_argument("--bot", "-b", action='store_true')
    bot_grp = arg.add_argument_group('bot options')
    bot_grp.add_argument("--access-token", "-at", action="store", type=str, default=getenv("ASNF_TOKEN"))
    bot_grp.add_argument("--refresh-token", "-rt", action="store",  type=str, default=getenv("ASNF_REFRESH"))
    bot_grp.add_argument("--client-id", "-id", action="store", type=str, default=getenv("ASNF_CLIENT_ID"))
    argv = arg.parse_args()

    setup_logging(level=argv.verbose)
    if argv.text:
        print(f"{generate_sentence(argv.channel)}")
    elif argv.bot:
        start_bot(argv.access_token, argv.channel)

if __name__ == "__main__":
    __main()
