from pathlib import Path

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

from config import Config

db = SQLAlchemy()
migrate = Migrate()


def ensure_storage(app):
    for key in ("DATA_DIR", "LIBRARY_DIR", "NEW_BOOKS_DIR", "COVERS_DIR", "DUPLICATE_BOOKS_DIR"):
        Path(app.config[key]).mkdir(parents=True, exist_ok=True)


def sync_sqlite_schema():
    engine = db.engine
    if engine.url.get_backend_name() != "sqlite":
        return

    db.create_all()

    inspector = inspect(engine)
    book_columns = {column["name"] for column in inspector.get_columns("book")} if inspector.has_table("book") else set()

    sqlite_book_columns = {
        "subtitle": "ALTER TABLE book ADD COLUMN subtitle VARCHAR(255)",
        "description": "ALTER TABLE book ADD COLUMN description TEXT",
        "isbn": "ALTER TABLE book ADD COLUMN isbn VARCHAR(32)",
        "publisher": "ALTER TABLE book ADD COLUMN publisher VARCHAR(255)",
        "published_date": "ALTER TABLE book ADD COLUMN published_date VARCHAR(32)",
        "language": "ALTER TABLE book ADD COLUMN language VARCHAR(32)",
        "page_count": "ALTER TABLE book ADD COLUMN page_count INTEGER",
        "rating": "ALTER TABLE book ADD COLUMN rating FLOAT",
        "needs_review": "ALTER TABLE book ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT 1",
        "is_favorite": "ALTER TABLE book ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0",
        "is_currently_reading": "ALTER TABLE book ADD COLUMN is_currently_reading BOOLEAN NOT NULL DEFAULT 0",
        "category_id": "ALTER TABLE book ADD COLUMN category_id INTEGER",
        "cover_image": "ALTER TABLE book ADD COLUMN cover_image VARCHAR(500)",
        "pdf_filename": "ALTER TABLE book ADD COLUMN pdf_filename VARCHAR(255)",
        "epub_filename": "ALTER TABLE book ADD COLUMN epub_filename VARCHAR(255)",
        "mobi_filename": "ALTER TABLE book ADD COLUMN mobi_filename VARCHAR(255)",
        "updated_at": "ALTER TABLE book ADD COLUMN updated_at DATETIME",
    }

    with engine.begin() as connection:
        for column_name, ddl in sqlite_book_columns.items():
            if column_name not in book_columns:
                connection.execute(text(ddl))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    ensure_storage(app)

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        sync_sqlite_schema()

    return app
