ALTER USER 'stadvdb'@'%' IDENTIFIED WITH 'mysql_native_password' BY 'stadvdb';
GRANT REPLICATION SLAVE ON *.* TO 'stadvdb'@'%';
FLUSH PRIVILEGES;

CHANGE MASTER TO 
  MASTER_HOST='source',
  MASTER_USER='stadvdb',
  MASTER_PASSWORD='stadvdb',
  MASTER_LOG_FILE='mysql-bin.000003',
  MASTER_LOG_POS=832;

START SLAVE;