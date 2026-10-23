from colorama import Fore
from globals import title, clear, askNumber
from core import Tracker, ABYSS, MAXTIME, isk_per_hour


def abyssMain(tracker=None):
    """
    Main function to track Abyssal runs and calculate profits.

    Args:
        tracker (Tracker, optional): Store to record runs in. Opens the default database if None.

    Returns:
        Session: The finished session with its totals.
    """
    tracker = tracker or Tracker()
    print(title)
    startingIsk = startingInven()
    session_id = tracker.start_session(ABYSS, startingIsk)
    try:
        while True:
            after_inv = afterInven()
            run = tracker.log_abyss_run(session_id, startingIsk, after_inv, timeLeft())
            startingIsk = after_inv
            printRun(run)

            while True:
                user_input = input(f"{Fore.GREEN}Track another Abyssal run? (1/0): {Fore.RED}")
                clear()

                if user_input == "1":
                    print(title)
                    print(f"\n{Fore.GREEN}Last Total: {Fore.RED}{startingIsk} Million\n")
                    break  # Exit the inner loop to continue tracking another Abyssal run
                elif user_input == "0":
                    tracker.end_session(session_id)
                    session = tracker.session(session_id)
                    print(
                        f"\n{Fore.GREEN}Total Profit: {Fore.RED}{session.profit} Million"
                        f"\n{Fore.GREEN}Total Abyssals Run: {Fore.RED}{session.runs}"
                        f"\n{Fore.GREEN}Total Time Spent: {Fore.RED}{session.minutes} Mins"
                        f"\n{Fore.GREEN}ISK per Hour: {Fore.RED}{session.isk_per_hour:.1f} Million"
                        f"\n{Fore.GREEN}Session saved"
                    )
                    return session  # Exit the function to return to the main menu
                else:
                    print(f"{Fore.YELLOW}Invalid input. Please enter 1 or 0.\n")
    finally:
        # Ctrl+C or a closed terminal still closes the session instead of leaving it live forever
        if tracker.session(session_id) and tracker.session(session_id).active:
            tracker.end_session(session_id)


def printRun(run):
    """
    Show the profit and time of a single Abyssal run.

    Args:
        run (Run): The run that was just logged.
    """
    print(
        f"\n{Fore.GREEN}Profit: {Fore.RED}{run.profit} Million"
        f"\n{Fore.GREEN}New total: {Fore.RED}{run.isk_after}"
        f"\n{Fore.GREEN}Time inside Abyss: {Fore.RED}{run.minutes} Mins"
        f"\n{Fore.GREEN}ISK per Hour: {Fore.RED}{isk_per_hour(run.profit, run.minutes):.1f} Million\n"
    )


def startingInven():
    """
    Get the ISK total before an Abyssal run.

    Returns:
        float: ISK total before Abyssal run.
    """
    return askNumber("\nIsk Total before Abyss")


def afterInven():
    """
    Get the ISK total after an Abyssal run.

    Returns:
        float: ISK total after Abyssal run.
    """
    return askNumber("Isk Total after Abyss")


def timeLeft():
    """
    Get the minutes left on the Abyssal timer when leaving.

    Returns:
        float: Minutes left on the timer.
    """
    return askNumber("Time Left when leaving", 0, MAXTIME)
