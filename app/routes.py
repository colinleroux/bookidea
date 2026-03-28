from flask import Blueprint, render_template
from .models import Book

main = Blueprint("main", __name__)

@main.route("/")
def index():
    books = Book.query.all()
    return render_template("index.html", books=books)
