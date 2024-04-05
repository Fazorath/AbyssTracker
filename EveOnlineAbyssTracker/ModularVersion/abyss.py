from colorama import Fore
import os
from globals import *

def abyssMain(startingIsk=None, abyssal_runs=0, total_Time=0):
    global total_profit  # Use the global total_profit variable

    while True:
        try:
            if startingIsk is None:
                startingIsk = startingInven()  # Ask for starting_inv only if it's None
        except ValueError:
            os.system('CLS')
            print(f"\n{Fore.RED}Invalid choice. Please enter a Float")
            startingIsk = None
            continue

        try:
            after_inv = afterInven()
            time_in_abyss = timeSpent()
        except ValueError:
            os.system('CLS')
            print(f"\n{Fore.RED}Invalid choice. Please enter a Float")
            continue

        profit = profitCalc(startingIsk, after_inv, time_in_abyss)
        startingIsk += profit  # Update startingIsk with the profit for this run
        abyssal_runs += 1  # Increment the counter for each Abyssal run
        total_Time += time_in_abyss

        while True:
            user_input = input(f"{Fore.GREEN}Track another Abyssal run? (1/0): {Fore.RED}").upper()
            os.system("CLS")

            if user_input == "1":
                break  # Exit the inner loop to continue tracking another Abyssal run
            elif user_input == "0":
                print(f"\n{Fore.GREEN}Total Profit: {Fore.RED}{total_profit}m")  # Use total_profit here
                print(f"{Fore.GREEN}Total Abyssals Run: {Fore.RED}{abyssal_runs}")
                print(f"{Fore.GREEN}Total Time Spent: {Fore.RED}{total_Time} Mins\n")
                
                return startingIsk, abyssal_runs, total_Time  # Exit the function to return to the main menu
            else:
                print(f"{Fore.YELLOW}Invalid input. Please enter 1 or 0.")


def profitCalc(starting_inv, after_inv, TimeinsideAbyss):
    global total_profit  # Use the global total_profit variable
    profit = after_inv - starting_inv
    new_total = starting_inv + profit
    total_profit += profit

    profit_string = f"\n{Fore.GREEN}Profit: {Fore.RED}{profit} Million\n{Fore.GREEN}New total: {Fore.RED}{new_total}\n{Fore.GREEN}Time inside Abyss: {Fore.RED}{TimeinsideAbyss}\n{Fore.GREEN}"
    print(profit_string)
    return profit  # Return the profit for the current run


def startingInven():
    before = float(input(f"\n{Fore.GREEN}Isk Total before Abyss: {Fore.RED}"))
    return before


def afterInven():
    after = float(input(f"{Fore.GREEN}Isk Total after Abyss: {Fore.RED}"))
    return after


def timeSpent():
    global MAXTIME
    timeLeft = float(input(f"{Fore.GREEN}Time Left when leaving: {Fore.RED}"))
    timeSpent = MAXTIME - timeLeft
    return timeSpent
