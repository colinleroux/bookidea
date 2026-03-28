# Library Atelier

Library Atelier is a personal-use Flask app for managing a home book collection with a simple Docker setup.

It is designed around a practical file-based workflow:

- you drop new `.pdf`, `.epub`, or `.mobi` files into an import folder
- the app imports them into the library
- one book can hold multiple formats
- the library is browsable as cards with search and filters
- imported metadata can be reviewed and corrected in the app

## Current features

- SQLite-based library database
- card-based homepage with search and category filtering
- nested categories and subcategories
- book detail pages with multiple download links
- one-click import from `data/new_books`
- support for a single book having PDF, EPUB, and MOBI formats
- generated fallback covers when no real cover is available
- manual cover upload from the edit screen
- review workflow for incomplete imports
- optional Calibre integration for richer metadata and cover extraction

## Project structure

- [app](app): Flask app code
- [data/books](data/books): imported library files
- [data/new_books](data/new_books): incoming files waiting to be imported
- [data/covers](data/covers): generated and uploaded cover images
- [scripts/import_books.py](scripts/import_books.py): import queue helper
- [scripts/enrich_books.py](scripts/enrich_books.py): enrich existing books with Calibre metadata/covers

## Running with Docker

Start the app with:

```powershell
docker compose up --build
```

The app is exposed at:

- `http://localhost:8008`

## Book import workflow

The current import flow is:

1. Put supported files into [data/new_books](data/new_books).
2. Open the app and click `Import New Books`.
3. The app moves those files into [data/books](data/books).
4. Metadata is extracted where possible.
5. If no usable cover is found, the app generates a colorful placeholder cover.
6. Imported books missing important information are marked `Needs review`.

You can then use `Manage Books` or `Review Imports` to clean up metadata.

## Multiple formats for the same book

The importer is designed for the common pattern where the same book exists in multiple formats:

- `Book Name.pdf`
- `Book Name.epub`
- `Book Name.mobi`

If the base filename matches, the importer treats them as one book record instead of creating duplicate cards. That means:

- one card on the homepage
- one book detail page
- multiple download links on the same book

## Covers

Cover handling currently works like this:

- if Calibre can extract a cover, the app uses that
- otherwise the app creates a generated fallback SVG cover
- if a book has no cover saved yet, viewing the book can trigger fallback generation
- you can upload a custom cover from the book edit screen

## Managing books

From `Manage Books`, you can:

- add books manually
- edit metadata
- assign categories
- upload or replace a cover image
- review incomplete imports
- delete books

From the edit page, delete supports two behaviors:

- delete only the database record
- delete the database record and also remove the actual stored files from `data/books`

The quick delete action in the `Manage Books` table currently removes the database record only.

## Categories

Categories support nesting such as:

- `Non-fiction / IT / Programming / Python`

Current category deletion rules are intentionally safe:

- categories cannot be deleted if books belong to that category tree
- categories cannot be deleted if they still have subcategories

The categories page shows when a category is in use and therefore cannot be deleted.

## Homepage links

The homepage cards include quick navigation:

- clicking the cover opens the book detail page
- clicking the category filters the library to that category/subcategory
- clicking the author shows all books by that author
- clicking `Needs review` opens the review list

## Optional Calibre integration

If Calibre's `ebook-meta` command is available, the importer can extract richer metadata and real covers.

It can help populate:

- title
- author
- publisher
- description/comments
- ISBN
- language
- published date
- cover image

### Enable Calibre in Docker

By default, Docker builds without Calibre.

To build the container with Calibre installed:

```powershell
$env:INSTALL_CALIBRE="1"
docker compose up --build
```

If you want to point the app at a specific `ebook-meta` binary:

```powershell
$env:CALIBRE_EBOOK_META="/usr/bin/ebook-meta"
docker compose up --build
```

### Enrich existing books

Once Calibre is available, you can enrich already-imported books with:

```powershell
python scripts\enrich_books.py
```

## Local development

You can also run the app locally with:

```powershell
python manage.py
```

## Notes

- This app is currently aimed at home/private use.
- Tailwind and Alpine are currently loaded by CDN for speed while the app is still evolving.
- The Docker setup currently focuses on app functionality first; a fuller frontend asset pipeline can be added later.
