""" Proxy class allowing legacy devices to interact with the blockchain """

# Special imports
from scapy.all import *
from web3 import Web3, HTTPProvider
from solc import compile_source

# Common imports
import os.path as path
import threading
# Create the network object that lists all Ip's
import ipaddress
# Check if address is public or private to choose interface
# from Ipy import IP
import netifaces as ni

# Use sqlite for a small db
import sqlite3

# We'll be needing a sniffer
# The proxy will have to use the contract interface as it will perform 
# the operations on behalf of the users
from interface import ContractInterface as Client


class Proxy:
    """ This proxy is in charge of adapting our system to older devices so they can sync with 
    the blockchain too. """

    DB_PATH = path.dirname(path.abspath(__file__)) + "/proxy.db"

    def __init__(self):
        
        # Initialize db
        self._initialize_database()

        # Initialize sniffer with our function
        self.w3 = Web3(HTTPProvider('http://localhost:8545'))
        # Cambiar esto
        self.w3.eth.defaultAccount = self.w3.eth.accounts[5]
        self.account = self.w3.eth.defaultAccount

        # Current client objects. Of the form { mac_address : client object }
        self.clients = {}

        # Connection
        # The database is of the shape:
        # devices(account, ip_address, mac_address) where account is primary key
        self.conn = self._get_connection()
        with self.conn as conn:
            # Get the macs
            cur = conn.cursor()
            cur.execute("select mac_address from devices")
            # Initialize self.macs as a set datatype
            self.macs = {row[0] for row in cur}
            print('Got my macs from the database', self.macs)
            cur.close()
            
        
        # We have to build a network to know which packets are of our interest
        self.addr, netmask = self._get_network_info()
        nw = ipaddress.IPv4Network("{}/{}".format(self.addr, netmask), strict = False)
        self.network = [str(addr) for addr in list(nw.hosts())]
        
    def run_forever(self):
        """ Starts the sniffer and the proxy action """
        sniff(prn = self._on_packet_action,store = False, filter = 'ip')
    
    def _on_packet_action(self, packet):
        """ Function that we'll execute to examine the packets we're receiving 
        The proxy will only receive packets from legacy devices, so he can keep his own database 
        of devices """

        # Get the mac address
        mac_address = packet[Ether].src
        # Añadir comprobación de si está en la red

        # If the mac address is not in macs but the ip is in our network
        # that means that the sender is one of the legacy devices
        if packet[IP].src in self.network and mac_address not in self.macs:
            packet.summary()
            # Add it to our mac address set
            self.macs.add(mac_address)
            print('Added', mac_address, 'to the list of addresses')

            # Create a new account using mac as password
            account_num = self.w3.personal.newAccount(mac_address)
            ip_addr = packet[IP].src
            print('Cuenta del cliente',account_num)

            # Unlock account forever
            self.w3.personal.unlockAccount(account_num, mac_address, 0)
            print('Account unlocked')

            # Create a new client
            # Since the client won't even know that we're in an 
            # ethereum environment, we have to set the proxy's w3 as the client's
            # so we can do transactions quickly
            new_client = Client(
                account=account_num, 
                w3 = self.w3,
                ip_address= ip_addr,
                mac_address= mac_address)
            # Register the client
            print('Registering client with address:', account_num)
            print('Proxy address', self.account)
            print('Default Account:', new_client.w3.eth.defaultAccount)

            # Register the new client
            new_client.register()
            print('Registered new client')

            # Set the dictionary so we relate mac_addresses to the clients' interface
            self.clients[mac_address] = new_client
            print('New dictionary:', self.clients)

            # Add it to the database
            with self.conn as conn:
                command = """
                INSERT INTO devices(account, mac_address, ip_address) values ('{}','{}','{}')
                """.format(account_num, mac_address, ip_addr)
                conn.execute(command)      

    def _get_network_info(self):
        """ Returns network info such as ip address and network mask """

        interfaces = ni.interfaces()
        iface = None

        if 'wlan0' in interfaces:
            iface = 'wlan0'
        elif 'eth0' in interfaces:
            iface = 'eth0'
        elif 'enp0s3' in interfaces:
            iface = 'enp0s3'
        else:
            print('Valid interface not found {}, exiting'
                  .format(interfaces))

        # Get the ip address and the netmask to construct the network
        ip = ni.ifaddresses(iface)[ni.AF_INET][0]['addr']
        mask = ni.ifaddresses(iface)[ni.AF_INET][0]['netmask']

        print('Returning network info:', (ip, mask))

        return (ip, mask)
        
    def _initialize_database(self):
        """ Initialization of the servers database """
        conn = self._get_connection()
        conn.execute(
            """CREATE TABLE IF NOT EXISTS devices(
                account varchar(100) primary key,
                mac_address varchar(40) unique,
                ip_address varchar(40) unique)
            """
        )
        conn.commit()
        conn.close()



    def _get_connection(self):
        return sqlite3.connect(self.DB_PATH)


if __name__ == "__main__":
    # Build proxy
    proxy = Proxy()
    print('Running proxy')
    proxy.run_forever()