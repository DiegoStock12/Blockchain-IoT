-- Sql file that creates all the necessary 

-- Table to register clients
CREATE TABLE IF NOT EXISTS clients(
		account_address varchar(100) primary key,
		mac_address varchar(40) unique, 
		ip_address varchar(40) unique,
		priority int default 4,
		coin_balance float,
		credit int default 100 not null, -- the credit is initialized at 100
		isBlocked bool default false,
		isRegistered bool default false
        );

-- Table to keep track of storage allocations
CREATE TABLE IF NOT EXISTS storage_allocations(
    id varchar(100) primary key,
    account_address varchar(100) not null,
    amount int, 
    Foreign Key (account_address) references clients(account_address)
    );

-- Table to keep track of cpu allocations
CREATE TABLE IF NOT EXISTS cpu_allocations(
    id varchar(100) primary key,
    account_address varchar(100) not null,
    amount int, 
    Foreign Key (account_address) references clients(account_address)
    );

-- Table of the charges pending to return to the clients
CREATE TABLE IF NOT EXISTS pending_charges(
    id varchar(100) primary key,
    account_address varchar(100),
    charge int
);

/*delimiter //
CREATE TRIGGER IF NOT EXISTS update_mem alloc 
AFTER INSERT OR UPDATE OR DELETE on storage_allocations
    FOR EACH ROW
    BEGIN
    UPDATE clients set */

    