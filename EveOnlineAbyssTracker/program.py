from colorama import *
import os

#ToDO: 
# Error catching for when wrong input
# measurement of time inside the abyss 
# Transfer tracked info into text file

starting_inv = None  # Global variable to store starting_inv
total_profit = 0
abyssal_runs = 0  # Counter for total Abyssals run
exit_program = False  # Flag to indicate when to exit the main menu loop
MAXTIME = 20.00

def menu():
    global total_profit, exit_program
    while not exit_program:
        menu_text = f"""{Fore.GREEN}Welcome to my EVE ONLINE Python projects.

1. Abyss Money Tracker
2. Exit

    Choice: {Fore.RED}"""
        user_input = input(menu_text)

        if user_input == "1":
            os.system('CLS')
            abyssMain()

        elif user_input == "2":
            print("goodbye\n")
            break  # Exit the loop and end the program

        else:
            print(f"\n{Fore.YELLOW}Invalid choice. Please enter 1 or 2.")

def abyssMain():
    global starting_inv, exit_program, abyssal_runs, total_profit
    
    if starting_inv is None:
        starting_inv = startingInven()  # Ask for starting_inv only if it's None

    while True:
        after_inv = afterInven()
        time_in_abyss = timeSpent()
        new_total = profitCalc(starting_inv, after_inv, time_in_abyss)
        starting_inv = new_total  # Update global starting_inv with new_total
        abyssal_runs += 1  # Increment the counter for each Abyssal run

        while True:
            user_input = input(f"{Fore.GREEN}Track another Abyssal run? (Y/N): {Fore.RED}").upper()
            os.system("CLS")

            if user_input == "Y":
                break  # Exit the inner loop to continue tracking another Abyssal run
            elif user_input == "N":
                print(f"\n{Fore.GREEN}Total Profits: {Fore.RED}{total_profit}m")
                print(f"{Fore.GREEN}Total Abyssals Run: {Fore.RED}{abyssal_runs}\n")
                print(f"{Fore.GREEN}Total Time Spent: {Fore.RED}{time_in_abyss}\n\n")
                exit_program = True
                return  # Exit the function to return to the main menu
            else:
                print(f"{Fore.YELLOW}Invalid input. Please enter Y or N.")



def profitCalc(starting_inv, after_inv, TimeinsideAbyss):
    global total_profit
    profit = after_inv - starting_inv
    new_total = starting_inv + profit
    total_profit += profit

    profit_string = f"\n{Fore.GREEN}Profit: {Fore.RED}{profit} Million\n{Fore.GREEN}New total: {Fore.RED}{new_total}\n{Fore.GREEN}Time inside Abyss: {Fore.RED}{TimeinsideAbyss}\n{Fore.GREEN}"
    print(profit_string)
    return new_total

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


if __name__ == "__main__":
    menu()
