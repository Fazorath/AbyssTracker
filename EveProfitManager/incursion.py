from colorama import Fore
import time
from globals import title, clear, askNumber
from core import Tracker, INCURSION


def incursion(tracker=None):
    """
    Main function to manage the incursion process.

    Args:
        tracker (Tracker, optional): Store to record sites in. Opens the default database if None.

    Returns:
        Session: The finished session with its totals.
    """
    tracker = tracker or Tracker()
    print(Fore.RED + f"{title}")

    # Get the profit per incursion
    profitPerIncursion = getProfitPerIncursion()
    session_id = tracker.start_session(INCURSION)

    # Loop until the user is done
    try:
        while True:
            clear()
            print(Fore.RED + f"{title}")
            tracker.log_incursion_site(session_id, profitPerIncursion, getTimePerIncursion())
            print("Profit Recorded")
            time.sleep(2)
            if not stillRunning():
                tracker.end_session(session_id)
                session = tracker.session(session_id)
                notRunning(session)
                return session
    finally:
        # Ctrl+C or a closed terminal still closes the session instead of leaving it live forever
        if tracker.session(session_id) and tracker.session(session_id).active:
            tracker.end_session(session_id)


def stillRunning():
    """
    Ask whether the user is running another site.

    Returns:
        bool: True to log another site, False when done.
    """
    while True:
        try:
            running = int(input(f"{Fore.GREEN}Still running (1/0): {Fore.RED}"))
        except ValueError:
            running = None
        if running in (0, 1):
            return running == 1
        clear()
        print(Fore.RED + f"{title}")
        print("Invalid input. Press 1 if running again, or 0 if done.")


def getProfitPerIncursion():
    """
    Function to get the profit gained per incursion from the user.

    Returns:
    - profitPerIncursion: The profit gained per incursion.
    """
    return askNumber("Profit per incursion", minimum=0)


def getTimePerIncursion():
    """
    Function to get the time spent per incursion from the user.

    Returns:
    - timePerIncursion: The time spent per incursion.
    """
    return askNumber("Time per incursion", minimum=0)


def notRunning(session):
    """
    Show the totals of the finished incursion session.

    Parameters:
    - session: The finished Session.
    """
    clear()
    print(f"{Fore.GREEN}Total Profit: {Fore.RED}{session.profit} Million")
    print(f"{Fore.GREEN}Total Sites: {Fore.RED}{session.runs}")
    print(f"{Fore.GREEN}Total Time: {Fore.RED}{session.minutes} Mins")
    print(f"{Fore.GREEN}ISK per Hour: {Fore.RED}{session.isk_per_hour:.1f} Million")
    print(f"{Fore.GREEN}Incursion Abandoned - {Fore.RED}Session saved")
