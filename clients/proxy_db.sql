-- Commands for creating the proxy database

CREATE TABLE IF NOT EXISTS devices(
    account varchar(100) primary_key,
    mac_address varchar(40) unique,
    ip_address varchar(40) unique,
);

-- Quizá aquí meter algún trigger
