import os
import json
from web3 import Web3
from solcx import compile_standard, install_solc


def load_contract_source(path: str) -> str:
    with open(path, 'r') as f:
        return f.read()


def compile_contract(source: str, solc_version: str = '0.8.20'):
    install_solc(solc_version)
    compiled = compile_standard({
        'language': 'Solidity',
        'sources': {
            'SRPKPayments.sol': {
                'content': source
            }
        },
        'settings': {
            'optimizer': {'enabled': True, 'runs': 200},
            'outputSelection': {'*': {'*': ['abi', 'evm.bytecode']}}
        }
    }, solc_version=solc_version)
    contract_data = compiled['contracts']['SRPKPayments.sol']['SRPKPayments']
    abi = contract_data['abi']
    bytecode = contract_data['evm']['bytecode']['object']
    return abi, bytecode


def deploy(chain_name: str):
    rpc = os.environ.get('ETH_RPC_URL' if chain_name == 'ethereum' else 'BSC_RPC_URL')
    private_key = os.environ.get('DEPLOYER_PRIVATE_KEY')
    merchant_address = os.environ.get('MERCHANT_ADDRESS')
    if not rpc or not private_key or not merchant_address:
        raise SystemExit('Missing ETH/BSC RPC, DEPLOYER_PRIVATE_KEY, or MERCHANT_ADDRESS in environment')

    w3 = Web3(Web3.HTTPProvider(rpc))
    account = w3.eth.account.from_key(private_key)

    source = load_contract_source(os.path.join(os.getcwd(), 'contracts', 'SRPKPayments.sol'))
    abi, bytecode = compile_contract(source)

    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    construct_txn = Contract.constructor(Web3.to_checksum_address(merchant_address)).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 3_000_000,
        'maxFeePerGas': w3.to_wei('30', 'gwei'),
        'maxPriorityFeePerGas': w3.to_wei('1', 'gwei')
    })
    signed = account.sign_transaction(construct_txn)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print(json.dumps({
        'chain': chain_name,
        'contractAddress': receipt.contractAddress,
        'txHash': tx_hash.hex(),
        'deployer': account.address,
        'abi': abi
    }, indent=2))

    # Write artifact
    os.makedirs('build', exist_ok=True)
    with open(os.path.join('build', 'SRPKPayments.json'), 'w') as f:
        json.dump({'abi': abi, 'address': receipt.contractAddress}, f, indent=2)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2 or sys.argv[1] not in ('ethereum', 'bsc'):
        print('Usage: python scripts/deploy_contract.py [ethereum|bsc]')
        raise SystemExit(1)
    deploy(sys.argv[1])

