from interface import ContractInterface
from sys import argv

# Change the client interface to a menu to decide which actions the client will perform


def register_client(client: ContractInterface):
    client.register()


def transfer_amount(client: ContractInterface, amount: int):
    client.transfer(
        to=client.w3.eth.accounts[2],
        amount=amount)


def request_storage(client: ContractInterface, amount: int):
    client.request_storage(amount)


def free_storage(client: ContractInterface):
    print("Seleccione la entrada que desea liberar ")
    # Enumerate posibilities
    posibilities = list(enumerate(client.remoteStorage.items()))
    for posib in posibilities:
        entry, (id, value) = posib
        print("{}) {} -> {} MB".format(entry, id, value))

    # for i, (k,v) in enumerate(client.remoteStorage.items()):
      #  print("{}) {} -> {} MB".format(i, k, v))

    choice = int(input(':'))

    # Get the values
    entry, (id, amount) = posibilities[choice]
    print('Selected entry: {} -> {} {} MB'.format(entry, id, amount))
    client.free_storage(id)


def request_cpu(client: ContractInterface, amount: int):
    client.request_computing_power(amount)

def free_cpu(client: ContractInterface):
    print("Seleccione la entrada que desea liberar ")
    # Enumerate posibilities
    posibilities = list(enumerate(client.remoteCPU.items()))
    for posib in posibilities:
        entry, (id, value) = posib
        print("{}) {} -> {}%".format(entry, id, value))

    # for i, (k,v) in enumerate(client.remoteStorage.items()):
      #  print("{}) {} -> {} MB".format(i, k, v))

    choice = int(input(':'))

    # Get the values
    entry, (id, amount) = posibilities[choice]
    print('Selected entry: {} -> {} {} MB'.format(entry, id, amount))
    client.free_computing_power(id)

def list_reservations(client: ContractInterface):
    print('Storage reservations:')
    print(client.remoteStorage)

    print()
    print('CPU reservations:')
    print(client.remoteCPU)

def force_error(client: ContractInterface):
    client.force_error()

def get_balances(client):
    w3 = client.w3
    accounts = w3.eth.accounts
    for account in accounts:
        balance = w3.fromWei(w3.eth.getBalance(account), 'ether')
        print('{} -> {} ETH'.format(account, balance))

ips = ['192.168.5.23', '192.168.2.66', '192.168.5.55']
macs = ['08:00:27:9e:7b:de', '08:00:27:9e:7b:da', '08:00:27:9e:7b:df']

def menu():

    client_registered = False

    """ Show interactive menu for more convenient testing """
    # Create the client interface
    client_number = int(argv[1])
    
    client = ContractInterface(client_number=client_number) 
    #if client_number > 1:
    #    # Tenemos que inventarnos la IP y la MAC
    #    client.IP = ips[client_number - 2]
    #    client.MAC = macs[client_number -2]

    print('Initialized contract interface for client')

    menu = """
    SELECCIONE UNA ACCION QUE EL CLIENTE DEBE REALIZAR:

    1) Registrarse  
    2) Realizar transferencia
    3) Peticion de almacenamiento
    4) Liberar almacenamiento
    5) Peticion de CPU
    6) Liberar CPU
    7) Listar reservas
    8) Force error
    9) Get balances

    """
    # Show the menu
    while True:
        choice = int(input(menu))
        # Registrar al usuario
        if choice == 1:
            if not client_registered:
                register_client(client)
                client_registered = True
            else:
                print('El cliente ya está registrado')
        # Realizar transferencia
        elif choice == 2:
            amount = int(input('Seleccione la cantidad a transferir: '))
            transfer_amount(client, amount)
        # Peticion de almacenamiento
        elif choice == 3:
            amount = int(input('Seleccione la cantidad a pedir: '))
            request_storage(client, amount)
        # Liberar almacenamiento
        elif choice == 4:
            free_storage(client)
        # Pedir cpu
        elif choice == 5:
            amount = int(input('Seleccione la cantidad a pedir: '))
            request_cpu(client, amount)
        # Liberar cpu
        elif choice == 6:
            free_cpu(client)
        # Listar reservas
        elif choice == 7:
            list_reservations(client)
        elif choice == 8:
            force_error(client)
        elif choice == 9:
            get_balances(client)
        else:
            print('Opción invalida')

        print()


def main():

    print('Instantiating ContractInterface')
    client = ContractInterface()

    print('Registering...')
    client.register()
    '''
    print("Transfering 50 IoT's")
    client.transfer(client.w3.eth.accounts[2], 50)'''

    # Request 5 GB. This one should be accepted
    print('Request 5 GB (even)')
    client.request_storage(5000)

    input('Press enter for freeing')
    id, _ = client.remoteStorage.popitem()
    client.free_storage(id)


if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print('Exiting...')
