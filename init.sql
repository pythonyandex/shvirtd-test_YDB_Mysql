CREATE DATABASE IF NOT EXISTS virtd;

USE virtd;

-- Создаем таблицу requests если не существует
CREATE TABLE IF NOT EXISTS requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    client_ip VARCHAR(45),
    request_ip VARCHAR(45),
    server_ip VARCHAR(45),
    request_date DATETIME
);
