from colorama import *
import os
from globals import *

profit = 0 

def incursion():
    while True:
        IncursionProfit=input("Profit per incursion: ")
        runningIncursion()

def runningIncursion():
    running = input("Still running: ")
    while True:
        if running.upper() == "Y":
            print("Profit Recorded")
            time=input("Time to Finish: ")
        elif running.upper() == "N":
            print("okay Shitter")
            break
        else:
            print("Press Y if running again\nPress N if done")
            break

