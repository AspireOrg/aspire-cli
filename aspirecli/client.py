#! /usr/bin/env python3

import os
import sys
import argparse
import logging
import getpass
from decimal import Decimal as D

from aspirelib.lib import log
logger = logging.getLogger(__name__)

from aspirelib.lib import config, script
from aspirelib.lib.util import make_id
from aspirelib.lib.log import isodt
from aspirelib.lib.exceptions import TransactionError
from aspirecli.util import add_config_arguments
from aspirecli.setup import generate_config_files
from aspirecli import APP_VERSION, util, messages, wallet, console, clientapi

APP_NAME = 'aspire-client'

CONFIG_ARGS = [
    [('-v', '--verbose'), {'dest': 'verbose', 'action': 'store_true', 'help': 'sets log level to DEBUG instead of WARNING'}],
    [('--testnet',), {'action': 'store_true', 'default': False, 'help': 'use {} testnet addresses and block numbers'.format(config.BTC_NAME)}],

    [('--aspire-rpc-connect',), {'default': 'localhost', 'help': 'the hostname or IP of the Aspire JSON-RPC server'}],
    [('--aspire-rpc-port',), {'type': int, 'help': 'the port of the Aspire JSON-RPC server'}],
    [('--aspire-rpc-user',), {'default': 'rpc', 'help': 'the username for the Aspire JSON-RPC server'}],
    [('--aspire-rpc-password',), {'help': 'the password for the Aspire JSON-RPC server'}],
    [('--aspire-rpc-ssl',), {'default': False, 'action': 'store_true', 'help': 'use SSL to connect to the Aspire server (default: false)'}],
    [('--aspire-rpc-ssl-verify',), {'default': False, 'action': 'store_true', 'help': 'verify SSL certificate of the Aspire server; disallow use of self‐signed certificates (default: false)'}],

    [('--wallet-name',), {'default': 'bitcoincore', 'help': 'the wallet name to connect to'}],
    [('--wallet-connect',), {'default': 'localhost', 'help': 'the hostname or IP of the wallet server'}],
    [('--wallet-port',), {'type': int, 'help': 'the wallet port to connect to'}],
    [('--wallet-user',), {'default': 'gasprpc', 'help': 'the username used to communicate with wallet'}],
    [('--wallet-password',), {'help': 'the password used to communicate with wallet'}],
    [('--wallet-ssl',), {'action': 'store_true', 'default': False, 'help': 'use SSL to connect to wallet (default: false)'}],
    [('--wallet-ssl-verify',), {'action': 'store_true', 'default': False, 'help': 'verify SSL certificate of wallet; disallow use of self‐signed certificates (default: false)'}],

    [('--json-output',), {'action': 'store_true', 'default': False, 'help': 'display result in json format'}],
    [('--unconfirmed',), {'action': 'store_true', 'default': False, 'help': 'allow the spending of unconfirmed transaction outputs'}],
    [('--encoding',), {'default': 'auto', 'type': str, 'help': 'data encoding method'}],
    [('--fee-per-kb',), {'type': D, 'default': D(config.DEFAULT_FEE_PER_KB / config.UNIT), 'help': 'fee per kilobyte, in {}'.format(config.BTC)}],
    [('--regular-dust-size',), {'type': D, 'default': D(config.DEFAULT_REGULAR_DUST_SIZE / config.UNIT), 'help': 'value for dust Pay‐to‐Pubkey‐Hash outputs, in {}'.format(config.BTC)}],
    [('--multisig-dust-size',), {'type': D, 'default': D(config.DEFAULT_MULTISIG_DUST_SIZE / config.UNIT), 'help': 'for dust OP_CHECKMULTISIG outputs, in {}'.format(config.BTC)}],
    [('--op-return-value',), {'type': D, 'default': D(config.DEFAULT_OP_RETURN_VALUE / config.UNIT), 'help': 'value for OP_RETURN outputs, in {}'.format(config.BTC)}],
    [('--unsigned',), {'action': 'store_true', 'default': False, 'help': 'print out unsigned hex of transaction; do not sign or broadcast'}],
    [('--disable-utxo-locks',), {'action': 'store_true', 'default': False, 'help': 'disable locking of UTXOs being spend'}],
    [('--dust-return-pubkey',), {'help': 'pubkey for dust outputs (required for P2SH)'}],
    [('--requests-timeout',), {'type': int, 'default': clientapi.DEFAULT_REQUESTS_TIMEOUT, 'help': 'timeout value (in seconds) used for all HTTP requests (default: 5)'}]
]

