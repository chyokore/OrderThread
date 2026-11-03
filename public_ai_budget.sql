CREATE TABLE IF NOT EXISTS ai_budget (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    remaining INTEGER NOT NULL CHECK (remaining >= 0)
);

-- Initial setup only. Reapplying this script never refills an existing budget.
INSERT OR IGNORE INTO ai_budget (id, remaining) VALUES (1, 0);
