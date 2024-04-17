from colorama import Fore
import time
import os
from globals import *



def incursion():
    global title
    print(title)
    while True:
        try:
            IncursionProfit = int(input(f"{Fore.GREEN}Profit per incursion: {Fore.RED}"))
            break  # Break out of the loop if input is successful
        except ValueError:
            os.system("CLS")
            print(title)
            print("Please enter a valid integer for profit per incursion.")
    while True:
        if not Menu(IncursionProfit):
            break


def Menu(profitPerRun):
    while True:
        try:
            running = input(f"{Fore.GREEN}Still running (Y/N): {Fore.RED}")
            if running.upper() == "Y":
                runningIncursion(profitPerRun)
            elif running.upper() == "N":
                notRunning()
                return False  # Return False to indicate the function should exit
            else:
                os.system("CLS")
                print("Invalid input. Press Y if running again, or N if done.")
                return True  # Return True if the user is still running
        except ValueError:
            os.system("CLS")
            print(Fore.RED + f"{title}")
            print("Please enter a valid integer for time.")  # Prompt for valid input
            continue

def runningIncursion(profitPerRun):
    global title, incProfit, incursiontime
    while True:
        os.system("CLS")  # Clear the screen
        incProfit += profitPerRun
        print(Fore.RED + f"{title}")
        while True:
            try:
                finishTime = int(input(f"{Fore.GREEN}Time to Finish: {Fore.RED}"))
                incursiontime += finishTime
                print("Profit Recorded")
                time.sleep(2)
                os.system("CLS")  # Clear the screen
                print(Fore.RED + f"{title}")
                return  # Return without any value
            except ValueError:
                os.system('CLS')
                print(Fore.RED + f"{title}")
                print("Please enter a valid integer for time.")  # Prompt for valid input
                continue

def notRunning():
    global incursiontime, incProfit
    os.system("CLS")
    print(f"{Fore.GREEN}Total Profit: {Fore.RED}{incProfit} Million")
    print(f"{Fore.GREEN}Total Time: {Fore.RED}{incursiontime} Mins")
    print(f"{Fore.GREEN}Exiting incursion.")
