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
from app.models import AppSetting, Book, Category, Tag, WantedBook
from app.services.importer import cover_file_path, ensure_placeholder_cover, import_new_books, slugify
from app.services.online_metadata import fetch_metadata_by_isbn, save_cover_from_url

main = Blueprint("main", __name__)

CATEGORY_EXCLUSIONS_SETTING = "homepage_excluded_category_ids"
WANTED_BOOK_STATUSES = {"wanted", "ordered", "acquired", "ignored"}


@main.route("/")
def index():
    return render_library_page()


@main.route("/favorites")
def favorites():
    return render_library_page(collection="favorites", heading="Favorites")


@main.route("/currently-reading")
def currently_reading():
    return render_library_page(collection="currently-reading", heading="Currently Reading")


@main.route("/source")
def source():
    query_text = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    sort = request.args.get("sort", "title").strip()
    direction = request.args.get("direction", "asc").strip()
    page = request.args.get("page", default=1, type=int)

    books_query = Book.query

    if query_text:
        search = f"%{query_text}%"
        books_query = books_query.filter(or_(Book.title.ilike(search), Book.author.ilike(search)))

    selected_category = None
    if category_id:
        selected_category = Category.query.get(category_id)
        if selected_category:
            category_ids = gather_category_ids(selected_category)
            books_query = books_query.filter(Book.category_id.in_(category_ids))

    sort_columns = {
        "title": Book.title,
        "author": Book.author,
        "category": Category.name,
    }
    sort = sort if sort in sort_columns else "title"
    direction = direction if direction in {"asc", "desc"} else "asc"
    sort_column = sort_columns[sort]

    if sort == "category":
        books_query = books_query.outerjoin(Book.category)

    ordered_column = sort_column.desc() if direction == "desc" else sort_column.asc()
    pagination = books_query.order_by(ordered_column, Book.title.asc()).paginate(page=page, per_page=100, error_out=False)
    wanted_matches = matching_wanted_books(query_text, selected_category)

    return render_template(
        "source.html",
        books=pagination.items,
        pagination=pagination,
        categories=Category.query.order_by(Category.name.asc()).all(),
        query_text=query_text,
        selected_category=selected_category,
        sort=sort,
        direction=direction,
        wanted_matches=wanted_matches,
    )


@main.route("/want-list", methods=["GET", "POST"])
def want_list():
    if request.method == "POST":
        wanted_book = WantedBook()
        populate_wanted_book_from_form(wanted_book, request.form)
        db.session.add(wanted_book)
        db.session.commit()
        flash("Wanted book added.", "success")
        return redirect(url_for("main.want_list"))

    query_text = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    status_filter = request.args.get("status", "active").strip()
    sort = request.args.get("sort", "author").strip()
    direction = request.args.get("direction", "asc").strip()
    page = request.args.get("page", default=1, type=int)

    wanted_query = filtered_wanted_books_query(query_text, category_id, status_filter)
    sort_columns = {
        "title": WantedBook.title,
        "author": WantedBook.author,
        "status": WantedBook.status,
        "created": WantedBook.created_at,
    }
    sort = sort if sort in sort_columns else "author"
    direction = direction if direction in {"asc", "desc"} else "asc"
    sort_column = sort_columns[sort]
    ordered_column = sort_column.desc() if direction == "desc" else sort_column.asc()
    pagination = wanted_query.order_by(ordered_column, WantedBook.title.asc()).paginate(
        page=page,
        per_page=100,
        error_out=False,
    )

    selected_category = Category.query.get(category_id) if category_id else None
    return render_template(
        "want_list.html",
        wanted_books=pagination.items,
        pagination=pagination,
        categories=Category.query.order_by(Category.name.asc()).all(),
        query_text=query_text,
        selected_category=selected_category,
        status_filter=status_filter,
        sort=sort,
        direction=direction,
        status_options=sorted(WANTED_BOOK_STATUSES),
    )


