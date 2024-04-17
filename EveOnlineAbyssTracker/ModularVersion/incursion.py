from colorama import Fore
import time
import os
from globals import *

def incursion():
    global title
    print(title)
    
    # Get the profit per incursion and time to finish
    profitPerIncursion = getProfitPerIncursion()
    timePerIncursion = getTimePerIncursion()

    # Loop the menu until the user is done
    while True:
        if not runMenu(profitPerIncursion, timePerIncursion):
            break



def runMenu(profitPerIncursion, timePerIncursion):
    global title, incProfit, incursiontime
    while True:
        try:
            running = input(f"{Fore.GREEN}Still running (Y/N): {Fore.RED}")
            if running.upper() == "Y":
                os.system("CLS")  # Clear the screen
                incProfit += profitPerIncursion
                incursiontime += timePerIncursion
                print(Fore.RED + f"{title}")
                print("Profit Recorded")
                time.sleep(2)
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
            print("Please enter a valid input.")  # Prompt for valid input
            continue
        
def getProfitPerIncursion():
    global title
    while True:
        try:
            profitPerIncursion = int(input(f"{Fore.GREEN}Profit per incursion: {Fore.RED}"))
            return profitPerIncursion
        except ValueError:
            os.system("CLS")
            print(title)
            print("Please enter a valid integer for profit per incursion.")

def getTimePerIncursion():
    global title
    while True:
        try:
            timePerIncursion = int(input(f"{Fore.GREEN}Time per incursion: {Fore.RED}"))
            return timePerIncursion
        except ValueError:
            os.system("CLS")
            print(title)
            print("Please enter a valid integer for time per incursion.")

def notRunning():
    global incursiontime, incProfit
    os.system("CLS")
    print(f"{Fore.GREEN}Total Profit: {Fore.RED}{incProfit} Million")
    print(f"{Fore.GREEN}Total Time: {Fore.RED}{incursiontime} Mins")
    print(f"{Fore.GREEN}Exiting incursion.")
