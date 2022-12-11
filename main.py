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
    g1.add_argument("--convert", action="store_true")
    bot_grp = arg.add_argument_group('bot options')
    bot_grp.add_argument("--approot", "-ar", action="store", type=str, default="./")
    bot_grp.add_argument("--dataroot", "-dr", action="store", type=str, default="./")
    bot_grp.add_argument("--access-token", "-at", action="store", type=str, default=getenv("ASNF_TOKEN"))
    bot_grp.add_argument("--refresh-token", "-rt", action="store",  type=str, default=getenv("ASNF_REFRESH"))
    bot_grp.add_argument("--client-id", "-id", action="store", type=str, default=getenv("ASNF_CLIENT_ID"))
    bot_grp.add_argument("--super-user", "-su", action="store", type=str, default=getenv("SUPER_USER"))
    argv = arg.parse_args()

    setup_logging(level=argv.verbose)
    if argv.text:
        print(f"{generate_sentence({ ch: 1.0 for ch in argv.channel })}")
    elif argv.bot:
        start_bot(argv.approot, argv.dataroot, argv.access_token, argv.channel, argv.super_user)
    elif argv.convert:
        from csv import writer
        for ch in argv.channel:
            with open(f"{ch}.data.log", 'r') as old:
                with open(f"{ch}.data.csv", 'w+') as new:
                    csv = writer(new)
                    xx = []
                    for x in old.readlines():
                        ch, uid, mid, msg = x.strip().split(',', 3)
                        from datetime import datetime, timezone
                        csv.writerow([ch, uid, mid, datetime(1970,1,1).replace(tzinfo=timezone.utc).isoformat(), msg])

if __name__ == "__main__":
    __main()
