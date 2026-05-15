import json
from pathlib import Path

from flask import current_app, has_app_context
from app import db


book_tags = db.Table(
    "book_tags",
    db.Column("book_id", db.Integer, db.ForeignKey("book.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    parent = db.relationship(
        "Category",
        remote_side=[id],
        backref=db.backref("children", lazy="select"),
    )

    def full_name(self):
        names = [self.name]
        current = self.parent
        while current:
            names.append(current.name)
            current = current.parent
        return " / ".join(reversed(names))

    def __repr__(self):
        return f"<Category {self.full_name()}>"


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(90), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def __repr__(self):
        return f"<Tag {self.name}>"


class AppSetting(db.Model):
    key = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    def json_value(self, default=None):
        if not self.value:
            return default
        try:
            return json.loads(self.value)
        except json.JSONDecodeError:
            return default

    @classmethod
    def get_json(cls, key, default=None):
        setting = cls.query.get(key)
        if not setting:
            return default
        return setting.json_value(default)

    @classmethod
    def set_json(cls, key, value):
        setting = cls.query.get(key)
        serialized = json.dumps(value)
        if setting:
            setting.value = serialized
        else:
            db.session.add(cls(key=key, value=serialized))


class ImportedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    format = db.Column(db.String(16), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False, unique=True, index=True)
    file_size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    book = db.relationship(
        "Book",
        backref=db.backref("imported_files", lazy="select", cascade="all, delete-orphan"),
    )

    def __repr__(self):
        return f"<ImportedFile {self.format} {self.stored_filename}>"


class WantedBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False, default="Unknown")
    notes = db.Column(db.Text)
    source = db.Column(db.String(255))
    status = db.Column(db.String(32), nullable=False, default="wanted")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    category = db.relationship("Category", backref=db.backref("wanted_books", lazy="select"))

    def __repr__(self):
        return f"<WantedBook {self.title} by {self.author}>"


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    subtitle = db.Column(db.String(255))
    author = db.Column(db.String(255), nullable=False, default="Unknown")
    description = db.Column(db.Text)
    isbn = db.Column(db.String(32))
    publisher = db.Column(db.String(255))
    published_date = db.Column(db.String(32))
    language = db.Column(db.String(32))
    page_count = db.Column(db.Integer)
    rating = db.Column(db.Float)
    needs_review = db.Column(db.Boolean, nullable=False, default=True)
    is_favorite = db.Column(db.Boolean, nullable=False, default=False)
    is_currently_reading = db.Column(db.Boolean, nullable=False, default=False)

    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    category = db.relationship("Category", backref=db.backref("books", lazy="select"))

    tags = db.relationship("Tag", secondary=book_tags, lazy="select", backref=db.backref("books", lazy="select"))

    cover_image = db.Column(db.String(500))
    pdf_filename = db.Column(db.String(255))
    epub_filename = db.Column(db.String(255))
    mobi_filename = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    @property
    def primary_format(self):
        formats = self.available_formats()
        if formats:
            return formats[0][0]
        return "Unknown"

    @property
    def tag_names(self):
        return ", ".join(tag.name for tag in sorted(self.tags, key=lambda item: item.name.lower()))

    def available_formats(self):
        formats = []
        if self.has_stored_file(self.pdf_filename):
            formats.append(("PDF", self.pdf_filename))
        if self.has_stored_file(self.epub_filename):
            formats.append(("EPUB", self.epub_filename))
        if self.has_stored_file(self.mobi_filename):
            formats.append(("MOBI", self.mobi_filename))
        return formats

    def has_stored_file(self, filename):
        if not filename:
            return False
        if not has_app_context():
            return True

        library_dir = Path(current_app.config["LIBRARY_DIR"]).resolve()
        file_path = (library_dir / filename).resolve()

        try:
            file_path.relative_to(library_dir)
        except ValueError:
            return False

        return file_path.is_file()

    def __repr__(self):
        return f"<Book {self.title} by {self.author}>"
