from web3.contract import ConciseContract
from solc import compile_source
import pprint
from web3 import Web3
import os

def deploy_contracts(w3: Web3, account: str, total_storage: int):

    pp = pprint.PrettyPrinter(indent=4)


    with open(os.path.dirname(os.path.abspath(__file__)) + '/../contracts/token.sol', 'r') as tokenContract:
        
        # Read the files and return the ConsiseContracts
        token_source = tokenContract.read()

    compiled_token = compile_source(token_source)

    # Get the compiled contracts ready for deployment
    token_interface = compiled_token['<stdin>:IoToken']


    # Create contract
    Token = w3.eth.contract(
        abi = token_interface['abi'],
        bytecode = token_interface['bin'])

    # Deploy the Token (We configure storage available as 1TB)
    tx_hash = Token.constructor(total_storage, 210000,account).transact()
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)

    # Create contract instance
    iot_token = w3.eth.contract(
        address = tx_receipt.contractAddress,
        abi = token_interface['abi'])
    pp.pprint(token_interface['abi'])
    print('Contract address', tx_receipt.contractAddress)

    return iot_token
