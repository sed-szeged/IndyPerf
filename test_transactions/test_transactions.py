"""
Example demonstrating how to do the key rotation on the ledger.
Steward already exists on the ledger and its DID/Verkey are obtained using seed.
Trust Anchor's DID/Verkey pair is generated and stored into wallet.
Stewards builds NYM request in order to add Trust Anchor to the ledger.
Once NYM transaction is done, Trust Anchor wants to change its Verkey.
First, temporary key is created in the wallet.
Second, Trust Anchor builds NYM request to replace the Verkey on the ledger.
Third, when NYM transaction succeeds, Trust Anchor makes new Verkey permanent in wallet
(it was only temporary before).
To assert the changes, Trust Anchor reads both the Verkey from the wallet and the Verkey from the ledger
using GET_NYM request, to make sure they are equal to the new Verkey, not the original one
added by Steward
"""

import asyncio
import json
import time


from indy import pool, ledger, wallet, did
from indy.error import IndyError, ErrorCode
from src.utils import get_pool_genesis_txn_path, PROTOCOL_VERSION

pool_name = 'prifob'
genesis_file_path = get_pool_genesis_txn_path(pool_name)

wallet_config = json.dumps({"id": "wallet"})
wallet_credentials = json.dumps({"key": "wallet_key"})


def print_log(value_color="", value_noncolor=""):
    """set the colors for text."""
    HEADER = '\033[92m'
    ENDC = '\033[0m'
    print(HEADER + value_color + ENDC + str(value_noncolor))


async def write_nym_and_query_verkey(thread, iter, wallet_handle, pool_handle):
    print_log('\nTest started\n')

    try:
        steward_seed = '000000000000000000000000Steward1'
        did_json = json.dumps({'seed': steward_seed})
        steward_did, steward_verkey = await did.create_and_store_my_did(wallet_handle, did_json)

        w_result = {
            'max': 0,
            'min': 1000,
            'avg': 0,
        }
        r_result = {
            'max': 0,
            'min': 1000,
            'avg': 0,
        }
        for i in range(0, 10):
            measurement = str(i) + ","
            trust_anchor_did, trust_anchor_verkey = await did.create_and_store_my_did(wallet_handle, "{}")
            nym_transaction_request = await ledger.build_nym_request(submitter_did=steward_did,
                                                                     target_did=trust_anchor_did,
                                                                     ver_key=trust_anchor_verkey,
                                                                     alias=None,
                                                                     role='TRUST_ANCHOR')

            start = time.time()
            await ledger.sign_and_submit_request(pool_handle=pool_handle,
                                                    wallet_handle=wallet_handle,
                                                    submitter_did=steward_did,
                                                    request_json=nym_transaction_request)
            end = time.time()
            result = end - start
            w_result['avg'] += result
            w_result['max'] = max(result, w_result['max'])
            w_result['min'] = min(result, w_result['min'])

            client_did, client_verkey = await did.create_and_store_my_did(wallet_handle, "{}")
            get_nym_request = await ledger.build_get_nym_request(submitter_did=client_did,
                                                                 target_did=steward_did)

            start = time.time()
            await ledger.submit_request(pool_handle=pool_handle, request_json=get_nym_request)
            end = time.time()
            result = end - start
            r_result['avg'] += result
            r_result['max'] = max(result, r_result['max'])
            r_result['min'] = min(result, r_result['min'])

            print_log(measurement)

        r_result['avg'] = r_result['avg'] / 10.0
        w_result['avg'] = w_result['avg'] / 10.0

        with open(thread + "_" + str(iter) + "_result.txt", "w") as r:
            r.write(json.dumps([w_result, r_result]))

    except IndyError as e:
        print('Error occurred: %s' % e)


async def main():
    await pool.set_protocol_version(PROTOCOL_VERSION)

    # 1.
    pool_config = json.dumps({'genesis_txn': str(genesis_file_path)})
    try:
        await pool.create_pool_ledger_config(config_name=pool_name, config=pool_config)
    except IndyError as ex:
        if ex.error_code == ErrorCode.PoolLedgerConfigAlreadyExistsError:
            pass

    # 2.
    pool_handle = await pool.open_pool_ledger(config_name=pool_name, config=None)

    # 3.
    try:
        await wallet.create_wallet(wallet_config, wallet_credentials)
    except IndyError as ex:
        if ex.error_code == ErrorCode.WalletAlreadyExistsError:
            pass

    # 4.
    wallet_handle = await wallet.open_wallet(wallet_config, wallet_credentials)

    tasks = list()
    for i in range(1):
        tasks.append(write_nym_and_query_verkey("1", i, wallet_handle, pool_handle))
    await asyncio.gather(*tasks)

    tasks = list()
    for i in range(50):
        tasks.append(write_nym_and_query_verkey("50", i, wallet_handle, pool_handle))
    await asyncio.gather(*tasks)

    tasks = list()
    for i in range(100):
        tasks.append(write_nym_and_query_verkey("100", i, wallet_handle, pool_handle))
    await asyncio.gather(*tasks)

    tasks = list()
    for i in range(150):
        tasks.append(write_nym_and_query_verkey("150", i, wallet_handle, pool_handle))
    await asyncio.gather(*tasks)

    tasks = list()
    for i in range(200):
        tasks.append(write_nym_and_query_verkey("200", i, wallet_handle, pool_handle))
    await asyncio.gather(*tasks)

    tasks = list()
    for i in range(250):
        tasks.append(write_nym_and_query_verkey("250", i, wallet_handle, pool_handle))
    await asyncio.gather(*tasks)

    await wallet.close_wallet(wallet_handle)
    await pool.close_pool_ledger(pool_handle)
    await wallet.delete_wallet(wallet_config, wallet_credentials)
    await pool.delete_pool_ledger_config(pool_name)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()

