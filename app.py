from flask import Flask, render_template, request

import db

# Create an application instance.
# __name__ is a built-in Python variable holding the current module's name.
# Flask uses it to figure out where the app lives, so it can locate
# related files (templates, static assets) later.
app = Flask(__name__)

# A "route" maps a URL path to a function.
# @app.route("/") means: when someone visits the root URL ("/"),
# run the function firectly below. The @ syntax is a "decorator" -
# a way to attach behavior to a function. For now, just read it as
# "this function handles requests to /".
@app.route("/")
def home():
    # request.args holds the URL query string values (the part after "?")
    # .get("search", "") means: fetch the value named "search",
    # or default to an empty string "" if it's not there.
    # The default is what makes the box optional -  no search yet? Show everything.
    search = request.args.get("search", "")

    # Pass the term straight into your existing function.
    # Empty string still matches everything, so the first page load is unchanged.
    cards = db.search_cards(search)

    # Pass the search term back to the template too, so we can keep it
    # displayed in the box after searching (a nice touch - the user sees
    # what they searched for).
    return render_template("home.html", cards=cards, search=search)