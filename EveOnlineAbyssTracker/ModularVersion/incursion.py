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
        if not runningIncursion(IncursionProfit):
            break

def runningIncursion(profitPerRun):
    global incProfit
    global title
    global incursiontime
    while True:
        running = input(f"{Fore.GREEN}Still running (Y/N): {Fore.RED}")
        if running.upper() == "Y":
            os.system("CLS")
            incProfit += profitPerRun
            print(title)
            finishTime = int(input(f"{Fore.GREEN}Time to Finish: {Fore.RED}"))
            incursiontime += finishTime
            print(f"{Fore.GREEN}Profit Recorded")
            time.sleep(2)
            os.system("CLS")
            print(f"{Fore.RED}{title}")
            break  # Break out of the inner loop
        elif running.upper() == "N":
            os.system("CLS")
            print(f"{Fore.GREEN}Total Profit: {Fore.RED}{incProfit} Million")
            print(f"{Fore.GREEN}Total Time: {Fore.RED}{incursiontime} Mins")
            print(f"{Fore.GREEN}Exiting incursion.")
            return False  # Return False to indicate the function should exit
        else:
            print("Invalid input. Press Y if running again, or N if done.")
    return True  # Return True if the user is still running
