from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

# Global variables
title = "Tracker"
total_profit = 0
MAXTIME = 20  # Example max time

@app.route('/')
def index():
    return render_template('index.html', title=title)

@app.route('/abyss', methods=['GET', 'POST'])
def track_abyss():
    if request.method == 'POST':
        continue_tracking = request.form.get('continue')
        if continue_tracking:
            if continue_tracking == 'yes':
                # Continue tracking Abyssal Runs
                startingIsk = float(request.form.get('startingIsk'))
                after_inv = float(request.form.get('after_inv'))
                timeLeft = float(request.form.get('timeLeft'))
                time_in_abyss = MAXTIME - timeLeft

                profit = profitCalc(startingIsk, after_inv, time_in_abyss)
                session['startingIsk'] = startingIsk + profit  # Update with the new starting ISK
                session['abyssal_runs'] = session.get('abyssal_runs', 0) + 1
                session['total_Time'] = session.get('total_Time', 0) + time_in_abyss

                # Redirect to the same page to continue tracking
                return redirect(url_for('track_abyss', title=title))
            elif continue_tracking == 'no':
                # Write to file and show results
                writetoFile(session['abyssal_runs'], session['total_Time'])
                session.pop('startingIsk', None)
                session.pop('abyssal_runs', None)
                session.pop('total_Time', None)
                return render_template('results.html', title=title, total_profit=total_profit)
        else:
            try:
                startingIsk = float(request.form.get('startingIsk'))
                after_inv = float(request.form.get('after_inv'))
                timeLeft = float(request.form.get('timeLeft'))
                time_in_abyss = MAXTIME - timeLeft

                profit = profitCalc(startingIsk, after_inv, time_in_abyss)
                session['startingIsk'] = startingIsk + profit  # Update with the new starting ISK
                session['abyssal_runs'] = session.get('abyssal_runs', 0) + 1
                session['total_Time'] = session.get('total_Time', 0) + time_in_abyss

                # Show prompt for the user to continue or finish
                return render_template('track.html', title=title, startingIsk=startingIsk, show_prompt=True)
            except ValueError:
                return render_template('track.html', title=title, error="Invalid input. Please enter numeric values.")
    else:
        # Initialize the session variables for tracking Abyssal Runs
        session['startingIsk'] = None
        session['abyssal_runs'] = 0
        session['total_Time'] = 0
        return render_template('track.html', title=title)


@app.route('/incursion', methods=['GET', 'POST'])
def incursion():
    if request.method == 'POST':
        try:
            profitPerIncursion = int(request.form.get('profitPerIncursion'))
            session['profitPerIncursion'] = profitPerIncursion
            session['incProf'] = 0
            session['incTime'] = 0
            session['amountRun'] = 0
            return redirect(url_for('run_menu'))
        except ValueError:
            return "Invalid input. Please enter a valid integer for profit per incursion."

    return render_template('incursion.html', title="Incursion Tracker")

@app.route('/run_menu', methods=['GET', 'POST'])
def run_menu():
    profitPerIncursion = session.get('profitPerIncursion')
    incProf = session.get('incProf', 0)
    incTime = session.get('incTime', 0)
    amountRun = session.get('amountRun', 0)

    if request.method == 'POST':
        try:
            running = int(request.form.get('running'))

            if running == 1:
                timePerIncursion = int(request.form.get('timePerIncursion'))
                incTime += timePerIncursion
                incProf += profitPerIncursion
                amountRun += 1
                session['incTime'] = incTime
                session['incProf'] = incProf
                session['amountRun'] = amountRun
            elif running == 0:
                writeToFile(incProf, amountRun, incTime)
                return redirect(url_for('index'))
            else:
                return "Invalid input. Press 1 if running again, or 0 if done."
        except ValueError:
            return "Please enter a valid input."

    return render_template('run_menu.html', title="Incursion Tracker", profitPerIncursion=profitPerIncursion, incProf=incProf, incTime=incTime, amountRun=amountRun)

def profitCalc(starting_inv, after_inv, TimeinsideAbyss):
    profit = after_inv - starting_inv
    return profit

def writetoFile(startingIsk, after_inv, time_in_abyss, profit):
    time = datetime.now()
    with open("Sessions.txt", "a") as file:
        data = [
            "Abyss Details!",
            " ",
            f"Starting ISK: {startingIsk} Million",
            f"After ISK: {after_inv} Million",
            f"Profit: {profit} Million",
            f"Time inside Abyss: {time_in_abyss} Mins",
            f"Date: {time.strftime('%m-%d-%Y %I:%M %p')}",
            "-------------------",
        ]
        for line in data:
            file.write(line + "\n")

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

if __name__ == '__main__':
    app.run(debug=True)
