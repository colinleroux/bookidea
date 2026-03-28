from app import db

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(255))
    author = db.Column(db.String(255))

    filename = db.Column(db.String(500), unique=True)
    file_path = db.Column(db.String(500))

    file_type = db.Column(db.String(10))  # pdf, epub, mobi

    category = db.Column(db.String(100))
    description = db.Column(db.Text)

    created_at = db.Column(db.DateTime, server_default=db.func.now())