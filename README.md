# Blockhain Support for Secure Communications in IoT

This project makes use of the Ethereum platform and smart contracts to provide IoT devices with a way of easily allocating resources in Edge blockchain servers as well as prevents malicious behavior by implementing a credit system based on a Virtual Token.

This code is part of the experiments made during my [Bachelor Thesis](http://castor.det.uvigo.es:8080/xmlui/bitstream/handle/123456789/338/TFG%20Diego%20Albo%20Mart%C3%ADnez.pdf?sequence=1&isAllowed=y) inspired by previous work of Pan et al. [1]

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



### References

[1] Pan, J., Wang, J., Hester, A., AlQerm, I., Liu, Y., & Zhao, Y. (2018). EdgeChain: An edge-IoT framework and prototype based on blockchain and smart contracts. *IEEE Internet of Things Journal*, *6*(3), 4719-4732., available [here](https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=8510796&casa_token=46rSzSIX804AAAAA:IMOZrjw-CQT1ikhOawv1V-dHURp2EsATbi8S1XQwuY2Geqs1vd1BJKxiscCxADjWOfvhxlrS)
