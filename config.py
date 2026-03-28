import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
LIBRARY_DIR = Path(os.getenv("LIBRARY_DIR", DATA_DIR / "books"))
NEW_BOOKS_DIR = Path(os.getenv("NEW_BOOKS_DIR", DATA_DIR / "new_books"))
COVERS_DIR = Path(os.getenv("COVERS_DIR", DATA_DIR / "covers"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "library.db"))
CALIBRE_EBOOK_META = os.getenv("CALIBRE_EBOOK_META", "").strip()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-library-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH.as_posix()}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DATA_DIR = DATA_DIR
    LIBRARY_DIR = LIBRARY_DIR
    NEW_BOOKS_DIR = NEW_BOOKS_DIR
    COVERS_DIR = COVERS_DIR
    CALIBRE_EBOOK_META = CALIBRE_EBOOK_META
