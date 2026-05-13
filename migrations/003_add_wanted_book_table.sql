CREATE TABLE IF NOT EXISTS wanted_book (
    id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    notes TEXT,
    source VARCHAR(255),
    status VARCHAR(32) DEFAULT 'wanted' NOT NULL,
    category_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(category_id) REFERENCES category (id)
);

CREATE INDEX IF NOT EXISTS ix_wanted_book_title ON wanted_book (title);
CREATE INDEX IF NOT EXISTS ix_wanted_book_author ON wanted_book (author);
CREATE INDEX IF NOT EXISTS ix_wanted_book_status ON wanted_book (status);
CREATE INDEX IF NOT EXISTS ix_wanted_book_category_id ON wanted_book (category_id);
