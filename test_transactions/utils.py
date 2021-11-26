import asyncio
import json
from pathlib import Path
from tempfile import gettempdir

import time
from indy import ledger


PROTOCOL_VERSION = 2


def path_home() -> Path:
    return Path.home().joinpath(".indy_client")


def get_pool_genesis_txn_path(pool_name):
    path_temp = Path(gettempdir()).joinpath("indy")
    path = path_temp.joinpath("{}.txn".format(pool_name))
    save_pool_genesis_txn_file(path)
    return path


def pool_genesis_txn_data():
    with open('/indy-sdk/samples/python/src/genesis.txt', 'r') as manifest:
        return  manifest.read(int(1E9))

def save_pool_genesis_txn_file(path):
    data = pool_genesis_txn_data()

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(str(path), "w+") as f:
        f.writelines(data)


def run_coroutine(coroutine, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    loop.run_until_complete(coroutine())


async def ensure_previous_request_applied(pool_handle, checker_request, checker):
    for _ in range(3):
        response = json.loads(await ledger.submit_request(pool_handle, checker_request))
        try:
            if checker(response):
                return json.dumps(response)
        except TypeError:
            pass
        time.sleep(5)
