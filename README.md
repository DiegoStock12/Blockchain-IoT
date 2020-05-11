# Blockhain Support for Secure Communications in IoT

This project makes use of the Ethereum platform and smart contracts to provide IoT devices with a way of easily allocating resources in Edge blockchain servers as well as prevents malicious behavior by implementing a credit system based on a Virtual Token.

### Main components

- Blockchain Client: IoT devices are given an easy proxy interface in Python to communicate with the server and ask for resources
- Blockchain Server: Hosts the smart contract and keeps track of clients and allows them to perform allocations of resources like CPU, memory, storage and bandwidth
- Packet Sniffer: Monitors the behavior of the IoT devices and augments/decreases their credit based on the observed behavior. Once the credit of a device reaches zero, it can no longer communicate with any other devices nor with the outside world

### Main Requirements

- Python 3
- Web3.py
- Scapy
- Py-Solc
- Ethereum



