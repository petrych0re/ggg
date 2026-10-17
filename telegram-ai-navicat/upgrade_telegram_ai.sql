-- Upgrade an existing telegram_ai database without deleting chat history.
-- Select/execute the entire script in Navicat Premium.
-- This script expects the existing users, chat_history, and bot_settings tables.

USE telegram_ai;

-- Add the chat-history lookup index only if it does not already exist.
SET @index_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'chat_history'
    AND index_name = 'idx_chat_history_telegram_id_id'
);

SET @migration_sql := IF(
  @index_exists = 0,
  'CREATE INDEX idx_chat_history_telegram_id_id ON chat_history (telegram_id, id)',
  'SELECT ''Index idx_chat_history_telegram_id_id already exists'' AS migration_status'
);

PREPARE migration_stmt FROM @migration_sql;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

-- Keep defaults present without overwriting any existing setting values.
INSERT IGNORE INTO bot_settings (setting_key, setting_value)
VALUES ('ai_enabled', '1'), ('model', 'gpt-4.1-mini');

SELECT 'Migration finished' AS migration_status;
SHOW INDEX FROM chat_history;
SELECT setting_key, setting_value
FROM bot_settings
ORDER BY setting_key;
