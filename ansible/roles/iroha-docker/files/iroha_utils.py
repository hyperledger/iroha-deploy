#!/usr/env/python3
# -*- coding: utf-8 -*-

import sys
import os
import logging
import json
import iroha
import binascii
import traceback
import base64
import copy
from google.protobuf.json_format import MessageToJson

from ansible.constants import DEFAULT_VAULT_ID_MATCH
from ansible.parsing.vault import VaultLib
from ansible.parsing.vault import VaultSecret

params = {'iroha_hosts': '', 'iroha_account': '', 'iroha_account_keys': ''}

def init_params():
    try:
        for param in params.keys():
            params[param] = os.environ[param.upper()]
        params['iroha_account_keys'] = params['iroha_account_keys'].split(',')
        params['iroha_hosts'] = params['iroha_hosts'].split(',')
        logging.info("Params: " + params.__str__())
    except Exception:
        exit_and_result(1, "Error reading environment variables")


def send_transaction(transaction):
    hex_hash = binascii.hexlify(iroha.IrohaCrypto.hash(transaction))
    logging.info('Transaction hash: {}, transaction creator: {}'.format(
        hex_hash, transaction.payload.reduced_payload.creator_account_id))
    for iroha_host in params['iroha_hosts']:
        try:
            ir_con = iroha.IrohaGrpc(iroha_host)
            ir_con.send_tx(transaction)
            for status in ir_con.tx_status_stream(transaction):
                logging.info('Status: ' + status.__str__())
                if status[0].find('COMMITTED') != -1:
                    return True
        except Exception as e:
            logging.error('Peer adding error. Peer is {}'.format(iroha_host))
            logging.error(traceback.print_tb(e.__traceback__))
            logging.error(e)
    return False


def send_query(query):
    hex_hash = binascii.hexlify(iroha.IrohaCrypto.hash(query))
    logging.info('Query hash: {}, query creator: {}'.format(
        hex_hash, query.payload.meta.creator_account_id))
    for iroha_host in params['iroha_hosts']:
        try:
            ir_con = iroha.IrohaGrpc(iroha_host)
            return(ir_con.send_query(query))
        except Exception as e:
            logging.error('Query error. Peer is {}'.format(iroha_host))
            logging.error(traceback.print_tb(e.__traceback__))
            logging.error(e)
    return False

def add_peer_tx(peer_host, peer_key):
    ir = iroha.Iroha(params['iroha_account'])
    peer = iroha.primitive_pb2.Peer()
    peer.address = peer_host
    peer.peer_key = peer_key
    tx = ir.transaction([ ir.command('AddPeer', peer=peer) ])
    iroha.IrohaCrypto.sign_transaction(tx, *params['iroha_account_keys'])
    return tx


def get_block(block_num):
    ir = iroha.Iroha(params['iroha_account'])
    query = iroha.IrohaCrypto.sign_query(ir.query('GetBlock', height=block_num), *params['iroha_account_keys'])
    return query


def get_genesis_block():
    query = get_block(1)
    resp = send_query(query)
    if resp:
        return json.loads(MessageToJson(resp.block_response.block))
    else:
        return False


def add_peer(peer_host, peer_pub_key):
    tx = add_peer_tx(peer_host, peer_pub_key)
    return(send_transaction(tx))


def exit_and_result(exit_code, result=''):
    print(json.dumps({'exit_code': exit_code, 'result': result}, indent=2))
    if exit_code != 0:
        logging.error(result)
    sys.exit(exit_code)


def gen_keys(number=1):
    result = []
    for i in range(number):
        priv = iroha.IrohaCrypto.private_key()
        pub = iroha.IrohaCrypto.derive_public_key(priv)
        result.append({'pub': pub.decode('ascii'), 'priv': priv.decode('ascii')})
    return result


def ansible_vault_encrypt(key, text):
    vault = VaultLib([(DEFAULT_VAULT_ID_MATCH, VaultSecret(key.rstrip('\n').encode('utf-8')))])
    return vault.encrypt(text.rstrip('\n').encode('utf-8')).decode('utf-8')


def filter_old_peers(block: dict):
    temp_block = copy.deepcopy(block)
    transactions = temp_block['block_v1']['payload']['transactions']
    for i in range(len(transactions)):
        tx_commands = transactions[i]['payload']['reducedPayload']['commands']
        clean_commands = filter(lambda command_list: 'addPeer' not in command_list.keys(), tx_commands)
        transactions[i]['payload']['reducedPayload']['commands'] = list(clean_commands)
    return temp_block


def add_new_peers(block: dict, new_peers: list):
    temp_block = copy.deepcopy(block)
    initial_tx_commands = temp_block['block_v1']['payload']['transactions'][0]['payload']['reducedPayload']['commands']
    for peer in new_peers:
        initial_tx_commands.append({'addPeer': {'peer': {
            'address': peer['hostname'],
            'peerKey': peer['pub_key']
        }}})
    return temp_block


if ('DEBUG' in os.environ) and os.environ['DEBUG'] == 'TRUE':
    logging_level = logging.INFO
else:
    logging_level = logging.ERROR
logging.basicConfig(format='%(asctime)s - %(funcName)s - %(levelname)s - %(message)s', level=logging_level)

if __name__ == "__main__":
    try:
        command = sys.argv[1]
    except Exception:
        exit_and_result(1, "Invalid command")
    logging.info("Command: " + sys.argv[1:].__str__())
    try:
        if command == 'generate_genesis' and len(sys.argv) == 4:
            try:
                base_block = json.loads(base64.b64decode(sys.argv[2]))
                peer_list = json.loads(base64.b64decode(sys.argv[3]))

                new_block = filter_old_peers(base_block)
                new_block = add_new_peers(new_block, peer_list)

                exit_and_result(0, new_block)
            except KeyError:
                logging.error("Malformed genesis block")
                exit_and_result(1, "Command failed")

            except Exception as e:
                logging.error("Could not load genesis from command " + str(e))
                exit_and_result(1, "Command failed")

        if command == 'get_genesis_block' and len(sys.argv) == 2:
            init_params()
            resp = get_genesis_block()
            if resp:
                exit_and_result(0, resp)
            else:
                exit_and_result(1, "Command failed")
        elif command == 'add_peer' and len(sys.argv) == 4:
            init_params()
            peer_host = sys.argv[2]
            peer_pub_key = sys.argv[3]
            if add_peer(peer_host, peer_pub_key):
                exit_and_result(0)
            else:
                exit_and_result(1, "Command failed")
        elif command == 'gen_keys' and len(sys.argv) in [2,3]:
            if len(sys.argv) == 2:
                exit_and_result(0, gen_keys())
            else:
                exit_and_result(0, gen_keys(int(sys.argv[2])))
        elif command == 'ansible_vault_encrypt' and len(sys.argv) == 4:
            exit_and_result(0, ansible_vault_encrypt(sys.argv[2], sys.argv[3]))
        else:
            exit_and_result(1, 'Invalid command')
    except Exception as e:
        logging.error(traceback.print_tb(e.__traceback__))
        logging.error(e)
        exit_and_result(1, "Unknown error")
