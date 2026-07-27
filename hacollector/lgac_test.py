import asyncio
import sys

from classes.lgac485 import LGACPacket, LGACPacketHandler
from classes.aircon import Aircon
from classes.appconf import MainConfig
from classes.utils import setup_logging
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda: None


def synchronize_async_helper(to_await):
    return asyncio.run(to_await)


def main(argv):
    import argparse
    parser = argparse.ArgumentParser(description="how to use in command line cls_lgac485.py")

    parser.add_argument("--group", "-g", help="group", required=True)
    parser.add_argument("--id", "-i", help="id", required=True)
    parser.add_argument("--action", "-a", help="action", required=True)
    parser.add_argument("--operation", "-o", help="operation", required=True)
    parser.add_argument("--fanmove", "-m", help="fan move", required=True)
    parser.add_argument("--fanmode", "-s", help="fan mode", required=True)
    parser.add_argument("--temp", "-t", help="Temperature", required=True)
    parser.add_argument('--checkchunk', '-c', help="Check One Chunk")

    args = parser.parse_args()

    import logging
    setup_logging()
    logger = logging.getLogger("CONSOLE")
    app_config = MainConfig()
    load_dotenv()
    app_config.load_env_values()

    if args.checkchunk is not None:

        chunk = LGACPacket()
        instr: str = str(args.checkchunk)
        logger.info(f'input = {instr}')

        chunk.set_packet_data(bytes.fromhex(instr))
        logger.info(f'Result = {chunk}')

        return

    handler = LGACPacketHandler(app_config)
    aircon_cmd = Aircon.Info(args.action, args.operation, args.fanmove, args.fanmode, 25, int(args.temp))
    info: Aircon.Info = synchronize_async_helper(handler.async_send_and_get_result(0, int(args.id), aircon_cmd))

    if info is not None:
        logger.info(
            f'action={info.action}, opmode={info.opmode}, fanmove={info.fanmove}, fanmode={info.fanmode}, '
            f'cur_temp={info.cur_temp}, target_temp={info.target_temp}'
        )
    else:
        logger.error("Error Return.")

    return


if __name__ == '__main__':
    main(sys.argv)
