from colorama import *
import os
from globals import *

profit = 0

def incursion():
    IncursionProfit = int(input("Profit per incursion: "))
    while True:
        if not runningIncursion(IncursionProfit):
            break

def runningIncursion(profitPerRun):
    global incProfit
    while True:
        running = input("Still running (Y/N): ")
        if running.upper() == "Y":
            incProfit += profitPerRun
            print(incProfit)
            time = input("Time to Finish: ")
            print("Profit Recorded")
            break  # Break out of the inner loop
        elif running.upper() == "N":
            print("Exiting incursion.")
            return False  # Return False to indicate the function should exit
        else:
            print("Invalid input. Press Y if running again, or N if done.")
    return True  # Return True if the user is still running