@main.route("/want-list/<int:wanted_book_id>/edit", methods=["GET", "POST"])
def edit_wanted_book(wanted_book_id):
    wanted_book = WantedBook.query.get_or_404(wanted_book_id)

    if request.method == "POST":
        populate_wanted_book_from_form(wanted_book, request.form)
        db.session.commit()
        flash("Wanted book updated.", "success")
        return redirect(url_for("main.want_list"))

    return render_template(
        "wanted_book_form.html",
        wanted_book=wanted_book,
        categories=Category.query.order_by(Category.name.asc()).all(),
        status_options=sorted(WANTED_BOOK_STATUSES),
    )


@main.route("/want-list/<int:wanted_book_id>/delete", methods=["POST"])
def delete_wanted_book(wanted_book_id):
    wanted_book = WantedBook.query.get_or_404(wanted_book_id)
    db.session.delete(wanted_book)
    db.session.commit()
    flash("Wanted book deleted.", "success")
    return redirect(url_for("main.want_list"))


@main.route("/want-list/<int:wanted_book_id>/acquired", methods=["POST"])
def mark_wanted_book_acquired(wanted_book_id):
    wanted_book = WantedBook.query.get_or_404(wanted_book_id)
    wanted_book.status = "acquired"
    db.session.commit()
    flash("Wanted book marked as acquired.", "success")
    return redirect(request.referrer or url_for("main.want_list"))


def render_library_page(collection=None, heading="Library"):
    query_text = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    author_name = request.args.get("author", "").strip()
    tag_slug = request.args.get("tag", "").strip()
    page = request.args.get("page", default=1, type=int)

    books_query = Book.query

    if collection == "favorites":
        books_query = books_query.filter(Book.is_favorite.is_(True))
    elif collection == "currently-reading":
        books_query = books_query.filter(Book.is_currently_reading.is_(True))

    if query_text:
        search = f"%{query_text}%"
        books_query = books_query.filter(or_(Book.title.ilike(search), Book.author.ilike(search)))

    selected_category = None
    if category_id:
        selected_category = Category.query.get(category_id)
        if selected_category:
            category_ids = gather_category_ids(selected_category)
            books_query = books_query.filter(Book.category_id.in_(category_ids))
    elif collection is None:
        excluded_category_ids = get_excluded_homepage_category_tree_ids()
        if excluded_category_ids:
            books_query = books_query.filter(
                or_(Book.category_id.is_(None), Book.category_id.notin_(excluded_category_ids))
            )

    if author_name:
        books_query = books_query.filter(Book.author == author_name)

    selected_tag = None
    if tag_slug:
        selected_tag = Tag.query.filter_by(slug=tag_slug).first()
        if selected_tag:
            books_query = books_query.join(Book.tags).filter(Tag.id == selected_tag.id)

    pagination = books_query.order_by(Book.title.asc()).paginate(page=page, per_page=24, error_out=False)
    books = pagination.items
    categories = Category.query.order_by(Category.name.asc()).all()
    endpoint = {
        "favorites": "main.favorites",
        "currently-reading": "main.currently_reading",
    }.get(collection, "main.index")

    return render_template(
        "index.html",
        books=books,
        pagination=pagination,
        categories=categories,
        query_text=query_text,
        selected_category=selected_category,
        author_name=author_name,
        selected_tag=selected_tag,
        current_collection=collection or "library",
        page_heading=heading,
        page_endpoint=endpoint,
        rating_stars=rating_stars,
    )


@main.route("/books/<int:book_id>")
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=book)


