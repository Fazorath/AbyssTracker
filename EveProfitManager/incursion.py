from colorama import Fore
import time
import os
from globals import *

def incursion():
    """
    Main function to manage the incursion process.
    """
    global title
    print(Fore.RED + f"{title}")

    # Get the profit per incursion
    profitPerIncursion = getProfitPerIncursion()
    
    # Loop the menu until the user is done
    while True:
        if not runMenu(profitPerIncursion):
            break

def runMenu(profitPerIncursion, incProf=0, incTime=0):
    """
    Function to run the menu for each incursion.

    Parameters:
    - profitPerIncursion: The profit gained per incursion.
    - incProf: Total profit gained in the current incursion.
    - incTime: Total time spent in the current incursion.
    """
    amountRun = 0
    os.system("CLS") 
    print(Fore.RED + f"{title}")
    incProf += profitPerIncursion
    incTime += getTimePerIncursion()
    print("Profit Recorded")
    time.sleep(2)
    amountRun += 1
    while True:
        try:
            running = int(input(f"{Fore.GREEN}Still running (1/0): {Fore.RED}"))
            if running == 1:
                os.system("CLS")  # Clear the screen
                print(Fore.RED + f"{title}")
                
                incTime += getTimePerIncursion()
                incProf += profitPerIncursion
                amountRun += 1
                print("Profit Recorded")
                time.sleep(2)
            elif running == 0:
                writeToFile(incProf, amountRun, incTime)
                notRunning(incProf, incTime)
                return False  # Return False to indicate the function should exit
            else:
                os.system("CLS")
                print("Invalid input. Press 1 if running again, or 0 if done.")
        except ValueError:
            os.system("CLS")
            print(Fore.RED + f"{title}")
            print("Please enter a valid input.")  # Prompt for valid input
            continue
        
def getProfitPerIncursion():
    """
    Function to get the profit gained per incursion from the user.

    Returns:
    - profitPerIncursion: The profit gained per incursion.
    """
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
    """
    Function to get the time spent per incursion from the user.

    Returns:
    - timePerIncursion: The time spent per incursion.
    """
    global title
    while True:
        try:
            timePerIncursion = int(input(f"{Fore.GREEN}Time per incursion: {Fore.RED}"))
            return timePerIncursion
        except ValueError:
            os.system("CLS")
            print(title)
            print("Please enter a valid integer for time per incursion.")

def notRunning(incProfit, incursiontime):
    """
    Function to handle the case when the incursion is not running.

    Parameters:
    - incProfit: Total profit gained in the incursion.
    - incursiontime: Total time spent in the incursion.
    """
    os.system("CLS")
    print(f"{Fore.GREEN}Total Profit: {Fore.RED}{incProfit} Million")
    print(f"{Fore.GREEN}Total Time: {Fore.RED}{incursiontime} Mins")
    print(f"{Fore.GREEN}Incursion Abandoned - {Fore.RED}Information written to Text File")

def writeToFile(incProfit, incursionsRun, incursiontime):
    """
    Function to write incursion details to a text file.

    Parameters:
    - incProfit: Total profit gained in the incursion.
    - incursionsRun: Total number of incursions run.
    - incursiontime: Total time spent in the incursion.
    """
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