def main():
    if os.name == 'nt':
        from aspirelib.lib import util_windows
        #patch up cmd.exe's "challenged" (i.e. broken/non-existent) UTF-8 logging
        util_windows.fix_win32_unicode()

    # Post installation tasks
    generate_config_files()

    # Parse command-line arguments.
    parser = argparse.ArgumentParser(prog=APP_NAME, description='Aspire CLI for aspire-server', add_help=False)
    parser.add_argument('-h', '--help', dest='help', action='store_true', help='show this help message and exit')
    parser.add_argument('-V', '--version', action='version', version="{} v{}; {} v{}".format(APP_NAME, APP_VERSION, 'aspire-lib', config.VERSION_STRING))
    parser.add_argument('--config-file', help='the location of the configuration file')

    add_config_arguments(parser, CONFIG_ARGS, 'client.conf')

    subparsers = parser.add_subparsers(dest='action', help='the action to be taken')

    parser_send = subparsers.add_parser('send', help='create and broadcast a *send* message')
    parser_send.add_argument('--source', required=True, help='the source address')
    parser_send.add_argument('--destination', required=True, help='the destination address')
    parser_send.add_argument('--quantity', required=True, help='the quantity of ASSET to send')
    parser_send.add_argument('--asset', required=True, help='the ASSET of which you would like to send QUANTITY')
    parser_send.add_argument('--memo', help='A transaction memo attached to this send')
    parser_send.add_argument('--memo-is-hex', action='store_true', default=False, help='Whether to interpret memo as a hexadecimal value')
    parser_send.add_argument('--no-use-enhanced-send', action='store_false', dest="use_enhanced_send", default=True, help='If set to false, compose a non-enhanced send with an gasp dust output')
    parser_send.add_argument('--fee', help='the exact {} fee to be paid to miners'.format(config.BTC))

    parser_issuance = subparsers.add_parser('issuance', help='issue a new asset, issue more of an existing asset or transfer the ownership of an asset')
    parser_issuance.add_argument('--source', required=True, help='the source address')
    parser_issuance.add_argument('--transfer-destination', help='for transfer of ownership of asset issuance rights')
    parser_issuance.add_argument('--quantity', default=0, help='the quantity of ASSET to be issued')
    parser_issuance.add_argument('--asset', required=True, help='the name of the asset to be issued (if it’s available)')
    parser_issuance.add_argument('--divisible', action='store_true', help='whether or not the asset is divisible (must agree with previous issuances)')
    parser_issuance.add_argument('--description', type=str, required=True, help='a description of the asset (set to ‘LOCK’ to lock against further issuances with non‐zero quantitys)')
    parser_issuance.add_argument('--fee', help='the exact {} fee to be paid to miners'.format(config.BTC))

    parser_broadcast = subparsers.add_parser('broadcast', help='broadcast textual and numerical information to the network')
    parser_broadcast.add_argument('--source', required=True, help='the source address')
    parser_broadcast.add_argument('--text', type=str, required=True, help='the textual part of the broadcast (set to ‘LOCK’ to lock feed)')
    parser_broadcast.add_argument('--value', type=float, default=-1, help='numerical value of the broadcast')
    parser_broadcast.add_argument('--fee', help='the exact {} fee to be paid to miners'.format(config.BTC))

    parser_dividend = subparsers.add_parser('dividend', help='pay dividends to the holders of an asset (in proportion to their stake in it)')
    parser_dividend.add_argument('--source', required=True, help='the source address')
    parser_dividend.add_argument('--quantity-per-unit', required=True, help='the quantity of {} to be paid per whole unit held of ASSET'.format(config.XCP))
    parser_dividend.add_argument('--asset', required=True, help='the asset to which pay dividends')
    parser_dividend.add_argument('--dividend-asset', required=True, help='asset in which to pay the dividends')
    parser_dividend.add_argument('--fee', help='the exact {} fee to be paid to miners'.format(config.BTC))

    parser_publish = subparsers.add_parser('publish', help='publish contract code in the blockchain')
    parser_publish.add_argument('--source', required=True, help='the source address')
    parser_publish.add_argument('--gasprice', required=True, type=int, help='the price of gas')
    parser_publish.add_argument('--startgas', required=True, type=int, help='the maximum quantity of {} to be used to pay for the execution (satoshis)'.format(config.XCP))
    parser_publish.add_argument('--endowment', required=True, type=int, help='quantity of {} to be transfered to the contract (satoshis)'.format(config.XCP))
    parser_publish.add_argument('--code-hex', required=True, type=str, help='the hex‐encoded contract (returned by `serpent compile`)')
    parser_publish.add_argument('--fee', help='the exact {} fee to be paid to miners'.format(config.BTC))

    parser_execute = subparsers.add_parser('execute', help='execute contract code in the blockchain')
    parser_execute.add_argument('--source', required=True, help='the source address')
    parser_execute.add_argument('--contract-id', required=True, help='the contract ID of the contract to be executed')
    parser_execute.add_argument('--gasprice', required=True, type=int, help='the price of gas')
    parser_execute.add_argument('--startgas', required=True, type=int, help='the maximum quantity of {} to be used to pay for the execution (satoshis)'.format(config.XCP))
    parser_execute.add_argument('--value', required=True, type=int, help='quantity of {} to be transfered to the contract (satoshis)'.format(config.XCP))
    parser_execute.add_argument('--payload-hex', required=True, type=str, help='data to be provided to the contract (returned by `serpent encode_datalist`)')
    parser_execute.add_argument('--fee', help='the exact {} fee to be paid to miners'.format(config.BTC))

    parser_destroy = subparsers.add_parser('destroy', help='destroy a quantity of an Aspire asset')
    parser_destroy.add_argument('--source', required=True, help='the source address')
    parser_destroy.add_argument('--asset', required=True, help='the ASSET of which you would like to destroy QUANTITY')
    parser_destroy.add_argument('--quantity', required=True, help='the quantity of ASSET to destroy')
    parser_destroy.add_argument('--tag', default='', help='tag')
    parser_destroy.add_argument('--fee', help='the exact {} fee to be paid to miners'.format(config.BTC))

    parser_address = subparsers.add_parser('balances', help='display the balances of a {} address'.format(config.XCP_NAME))
    parser_address.add_argument('address', help='the address you are interested in')

    parser_asset = subparsers.add_parser('asset', help='display the basic properties of a {} asset'.format(config.XCP_NAME))
    parser_asset.add_argument('asset', help='the asset you are interested in')

    parser_wallet = subparsers.add_parser('wallet', help='list the addresses in your backend wallet along with their balances in all {} assets'.format(config.XCP_NAME))

    parser_getrows = subparsers.add_parser('getrows', help='get rows from an Aspire table')
    parser_getrows.add_argument('--table', required=True, help='table name')
    parser_getrows.add_argument('--filter', nargs=3, action='append', help='filters to get specific rows')
    parser_getrows.add_argument('--filter-op', choices=['AND', 'OR'], help='operator uses to combine filters', default='AND')
    parser_getrows.add_argument('--order-by', help='field used to order results')
    parser_getrows.add_argument('--order-dir', choices=['ASC', 'DESC'], help='direction used to order results')
    parser_getrows.add_argument('--start-block', help='return only rows with block_index greater than start-block')
    parser_getrows.add_argument('--end-block', help='return only rows with block_index lower than end-block')
    parser_getrows.add_argument('--status', help='return only rows with the specified status')
    parser_getrows.add_argument('--limit', help='number of rows to return', default=100)
    parser_getrows.add_argument('--offset', help='number of rows to skip', default=0)

    parser_getrunninginfo = subparsers.add_parser('getinfo', help='get the current state of the server')

    parser_get_tx_info = subparsers.add_parser('get_tx_info', help='display info of a raw TX')
    parser_get_tx_info.add_argument('tx_hex', help='the raw TX')

    args = parser.parse_args()

    # Logging
    log.set_up(logger, verbose=args.verbose)
    logger.propagate = False

    logger.info('Running v{} of {}.'.format(APP_VERSION, APP_NAME))

    # Help message
    if args.help:
        parser.print_help()
        sys.exit()

    # Configuration
    clientapi.initialize(testnet=args.testnet,
                        aspire_rpc_connect=args.aspire_rpc_connect, aspire_rpc_port=args.aspire_rpc_port,
                        aspire_rpc_user=args.aspire_rpc_user, aspire_rpc_password=args.aspire_rpc_password,
                        aspire_rpc_ssl=args.aspire_rpc_ssl, aspire_rpc_ssl_verify=args.aspire_rpc_ssl_verify,
                        wallet_name=args.wallet_name, wallet_connect=args.wallet_connect, wallet_port=args.wallet_port,
                        wallet_user=args.wallet_user, wallet_password=args.wallet_password,
                        wallet_ssl=args.wallet_ssl, wallet_ssl_verify=args.wallet_ssl_verify,
                        requests_timeout=args.requests_timeout)

    # MESSAGE CREATION
    if args.action in list(messages.MESSAGE_PARAMS.keys()):
        unsigned_hex = messages.compose(args.action, args)
        logger.info('Transaction (unsigned): {}'.format(unsigned_hex))
        if not args.unsigned:
            if script.is_multisig(args.source):
                logger.info('Multi‐signature transactions are signed and broadcasted manually.')

            elif input('Sign and broadcast? (y/N) ') == 'y':

                if wallet.is_mine(args.source):
                    if wallet.is_locked():
                        passphrase = getpass.getpass('Enter your wallet passhrase: ')
                        logger.info('Unlocking wallet for 60 (more) seconds.')
                        wallet.unlock(passphrase)
                    signed_tx_hex = wallet.sign_raw_transaction(unsigned_hex)
                else:
                    private_key_wif = input('Source address not in wallet. Please enter the private key in WIF format for {}:'.format(args.source))
                    if not private_key_wif:
                        raise TransactionError('invalid private key')
                    signed_tx_hex = wallet.sign_raw_transaction(unsigned_hex, private_key_wif=private_key_wif)

                logger.info('Transaction (signed): {}'.format(signed_tx_hex))
                tx_hash = wallet.send_raw_transaction(signed_tx_hex)
                logger.info('Hash of transaction (broadcasted): {}'.format(tx_hash))


    # VIEWING
    elif args.action in ['balances', 'asset', 'wallet', 'getinfo', 'getrows', 'get_tx_info']:
        view = console.get_view(args.action, args)
        print_method = getattr(console, 'print_{}'.format(args.action), None)
        if args.json_output or print_method is None:
            util.json_print(view)
        else:
            print_method(view)

    else:
        parser.print_help()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
