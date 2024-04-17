from colorama import *
import os
from globals import *

profit = 0 

def incursion():
    IncursionProfit=int(input("Profit per incursion: "))
    while True:
        runningIncursion(IncursionProfit)

def runningIncursion(profitPerRun):
    global incProfit
    while True:
        running = input("Still running: ")
        if running.upper() == "Y":
            print("Profit Recorded")
            incProfit += profitPerRun
            print(incProfit)
            time=input("Time to Finish: ")
            break
        elif running.upper() == "N":
            print("okay Shitter")
            break
        else:
            print("Press Y if running again\nPress N if done")
            break

