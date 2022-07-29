import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    table = db.execute("SELECT symb, name, sum(shares) FROM my WHERE userID == ? group by symb", session['user_id'])
    total = db.execute ("SELECT cash FROM users WHERE id == ?", session['user_id'])
    sum = 0
    for row in table:
        sum = sum + (lookup(row["symb"])["price"] * row["sum(shares)"])
    return render_template("index.html", table=table, lookup=lookup, total=total, sum=sum)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol1 = request.form.get("symbol")
        symbol = symbol1.upper()
        shares = request.form.get("shares")
        stock = lookup(symbol)
        if not symbol or stock == None:
            return apology("no symbol entered or no such stock symbol exists", 403)
        if not shares.isnumeric() or int(shares) < 1 or not shares:
            return apology("no shares entered or shares is not a positive integer", 403)
        # Check price
        price = stock["price"]
        # Check user balance
        balance = db.execute("SELECT cash FROM users WHERE id == ?", session["user_id"])
        if balance[0]["cash"] < (price * int(shares)):
            return apology("No money", 403)

        total_price = stock["price"] * int(shares)
        portfolio = db.execute("INSERT INTO portfolio (usernameID, symbol, stock, price, number_of_shares, total_price, stat) VALUES(?, ?, ?, ?, ?, ?, ?)", session["user_id"],stock["symbol"], stock["name"], stock["price"], int(shares), total_price, "buy")
        x = balance[0]["cash"] - total_price
        update = db.execute("UPDATE users SET cash == ? WHERE id == ?", x, session["user_id"])

        my_symbol = db.execute("SELECT symb FROM my WHERE userID = ? AND symb = ?", session["user_id"], symbol)
        my_shares = db.execute("SELECT shares FROM my WHERE userID = ? AND symb = ?", session["user_id"], symbol)

        if len(my_symbol) >= 1:
            if symbol == my_symbol[0]["symb"]:
                new_shares = my_shares[0]["shares"] + int(shares)
                db.execute("UPDATE my SET shares = ? WHERE userID = ? AND symb = ?", new_shares, session["user_id"], symbol)
        else:
            db.execute("INSERT INTO my (userID, symb, name, shares) VALUES(?, ?, ?, ?)", session["user_id"], stock["symbol"], stock["name"], int(shares))

        return render_template("buy.html")
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    table = db.execute("SELECT symbol, stock, price, number_of_shares, stat, data_time FROM portfolio WHERE usernameID == ? ORDER BY data_time DESC", session['user_id'])
    return render_template("history.html", table=table)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        if stock != None:
            return render_template("quoted.html", name = stock)
        return apology("the stock does not exist", 403)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        #row = db.execute("SELECT username FROM users WHERE ? IN username", request.form.get("username"))

        if not username or db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username")):
            return apology("must provide username", 403)

        if not password or password != confirmation:
            return apology("a password must be specified or the two passwords do not match", 403)
        hash = generate_password_hash(password, method="pbkdf2:sha256")
        table = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock = lookup(symbol)
        my = db.execute("SELECT symb FROM my WHERE userID = ?", session["user_id"])
        sumShares = db.execute("SELECT shares FROM my WHERE userID = ? AND symb = ?", session["user_id"], symbol.upper())
        if not symbol:
            return apology("not symbol", 403)
        i=0
        for row in my:
            if symbol.upper() == row["symb"]:
                i+=1
        if i <= 0:
            return apology("you not have this stocks", 403)
        if not shares.isnumeric() or int(shares) < 1:
            return apology("proble with shares", 403)
        if int(shares) > sumShares[0]["shares"]:
            return apology("not have", 403)

        # Check price
        price = stock["price"]

        balance = db.execute("SELECT cash FROM users WHERE id == ?", session["user_id"])
        total_price = stock["price"] * int(shares)
        portfolio = db.execute("INSERT INTO portfolio (usernameID, symbol, stock, price, number_of_shares, total_price, stat) VALUES(?, ?, ?, ?, ?, ?, ?)", session["user_id"],stock["symbol"], stock["name"], stock["price"], int(shares), total_price, "sell")

        new_balance = balance[0]["cash"] + total_price
        update = db.execute("UPDATE users SET cash == ? WHERE id == ?", new_balance, session["user_id"])
        my_shares = db.execute("SELECT shares FROM my WHERE userID = ? AND symb = ?", session["user_id"], symbol.upper())
        new_shares = int(my_shares[0]["shares"]) - int(shares)
        db.execute("UPDATE my SET shares = ? WHERE userID = ? AND symb = ?", new_shares, session["user_id"], symbol.upper())

        check = db.execute("SELECT shares FROM my WHERE userID = ? AND symb = ?", session["user_id"], symbol.upper())
        if check[0]["shares"] == 0:
            db.execute("DELETE FROM my WHERE userID = ? AND symb = ?", session["user_id"], symbol.upper())
            
        return render_template("sell.html")
    else:
        return render_template("sell.html")
