''' This file contains the functions used to receive new events transacted into the blockchain '''

import time
import mysql.connector
import sys
from web3 import Web3
from web3.contract import ConciseContract
from mysql.connector import pooling
from mysql.connector import Error
import uuid
from multiprocessing import Value, Lock
from server import BlockchainServer, Resource
import web3

# Global variables to use for storage management
CPU_AVAILABLE = 100
STORAGE_AVAILABLE = 1000000  # 1 TB = 10^6 MB

# Connection pool used by the processes for accesing the database
connection_pool = None


def register_listerner(w3: Web3, contract,  fromBlock=0, toBlock='latest'):
    ''' This listener listens to register events and executes a series of commands
            to update the database records of that particular client '''

    print('[x] register_listener: started')
    register_filter = contract.events.Register.createFilter(
        fromBlock=fromBlock, toBlock=toBlock)
    time.sleep(1)

    connection = None

    # We iterate infinitelly so we can recover the entries of the filter
    while True:
        try:
            new_entries = register_filter.get_new_entries()

            if len(new_entries) > 0:
                # If there are new entries, try to insert them in the table
                try:

                    connection = _getConnection()
                    cursor = connection.cursor()

                    # print the data of the entries
                    for entry in new_entries:
                        args = entry['args']
                        print('Account =', args['account'])

                        # If it's not the user is already registered and already has an account
                        cursor.execute('''SELECT account_address, mac_address, ip_address FROM clients WHERE account_address = '{}'
                        '''.format(args['account']))
                        # If there's something in the database already
                        results = cursor.fetchall()
                        if cursor.rowcount != 0:
                            print('Client is already in the database')
                            print(results)
                            account_address, mac_address, ip_address = results[0]
                            print('Datos del cliente: {}, {}, {}'.format(
                                account_address, mac_address, ip_address))
                            cursor.execute('''UPDATE clients SET mac_address = '{}', ip_address = '{}' WHERE account_address = '{}' '''
                                            .format(args['mac_address'], args['ip_address'], account_address))
                        else:
                            print('Client was not registered')
                            cursor.execute('''INSERT INTO clients(account_address, mac_address, ip_address, coin_balance, isRegistered) value
                                ('{}', '{}', '{}', {}, {})'''.format(args['account'], args['mac_address'], args['ip_address'], args['balance'], 'true'))

                        connection.commit()
                        contract.functions.answerRegisterRequest(
                            True,
                            args['account'],
                            args['ip_address'],
                            args['mac_address']).transact()

                        print('Answered register request')

                except mysql.connector.Error as error:
                    connection.rollback()
                    print('Failed inserting new record into table: {}'.format(error))

                finally:
                    cursor.close()
                    connection.close()
                    print('MySQL connection is closed')

            # Sleep 20 seconds until mining other things
            time.sleep(1)

        except KeyboardInterrupt:
            print("[*] register_listener: exiting...")
            sys.exit(0)


def transfer_listener(contract, fromBlock=0, toBlock='latest'):
    ''' This listener listens to transfer events and executes a series of commands '''

    print('[x] transfer_listener: started')
    myFilter = contract.events.Transfer.createFilter(
        fromBlock=fromBlock, toBlock=toBlock)
    time.sleep(1)

    while True:
        try:
            new_entries = myFilter.get_new_entries()

            if len(new_entries) > 0:
                # print the data of the entries
                for entry in new_entries:
                    print(entry['args'])
                # Sleep 20 seconds until mining other things

            time.sleep(1)
        except KeyboardInterrupt:
            print("[*] transfer_listener: exiting...")
            sys.exit(0)


