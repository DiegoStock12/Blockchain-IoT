""" Basic server class """

from web3 import Web3, HTTPProvider
from multiprocessing import Process, Value, Lock
from multiprocessing.connection import Listener
import schedule
import event_listeners
import threading
import mysql.connector
from enum import Enum

import threading
import os
import time
import sys

import initialization


class Resource(Enum):
    """ Enum listing the available resources devices can ask for """
    computing_power = 1
    storage = 2
    bandwidth = 3
    memory = 4


class Price(Enum):
    """ Enum listing the price of the available resources devices can ask for.
    All the prices are listed in IoTokens per unit """
    computing_power = 10**4
    storage = 10**4
    bandwidth = 10**4
    memory = 10**4


def _f(resource_price: Price, amount_requested: int, available: int, credit: int):
    """ Formula used to calculate the cost of the resources """
    print('Received price = {}, amount = {}, available = {}, credit = {}'.format(
        resource_price, amount_requested, available, credit))
    return resource_price*(amount_requested/available)*(100/credit)


def _getConnection():
    return mysql.connector.connect(
        host='localhost',
        user='diego',
        passwd='chinforris',
        database='tfg'
    )


class BlockchainServer:

    # Amount of resources
    TOTAL_CPU = 100  # Represented as 100% of available cpu
    TOTAL_STORAGE = 1000000  # 1TB in MB
    TOTAL_BANDWIDTH = 100  # Represented as 100%
    TOTAL_MEMORY = 100  # Represented as 100%

    # Pricing constants
    ETA = 1

    # Server listening port
    LISTENING_PORT = 12000  # Listening port for connections

    def __init__(self):

        self.w3 = Web3(HTTPProvider("http://localhost:8545"))

        # Initialize database
        self._initialize_database()

        # Setup the default account
        self.account = self.w3.eth.accounts[0]
        self.w3.eth.defaultAccount = self.account

        # Deploy contract and get back the python interface
        # for interacting with it
        self.contract = initialization.deploy_contracts(
            w3=self.w3,
            account=self.account,
            total_storage=self.TOTAL_STORAGE)

        # Connections with the multiple sniffers.
        # They are organized as (ip_address, port) : connection
        self.connections = {}

    def serve_forever(self):
        """ Serve until excplicit shutdown 

        This method creates the multiple processes necessary for the good 
        functioning of the server and also sends regular updates to the 
        packet sniffers to show which accounts are on which network 

        """
        # Creation of shared memory objects
        # 1) CPU
        available_cpu = Value('i', self.TOTAL_CPU)
        cpu_lock = Lock()
        # 2) STORAGE
        available_storage = Value('i', self.TOTAL_STORAGE)
        st_lock = Lock()
        # 3) BANDWIDTH
        available_bandwidth = Value('i', self.TOTAL_BANDWIDTH)
        bw_lock = Lock()
        # 4) MEMORY
        available_memory = Value('i', self.TOTAL_MEMORY)
        mem_lock = Lock()

        # Creation of processes
        register_process = Process(
            target=event_listeners.register_listerner, args=(self.w3, self.contract, ))
        register_process.start()

        transfer_process = Process(
            target=event_listeners.transfer_listener, args=(self.contract,))
        transfer_process.start()

        storage_process = Process(
            target=event_listeners.storage_allocator, args=(self.contract, available_storage, st_lock))
        storage_process.start()

        free_storage_process = Process(
            target=event_listeners.free_storage_listener, args=(self.contract, available_storage, st_lock))
        free_storage_process.start()

        cpu_process = Process(
            target=event_listeners.cpu_allocator, args=(self.contract, available_cpu, cpu_lock))
        cpu_process.start()

        free_cpu_process = Process(
            target=event_listeners.free_cpu_listener,  args=(self.contract, available_cpu, cpu_lock))
        free_cpu_process.start()

        # Start connection listening threaad
        threading.Thread(
            target=self._sniffer_connection_listener, daemon=True).start()

        # Schedule the update sending
        schedule.every(40).seconds.do(self._send_updated_info)
        schedule.every(3).minutes.do(self._review_pending_charges)

        # Infinite loop
        while True:
            schedule.run_pending()
            time.sleep(5)

    def _wait_for_reports(self, connection):
        """ Server thread that listens for reports """

        print('Waiting for reports... ')
        while True:
            report = connection.recv()
            print('Received report from sniffer', report)

            # Here update credit based on behavior

            # Get current registered devices
            try:
                db_conn = _getConnection()
                cursor = db_conn.cursor()
                cursor.execute(
                    "Select account_address, mac_address, credit from clients")
                current_clients = cursor.fetchall()

                # Update credit and balances of all the clients
                for client in current_clients:
                    # Extract parameters from the client
                    account_address, mac_address, credit = client
                    credit = int(credit)
                    print('Client data: {}, {}, {}'.format(
                        account_address, mac_address, credit))

                    # check if it is reported and if it is calculate the credit reduction
                    if mac_address in report.keys() and report[mac_address] != 0:
                        # Discount 5 credit for every suspicious behavior
                        penalty = 5*int(report[mac_address])
                        print('Penalty for {} is {}'.format(
                            mac_address, penalty))

                        new_credit = credit - penalty
                        # If the credit is less than 0 or 0 we have to clock the client
                        if new_credit <= 0:
                            new_credit = 0
                            print('Credit has been exhausted, blocking client')
                            # Block the client in the contract
                            self.contract.functions.freezeAccount(
                                account_address, True).transact()
                            # Block the client in the database
                            cursor.execute("UPDATE clients SET isBlocked = {} WHERE account_address = '{}'"
                                           .format(True, account_address))

                        # Update the credit
                        cursor.execute("UPDATE clients SET credit = {} WHERE account_address = '{}'"
                                       .format(new_credit, account_address))
                        print('New credit =', new_credit)
                        db_conn.commit()

                    else:
                        # If it has not commited any irregular behavior we update his credit and balance
                        # If credit is at its max we don't update it
                        if credit != 100:
                            credit += 1
                            print(
                                "Increased credit for {} -> {}".format(account_address, credit))
                            cursor.execute("UPDATE clients SET credit = {} where account_address = '{}'"
                                           .format(credit, account_address))
                            db_conn.commit()

                cursor.close()
                db_conn.close()

            except mysql.connector.Error as error:
                db_conn.rollback()
                print('Error while updating credits: {}'.format(error))

    def _review_pending_charges(self):

        print('Reviewing pending charges')
        try:
            connection = _getConnection()
            cursor = connection.cursor()

            cursor.execute("select * from pending_charges")
            pending_charges = cursor.fetchall()

            for charge in pending_charges:
                res_id, account, amount = charge
                cursor.execute(
                    "Select credit from clients where account_address = '{}'".format(account))
                results = cursor.fetchall()
                credit = int(results[0][0])
                # Update balance in db and contract
                cursor.execute("UPDATE clients set coin_balance = coin_balance + {} where account_address = '{}'"
                               .format(int(amount)+credit*self.ETA, account))
                self.contract.functions.updateBalance(
                    account,
                    int(amount)+credit*self.ETA,
                    True
                ).transact()
                print('Updated balance of client {}, {}'.format(
                    account, int(amount)+credit*self.ETA))

                # Delete that charge
                cursor.execute("DELETE from pending_charges where id = '{}'"
                               .format(res_id))
                print('Deleted reservation entry')

                connection.commit()

            cursor.close()
            connection.close()

        except mysql.connector.Error as e:
            connection.rollback()
            print("An error ocurred: {}".format(e))

    def _send_updated_info(self):
        """ Sends updated info to the packet sniffer """
        db_conn = _getConnection()
        cursor = db_conn.cursor(dictionary=True)
        cursor.execute(
            "Select account_address, ip_address, mac_address, isBlocked from clients")
        results = cursor.fetchall()

        for address, connection in self.connections.copy().items():
            try:
                connection.send(results)
            except (BrokenPipeError, ConnectionResetError) as e:
                print('Error sending updates: {}'.format(e))
                connection.close()
                del self.connections[address]

        #print('Connection dictionary:', self.connections)

        cursor.close()
        db_conn.close()

    def _sniffer_connection_listener(self):
        """ Thread listening for new connection requests and 
        adds it to the connection dictionary """

        listening_address = ('localhost', self.LISTENING_PORT)
        listener = Listener(listening_address)

        while True:
            conn = listener.accept()
            print('Connection accepted from', listener.last_accepted)
            self.connections[listener.last_accepted] = conn
            # Start thread to serve petitions
            threading.Thread(target=self._wait_for_reports,
                             args=(conn, ), daemon=True).start()

    def _initialize_database(self):
        """ Initialization of the servers database """
        conn = _getConnection()
        cursor = conn.cursor()

        # Execute the commands for initializing the database
        self._execute_mysql_script(cursor)

        conn.commit()
        cursor.close()
        conn.close()

    def _execute_mysql_script(self, cur):
        ''' Executes all the mysql commands in a sql file '''

        with open(os.path.dirname(os.path.abspath(__file__)) + '/serverDB.sql') as sqlFile:
            lines = str(sqlFile.read())
            commands = lines.split(";")
            for command in commands:
                try:
                    if command.strip() != '':
                        cur.execute(command)
                except IOError:
                    print("Command skipped")

    @staticmethod
    def calculate_price_of_request(resource_type: Resource, amount: int, value: Value, account: str):
        """ This method will calculate the price to apply a priori 
        for a particular request and return it so the client can be charged 

        We don't need to wait for the lock since all the price calculations will be performed while
        'holding' the lock """

        credit = None

        # Get credit for the account
        try:
            connection = _getConnection()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT credit from clients where account_address = '{}'".format(account))
            results = cursor.fetchall()
            credit = int(results[0][0])
            print('Credit of account {} is {}'.format(account, credit))

        except mysql.connector.Error as error:
            connection.rollback()
            print('Failed getting new record into table: {}'.format(error))

        finally:
            cursor.close()
            connection.close()

        if credit is None:
            return None

        # If asking for computing power
        if resource_type == Resource.computing_power:
            price = _f(Price.computing_power.value,
                       amount, value.value, credit)
            print('Price os reservation is', price, 'IoTokens')
            return int(round(price))
        # Asking for storage
        elif resource_type == Resource.storage:
            print('Price for all: {}, amount: {}, available: {}'.format(
                Price.storage.value, amount, value.value))
            price = _f(Price.storage.value, amount, value.value, credit)
            return int(round(price))
        # Asking for bandwidth
        # elif resource_type == Resource.bandwidth:
           # price = Price.bandwidth.value**(amount/value.value)
            # return int(round(price))
        # Asking for memory
        # elif resource_type == Resource.memory:
            #price = Price.memory.value**(amount/value.value)
            # return int(round(price))


def main():
    server = BlockchainServer()
    time.sleep(5)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