@main.route("/manage/books")
def manage_books():
    review_only = request.args.get("review") == "1"
    status_filter = request.args.get("status", "").strip()
    query_text = request.args.get("q", "").strip()
    page = request.args.get("page", default=1, type=int)

    if review_only:
        status_filter = "needs_review"

    books_query = Book.query

    if status_filter == "needs_review":
        books_query = books_query.filter_by(needs_review=True)
    elif status_filter == "ready":
        books_query = books_query.filter_by(needs_review=False)

    if query_text:
        search = f"%{query_text}%"
        books_query = books_query.filter(or_(Book.title.ilike(search), Book.author.ilike(search)))

    pagination = (
        books_query.order_by(Book.needs_review.desc(), Book.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )

    return render_template(
        "manage_books.html",
        books=pagination.items,
        pagination=pagination,
        review_only=review_only,
        status_filter=status_filter,
        query_text=query_text,
        pending_imports=count_pending_imports(),
        review_count=Book.query.filter_by(needs_review=True).count(),
    )


@main.route("/manage/books/new", methods=["GET", "POST"])
def new_book():
    if request.method == "POST":
        book = Book()
        db.session.add(book)
        populate_book_from_form(book, request.form)
        db.session.commit()
        flash("Book created.", "success")
        return redirect(url_for("main.manage_books"))

    return render_template(
        "book_form.html",
        book=None,
        categories=Category.query.order_by(Category.name.asc()).all(),
        tags=Tag.query.order_by(Tag.name.asc()).all(),
        form_action=url_for("main.new_book"),
        page_title="Add Book",
    )


@main.route("/manage/books/<int:book_id>/edit", methods=["GET", "POST"])
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    review_mode = request.args.get("review") == "1"
    next_review_book = get_next_review_book(book.id)

    if request.method == "POST":
        action = request.form.get("action", "save")
        review_mode = request.form.get("review_mode") == "1"
        populate_book_from_form(book, request.form)
        db.session.commit()
        flash("Book updated.", "success")
        if action == "save_next" and review_mode:
            next_review_book = get_next_review_book(book.id)
            if next_review_book:
                return redirect(url_for("main.edit_book", book_id=next_review_book.id, review=1))
            flash("No more books currently need review.", "info")
            return redirect(url_for("main.manage_books", review=1))
        if action == "save_return" and review_mode:
            return redirect(url_for("main.manage_books", review=1))
        return redirect(url_for("main.book_detail", book_id=book.id))

    return render_template(
        "book_form.html",
        book=book,
        categories=Category.query.order_by(Category.name.asc()).all(),
        tags=Tag.query.order_by(Tag.name.asc()).all(),
        form_action=url_for("main.edit_book", book_id=book.id, review=1) if review_mode else url_for("main.edit_book", book_id=book.id),
        page_title=f"Edit {book.title}",
        review_mode=review_mode,
        next_review_book=next_review_book,
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


@main.route("/manage/books/<int:book_id>/fetch-details", methods=["POST"])
def fetch_book_details(book_id):
    book = Book.query.get_or_404(book_id)
    redirect_args = {"review": 1} if request.args.get("review") == "1" else {}

    if not book.isbn:
        flash("Add an ISBN before trying to fetch details online.", "error")
        return redirect(url_for("main.edit_book", book_id=book.id, **redirect_args))

    metadata = fetch_metadata_by_isbn(book.isbn)
    if not metadata:
        flash("No online details were found for that ISBN.", "error")
        return redirect(url_for("main.edit_book", book_id=book.id, **redirect_args))

    applied_fields = []
    for field in ("title", "subtitle", "author", "publisher", "published_date", "page_count", "description"):
        incoming = metadata.get(field)
        existing = getattr(book, field)
        if incoming and not existing:
            setattr(book, field, incoming)
            applied_fields.append(field)

    if not book.cover_image and metadata.get("cover_url"):
        saved_cover = save_cover_from_url(book, metadata["cover_url"])
        if saved_cover:
            book.cover_image = saved_cover
            applied_fields.append("cover")

    db.session.commit()

    if applied_fields:
        flash(f"Online details added: {', '.join(applied_fields)}.", "success")
    else:
        flash("Online details were found, but your current values were already populated.", "info")

    return redirect(url_for("main.edit_book", book_id=book.id, **redirect_args))


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
    excluded_category_ids = get_excluded_homepage_category_ids()
    category_rows = [
        {
            "category": category,
            "tree_book_count": count_books_in_category_tree(category),
            "has_children": bool(category.children),
            "is_homepage_excluded": category.id in excluded_category_ids,
        }
        for category in categories
    ]
    return render_template(
        "manage_categories.html",
        categories=categories,
        category_rows=category_rows,
        excluded_category_ids=excluded_category_ids,
    )


@main.route("/manage/categories/homepage-exclusions", methods=["POST"])
def update_homepage_category_exclusions():
    valid_category_ids = {category.id for category in Category.query.with_entities(Category.id).all()}
    selected_ids = []

    for raw_category_id in request.form.getlist("excluded_category_ids"):
        try:
            category_id = int(raw_category_id)
        except (TypeError, ValueError):
            continue
        if category_id in valid_category_ids:
            selected_ids.append(category_id)

    AppSetting.set_json(CATEGORY_EXCLUSIONS_SETTING, sorted(set(selected_ids)))
    db.session.commit()
    flash("Homepage category exclusions updated.", "success")
    return redirect(url_for("main.manage_categories"))


@main.route("/manage/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    descendant_book_count = count_books_in_category_tree(category)

    if descendant_book_count:
        flash(
            f"Category cannot be deleted because {descendant_book_count} book(s) belong to this category tree.",
            "error",
        )
        return redirect(url_for("main.manage_categories"))

    if category.children:
        flash("Category cannot be deleted while it still has subcategories.", "error")
        return redirect(url_for("main.manage_categories"))

    db.session.delete(category)
    db.session.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("main.manage_categories"))


@main.route("/manage/tags", methods=["GET", "POST"])
def manage_tags():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        tag_id = request.form.get("tag_id", type=int)

        if not name:
            flash("Tag name is required.", "error")
            return redirect(url_for("main.manage_tags"))

        slug = slugify(name)
        existing = Tag.query.filter_by(slug=slug).first()

        if tag_id:
            tag = Tag.query.get_or_404(tag_id)
            if existing and existing.id != tag.id:
                flash("A tag with that name already exists.", "error")
                return redirect(url_for("main.manage_tags"))
            tag.name = name
            tag.slug = slug
            db.session.commit()
            flash("Tag updated.", "success")
            return redirect(url_for("main.manage_tags"))

        if existing:
            flash("That tag already exists.", "error")
            return redirect(url_for("main.manage_tags"))

        db.session.add(Tag(name=name, slug=slug))
        db.session.commit()
        flash("Tag created.", "success")
        return redirect(url_for("main.manage_tags"))

    tags = Tag.query.order_by(Tag.name.asc()).all()
    return render_template("manage_tags.html", tags=tags)


@main.route("/manage/tags/<int:tag_id>/delete", methods=["POST"])
def delete_tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    usage_count = len(tag.books)

    if usage_count:
        flash(f"Tag cannot be deleted because it is used by {usage_count} book(s).", "error")
        return redirect(url_for("main.manage_tags"))

    db.session.delete(tag)
    db.session.commit()
    flash("Tag deleted.", "success")
    return redirect(url_for("main.manage_tags"))


@main.route("/import", methods=["POST"])
def import_books():
    batch_size = request.form.get("batch_size", default=25, type=int) or 25
    result = import_new_books(limit=batch_size)
    processed_count = len(result["processed"])
    skipped_count = len(result["skipped"])

    if result["remaining"] > 0:
        return render_template(
            "import_progress.html",
            processed_count=processed_count,
            skipped_count=skipped_count,
            remaining_count=result["remaining"],
            batch_size=batch_size,
        )

    if processed_count:
        message = f"Imported or updated {processed_count} book files."
        if skipped_count:
            message += f" Quarantined {skipped_count} duplicate or conflicting file(s)."
        flash(f"{message} Import queue is now complete.", "success")
    elif skipped_count:
        flash(
            f"Quarantined {skipped_count} duplicate or conflicting file(s). Import queue is now complete.",
            "info",
        )
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


def count_books_in_category_tree(category):
    category_ids = gather_category_ids(category)
    return Book.query.filter(Book.category_id.in_(category_ids)).count()


def filtered_wanted_books_query(query_text="", category_id=None, status_filter="active"):
    wanted_query = WantedBook.query

    if query_text:
        search = f"%{query_text}%"
        wanted_query = wanted_query.filter(or_(WantedBook.title.ilike(search), WantedBook.author.ilike(search)))

    if category_id:
        selected_category = Category.query.get(category_id)
        if selected_category:
            wanted_query = wanted_query.filter(WantedBook.category_id.in_(gather_category_ids(selected_category)))

    if status_filter == "active":
        wanted_query = wanted_query.filter(WantedBook.status.in_(["wanted", "ordered"]))
    elif status_filter in WANTED_BOOK_STATUSES:
        wanted_query = wanted_query.filter(WantedBook.status == status_filter)

    return wanted_query


def matching_wanted_books(query_text, selected_category):
    if not query_text and not selected_category:
        return []

    wanted_query = WantedBook.query.filter(WantedBook.status.in_(["wanted", "ordered"]))

    if query_text:
        search = f"%{query_text}%"
        wanted_query = wanted_query.filter(or_(WantedBook.title.ilike(search), WantedBook.author.ilike(search)))

    if selected_category:
        wanted_query = wanted_query.filter(WantedBook.category_id.in_(gather_category_ids(selected_category)))

    return wanted_query.order_by(WantedBook.author.asc(), WantedBook.title.asc()).limit(25).all()


def count_pending_imports():
    new_books_dir = Path(current_app.config["NEW_BOOKS_DIR"])
    if not new_books_dir.exists():
        return 0

    count = 0
    for file_path in new_books_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in {".pdf", ".epub", ".mobi"}:
            count += 1
    return count


def get_excluded_homepage_category_ids():
    raw_ids = AppSetting.get_json(CATEGORY_EXCLUSIONS_SETTING, [])
    if not isinstance(raw_ids, list):
        return set()

    excluded_ids = set()
    for raw_id in raw_ids:
        try:
            excluded_ids.add(int(raw_id))
        except (TypeError, ValueError):
            continue
    return excluded_ids


def get_excluded_homepage_category_tree_ids():
    excluded_ids = get_excluded_homepage_category_ids()
    tree_ids = set()

    for category_id in excluded_ids:
        category = Category.query.get(category_id)
        if category:
            tree_ids.update(gather_category_ids(category))

    return tree_ids


def get_next_review_book(current_book_id):
    return (
        Book.query.filter(Book.needs_review.is_(True), Book.id != current_book_id)
        .order_by(Book.created_at.desc())
        .first()
    )


def rating_stars(rating):
    if rating is None:
        return None

    filled_count = max(0, min(5, int(float(rating) + 0.5)))
    return {
        "filled": filled_count,
        "empty": 5 - filled_count,
        "label": f"{float(rating):.1f} out of 5",
    }


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
    book.is_favorite = form.get("is_favorite") == "on"
    book.is_currently_reading = form.get("is_currently_reading") == "on"
    sync_book_tags(book, request.form.getlist("tag_ids"))


def populate_wanted_book_from_form(wanted_book, form):
    wanted_book.title = form.get("title", "").strip() or "Untitled"
    wanted_book.author = form.get("author", "").strip() or "Unknown"
    wanted_book.category_id = form.get("category_id", type=int) or None
    wanted_book.notes = form.get("notes", "").strip() or None
    wanted_book.source = form.get("source", "").strip() or None
    status = form.get("status", "wanted").strip()
    wanted_book.status = status if status in WANTED_BOOK_STATUSES else "wanted"


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


def sync_book_tags(book, raw_tag_ids):
    tag_ids = []
    for value in raw_tag_ids:
        try:
            tag_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    if not tag_ids:
        book.tags = []
        return

    book.tags = Tag.query.filter(Tag.id.in_(tag_ids)).order_by(Tag.name.asc()).all()


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
