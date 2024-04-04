from colorama import *
import os

starting_inv = None  # Global variable to store starting_inv
total_profit = 0
abyssal_runs = 0  # Counter for total Abyssals run
exit_program = False  # Flag to indicate when to exit the main menu loop

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
    global starting_inv, exit_program, abyssal_runs  # Use the global variables
    if starting_inv is None:
        starting_inv = startingInven()  # Ask for starting_inv only if it's None

    while True:
        after_inv = afterInven()
        new_total = profitCalc(starting_inv, after_inv)
        starting_inv = new_total  # Update global starting_inv with new_total
        abyssal_runs += 1  # Increment the counter for each Abyssal run
        user_input = input(f"{Fore.GREEN}Track another Abyssal run? (Y/N): {Fore.RED}")
        os.system("CLS")
        if user_input.upper() == "N":
            print(f"\n{Fore.GREEN}Total Profits: {Fore.RED}{total_profit}m")
            print(f"{Fore.GREEN}Total Abyssals Run: {Fore.RED}{abyssal_runs}")
            exit_program = True
            break  # Exit the loop to return to main menu
        elif user_input.upper() != "Y":
            print(f"{Fore.YELLOW}Invalid input. Please enter Y or N.")

def profitCalc(starting_inv, after_inv):
    global total_profit
    profit = after_inv - starting_inv
    new_total = starting_inv + profit
    total_profit += profit

    profit_string = f"\n{Fore.GREEN}Profit: {Fore.RED}{profit} Million\n{Fore.GREEN}New total: {Fore.RED}{new_total}\n"
    print(profit_string)
    return new_total

def startingInven():
    before = float(input(f"\n{Fore.GREEN}Isk Total before Abyss: {Fore.RED}"))
    return before

def afterInven():
    after = float(input(f"{Fore.GREEN}Isk Total after Abyss: {Fore.RED}"))
    return after

if __name__ == "__main__":
    menu()
