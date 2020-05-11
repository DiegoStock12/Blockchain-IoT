''' This file acts as an interface between the python programming 
language and the smart contract interface deployed on the blockchain '''

from web3 import Web3, HTTPProvider
from solc import compile_source
from web3.contract import ConciseContract
import time
import utils
import pickle
import os
import os.path as path

''' This contract address should be a constant in the end of development,
and stay in the blockchain '''

CONTRACT_ADDRESS = "0x1f24b48b2999d6ff6ce642581074A350e104563E"
RESERVATIONS_PICKLE_FILE = os.path.dirname(
    os.path.abspath(__file__)) + "/reservations.pickle"
ADDRESS_PICKLE_FILE = os.path.dirname(
    os.path.abspath(__file__)) + "/address.pickle"


class ContractInterface:
    '''
    This python interface mimics the solidity smart contract interface deployed on the blockchain
    and its methods.

    This way, it's much simpler and easier on the eyes the interaction with the smart 
    contract functions from the client side
    '''

    CONTRACT_PATH = path.dirname(path.abspath(__file__)) + "/../contracts/token.sol"
    COMPILED_CONTRACT_PATH = path.dirname(path.abspath(__file__)) + "/../contracts/contract_compiled.pickle"

    # Client number is only for tests
    def __init__(self,  account=None, ip_address=None, mac_address=None,
                 w3=None, client_number: int = None):
        ''' Default constructor of the interface class, with parameters
    that make the code much cleaner in our client API .

    For now the only parameter is the client number which identifies which of 
    the default accounts provided by ganache-cli the client sets as its default one
    {1 - 9} since 0 is for the server and owner of the contract '''

        # In case there's no w3 given we initialize to the default server
        if w3 is None:
            self.w3 = Web3(HTTPProvider("http://localhost:8545"))
            #self.w3 = Web3(HTTPProvider("http://192.168.0.29:8545"))
        else:
            self.w3 = w3

        # Regular register (not from proxy)
        if ip_address is None and mac_address is None:
            self.IP = utils.getIP()
            self.MAC = utils.getMAC()
        else:
            self.IP = ip_address
            self.MAC = mac_address

        self.contract = self._getContract(self.w3)
        #self.contract = self._load_contract(self.w3)

        # The ConciseContract class is much better for reaidng variables straight away.
        # If our goal is not transact something, we'll use the Concise version of the contract
        self.contractConcise = ConciseContract(self.contract)

        # set the default account for the client, if it's None we'll register and we'll get a new one
        # Only for tests
        if client_number is not None:
            self.w3.eth.defaultAccount = self.w3.eth.accounts[client_number]
            self.account = self.w3.eth.defaultAccount
        else:
            # Usamos el w3 del proxy en ese caso
            # The client's own address is in the account variable
            self.account = account
            # The default account is however the one of the server

        # DATA FOR LEASES:

        # The dictionary is of the shape { grant_id : amount } so for the total memory we
        # just add the values
        self.remoteStorage = {}

        # The dictionary is of the shape { grant_id : amount } where amount is a number from
        # 0 to 100. 100 would mean that the amount is equal to all the available storage on
        # the remote server
        self.remoteCPU = {}

        # Load the reservations
        self._load_reservations()

    def register(self):
        ''' Registers the client in the server's contract, and sends the useful information
        so that the server can recognize each client '''

        tx_hash = None
        print('Registering with', self.account)

        # Regular register
        tx_hash = self.contract.functions.register(
            self.account, self.IP, self.MAC).transact()

        self.w3.eth.waitForTransactionReceipt(tx_hash)

        # build a listener so we can get the server's response
        server_answer_filter = self.contract.events.RegisterResponse.createFilter(
            fromBlock=0,
            toBlock='latest',
            argument_filters={
                'account': self.account
            })

        print('Created filter to wait for server register response')
        while True:
            response = server_answer_filter.get_new_entries()
            if len(response) != 0:
                for grant in response:
                    args = grant['args']
                    if args['accepted']:
                        print('Accepted request')
                        # If we don't have an account we stablish it
                        if self.account is None:
                            self.account = args['account']
                            self.w3.eth.defaultAccount = self.account
                            self._pickle_address()
                            print('Address pickled')
                    else:
                        print('Grant rejected')
                break
            else:
                print('No answer yet')
                time.sleep(1)

        print('Balance after register:', self.contractConcise.balanceOf(
            self.account), self.contractConcise.symbol())

        del server_answer_filter

    def transfer(self, to: str, amount: int):
        ''' Transfers to the specified ethereum account (expressed
        as a hexadecimal string) the specified amount of IoT (tokens) '''

        print('Balances before: {}, {}'
              .format(self.contractConcise.balanceOf(self.account), self.contractConcise.balanceOf(to)))
        tx_hash = self.contract.functions.transfer(
            self.account, to, amount).transact()
        self.w3.eth.waitForTransactionReceipt(tx_hash)
        print('Balances after: {}, {}'
              .format(self.contractConcise.balanceOf(self.account), self.contractConcise.balanceOf(to)))

    def request_storage(self, amount: int):
        ''' Requests storage from the server '''

        print('Asking for {} for account {}'.format(amount, self.account))

        tx_hash = self.contract.functions.getStorage(
            self.account, amount).transact()
        self.w3.eth.waitForTransactionReceipt(tx_hash)

        # Wait for the storage grant and filter just the ones for us
        petitionFilter = self.contract.events.StorageResponse.createFilter(
            fromBlock=0,
            toBlock='latest',
            argument_filters={
                'account': self.account
            })
        print('Created filter for storage grants')

        while True:
            response = petitionFilter.get_new_entries()
            if len(response) != 0:
                for grant in response:
                    args = grant['args']
                    if args['accepted']:
                        print('Accepted request')
                        self.remoteStorage[args['grantID']] = int(
                            args['amount'])
                        print('new dict:', self.remoteStorage)
                    else:
                        print('Grant rejected')
                break
            else:
                print('No answer yet')
                time.sleep(1)

        # We no longer need the filter
        del petitionFilter
        self._update_reservations()

    def free_storage(self, id):
        ''' Free the storage acquired from the server '''

        print('Removing item with id=', id)
        tx_hash = self.contract.functions.freeStorage(
            self.account, id).transact()
        self.w3.eth.waitForTransactionReceipt(tx_hash)
        print('freed storage')
        # Pop the item
        self.remoteStorage.pop(id)
        self._update_reservations()

    def request_computing_power(self, amount: int):
        """ Request computing power from the server """
        print('Asking for {}% of cpu for account {}'.format(amount, self.account))

        # Transact and wait for the transaction receipt
        tx_hash = self.contract.functions.getComputingPower(
            self.account, amount).transact()
        self.w3.eth.waitForTransactionReceipt(tx_hash)

        # Filter the answers to get if our request was granted
        petition_filter = self.contract.events.CPUResponse.createFilter(
            fromBlock=0,
            toBlock='latest',
            argument_filters={
                'account': self.account
            })

        print('Created computing power filter for account', self.account)

        # Wait for our response
        while True:
            response = petition_filter.get_new_entries()
            if len(response) != 0:
                for answer in response:
                    args = answer['args']
                    if args['accepted']:
                        print('Our computing power request was granted')
                        self.remoteCPU[args['grantID']] = int(args['amount'])
                        print('New dict: ', self.remoteCPU)
                    else:
                        print('Grant rejected')
                break
            else:
                print('No answer to cpu request yet')
                time.sleep(1)

        del petition_filter
        self._update_reservations()

    def free_computing_power(self, id):
        ''' Free the cpu reservation '''

        print('Removing cpu reservation with id', id)
        tx_hash = self.contract.functions.freeComputingPower(
            self.account, id).transact()
        self.w3.eth.waitForTransactionReceipt(tx_hash)
        print('Freed cpu storage')
        # Pop item
        self.remoteCPU.pop(id)
        self._update_reservations()

    def force_error(self):
        """ Method to test whether the onlyOwner modifier works properly """
        print('Trying to force an error')
        tx_hash = self.contract.functions._freeStorage(
            self.account, 500).transact()
        self.w3.eth.waitForTransactionReceipt(tx_hash)
        print('Received transaction hash')

    def _pickle_address(self):
        """ Saves the device's address in a pickle file """
        with open(ADDRESS_PICKLE_FILE, 'wb') as pickle_file:
            # dump the address
            pickle.dump(self.account, pickle_file)

    def _unpickle_address(self):
        """ Gets this device's address from the file """
        if os.path.exists(ADDRESS_PICKLE_FILE):
            with open(ADDRESS_PICKLE_FILE, 'rb') as pickle_file:
                self.account = pickle.load(pickle_file)
                self.w3.eth.defaultAccount = self.account

                #self.w3.eth.defaultAccount = self.w3.eth.accounts[client_number]
                #self.account = self.w3.eth.defaultAccount

    def _update_reservations(self):
        """ Updates the reservations in the pickle file after a reservation is made or freed """
        with open(RESERVATIONS_PICKLE_FILE, 'wb') as pickle_file:
            # save the dictionaries
            pickle.dump(self.remoteStorage, pickle_file)
            pickle.dump(self.remoteCPU, pickle_file)

    def _load_reservations(self):
        """ Use pickle to load the remote storage and computing power reservations. 
        This way we make them persistent in case of a reboot of the service. The variables
        inside the pickle file keep the same name """
        if os.path.exists(RESERVATIONS_PICKLE_FILE):

            with open(RESERVATIONS_PICKLE_FILE, 'rb') as pickle_file:
                # restore the dictionaries
                self.remoteStorage = pickle.load(pickle_file)
                self.remoteCPU = pickle.load(pickle_file)

            print('Restored storage reservations:\n', self.remoteStorage)
            print('Restored cpu reservations:\n', self.remoteCPU)
    
    def _load_contract(self, w3:Web3):
        with open(self.COMPILED_CONTRACT_PATH, 'rb') as pickle_file:
            interface = pickle.load(pickle_file)
            contract = w3.eth.contract(
                abi=interface['abi'],
                address=CONTRACT_ADDRESS)
            return contract


    def _getContract(self, w3: Web3):
        with open(self.CONTRACT_PATH, "r") as contract_file:
            global CONTRACT_ADDRESS
            source_code = contract_file.read()
            compiled = compile_source(source_code)
            interface = compiled['<stdin>:IoToken']
            contract = w3.eth.contract(
                abi=interface['abi'],
                address=CONTRACT_ADDRESS)
            return contract
