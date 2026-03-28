from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from app import db
from app.models import Book, Category
from app.services.importer import cover_file_path, ensure_placeholder_cover, import_new_books, slugify

main = Blueprint("main", __name__)


@main.route("/")
def index():
    query_text = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)

    books_query = Book.query

    if query_text:
        search = f"%{query_text}%"
        books_query = books_query.filter(
            or_(Book.title.ilike(search), Book.author.ilike(search), Book.isbn.ilike(search))
        )

    selected_category = None
    if category_id:
        selected_category = Category.query.get(category_id)
        if selected_category:
            category_ids = gather_category_ids(selected_category)
            books_query = books_query.filter(Book.category_id.in_(category_ids))

    books = books_query.order_by(Book.title.asc()).all()
    categories = Category.query.order_by(Category.name.asc()).all()
    pending_imports = count_pending_imports()
    review_count = Book.query.filter_by(needs_review=True).count()

    return render_template(
        "index.html",
        books=books,
        categories=categories,
        pending_imports=pending_imports,
        review_count=review_count,
        query_text=query_text,
        selected_category=selected_category,
    )


@main.route("/books/<int:book_id>")
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=book)


@main.route("/manage/books")
def manage_books():
    review_only = request.args.get("review") == "1"
    books_query = Book.query
    if review_only:
        books_query = books_query.filter_by(needs_review=True)

    books = books_query.order_by(Book.created_at.desc()).all()
    return render_template("manage_books.html", books=books, review_only=review_only)


@main.route("/manage/books/new", methods=["GET", "POST"])
def new_book():
    if request.method == "POST":
        book = Book()
        populate_book_from_form(book, request.form)
        db.session.add(book)
        db.session.commit()
        flash("Book created.", "success")
        return redirect(url_for("main.manage_books"))

    return render_template(
        "book_form.html",
        book=None,
        categories=Category.query.order_by(Category.name.asc()).all(),
        form_action=url_for("main.new_book"),
        page_title="Add Book",
    )


@main.route("/manage/books/<int:book_id>/edit", methods=["GET", "POST"])
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)

    if request.method == "POST":
        populate_book_from_form(book, request.form)
        db.session.commit()
        flash("Book updated.", "success")
        return redirect(url_for("main.book_detail", book_id=book.id))

    return render_template(
        "book_form.html",
        book=book,
        categories=Category.query.order_by(Category.name.asc()).all(),
        form_action=url_for("main.edit_book", book_id=book.id),
        page_title=f"Edit {book.title}",
    )


