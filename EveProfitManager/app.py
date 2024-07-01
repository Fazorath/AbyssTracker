from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import os
import time

app = Flask(__name__)

# Global variables
title = "Abyss Tracker"
total_profit = 0
MAXTIME = 20  # Example max time

@app.route('/')
def index():
    return render_template('index.html', title=title)

@app.route('/abyss', methods=['GET', 'POST'])
def track_abyss():
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

@app.route('/incursion', methods=['GET', 'POST'])
def incursion():
    if request.method == 'POST':
        profitPerIncursion = int(request.form.get('profitPerIncursion'))
        return redirect(url_for('run_menu', profitPerIncursion=profitPerIncursion))
    return render_template('incursion.html', title="Incursion Tracker")

@app.route('/run_menu/<int:profitPerIncursion>', methods=['GET', 'POST'])
def run_menu(profitPerIncursion):
    if request.method == 'POST':
        running = int(request.form.get('running'))
        incProf = int(request.form.get('incProf'))
        incTime = int(request.form.get('incTime'))
        amountRun = int(request.form.get('amountRun'))

        if running == 1:
            incTime += getTimePerIncursion()
            incProf += profitPerIncursion
            amountRun += 1
            time.sleep(2)
        elif running == 0:
            writeToFile(incProf, amountRun, incTime)
            notRunning(incProf, incTime)
            return redirect(url_for('index'))

    return render_template('run_menu.html', title="Incursion Tracker", profitPerIncursion=profitPerIncursion)

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

def notRunning(incProfit, incursiontime):
    os.system("CLS")
    print(f"Total Profit: {incProfit} Million")
    print(f"Total Time: {incursiontime} Mins")
    print("Incursion Abandoned - Information written to Text File")

def writeToFile(incProfit, incursionsRun, incursiontime):
    with open("Sessions.txt", "a") as file:
        data = [
            "Incursion Details!",
            " ",
            f"Total Profit: {incProfit} Million",
            f"Total Incursions Ran: {incursionsRun} Sites",
            f"Total Time: {incursiontime} Min",
            "-------------------",
        ]
        for line in data:
            file.write(line + "\n")

def getTimePerIncursion():
    global title
    while True:
        try:
            timePerIncursion = int(input(f"Time per incursion: "))
            return timePerIncursion
        except ValueError:
            os.system("CLS")
            print(title)
            print("Please enter a valid integer for time per incursion.")

if __name__ == '__main__':
    app.run(debug=True)
