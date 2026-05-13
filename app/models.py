import json

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
        if self.pdf_filename:
            return "PDF"
        if self.epub_filename:
            return "EPUB"
        if self.mobi_filename:
            return "MOBI"
        return "Unknown"

    @property
    def tag_names(self):
        return ", ".join(tag.name for tag in sorted(self.tags, key=lambda item: item.name.lower()))

    def available_formats(self):
        formats = []
        if self.pdf_filename:
            formats.append(("PDF", self.pdf_filename))
        if self.epub_filename:
            formats.append(("EPUB", self.epub_filename))
        if self.mobi_filename:
            formats.append(("MOBI", self.mobi_filename))
        return formats

    def __repr__(self):
        return f"<Book {self.title} by {self.author}>"