@main.route("/manage/books/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    delete_files = request.form.get("delete_files") == "on"

    if delete_files:
        delete_book_files(book)

    db.session.delete(book)
    db.session.commit()
    if delete_files:
        flash("Book and associated files deleted.", "success")
    else:
        flash("Book deleted from the database.", "success")
    return redirect(url_for("main.manage_books"))


@main.route("/manage/categories", methods=["GET", "POST"])
def manage_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        parent_id = request.form.get("parent_id", type=int)

        if not name:
            flash("Category name is required.", "error")
            return redirect(url_for("main.manage_categories"))

        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while Category.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        category = Category(name=name, slug=slug, parent_id=parent_id or None)
        db.session.add(category)
        db.session.commit()
        flash("Category added.", "success")
        return redirect(url_for("main.manage_categories"))

    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template("manage_categories.html", categories=categories)


@main.route("/manage/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)

    if category.books:
        flash("Category cannot be deleted while books still use it.", "error")
        return redirect(url_for("main.manage_categories"))

    if category.children:
        flash("Category cannot be deleted while it still has subcategories.", "error")
        return redirect(url_for("main.manage_categories"))

    db.session.delete(category)
    db.session.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("main.manage_categories"))


@main.route("/import", methods=["POST"])
def import_books():
    result = import_new_books()
    processed_count = len(result["processed"])

    if processed_count:
        flash(f"Imported or updated {processed_count} book files.", "success")
    else:
        flash("No new supported book files were found to import.", "info")

    return redirect(url_for("main.index"))


@main.route("/files/<path:filename>")
def download_book_file(filename):
    return send_from_directory(current_app.config["LIBRARY_DIR"], filename, as_attachment=True)


@main.route("/books/<int:book_id>/cover")
def book_cover(book_id):
    book = Book.query.get_or_404(book_id)

    cover_path = cover_file_path(book.cover_image) if book.cover_image else None
    if not book.cover_image or not cover_path or not cover_path.exists():
        book.cover_image = ensure_placeholder_cover(book)
        db.session.commit()
    elif cover_path.suffix.lower() == ".svg":
        refreshed_cover = ensure_placeholder_cover(book)
        if refreshed_cover != book.cover_image:
            book.cover_image = refreshed_cover
            db.session.commit()

    return send_from_directory(current_app.config["COVERS_DIR"], Path(book.cover_image).name)


@main.route("/covers/<path:filename>")
def cover_image(filename):
    return send_from_directory(current_app.config["COVERS_DIR"], filename)


def gather_category_ids(category):
    ids = [category.id]
    for child in category.children:
        ids.extend(gather_category_ids(child))
    return ids


def count_pending_imports():
    new_books_dir = Path(current_app.config["NEW_BOOKS_DIR"])
    if not new_books_dir.exists():
        return 0

    count = 0
    for file_path in new_books_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in {".pdf", ".epub", ".mobi"}:
            count += 1
    return count


def populate_book_from_form(book, form):
    book.title = form.get("title", "").strip() or "Untitled"
    book.subtitle = form.get("subtitle", "").strip() or None
    book.author = form.get("author", "").strip() or "Unknown"
    book.description = form.get("description", "").strip() or None
    book.isbn = form.get("isbn", "").strip() or None
    book.publisher = form.get("publisher", "").strip() or None
    book.published_date = form.get("published_date", "").strip() or None
    book.language = form.get("language", "").strip() or None
    book.page_count = parse_int(form.get("page_count"))
    book.rating = parse_float(form.get("rating"))
    book.category_id = form.get("category_id", type=int) or None
    book.pdf_filename = form.get("pdf_filename", "").strip() or None
    book.epub_filename = form.get("epub_filename", "").strip() or None
    book.mobi_filename = form.get("mobi_filename", "").strip() or None
    book.cover_image = normalize_cover_path(form.get("cover_image", "").strip()) or book.cover_image
    uploaded_cover = request.files.get("cover_file")
    if uploaded_cover and uploaded_cover.filename:
        book.cover_image = save_uploaded_cover(book, uploaded_cover)
    elif not book.cover_image:
        book.cover_image = ensure_placeholder_cover(book)
    book.needs_review = form.get("needs_review") == "on"


def normalize_cover_path(value):
    if not value:
        return None
    if value.startswith("covers/"):
        return value
    return f"covers/{Path(value).name}"


def parse_int(value):
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(value):
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def delete_book_files(book):
    library_dir = Path(current_app.config["LIBRARY_DIR"])
    for filename in (book.pdf_filename, book.epub_filename, book.mobi_filename):
        if not filename:
            continue
        file_path = library_dir / filename
        if file_path.exists() and file_path.is_file():
            file_path.unlink()


def save_uploaded_cover(book, uploaded_cover):
    extension = Path(secure_filename(uploaded_cover.filename)).suffix.lower() or ".jpg"
    filename = f"{slugify(f'{book.title}-{book.author}')}{extension}"
    destination = Path(current_app.config["COVERS_DIR"]) / filename
    counter = 1

    while destination.exists():
        filename = f"{slugify(f'{book.title}-{book.author}')}-{counter}{extension}"
        destination = Path(current_app.config["COVERS_DIR"]) / filename
        counter += 1

    uploaded_cover.save(destination)
    return f"covers/{filename}"
