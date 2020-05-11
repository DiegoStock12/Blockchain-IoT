pragma solidity ^0.4.2;

contract owned{
    address public owner;
    
    constructor() public{
        owner = msg.sender;
    }
    
    modifier onlyOwner{
        require(msg.sender == owner);
        _;
    }
    
    function transferOwnership(address newOwner) onlyOwner public{
        owner = newOwner;
    }
}

contract IoToken is owned{
    
    // Public variables
    string public name = "IoToken";
    string public symbol = "IOT";
    uint8 public decimals = 18;

    // storage management
    uint256 totalStorage; // Total storage available for clients in MB
    uint256 availableStorage; 

    // CPU management
    uint256 totalComputingPower = 100; // 100 is all the computing power available. Since solidity does not support floats we have to do it like this
    uint256 availableComputingPower = 100; // 1 - the amount used by the clients

    // Total coin supply
    uint256 totalSupply;
    
    //Mappings
    mapping(address => uint256) public balanceOf;
    mapping(address => bool) frozenAccount;

    // Mappings for resource usage
    mapping(address => uint256)  public storageUse;
    mapping (address => uint256)  public cpuUse;
    

    // Events produced by the keys
    event FrozenFunds(address target, bool frozen);
    // This generates a public event on the blockchain that will notify clients
    event Transfer(address indexed from, address indexed to, uint256 value);
    // This notifies that one user is registered
    event Register(address indexed account, string ip_address, string mac_address, uint256 balance);
    event RegisterResponse(bool accepted, address indexed account, string ip_address, string mac_address);
    // Event to get some storage
    event StoragePetition(address indexed account, uint256 amount);
    event StorageResponse(bool accepted, address indexed account, uint256 amount, string grantID);
    event FreeStorage(address indexed account, string grantID);
    // Event to get some CPU
    event CPUPetition(address indexed account, uint256 amount);
    event CPUResponse(bool accepted, address indexed account, uint256 amount, string grantID);
    event FreeComputingPower(address indexed account, string grantID);


    // Recibimos la cantidad de dinero con la que queremos inicializar el sistema
    constructor(
        uint256 _availableStorage,
        uint256 _initialSupply,
        address _centralMinter) onlyOwner public {
            availableStorage = _availableStorage;
            if (_centralMinter != 0) owner = _centralMinter;
            totalSupply = _initialSupply *10 * uint256(decimals);
            balanceOf[msg.sender] = totalSupply;
        }
        
    /**
     * Internal transfer
     */
    function transfer(address _from, address _to, uint _value) public {
        // require that the message sender is trying to transfer money from his own account
        require(_from == msg.sender);
        // Prevent transfer to 0x0 address. Use burn() instead
        require(_to != address(0x0));
        // Check if the sender has enough
        require(balanceOf[_from] >= _value);
        // Check for overflows
        require(balanceOf[_to] + _value >= balanceOf[_to]);
        require(!frozenAccount[msg.sender]);
        // Save this for an assertion in the future
        uint previousBalances = balanceOf[_from] + balanceOf[_to];
        // Subtract from the sender
        balanceOf[_from] -= _value;
        // Add the same to the recipient
        balanceOf[_to] += _value;
        emit Transfer(_from, _to, _value);
        // Asserts are used to use static analysis to find bugs in your code. They should never fail
        assert(balanceOf[_from] + balanceOf[_to] == previousBalances);
    }
    
    /**
     * Function with which the user registers for the first time
     */
    function registerFirstTime(string ip_address, string mac_address) public {
        // Mirar qué puedo exigir aquí
        emit Register(address(0), ip_address, mac_address, balanceOf[address(0)]);
    }
    /**
    * Function with which the users can register in the system 
    */
    function register(address _account, string ip_address, string mac_address) public {
        require(_account != address(0x0));
        
        // Give some money to it at time of registration
        balanceOf[_account] += 500;
        emit Register(_account, ip_address, mac_address, balanceOf[_account]);
    }

    /**
     * Function executed by the server to answer register requests
     */
    function answerRegisterRequest(bool _accepted, address _account, string _ip_address, string _mac_address ) onlyOwner public {

        if (_accepted){
            emit RegisterResponse(_accepted, _account, _ip_address, _mac_address);
        }
        else {
            emit RegisterResponse(_accepted, address(0), _ip_address, _mac_address);
        }

    } 


     /*
    * FUNTIONS TO TAKE CARE OF ALL OPERATIONS WHEN A CLIENT ASKS FOR STORAGE
    */

    /**
    * Function to ask for storage from the server.
    * The amount of storage will be given in MB
    */
    function getStorage(address _account, uint256 _amount) public {
        require(_account != address(0x0));

        // Require that the account is not frozen
        require (!frozenAccount[_account]);

        // Require that the balance is more than the cost
        //require (balanceOf[_account] >= 50 );// here we should calculate the cost

        // Require that we have enough storage to satisfy the question
        require (availableStorage - _amount > 0);

        // In case we satisfy all this we emit an Event so the server will know
        emit StoragePetition(_account, _amount);
    }

    /**
    * Function with which the server grants storage to the client
    */
    function answerStorageRequest(address _account, uint256 _amount, string _grantID, bool _accepted) onlyOwner public {
       
        // The request has to be accepted in order to decrement the memory
        if (_accepted){
            // We update the current amount available
            availableStorage -= _amount;
            // We then add the storage to the corresponding client
            storageUse[_account] += _amount;
            emit StorageResponse(_accepted, _account, _amount, _grantID);
        }

        // If the storage is not granted for whatever reason we respond that it was not accepted
        else {
            emit StorageResponse(_accepted, _account, _amount, '-1');
        }


    }

    /**
    * Function accessible to the clients for freeing storage
    */
    function freeStorage(address _account, string _grantID) public {

        // require that the user has storage
        require(storageUse[_account] != 0);

        // Emit petition event
        emit FreeStorage(_account, _grantID);
    }

    /**
    * Function used by the server to free storage after it has done its comprobations
    */
    function _freeStorage(address _account, uint256 _amountFreed) onlyOwner public {

        availableStorage += _amountFreed;
        storageUse[_account] -= _amountFreed;
    }



    /*
    * FUNTIONS TO TAKE CARE OF ALL OPERATIONS WHEN A CLIENT ASKS FOR COMPUTING POWER
    */

    /**
    * Function used by the client to ask for computing power
    */
    function getComputingPower(address _account, uint256 _amount) public {
        require(_account != address(0x0));

        // Require that the account is not frozen
        require (!frozenAccount[_account]);

        // Require that the balance is more than the cost
        require (balanceOf[_account] >= 50 );// here we should calculate the cost

        // Require that we have enough storage to satisfy the question
        //require (availableComputingPower - _amount > 0);

        // In case we satisfy all this we emit an Event so the server will know
        emit CPUPetition(_account, _amount);
    }

    /**
    * Function with which the server grants cpu to the client
    */
    function answerComputingPowerRequest(address _account, uint256 _amount, string _grantID, bool _accepted) onlyOwner public{

        if (_accepted) {
            // We update the current amount available
            availableComputingPower -= _amount;

            // We then add the storage to the corresponding client
            cpuUse[_account] += _amount;
            emit CPUResponse(_accepted, _account, _amount, _grantID);
        }
        else{
            emit CPUResponse(_accepted, _account, _amount, '-1');
        }

    }

    /**
    * Method accessible to the clients for freeing cpu
    */
    function freeComputingPower(address _account, string _grantID) public{
        
        // First filter
        require (cpuUse[_account] != 0);

        emit FreeComputingPower(_account, _grantID);
    }

    /*
    * Method used by the server to free storage after it has done its comprobations
    */
    function _freeComputingPower(address _account, uint256 _amountFreed) onlyOwner public {

        availableComputingPower += _amountFreed;
        cpuUse[_account] -= _amountFreed;
    }


    /**
     * Create new tokens
     */ 
    function mintToken(address target, uint256 mintedAmount) onlyOwner public {
        balanceOf[target] += mintedAmount;
        totalSupply += mintedAmount;
        emit Transfer(0, owner, mintedAmount);
        emit Transfer(owner, target, mintedAmount);
    }
    
    /**
     * Function used by the server to block some device's account in case of misbehavior
     */
    function freezeAccount(address target, bool freeze) onlyOwner  public {
        frozenAccount[target] = freeze;
        emit FrozenFunds(target, freeze);
    }
    
    
    /**
     * Function so that the server can update some client's balance
     * The increment boolean tells us if we should add or subtract
     *
     * This function will be used to update the balance periodically based on behavior
     * and to charge the clients for their requests
     */
    function updateBalance(address _account, uint256 amount, bool _increment) onlyOwner public {
        if (_increment){
            balanceOf[_account] += amount;
        }
        else{
            balanceOf[_account] -= amount;
        }
    }
        
        
        
    
}