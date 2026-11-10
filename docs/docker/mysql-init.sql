-- ===============================================================
-- 演示环境的 MySQL 初始化脚本
-- 由 docker-entrypoint-initdb.d 在容器首次启动时自动执行。
-- 开发环境不需要它：默认走 SQLite，零配置。
-- ===============================================================

CREATE DATABASE IF NOT EXISTS smarttrip
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

-- 应用账号只授予本库权限，不给 root
CREATE USER IF NOT EXISTS 'smarttrip'@'%' IDENTIFIED BY 'smarttrip';

GRANT ALL PRIVILEGES ON smarttrip.* TO 'smarttrip'@'%';

FLUSH PRIVILEGES;
