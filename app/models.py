from app import db


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

    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    category = db.relationship("Category", backref=db.backref("books", lazy="select"))

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
