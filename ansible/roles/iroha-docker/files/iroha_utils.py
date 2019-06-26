#!/usr/env/python3

import sys
import os
import logging
import json
import iroha
import binascii
import traceback
from google.protobuf.json_format import MessageToJson

params = {'iroha_hosts': '', 'iroha_account': '', 'iroha_account_keys': ''}


def send_transaction(transaction):
    hex_hash = binascii.hexlify(iroha.IrohaCrypto.hash(transaction))
    logging.info('Transaction hash: {}, transactionc reator: {}'.format(
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


logging.basicConfig(format='%(asctime)s - %(funcName)s - %(levelname)s - %(message)s', level=logging.INFO)
try:
    for param in params.keys():
        params[param] = os.environ[param.upper()]
    params['iroha_account_keys'] = params['iroha_account_keys'].split(',')
    params['iroha_hosts'] = params['iroha_hosts'].split(',')
except Exception:
    exit_and_result(1, "Error reading environment variables")

if __name__ ==  "__main__":
    try:
        command = sys.argv[1]
    except Exception:
        exit_and_result(1, "Invalid command")
    logging.info("Params: " + params.__str__())
    logging.info("Command: " + sys.argv[1:].__str__())
    try:
        if command == 'get_genesis_block' and len(sys.argv) == 2:
            resp = get_genesis_block()
            if resp:
                exit_and_result(0, resp)
            else:
                exit_and_result(1, "Command failed")
        elif command == 'add_peer' and len(sys.argv) == 4:
            peer_host = sys.argv[2]
            peer_pub_key = sys.argv[3]
            if add_peer(peer_host, peer_pub_key):
                exit_and_result(0)
            else:
                exit_and_result(1, "Command failed")
        else:
            exit_and_result(1, 'Invalid command')
    except Exception as e:
        logging.error(traceback.print_tb(e.__traceback__))
        logging.error(e)
        exit_and_result(1, "Unknown error")
