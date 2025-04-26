-- Create Schema Versioning Table
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    description TEXT
);

-- Check current schema version before applying changes
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_version WHERE version = 1) THEN

        -- Stock Table
        CREATE TABLE stock (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(10) NOT NULL,
            name VARCHAR(100),
            UNIQUE (symbol)
        );

        -- Users Table
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL
        );

        -- Transaction Table
        CREATE TABLE transaction (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            stock_id INTEGER REFERENCES stock(id) NOT NULL,
            date Date NOT NULL,
            type VARCHAR(4) CHECK (type IN ('buy', 'sell')) NOT NULL,
            units NUMERIC(12, 4),
            price NUMERIC(12, 4),
            value NUMERIC(14, 4),
            fee NUMERIC(10, 4),
            cost NUMERIC(14, 4),
            fy VARCHAR(10)
        );

        -- Insert Initial Version Record
        INSERT INTO schema_version (version, description) VALUES (1, 'Initial schema creation');

    END IF;
END $$;
