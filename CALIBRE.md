# Calibre Integration

The importer can use Calibre's `ebook-meta` command to enrich imported books with:

- title
- author
- publisher
- description/comments
- ISBN
- language
- published date
- extracted cover image

## Docker usage

By default, Docker builds without Calibre.

To build the container with Calibre installed:

```powershell
$env:INSTALL_CALIBRE="1"
docker compose up --build
```

If you already have a compatible `ebook-meta` binary available in the container, you can point the app at it:

```powershell
$env:CALIBRE_EBOOK_META="/usr/bin/ebook-meta"
docker compose up --build
```

## Existing library enrichment

Once Calibre is available to the app, you can enrich already-imported books with:

```powershell
python scripts\enrich_books.py
```

That script fills in missing metadata where possible and extracts a cover before falling back to the generated placeholder.
