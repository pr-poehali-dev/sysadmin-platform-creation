CREATE TABLE IF NOT EXISTS proxy_log (
  id SERIAL PRIMARY KEY,
  target TEXT NOT NULL,
  status INT,
  response TEXT,
  ts TIMESTAMP DEFAULT NOW()
);