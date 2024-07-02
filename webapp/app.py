from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Use a secure key in production

# Define MAXTIME for the Abyssal Run (in minutes)
MAXTIME = 20

# Profit calculation function
def profitCalc(startingIsk, after_inv, time_in_abyss):
    """
    Calculate profit from an Abyssal run.

    Args:
        startingIsk (float): ISK before Abyssal run.
        after_inv (float): ISK after Abyssal run.
        time_in_abyss (float): Time spent in Abyssal run.

    Returns:
        float: Profit from the Abyssal run.
    """
    profit = after_inv - startingIsk
    return profit  # Return the profit for the current run

@app.route('/')
def index():
    return render_template('index.html', title="Abyssal Tracker")

@app.route('/track', methods=['GET', 'POST'])
def track_abyss():
    if request.method == 'POST':
        startingIsk = request.form.get('startingIsk')
        after_inv = request.form.get('after_inv')
        timeLeft = request.form.get('timeLeft')
        continue_tracking = request.form.get('continue')

        if startingIsk and not continue_tracking:
            try:
                startingIsk = float(startingIsk)
                after_inv = float(after_inv)
                timeLeft = float(timeLeft)
                time_in_abyss = MAXTIME - timeLeft

                # Calculate the profit
                profit = profitCalc(startingIsk, after_inv, time_in_abyss)
                newStartingIsk = startingIsk + profit

                # Update session
                session['startingIsk'] = newStartingIsk
                session['abyssal_runs'] = session.get('abyssal_runs', 0) + 1
                session['total_Time'] = session.get('total_Time', 0) + time_in_abyss

                return render_template('track.html', title="Track Abyssal Run", startingIsk=startingIsk, profit=profit, time_in_abyss=time_in_abyss, newStartingIsk=newStartingIsk, results=True)

            except ValueError:
                return render_template('track.html', title="Track Abyssal Run", error="Invalid input. Please enter numeric values.")

        elif continue_tracking == 'yes':
            # Continue tracking the Abyssal Run
            startingIsk = session.get('startingIsk')
            if startingIsk:
                return render_template('track.html', title="Track Abyssal Run", startingIsk=startingIsk)

        elif continue_tracking == 'no':
            # Finalize the results
            startingIsk = session.get('startingIsk', 0)
            abyssal_runs = session.get('abyssal_runs', 0)
            total_Time = session.get('total_Time', 0)
            total_profit = startingIsk - float(request.form.get('startingIsk', 0))  # Calculate the total profit

            # Write to file
            writetoFile(abyssal_runs, total_Time, total_profit)

            # Clear session data
            session.pop('startingIsk', None)
            session.pop('abyssal_runs', None)
            session.pop('total_Time', None)

            # Show the final results
            return render_template('results.html', title="Abyssal Run Results", startingIsk=startingIsk, total_profit=total_profit, abyssal_runs=abyssal_runs, total_Time=total_Time)
        
    else:
        # Initialize the session variables for tracking Abyssal Runs
        session['startingIsk'] = None
        session['abyssal_runs'] = 0
        session['total_Time'] = 0
        return render_template('track.html', title="Track Abyssal Run")

def writetoFile(abyssal_runs, total_Time, total_profit):
    with open('Sessions.txt', 'a') as f:
        f.write(f'Abyssal Details:\n')
        f.write(f'Total Profit: {total_profit} Million\n')
        f.write(f'Total Abyssal Runs: {abyssal_runs} Runs\n')
        f.write(f'Total Time: {total_Time} Minutes\n')
        f.write(f'-------------------\n')

if __name__ == '__main__':
    app.run(debug=True)
