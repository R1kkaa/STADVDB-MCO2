ALTER USER 'stadvdb'@'%' IDENTIFIED WITH 'mysql_native_password' BY 'stadvdb';
GRANT REPLICATION SLAVE ON *.* TO 'stadvdb'@'%';
FLUSH PRIVILEGES;
SHOW MASTER STATUS;