def storage_allocator(contract, available_storage: Value, lock: Lock, fromBlock=0, toBlock='latest'):
    ''' Process that decides whether a storage request is granted or not.

    Most of the requirement checking is done directly by the smart contract, so here
    the main task of this method is to generate a unique id for the reservation - with
    the uuid4 module - and store all the data of the reservation in the database 

    One of the requirements to be able to allocate memory is being reggistered in the system.
    If not, the call will fail '''

    print('[x] storage_allocator: started')

    # Create filters for all events related to storage
    petitionFilter = contract.events.StoragePetition.createFilter(
        fromBlock=fromBlock,
        toBlock=toBlock)
    time.sleep(1)

    # Concise contract to access the balances in a much more direct way
    concise_contract = ConciseContract(contract)

    try:
        while True:
            newStoragePetitions = petitionFilter.get_new_entries()

            if len(newStoragePetitions) != 0:
                try:
                    connection = _getConnection()
                    cursor = connection.cursor()

                    # Acquire lock to change the reservations
                    with lock:
                        for petition in newStoragePetitions:
                            args = petition['args']
                            print('Args: {}, {}'.format(
                                args['account'], args['amount']))

                            # Make the appropriate comprobations
                            if available_storage.value - args['amount'] >= 0:
                                st_id = uuid.uuid4()
                                price = BlockchainServer.calculate_price_of_request(Resource.storage, int(args['amount']),available_storage, args['account'])
                                print('Price of the request:', price, 'IoTokens')

                                # Get balance of the account requesting storage
                                balance = concise_contract.balanceOf(args['account'])
                                print('Balance is {} and price is {}'.format(balance, price))

                                if balance >= price:
                                    # Decrease the balance
                                    print('Accepting Request')
                                    # Update balance, False = decrement
                                    contract.functions.updateBalance(
                                        args['account'],
                                        int(price),
                                        False
                                    ).transact()
                                    contract.functions.answerStorageRequest(
                                        args['account'],
                                        args['amount'],
                                        str(st_id),
                                        True).transact()
                                    # Add storage reservation to the database
                                    cursor.execute('''
                                        INSERT INTO storage_allocations(id, account_address, amount) value 
                                        ('{}','{}',{})'''.format(str(st_id), args['account'], args['amount']))
                                    # Update client balance in the database
                                    cursor.execute("UPDATE clients set coin_balance = coin_balance - {} where account_address = '{}'".format(price, args['account']))

                                    # Insert new transaction pending of charge
                                    cursor.execute("INSERT INTO pending_charges(id, account_address, charge) value ('{}','{}',{})"
                                    .format(st_id, args['account'], price))
                                    connection.commit()

                                    available_storage.value -= args['amount']
                                    print('Storage available:',
                                        available_storage.value, 'MB')
                                    new_balance = concise_contract.balanceOf(args['account'])
                                    print('New balance', new_balance)
                                
                                else:
                                    # Not enough balance in the client's account
                                    print('Not enough funds')
                                    print('Rejecting request')
                                    contract.functions.answerStorageRequest(
                                    args['account'],
                                    args['amount'],
                                    '',
                                    False).transact()


                            else:
                                # Not enough available storage
                                print('Rejecting request')
                                contract.functions.answerStorageRequest(
                                    args['account'],
                                    args['amount'],
                                    '',
                                    False).transact()

                except mysql.connector.Error as error:
                    connection.rollback()
                    print('Failed inserting new record into table: {}'.format(error))

                finally:
                    cursor.close()
                    connection.close()

            time.sleep(1)

    except KeyboardInterrupt:
        print("[*] storage_allocator: exiting...")
        sys.exit(0)


def free_storage_listener(contract, available_storage: Value, lock: Lock, fromBlock=0, toBlock='latest'):
    ''' Receives the storage freeing requests from all the clients.
    After that, it deletes the entries for that reservation-id from the database,
    and proceeds to execute the onlyOwner method of the smart contract in order
    to update the contract's memory management mapping and current storage available '''

    print('[x] free_storage: started')

    freeStorageFilter = contract.events.FreeStorage.createFilter(
        fromBlock=fromBlock,
        toBlock=toBlock)
    time.sleep(1)

    try:
        while True:
            requests = freeStorageFilter.get_new_entries()

            if len(requests) != 0:

                try:
                    connection = _getConnection()
                    cursor = connection.cursor()

                    for entry in requests:
                        args = entry['args']  # Devuelve account e id
                        cursor.execute("SELECT amount from storage_allocations WHERE id = '{}'"
                                       .format(args['grantID']))
                        results = cursor.fetchall()
                        print(results)
                        amount = results[0][0]

                        cursor.execute("DELETE FROM storage_allocations WHERE id ='{}'"
                                       .format(args['grantID']))
                        print("Deleted storage reservation")
                        connection.commit()

                        cc = ConciseContract(contract)
                        print("Storage use:", cc.storageUse(args['account']))

                        contract.functions._freeStorage(
                            args['account'], amount).transact()
                        print('transacted function')

                        print("Storage use:", cc.storageUse(args['account']))

                        with lock:
                            available_storage.value += amount

                except mysql.connector.Error as error:
                    connection.rollback()
                    print('Failed inserting new record into table: {}'.format(error))

                finally:
                    cursor.close()
                    connection.close()

            time.sleep(1)

    except KeyboardInterrupt:
        print("[*] free_storage: exiting...")
        sys.exit(0)


