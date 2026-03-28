from pathlib import Path

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
migrate = Migrate()


def ensure_storage(app):
    for key in ("DATA_DIR", "LIBRARY_DIR", "NEW_BOOKS_DIR", "COVERS_DIR"):
        Path(app.config[key]).mkdir(parents=True, exist_ok=True)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    ensure_storage(app)

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()

    return app
