from colorama import *

starting_inv = None  # Global variable to store starting_inv
total_profit = 0

def menu():
    global total_profit
    while True:
        menu_text = f"""{Fore.GREEN}Welcome to my EVE ONLINE Python projects.
1. Abyss Money Tracker
2. Exit

    Choice: {Fore.RED}"""
        user_input = input(menu_text)

        if user_input == "1":
            abyssMain()

        elif user_input == "2":
            print(f"\n{Fore.GREEN}Total Profits: {total_profit}m")
            print("goodbye\n")
            break  # Exit the loop and end the program

        else:
            print(f"\n{Fore.YELLOW}Invalid choice. Please enter 1 or 2.")

def abyssMain():
    global starting_inv  # Use the global starting_inv variable
    if starting_inv is None:
        starting_inv = startingInven()  # Ask for starting_inv only if it's None

    after_inv = afterInven()
    new_total = profitCalc(starting_inv, after_inv)
    starting_inv = new_total  # Update global starting_inv with new_total

    while True:
        user_input = input(f"{Fore.GREEN}Track another Abyssal run? (Y/N): {Fore.RED}")
        if user_input.upper() == "N":
            break  # Exit the loop and return to main menu
        elif user_input.upper() == "Y":
            after_inv = afterInven()  # Ask for the next ISK total
            new_total = profitCalc(starting_inv, after_inv)  # Calculate profit with the new total
            starting_inv = new_total  # Update starting_inv for the next iteration
        else:
            print(f"{Fore.YELLOW}Invalid input. Please enter Y or N.")

def profitCalc(starting_inv, after_inv):
    global total_profit
    profit = after_inv - starting_inv
    new_total = starting_inv + profit
    total_profit += profit

    profit_string = f"\n{Fore.GREEN}Profit is going to be {Fore.RED}{profit} Million\n{Fore.GREEN}New total is going to be: {Fore.RED}{new_total}"
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
