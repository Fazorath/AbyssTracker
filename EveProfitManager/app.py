from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import os

app = Flask(__name__)

# Global variables
title = "Abyss Tracker"
total_profit = 0
MAXTIME = 20  # Example max time

@app.route('/')
def index():
    return render_template('index.html', title=title)

@app.route('/track', methods=['GET', 'POST'])
def track():
    global total_profit
    if request.method == 'POST':
        try:
            startingIsk = float(request.form.get('startingIsk'))
            after_inv = float(request.form.get('after_inv'))
            timeLeft = float(request.form.get('timeLeft'))
            time_in_abyss = MAXTIME - timeLeft

            profit = profitCalc(startingIsk, after_inv, time_in_abyss)
            writetoFile(startingIsk, after_inv, time_in_abyss, profit)

            return redirect(url_for('index'))
        except ValueError:
            return "Invalid input. Please enter numeric values."

    return render_template('track.html', title=title)

def profitCalc(starting_inv, after_inv, TimeinsideAbyss):
    global total_profit
    profit = after_inv - starting_inv
    total_profit += profit

    return profit

def writetoFile(startingIsk, after_inv, time_in_abyss, profit):
    global total_profit
    time = datetime.now()
    with open("Sessions.txt", "a") as file:
        data = [
            "Abyss Details!",
            " ",
            f"Starting ISK: {startingIsk} Million",
            f"After ISK: {after_inv} Million",
            f"Profit: {profit} Million",
            f"Time inside Abyss: {time_in_abyss} Mins",
            f"Total Profit: {total_profit} Million",
            f"Date: {time.strftime('%m-%d-%Y %I:%M %p')}",
            "-------------------",
        ]
        for line in data:
            file.write(line + "\n")

if __name__ == '__main__':
    app.run(debug=True)
