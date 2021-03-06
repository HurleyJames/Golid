# {
#     "index": 0,
#     "timestamp": "",
#     "transactions": [
#         {
#             "sender": "",
#             "receipient": "",
#             "amount": 5,
#         }
#     ],
#     "proof": "",
#     "previous_hash": "",
# }
import hashlib
import json
import parser
from time import time, sleep
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request
from argparse import ArgumentParser

class Blockchain:

    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        # 创世纪的区块
        self.new_blcok(proof=100, previous_hash=1)

    def register_node(self, address):
        """
        注册节点，存储网络地址
        :param address: http://127.0.0.1:5001
        """
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain) -> bool:
        """
        判断链条是否是有效的链条
        :param chain:
        """
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            # 第0块是创世界块，它的哈希值是不用计算的
            block = chain[current_index]

            # 如果之间块的哈希望与计算出的哈希值不相等，则说明是一个虚假的链
            if block['previous_hash'] != self.hash(last_block):
                return False
            # 如果不满足工作量证明（上一个块的工作量证明和现在的块的工作量证明）
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolove_conflicts(self) -> bool:
        neighbours = self.nodes

        max_length = len(self.chain)
        new_chain = None

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # 判断链条是有效的，即验证每一块的哈希值是否匹配
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True
        return False

    def new_blcok(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.last_block)
        }

        # 交易已经打包成区块了，当前的交易已经没有了
        self.current_transactions = []
        # 将区块加入到链条中
        self.chain.append(block)

        return block

    def new_transactions(self, sender, recipient, amount) -> int:
        """
        新添加了一个交易
        :param sender: 发送者
        :param recipient: 接收者
        :param amount: 金额
        :return:
        """
        self.current_transactions.append(
            {
                "sender": sender,
                "recipient": recipient,
                "amount": amount
            }
        )

        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof: int) -> int:
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        print(proof)
        return proof

    def valid_proof(self, last_proof: int, proof: int) -> bool:
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        # sleep(1)
        print(guess_hash)
        if guess_hash[0:4] == '0000':
            return True
        else:
            return False


# 验证工作量证明
# testPow = Blockchain()
# testPow.proof_of_work(100)

app = Flask(__name__)
blockchain = Blockchain()

node_identifier = str(uuid4()).replace('-', '')


# @app.route('/index', methods=['GET'])
# def index():
#     return "Hello BlockChain"


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ["sender", "recipient", "amount"]
    if values is None:
        return "Missing values", 400
    if not all(key in values for key in required):
        return "Missing values", 400

    index = blockchain.new_transactions(values['sender'],
                                values['recipient'],
                                values['amount'])

    response = {"message": f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transactions(sender="0",
                                recipient=node_identifier,
                                amount=1)

    block = blockchain.new_blcok(proof, None)

    response = {
        "message": "New Block Forged",
        "index": block['index'],
        "transactions": block['transactions'],
        "proof": block['proof'],
        "previous_hash": block['previous_hash']
    }

    return jsonify(response), 200


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }

    return jsonify(response), 200


# {
#     "nodes": ["http://127.0.0.2:5000"]
# }
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get("nodes")

    if nodes is None:
        return "Error: please supply a valid list of nodes", 400
    for node in nodes:
        blockchain.register_node(node)

    response = {
        "message": "New nodes have been added",
        "total_nodes": list(blockchain.nodes)
    }

    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    is_replace = blockchain.resolove_conflicts()

    if is_replace:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'new_chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    # 每一个端口可以运行不同的服务器，充当不同的节点
    parser = ArgumentParser()
    # 输入命令时加上端口 -p --port 5001
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen to')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
