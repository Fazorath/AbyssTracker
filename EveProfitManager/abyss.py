from colorama import Fore
from globals import title, clear, askNumber, askChoice
from core import Tracker, ABYSS, MAXTIME, TIERS, WEATHERS, isk_per_hour, tier_label


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
    weather, tier = askFilament(tracker)
    session_id = tracker.start_session(ABYSS, weather=weather, tier=tier)
    try:
        while True:
            before = cargoBefore(tracker.latest_cargo_after(session_id))
            run = tracker.log_cargo_run(session_id, before, cargoAfter(), timeLeft())
            printRun(run)

            while True:
                user_input = input(f"{Fore.GREEN}Track another Abyssal run? (1/0): {Fore.RED}")
                clear()

                if user_input == "1":
                    print(title)
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
        f"\n{Fore.GREEN}Cargo after: {Fore.RED}{run.cargo_after} Million"
        f"\n{Fore.GREEN}Time inside Abyss: {Fore.RED}{run.minutes} Mins"
        f"\n{Fore.GREEN}ISK per Hour: {Fore.RED}{isk_per_hour(run.profit, run.minutes):.1f} Million\n"
    )


def askFilament(tracker):
    """
    Ask for the weather and tier of the filament being run, defaulting to the last choice.

    Args:
        tracker (Tracker): Store holding the last choice.

    Returns:
        tuple: (weather, tier) for Tracker.start_session.
    """
    last_weather, last_tier = tracker.last_filament()
    print()
    weather_index = askChoice("Weather", WEATHERS, WEATHERS.index(last_weather) if last_weather else None)
    print()
    tier = askChoice("Tier", [tier_label(t) for t in range(len(TIERS))], last_tier)
    return WEATHERS[weather_index], tier


def cargoBefore(default):
    """
    Get the cargo value going into an Abyssal run.

    Args:
        default (float | None): Last run's cargo after, taken on Enter. None on a session's first run.

    Returns:
        float: Cargo value before the run, in millions.
    """
    print()
    return askNumber("Cargo before", minimum=0, default=default)


def cargoAfter():
    """
    Get the cargo value coming out of an Abyssal run.

    Returns:
        float: Cargo value after the run, in millions.
    """
    return askNumber("Cargo after", minimum=0)


def timeLeft():
    """
    Get the minutes left on the Abyssal timer when leaving.

    Returns:
        float: Minutes left on the timer.
    """
    return askNumber("Time Left when leaving", 0, MAXTIME)
