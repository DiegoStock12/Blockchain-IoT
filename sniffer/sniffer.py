"""
This packet sniffer will run on the network router and will help our server detect bad behavior
from the devices in the network and help it decrease their credit or block them reached a certain
point.

First we need to define which kind of packets coming from the network devices we'll consider
unacceptable or suspicious, probably being produced by a hacked device trying to attack our network
or use our devices as part of a greater botnet.
"""

from multiprocessing import Process
from multiprocessing.connection import Client
from scapy.all import *
import threading
import sys
import netifaces as ni
import ipaddress
import schedule
import time



""" The server process connecting with the sniffer will run on port 12000 """



class Sniffer:
    """ Packet sniffer in charge of detecting bad behavior from the IoT devices and
    sending those reports to the server.
    
    The server then reacts according to the predefined rules 
    """

    SERVER_IP = 'localhost'
    SERVER_PORT = 12000

    def __init__(self):

        # Known devices from the network
        self.known_devices = {}
        # MAC addresses of the devices we have to watch in the network.
        # The dict will have format {MAC address : isBlocked}
        self.iot_macs = {}
        self.addr, mask = self._get_network_info()
        # Get the network object
        network = ipaddress.IPv4Network('{}/{}'.format(self.addr, mask),
                                             strict=False)
        self.network = [str(addr) for addr in list(network.hosts())]
        
        # Start communication with server
        server_addr = (self.SERVER_IP, self.SERVER_PORT)
        self.conn = Client(server_addr)
        self.com_thread = threading.Thread(target=self._comunicate_with_server,
                                           args=(self.conn, ), daemon=True)
        self.com_thread.start()

        # Current report
        # Reports are sent to the server periodically, they have the shape:
        # {mac_address (best way to identify the sender) : number of bad behaviors}
        self.report = {}
        


    def sniff_packets(self, filter='ip', store=False):
        # Schedule the report sending task
        schedule.every(2).minutes.do(self._send_report)
        # Start sniffing packets
        kwargs = {'prn' : self._on_packet, 'store' : store, 'filter' : filter}
        threading.Thread(target = sniff, kwargs = kwargs, daemon = True).start()
        #sniff(filter=filter, prn=self._on_packet, store=store)
        print('I got here')
        while True:
            schedule.run_pending()
            time.sleep(5)
            

    def _on_packet(self, packet):
        """ Inside this method we should check the different parameters that 
        could set a packet as suspicious and therefore inspect it and inform the server so it can 
        perform several actions regarding the sender 

        The initial packet protection protocol is going to cover the basics as seen on: 
        https://www.juniper.net/documentation/en_US/junos/topics/concept/suspicious-packet-overview.html

        This is:

        - ICMP Fragment
        - Large ICMP packets
        - Bad IP
        - Unknown protocol
        - IP packet fragment
        - SYN packet protection 

        """

        # Chech if this is a packet we need to watch (from our IOT network)
        if packet[Ether].src in self.iot_macs.keys():
            
            # Get the MAC address 
            mac_address = packet[Ether].src

            # If it's blocked just say that the package is blocked
            if self.iot_macs[mac_address]:
                # The device is blocked
                print('Device is blocked, dropping package')
            

            else:
                # If the device is not blocked
                if mac_address not in self.report.keys():
                    self.report[mac_address] = 0

                # 1) Take care of ICMP exploits
                if packet.haslayer(ICMP):
                    packet.show()
                    # Packet is a fragment (nonsense)
                    if packet[IP].frag != 0:
                        print('[ICMP] Dangerous packet detected. Packet is fragmented')
                        self.report[mac_address] += 1
                    if packet[IP].flags == 1:
                        print('[ICMP] Dangerous packet detected: MF set to 1')
                        self.report[mac_address] += 1
                    # If packet is too big
                    if packet[IP].len > 1024:
                        print('[ICMP] Dangerous packet. Payload too big')
                        self.report[mac_address] += 1

                # 2) SYN Protection in TCP packets
                if packet.haslayer(TCP):
                    if packet[IP].frag != 0 or packet[IP].flags == 1:
                        # Check if the syn flag is set
                        if packet[TCP].flags & 0x02:
                            print('[TCP] Dangerous packet. SYN and fragmented')
                            self.report[mac_address] += 1

                # 3) IP outside of subnet, suspicious for an attack
                if packet[IP].src not in self.network:
                    packet.show()
                    print('[IP] Packet src address outside of network')
                    self.report[mac_address] += 1

                # 4) Unknown protocol
                if packet[IP].proto > 143:
                    print('[IP] Packet protocol is unknown')
                    self.report[mac_address] += 1

                # 5) Communication with wrong port from the server
                # Could be an nmap or a hacking attemp
                if packet[IP].dst == self.SERVER_IP:
                    if packet.haslayer(TCP):
                        if packet[TCP].dport != self.SERVER_PORT:
                            self.report[mac_address] += 1
                    elif packet.haslayer(UDP):
                        if packet[UDP].dport != self.SERVER_PORT:
                            self.report[mac_address] += 1

    def _comunicate_with_server(self, connection):
        print('Starting communication with server')
        while True:
            msg = connection.recv()

            # Update the known devices
            self.known_devices = msg
            self.iot_macs = {entry['mac_address']:entry['isBlocked'] for entry in msg}
            print('New mac states:', self.iot_macs)
        
    def _send_report(self):
        """ Sends latest reports to the server for it to analyze """
        print('Sending report to the server...')
        print('Report: ', self.report)

        self.conn.send(self.report)
        self.report = {}

    def _get_network_info(self):
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


def main():

    sniffer = Sniffer()

    try:
        sniffer.sniff_packets()
    except KeyboardInterrupt:
        print('Exiting...')
        sys.exit(0)
    finally:
        sniffer.conn.close()


if __name__ == "__main__":
    main()