def cpu_allocator(contract,  available_cpu: Value, lock: Lock, fromBlock=0, toBlock='latest'):
    """ Similar to the storage allocator, this method allocates cpu computing power to a certain
    client after it's requested, returning an id for said reservation """

    print('[x] cpu_allocator: started')

    # Create the filter necessary
    cpu_allocator_filter = contract.events.CPUPetition.createFilter(
        fromBlock=fromBlock,
        toBlock=toBlock)
    time.sleep(1)

    # Concise contract to access the balances in a much more direct way
    concise_contract = ConciseContract(contract)

    try:
        # Main loop of the receiver
        while True:
            new_cpu_petitions = cpu_allocator_filter.get_new_entries()

            if len(new_cpu_petitions) != 0:

                # Open mysql connection
                try:
                    connection = _getConnection()
                    cursor = connection.cursor()

                    with lock:
                        for petition in new_cpu_petitions:
                            args = petition['args']
                            print(
                                'Cpu_petition: {} -> {}'.format(args['account'], args['amount']))

                            # Check to see if rejecting and accepting works, we need
                            # to change it after
                            if available_cpu.value - args['amount'] >= 0:
                                cpu_id = uuid.uuid4()
                                price = BlockchainServer.calculate_price_of_request(Resource.computing_power, int(args['amount']),available_cpu, args['account'])
                                
                                # Get balance of the account requesting storage
                                balance = concise_contract.balanceOf(args['account'])
                                print('Balance is {} and price is {}'.format(balance, price))

                                if balance >= price:
                                    # Decrease the balance
                                    print('Accepting Request')
                                    # Update balance, False = decrement
                                    contract.functions.updateBalance(
                                        args['account'],
                                        int(price),
                                        False
                                    ).transact()
                                    contract.functions.answerComputingPowerRequest(
                                        args['account'],
                                        args['amount'],
                                        str(cpu_id),
                                        True).transact()
                                    available_cpu.value -= args['amount']

                                    # 1) Insert cpu allocation in the database
                                    cursor.execute("""
                                    INSERT INTO cpu_allocations(id, account_address, amount) value
                                    ('{}', '{}', {})""".format(str(cpu_id), args['account'], args['amount']))

                                    # 2) Update client balance in the database
                                    cursor.execute("UPDATE clients set coin_balance = coin_balance - {} where account_address = '{}'".format(price, args['account']))

                                    # 3) Insert new transaction pending of charge
                                    cursor.execute("INSERT INTO pending_charges(id, account_address, charge) value ('{}','{}',{})"
                                    .format(cpu_id, args['account'], price))

                                    # Commit changes
                                    connection.commit()

                                    new_balance = concise_contract.balanceOf(args['account'])
                                    print('New balance', new_balance)
                                
                                else:
                                    # Client does not have enough funds
                                    print('Not enough funds')
                                    print('Rejecting request')
                                    contract.functions.answerComputingPowerRequest(
                                    args['account'],
                                    args['amount'],
                                    '',
                                    False).transact()

                            else:
                                # Not enough spare CPU
                                print('Rejecting request... number {} is not even'
                                      .format(args['amount']))
                                contract.functions.answerComputingPowerRequest(
                                    args['account'],
                                    args['amount'],
                                    '',
                                    False).transact()

                except mysql.connector.Error as error:
                    connection.rollback()
                    print('Error in mysql: {}'.format(error))

                finally:
                    cursor.close()
                    connection.close()

            # Sleep until the next comprobation
            time.sleep(1)

    except KeyboardInterrupt:
        print("[*] cpu_allocator: exiting...")
        sys.exit(0)


def free_cpu_listener(contract, available_cpu: Value, lock: Lock, fromBlock=0, toBlock='latest'):
    """ Receives the CPU freeing petitions from all the clients.
    After that, it deletes the database entries of the given reservation indexed by an uuid
    and executes the owner-only accesible function in the smart contract to complete the procedure
    of making the memory available again """

    print('[x] free_cpu: started')

    # Create the listener for the events
    free_cpu_listener = contract.events.FreeComputingPower.createFilter(
        fromBlock=fromBlock,
        toBlock=toBlock)
    time.sleep(1)

    try:
        while True:
            requests = free_cpu_listener.get_new_entries()

            if len(requests) != 0:

                try:
                    connection = _getConnection()
                    cursor = connection.cursor()

                    for entry in requests:
                        args = entry['args']  # Devuelve account e id
                        cursor.execute("SELECT amount from cpu_allocations WHERE id = '{}'"
                                       .format(args['grantID']))
                        results = cursor.fetchall()
                        print(results)
                        amount = results[0][0]

                        # Delete the cpu reservation from the database
                        cursor.execute("DELETE FROM cpu_allocations WHERE id ='{}'"
                                       .format(args['grantID']))
                        connection.commit()
                        print("Deleted cpu reservation")
                        connection.commit()

                        cc = ConciseContract(contract)
                        print("Comp. Power use before:",
                              cc.cpuUse(args['account']))

                        # Execute the owner only method of the contract
                        contract.functions._freeComputingPower(
                            args['account'], amount).transact()

                        print("Comp. Power use after:",
                              cc.cpuUse(args['account']))

                        with lock:
                            available_cpu.value += amount
                            print('Updated amount:', available_cpu.value)

                except mysql.connector.Error as error:
                    connection.rollback()
                    print('Failed inserting new record into table: {}'.format(error))

                finally:
                    cursor.close()
                    connection.close()

            time.sleep(1)

    except KeyboardInterrupt:
        print("[*] free_cpu: exiting...")
        sys.exit(0)


def _getConnection():
    ''' Private method encapsulating the connection pool for the DB and 
    providing the multiple connections when needed '''
    global connection_pool
    if connection_pool is None:
        _createConnectionPool()
    try:
        return connection_pool.get_connection()
    except Error as e:
        print('Error while returning connecton from connection pool: {}'
              .format(e))


def _createConnectionPool():
    ''' Creates and initialized the connection pool used throughout the 
    receiving processes to store the data of the clients '''

    global connection_pool
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_size=5,
        pool_name="connection_pool",
        pool_reset_session=True,
        database='tfg',
        host='localhost',
        user=user,
        password=pwd
    )
