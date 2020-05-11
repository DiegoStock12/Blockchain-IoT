""" This module uses scapy to build packets that might trigger the sniffer filters """

from scapy.all import *
import netifaces as ni
from sys import argv
import random

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

def get_filled(packet, final_length):
    length = len(packet)
    padding = ('0'*(final_length-length)).encode('utf-8')
    return padding

def icmp(option: str):

    # build ip packet
    packet = IP(dst = '8.8.8.8')/ICMP()

    if option == 'frag':
        # Set random fragment number
        packet.frag = 25
    elif option == 'large':
        # Set len > 1024
        packet.len = 2048
        padding = get_filled(packet, 2048)
        packet = packet/padding
    elif option == 'mf':
        # Set mf flag
        packet.flags = 1
        
    
    packet.show()
    send(packet)

def tcp():
    """ Send fragmented syn tcp """
    packet = IP(dst = "8.8.8.8", flags = 1, frag = 1480)/TCP(sport = 2000, dport = 40000, flags = 0x02)/ "Este es un mensaje que prueba".encode('utf-8')
    packet.show()
    send(packet)

def not_in_network():
    """ Sender not in network """
    packet = IP(dst = "8.8.8.8", src= "7.7.7.7") / TCP(sport = 2000, dport = 40000) / "payload example for the packet".encode('utf-8')
    packet.show()
    send(packet)

def protocol_unknown():

    packet = IP(dst = "8.8.8.8", proto = 145) / TCP() / "content".encode('utf-8')
    packet.show()
    send(packet)

def other_ether_address():
    eth = set(['02:05:65:54:65:08','05:05:65:54:66:08','03:05:65:54:67:08','04:05:65:54:65:08',
    '06:05:65:54:65:08','07:05:65:54:65:08'])
    addr = random.sample(eth, 1)[0]
    packet = Ether(src = addr) / IP(dst = '8.8.8.8') / ICMP()
    packet.show()
    send(packet)


def menu():
    """ Main menu """

    menu ="""
    Selecciona el paquete a construir:

    1) ICMP Fragment
    2) Large ICMP
    3) ICMP More fragments
    4) Fragmented SYN TCP
    5) Packet not in network
    6) Protocol unknown
    7) Other ether address

    """
    

    while True:
        option = int(input(menu))
        if option == 1:
            icmp('frag')
        elif option == 2:
            icmp('large')
        elif option == 3:
            icmp('mf')
        elif option == 4:
            tcp()
        elif option == 5:
            not_in_network()
        elif option == 6:
            protocol_unknown()
        elif option == 7:
            other_ether_address()
        else:
            print('Unknown option')




if __name__ == "__main__":
    menu()