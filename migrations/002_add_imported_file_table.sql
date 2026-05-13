CREATE TABLE IF NOT EXISTS imported_file (
    id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    format VARCHAR(16) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    file_size INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (sha256),
    FOREIGN KEY(book_id) REFERENCES book (id)
);

CREATE INDEX IF NOT EXISTS ix_imported_file_sha256 ON imported_file (sha256);
