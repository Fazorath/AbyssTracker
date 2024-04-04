from colorama import *

starting_inv = None  # Global variable to store starting_inv
total_profit = 0


def menu():
    global total_profit
    menu_text = f"""{Fore.GREEN}Welcome to my EVE ONLINE Python projects.
1. Abyss Money Tracker
2. Exit

    Choice: {Fore.RED}"""
    user_input = input(menu_text)

    while user_input != "2":
        if user_input == "1":
            abyssMain()
        user_input = input(
            """
    Again 1Y 2N: """
        )  # Ask for input again
        if user_input == "2":
            print(f"\n{Fore.GREEN}Total Profits: {total_profit}m")
            print("goodbye\n")


def abyssMain():
    global starting_inv  # Use the global starting_inv variable
    if starting_inv is None:
        starting_inv = startingInven()  # Ask for starting_inv only if it's None

    after_inv = afterInven()
    new_total = profitCalc(starting_inv, after_inv)
    starting_inv = new_total  # Update global starting_inv with new_total


def profitCalc(starting_inv, after_inv):
    global total_profit
    profit = after_inv - starting_inv
    new_total = starting_inv + profit
    total_profit += profit

    profit_string = f"\n{Fore.GREEN}Profit is going to be {Fore.RED}{profit} Million\n{Fore.GREEN}New total is going to be: {Fore.RED}{new_total}"
    print(profit_string)
    return new_total


def startingInven():
    before = float(input(f"\n{Fore.GREEN}Isk Total before Abyss: {Fore.RED}"))
    return before


def afterInven():
    after = float(input(f"{Fore.GREEN}Isk Total after Abyss: {Fore.RED}"))
    return after


if __name__ == "__main__":
    menu()
