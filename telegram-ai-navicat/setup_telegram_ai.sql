-- Fresh-install schema for the Telegram AI + GitHub bot.
-- In Navicat, execute the whole script using a MySQL account allowed to create a database.

CREATE DATABASE IF NOT EXISTS telegram_ai
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE telegram_ai;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  telegram_id BIGINT NOT NULL,
  username VARCHAR(255) NULL,
  is_admin BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_telegram_id (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_history (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  telegram_id BIGINT NOT NULL,
  role ENUM('user', 'assistant') NOT NULL,
  message TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_chat_history_telegram_id_id (telegram_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bot_settings (
  setting_key VARCHAR(100) NOT NULL,
  setting_value TEXT NOT NULL,
  PRIMARY KEY (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- The bot reads ai_enabled from this table on startup.
-- Secrets (Telegram/OpenAI/GitHub tokens) must stay in the local .env file, not in MySQL.
INSERT IGNORE INTO bot_settings (setting_key, setting_value)
VALUES ('ai_enabled', '1'), ('model', 'gpt-4.1-mini');

SHOW TABLES;
SELECT setting_key, setting_value
FROM bot_settings
ORDER BY setting_key;
