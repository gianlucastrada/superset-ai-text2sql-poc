-- Utente usato da Superset e dall'IA per i dati di vendita: SOLO LETTURA.
-- Anche se il modello generasse una query di modifica, Postgres la rifiuterebbe.

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE vendite TO ai_reader;
GRANT USAGE ON SCHEMA public TO ai_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ai_reader;   -- include la vista v_vendite
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ai_reader;

ALTER ROLE ai_reader SET default_transaction_read_only = on;
ALTER ROLE ai_reader SET statement_timeout = '30s';
