#!/usr/bin/env python3
import sys, os

sys.path.insert(1, os.path.dirname(sys.path[0]))

from eth_utils import decode_hex
import conflux.config

'''
This is the state root for pre-generated genesis accounts in `genesis_secrets.txt`.
'''

STORAGE = os.environ.get("CONFLUX_DEV_STORAGE", "dmpt")
SHARD_SIZE = os.environ.get("AMT_SHARD_SIZE")

SECRET = "seq_secrets.txt"
if STORAGE == "amt":
    if SHARD_SIZE is None:
        GENESIS_ROOT = "0x10c5eb78d8d7f9794d826fbbf306397bffc15cb5fbde4105759508af8029f6de"
    elif int(SHARD_SIZE) == 64:
        GENESIS_ROOT = "0x540ab19ec2ceb0a88fa2cf44e2f9b381bcd914be23de26f6490e55e78c36ce1a"
    elif int(SHARD_SIZE) == 16:
        GENESIS_ROOT = "0xb3487e95aef46626c2c0b9688eff172663f84b44564cee047ae6f7aa59992935"
elif STORAGE == "mpt":
    GENESIS_ROOT = "0x05b1ba2c15838e58b054ced4497db8bca54053a018f54a5ae5283bcf6a34d5cb"
else:
    GENESIS_ROOT = "0xf7d1918d912bb8d47d34c48297735bcef3220e16efec980ca4a9cb47e90905a9"

conflux.config.default_config["GENESIS_STATE_ROOT"] = decode_hex(GENESIS_ROOT)

BASE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../..")

if STORAGE == "amt":
    BINARY = os.path.join(BASE_PATH, "target/amt-db/release/conflux")
elif STORAGE == "mpt":
    BINARY = os.path.join(BASE_PATH, "target/mpt-db/release/conflux")
else:
    BINARY = os.path.join(BASE_PATH, "target/release/conflux")

from test_framework.block_gen_thread import BlockGenThread
from test_framework.test_framework import ConfluxTestFramework
from test_framework.mininode import *
from test_framework.util import *
import shutil

from send_tx import send_transaction_with_goodput, wait_transaction_with_goodput
from load_tx import get_loader

# from tools.metrics_echarts import generate_metric_chart

from pathlib import Path


