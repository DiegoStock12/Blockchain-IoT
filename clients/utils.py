import netifaces as ni

''' For the registering process we need to get some fields like 
	
	- Device MAC address
	- Device IP address
	- Device NetworkPort
'''

def getIP():
	ip = ni.ifaddresses('enp0s3')[ni.AF_INET][0]['addr']
	return ip

def getMAC():
	mac = ni.ifaddresses('enp0s3')[ni.AF_LINK][0]['addr']
	return mac