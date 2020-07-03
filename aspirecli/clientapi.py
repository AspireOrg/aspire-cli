import sys
import logging
from urllib.parse import quote_plus as urlencode

from aspirelib.lib import config, script
from aspirecli import util
from aspirecli import wallet
from aspirecli import messages
from aspirecli.messages import get_pubkeys

logger = logging.getLogger()

DEFAULT_REQUESTS_TIMEOUT = 5  # seconds


class ConfigurationError(Exception):
    pass


def initialize(testnet=False,
               aspire_rpc_connect=None, aspire_rpc_port=None,
               aspire_rpc_user=None, aspire_rpc_password=None,
               aspire_rpc_ssl=False, aspire_rpc_ssl_verify=False,
               wallet_name=None, wallet_connect=None, wallet_port=None,
               wallet_user=None, wallet_password=None,
               wallet_ssl=False, wallet_ssl_verify=False,
               requests_timeout=DEFAULT_REQUESTS_TIMEOUT):

    def handle_exception(exc_type, exc_value, exc_traceback):
        logger.error("Unhandled Exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = handle_exception

    # testnet
    config.TESTNET = testnet or False

    ##############
    # THINGS WE CONNECT TO

    # Server host (AspireGas Core)
    config.ASPIRE_RPC_CONNECT = aspire_rpc_connect or 'localhost'

    # Server RPC port (AspireGas Core)
    if aspire_rpc_port:
        config.ASPIRE_RPC_PORT = aspire_rpc_port
    else:
        if config.TESTNET:
            config.ASPIRE_RPC_PORT = config.DEFAULT_RPC_PORT_TESTNET
        else:
            config.ASPIRE_RPC_PORT = config.DEFAULT_RPC_PORT
    try:
        config.ASPIRE_RPC_PORT = int(config.ASPIRE_RPC_PORT)
        if not (int(config.ASPIRE_RPC_PORT) > 1 and int(config.ASPIRE_RPC_PORT) < 65535):
            raise ConfigurationError('invalid RPC port number')
    except:
        raise Exception("Please specific a valid port number aspire-rpc-port configuration parameter")

    # Server RPC user (AspireGas Core)
    config.ASPIRE_RPC_USER = aspire_rpc_user or 'rpc'

    # Server RPC password (AspireGas Core)
    if aspire_rpc_password:
        config.ASPIRE_RPC_PASSWORD = aspire_rpc_password
    else:
        config.ASPIRE_RPC_PASSWORD = None

    # Server RPC SSL
    config.ASPIRE_RPC_SSL = aspire_rpc_ssl or False  # Default to off.

    # Server RPC SSL Verify
    config.ASPIRE_RPC_SSL_VERIFY = aspire_rpc_ssl_verify or False  # Default to off (support self‐signed certificates)

    # Construct server URL.
    config.ASPIRE_RPC = config.ASPIRE_RPC_CONNECT + ':' + str(config.ASPIRE_RPC_PORT)
    if config.ASPIRE_RPC_PASSWORD:
        config.ASPIRE_RPC = urlencode(config.ASPIRE_RPC_USER) + ':' + urlencode(config.ASPIRE_RPC_PASSWORD) + '@' + config.ASPIRE_RPC
    if config.ASPIRE_RPC_SSL:
        config.ASPIRE_RPC = 'https://' + config.ASPIRE_RPC
    else:
        config.ASPIRE_RPC = 'http://' + config.ASPIRE_RPC
    config.ASPIRE_RPC += '/rpc/'

    # GASP Wallet name
    config.WALLET_NAME = wallet_name or 'bitcoincore'

    # GASP Wallet host
    config.WALLET_CONNECT = wallet_connect or 'localhost'

    # GASP Wallet port
    if wallet_port:
        config.WALLET_PORT = wallet_port
    else:
        if config.TESTNET:
            config.WALLET_PORT = config.DEFAULT_BACKEND_PORT_TESTNET
        else:
            config.WALLET_PORT = config.DEFAULT_BACKEND_PORT
    try:
        config.WALLET_PORT = int(config.WALLET_PORT)
        if not (int(config.WALLET_PORT) > 1 and int(config.WALLET_PORT) < 65535):
            raise ConfigurationError('invalid wallet API port number')
    except:
        raise ConfigurationError("Please specific a valid port number wallet-port configuration parameter")

    # GASP Wallet user
    config.WALLET_USER = wallet_user or 'gasprpc'

    # GASP Wallet password
    if wallet_password:
        config.WALLET_PASSWORD = wallet_password
    else:
        raise ConfigurationError('wallet RPC password not set. (Use configuration file or --wallet-password=PASSWORD)')

    # GASP Wallet SSL
    config.WALLET_SSL = wallet_ssl or False  # Default to off.

    # GASP Wallet SSL Verify
    config.WALLET_SSL_VERIFY = wallet_ssl_verify or False # Default to off (support self‐signed certificates)

    # Construct GASP wallet URL.
    config.WALLET_URL = urlencode(config.WALLET_USER) + ':' + urlencode(config.WALLET_PASSWORD) + '@' + config.WALLET_CONNECT + ':' + str(config.WALLET_PORT)
    if config.WALLET_SSL:
        config.WALLET_URL = 'https://' + config.WALLET_URL
    else:
        config.WALLET_URL = 'http://' + config.WALLET_URL

    config.REQUESTS_TIMEOUT = requests_timeout

    # Encoding
    config.PREFIX = b'ASPR'             # 4 bytes

    # (more) Testnet
    if config.TESTNET:
        config.MAGIC_BYTES = config.MAGIC_BYTES_TESTNET
        config.ADDRESSVERSION = config.ADDRESSVERSION_TESTNET
        config.P2SH_ADDRESSVERSION = config.P2SH_ADDRESSVERSION_TESTNET
        config.BLOCK_FIRST = config.BLOCK_FIRST_TESTNET
        config.UNSPENDABLE = config.UNSPENDABLE_TESTNET
    else:
        config.MAGIC_BYTES = config.MAGIC_BYTES_MAINNET
        config.ADDRESSVERSION = config.ADDRESSVERSION_MAINNET
        config.P2SH_ADDRESSVERSION = config.P2SH_ADDRESSVERSION_MAINNET
        config.BLOCK_FIRST = config.BLOCK_FIRST_MAINNET
        config.UNSPENDABLE = config.UNSPENDABLE_MAINNET


WALLET_METHODS = [
    'get_wallet_addresses', 'get_gasp_balances', 'sign_raw_transaction',
    'get_pubkey', 'is_valid', 'is_mine', 'get_gasp_balance', 'send_raw_transaction',
    'wallet', 'asset', 'balances', 'is_locked', 'unlock', 'wallet_last_block'
]


def call(method, args, pubkey_resolver=None):
    """
        Unified function to call Wallet and Server API methods
        Should be used by applications like `aspire-gui`

        :Example:

        import aspirecli.clientapi
        clientapi.initialize(...)
        unsigned_hex = clientapi.call('create_send', {...})
        signed_hex =  clientapi.call('sign_raw_transaction', unsigned_hex)
        tx_hash = clientapi.call('send_raw_transaction', signed_hex)
    """
    if method in WALLET_METHODS:
        func = getattr(wallet, method)
        return func(**args)
    else:
        if method.startswith('create_'):
            # Get provided pubkeys from params.
            pubkeys = []
            for address_name in ['source', 'destination']:
                if address_name in args:
                    address = args[address_name]
                    if script.is_multisig(address) or address_name != 'destination':    # We don’t need the pubkey for a mono‐sig destination.
                        pubkeys += get_pubkeys(address, pubkey_resolver=pubkey_resolver)
            args['pubkey'] = pubkeys

        result = util.api(method, args)

        if method.startswith('create_'):
            messages.check_transaction(method, args, result)

        return result


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