class SingleBench(ConfluxTestFramework):
    def __init__(self):
        super().__init__()

    def set_test_params(self):
        self.num_nodes = 1
        self.rpc_timewait = 600
        # The file can be downloaded from `https://s3-ap-southeast-1.amazonaws.com/conflux-test/genesis_secrets.txt`
        print(os.path.dirname(os.path.realpath(__file__)))
        genesis_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), SECRET)
        amt_public_params_path = os.path.join(BASE_PATH, "pp")
        log_config = os.path.join(BASE_PATH, "run/log.yaml")
        self.conf_parameters = dict(
            tx_pool_size=10_000_000,
            heartbeat_timeout_ms=10000000000,
            record_tx_index="false",
            node_type="'archive'",
            executive_trace="true",
            genesis_secrets=f"\"{genesis_file_path}\"",
            amt_public_params=f"'{amt_public_params_path}'",
            log_level="'debug'",
            # log_conf=f"'{log_config}'",
            storage_delta_mpts_cache_size=4_000_000,
            storage_delta_mpts_cache_start_size=2_000_000,
            storage_delta_mpts_slab_idle_size=2_000_000,
        )
        if SHARD_SIZE is not None:
            self.conf_parameters["amt_shard_size"] = SHARD_SIZE

    def add_options(self, parser):
        parser.add_argument(
            "--bench-keys",
            dest="keys",
            default="10k",
            type=str)

        parser.add_argument(
            "--warmup-keys",
            dest="warmup_n",
            default="0",
            type=str)

        parser.add_argument(
            "--bench-txs",
            dest="tx_num",
            default="10k",
            type=str)

        parser.add_argument(
            "--bench-mode",
            dest="bench_mode",
            default="normal",
            type=str
        )

        parser.add_argument(
            "--shard-size",
            dest="shard_size",
            default=-1,
            type=int
        )

        parser.add_argument(
            "--bench-token",
            dest="bench_token",
            default="native",
            type=str
        )

        parser.add_argument(
            "--metric-folder",
            dest="metric_folder",
            default=None,
            type=str
        )

    def setup_network(self):
        self.setup_nodes()

    def setup_nodes(self, binary=None):
        """Override this method to customize test node setup"""
        self.add_nodes(self.num_nodes, binary=[BINARY] * self.num_nodes)
        stdout = None
        # stdout = sys.stdout
        self.start_nodes(stdout=stdout)

    def run_test(self):
        if SHARD_SIZE:
            shard = SHARD_SIZE
        else:
            shard = ""
        self.log.info(f"Run with backend {STORAGE}{shard}, keys {self.options.keys}, txs {self.options.tx_num}")
        # time.sleep(10)

        # Start mininode connection
        self.node = self.nodes[0]
        print(self.node.ip, self.node.port)
        n_connections = 5
        p2p_connections = []
        for node in range(n_connections):
            conn = DefaultNode()
            p2p_connections.append(conn)
            self.node.add_p2p_connection(conn)
        network_thread_start()

        for p2p in p2p_connections:
            p2p.wait_for_status()

        num_txs = 10000
        interval_fixed = 0.02

        block_gen_thread = BlockGenThread([self.node], self.log, num_txs=num_txs, interval_fixed=interval_fixed)
        block_gen_thread.start()

        loader = get_loader(self.options)

        def send_tx(i, encoded):
            self.node.p2ps[i % n_connections].send_protocol_packet(encoded.encoded + int_to_bytes(
                TRANSACTIONS))

        base = 0
        for warmup_transaction_batch in loader.warmup_transaction():
            base += send_transaction_with_goodput(warmup_transaction_batch, send_tx, self.node, base=base,
                                                  log=self.log.info)
            wait_transaction_with_goodput(base, self.node, log=self.log.info)

        if base > 0:
            for i in range(100):
                if i % 10 == 0:
                    self.log.info(f"Waiting {i}%")
                time.sleep(0.5)

        base += send_transaction_with_goodput(loader.bench_transaction(), send_tx, self.node, base=base,
                                              log=self.log.info)
        wait_transaction_with_goodput(base, self.node, log=self.log.info)

        metric_file_path = os.path.join(self.options.tmpdir, "node0",
                                        conflux.config.small_local_test_conf["metrics_output_file"][1:-1])

        if self.options.metric_folder is None:
            metric_folder = os.path.basename(self.options.tmpdir)
        else:
            metric_folder = self.options.metric_folder

        warmup_info = ""
        if loader.warmup_n > 0:
            warmup_info = f"-{self.options.warmup_n}"

        log_name = f"{self.options.bench_mode}-{self.options.bench_token}-{STORAGE}{shard}-{self.options.keys}{warmup_info}"
        Path(f"experiment_data/metrics/{metric_folder}").mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(BASE_PATH, f"experiment_data/metrics/{metric_folder}/{log_name}.log")
        shutil.copyfile(metric_file_path, output_path)

        block_gen_thread.stop()
        block_gen_thread.join()
        self.node.stop()


if __name__ == "__main__":
    SingleBench().main()

# from conflux.rpc import RpcClient

# path = os.path.join(BASE_PATH, f"experiment_data/transactions/test_erc20")
# test_txs, hashes = load(path, 2, log=self.log.info)
# test_txs = test_txs[0].encoded
# tx_hash1 = hashes[0]
# tx_hash2 = hashes[1]
# self.rpc = RpcClient(self.node)
# print("Send tx")
# self.node.p2ps[0].send_protocol_packet(test_txs + int_to_bytes(TRANSACTIONS))
# print("Wait receipt 1")
# self.rpc.wait_for_receipt(tx_hash1)
# print("Wait receipt 2")
# self.rpc.wait_for_receipt(tx_hash2)
# print("Get tx")
# # print(self.rpc.get_tx(tx_hash1))
# # print(self.rpc.get_tx(tx_hash2))
# print("Get receipt")
# print(self.rpc.get_transaction_receipt(tx_hash1))
# print(self.rpc.get_transaction_receipt(tx_hash2))
# exit(0)
