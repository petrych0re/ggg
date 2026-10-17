-- 💗 Cute Control Panel — Telegram AI Bot
-- Jalankan seluruh skrip ini di Navicat setelah memilih database telegram_ai.
--
-- Ubah HANYA nilai @cute_action di bawah, lalu klik Run:
--   'status'                  = lihat status saat ini (default)
--   'on'                      = nyalakan AI
--   'off'                     = matikan AI
--   'model:gpt-4.1-mini'      = ganti model AI (harus tersedia di akun API lu)
--
-- Contoh model lain boleh ditulis sebagai 'model:NAMA_MODEL' jika API mendukungnya.
-- Perubahan AI ON/OFF dan model dibaca bot saat pesan baru masuk, tanpa restart,
-- selama MYSQL_ENABLED=1 dan bot memakai versi kode terbaru.

USE telegram_ai;

SET @cute_action := 'status'; -- <-- EDIT BAGIAN INI SAJA

-- Update status AI bila action = on/off.
INSERT INTO bot_settings (setting_key, setting_value)
SELECT
  'ai_enabled',
  CASE WHEN @cute_action = 'on' THEN '1' ELSE '0' END
WHERE @cute_action IN ('on', 'off')
ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);

-- Update model bila action diawali "model:".
SET @cute_model := CASE
  WHEN LEFT(@cute_action, 6) = 'model:' THEN SUBSTRING(@cute_action, 7)
  ELSE ''
END;

INSERT INTO bot_settings (setting_key, setting_value)
SELECT 'model', @cute_model
WHERE @cute_model REGEXP '^[A-Za-z0-9._:-]{1,100}$'
ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value);

-- Tampilkan status terkini setelah action diproses.
SELECT
  CASE
    WHEN setting_key = 'ai_enabled' AND setting_value = '1' THEN '💚 AI NYALA'
    WHEN setting_key = 'ai_enabled' AND setting_value = '0' THEN '💤 AI OFF'
    ELSE setting_value
  END AS cute_status,
  setting_key,
  setting_value
FROM bot_settings
WHERE setting_key IN ('ai_enabled', 'model')
ORDER BY FIELD(setting_key, 'ai_enabled', 'model');
