from colorama import Fore
from globals import *
import os

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
            from abyss import abyssMain  # Importing abyssMain from abyss.py
            abyssMain()

        elif user_input == "2":
            print("goodbye\n")
            break  # Exit the loop and end the program

        else:
            print(f"\n{Fore.YELLOW}Invalid choice. Please enter 1 or 2.")
