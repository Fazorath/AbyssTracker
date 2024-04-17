from colorama import *
import time
import os
from globals import *

profit = 0


def incursion():
    global title
    print(title)
    IncursionProfit = int(input(f"{Fore.GREEN}Profit per incursion: {Fore.RED}"))
    while True:
        if not Menu(IncursionProfit):
            break


def Menu(profitPerRun):
    while True:
        running = input(f"{Fore.GREEN}Still running (Y/N): {Fore.RED}")
        if running.upper() == "Y":
            runningIncursion(profitPerRun)
        elif running.upper() == "N":
            notRunning()
            return False  # Return False to indicate the function should exit
        else:
            print("Invalid input. Press Y if running again, or N if done.")
            return True  # Return True if the user is still running


def runningIncursion(profitPerRun, incProfit=0, incursiontime=0):
    global title
    while True:
        os.system("CLS")  # Clear the screen
        incProfit += profitPerRun
        print(Fore.RED + f"{title}")
        while True:
            try:
                finishTime = int(input(f"{Fore.GREEN}Time to Finish: {Fore.RED}"))
                incursiontime += finishTime
                print(f"{Fore.GREEN}Profit Recorded")
                time.sleep(2)
                os.system("CLS")  # Clear the screen
                print(Fore.RED + f"{title}")
                return incProfit, incursiontime  # Return the updated values
            except ValueError:
                os.system('CLS')
                print(Fore.RED + f"{title}")
                print("Please enter a valid integer for time.")  # Prompt for valid input
                continue

def notRunning():
    os.system("CLS")
    print(f"{Fore.GREEN}Total Profit: {Fore.RED}{incProfit} Million")
    print(f"{Fore.GREEN}Total Time: {Fore.RED}{incursiontime} Mins")
    print(f"{Fore.GREEN}Exiting incursion.")
