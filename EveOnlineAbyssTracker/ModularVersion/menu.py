from colorama import Fore
from globals import *
import os
from abyss import *

def menu(startloop="False"):
    while startloop != True:
        menu_text = f"""{Fore.GREEN}Welcome to my EVE ONLINE Python projects.

1. Abyss Money Tracker
2. Exit

    Choice: {Fore.RED}"""
        try:
            user_input = input(menu_text)
        except ValueError:
            os.system('CLS')
            print(f"\n{Fore.RED}Invalid choice. Please enter 1 or 2.")
            

        if user_input == "1":
            os.system('CLS')
            abyssMain()

        elif user_input == "2":
            print("goodbye\n")
            break  # Exit the loop and end the program

        else:
            os.system('CLS')
            print(f"\n{Fore.RED}Invalid choice. Please enter 1 or 2.")
