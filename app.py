import os
import sqlite3

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


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
    # user id
    user_id = session["user_id"]

    # query to user money
    rows = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = rows[0]["cash"]

    # query of the user holding
    holdings = db.execute("SELECT * FROM holdings WHERE user_id = ?", user_id)


    # user holdings query
    stocks = []
    total_stock_value = 0

    # current stock price
    for holding in holdings:
        symbol = holding["symbol"]
        shares = holding["shares"]
        stock = lookup(symbol)
        if stock:
            price = stock["price"]
            total_value = shares * price
            total_stock_value += total_value
            stocks.append({
                "symbol":symbol,
                "shares":shares,
                "price":price,
                "total_value":total_value
            })
    #calculation of the total cash
    grand_total = cash + total_stock_value
    return render_template("index.html", stocks=stocks, cash=cash, grand_total=grand_total)

def usd(value):
    """Format Value of USD"""
    try:
        float_num=float(value)
        return f"${float_num:,.2f}"
    except ValueError:
        return "invalid input"


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # form
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # validation
        if not symbol:
            return apology("stock symbol required", 400)

        if not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("must be a number", 400)

        shares = int(shares)

        #check stock price
        stock = lookup(symbol)
        # print(f"Quote data: {stock}")
        if stock is None:
            return apology("invalid symbol", 400)

        price = stock["price"]
        total_cost = price * shares

        #check balance
        user_id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]


        #check if user can afford to buy
        if total_cost>cash:
            return apology("money not found 404", 400)

        #deduct money
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", total_cost, user_id)


        # Check if the user already has this stock in holdings
        rows = db.execute("SELECT * FROM holdings WHERE user_id = ? AND symbol = ?", user_id, symbol)

        if len(rows) == 0:
            db.execute("INSERT INTO holdings (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", user_id, symbol, shares, price)
        else:
            db.execute("UPDATE holdings SET shares = shares + ? WHERE user_id = ? AND symbol = ?", shares, user_id, symbol)
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", user_id, symbol, shares, price)

        # redirect to home
        return redirect("/")
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    #transaction
    transactions = db.execute("SELECT symbol, shares, price, transacted FROM transactions WHERE user_id = ?", user_id)
    print("Transactions:", transactions)
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

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
        # get symbol from form
        symbol = request.form.get("symbol")

        #check if blank
        if not symbol:
            return apology("Stock symbol is required", 400)
        # look the stock using function
        stock = lookup(symbol)

        # if the symbol is invalid
        if stock is None:
            return apology("Stock symbol is required", 400)

        # render template
        price_formatted= usd(stock["price"])
        return render_template("quoted.html", symbol=stock["symbol"], name=stock.get("name", "N/A"), price=price_formatted)
    # render the form
    return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # the form data
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Debug
        #print(f"Username: {username}")
        #print(f"Password: {password}")
        #print(f"Confirmation: {confirmation}")



        # if name is blank
        if not username:
           return apology("username is required", 400)

        # if password is blank
        if not password or not confirmation:
            return apology("password and confirmation are required", 400)

        # check if password matches the confirmation password
        if password != confirmation:
             return apology("passwords do not match", 400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(rows) > 0:
            return apology("username already exists", 400)

        # hashing
        hashed_pass = generate_password_hash(password, method = 'pbkdf2:sha256', salt_length=8)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed_pass)
        # try:
        #     db.execute("INSERT INTO users (username, hash) VALUES (?,?)", username, hashed_pass)
        # except sqlite3.IntegrityError as e:
        #     if "UNIQUE constraint failed: users.username" in str(e):
        #         return apology("username already exists", 400)
        #     else:
        #         return apology("an error occurred", 400)



        #return to the main page
        return redirect("/login")

    return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]

    if request.method == "POST":
        # get data

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # symbol not selected
        if not symbol:
            return apology("must provide symbol", 400)

        # shares not negative
        if not shares or not shares.isdigit() or int(shares) <=0:
            return apology("must provide a positive number of shares", 400)

        shares = int(shares)

        holding = db.execute("SELECT shares FROM holdings WHERE user_id = ? AND symbol = ?", user_id, symbol)
        if len(holding) !=1 or holding[0]["shares"]<shares:
            return apology("you do not own enough shares", 400)

        stock = lookup(symbol)
        if not stock:
            return apology("invalid symbol",400)
        # sale value
        sale_value = shares * stock["price"]

        # update cash in db
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", sale_value, user_id)

        # update user's holdings
        if holding[0]["shares"] == shares:
            db.execute("DELETE FROM holdings WHERE user_id = ? AND symbol = ?", user_id, symbol)
        else:
            db.execute("UPDATE holdings SET shares = shares - ? WHERE user_id = ? AND symbol = ?", shares, user_id, symbol)
        # history record
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?,?,?,?)",user_id, symbol, -shares, stock["price"])
        return redirect("/")
    else:
        # get user holdings from menu
        holdings = db.execute("SELECT symbol FROM holdings WHERE user_id = ?", user_id)
        return render_template("sell.html", holdings=holdings)
