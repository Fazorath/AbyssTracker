from colorama import Fore
from abyss import abyssMain
from incursion import incursion
from globals import clear
from core import Tracker


def menu():
    tracker = Tracker()
    while True:
        menu_text = f"""{Fore.RED}
 ██▓███   ██▀███   ▒█████    █████▒██▓▄▄▄█████▓    ███▄ ▄███▓ ▄▄▄       ███▄    █  ▄▄▄        ▄████ ▓█████  ██▀███  
▓██░  ██▒▓██ ▒ ██▒▒██▒  ██▒▓██   ▒▓██▒▓  ██▒ ▓▒   ▓██▒▀█▀ ██▒▒████▄     ██ ▀█   █ ▒████▄     ██▒ ▀█▒▓█   ▀ ▓██ ▒ ██▒
▓██░ ██▓▒▓██ ░▄█ ▒▒██░  ██▒▒████ ░▒██▒▒ ▓██░ ▒░   ▓██    ▓██░▒██  ▀█▄  ▓██  ▀█ ██▒▒██  ▀█▄  ▒██░▄▄▄░▒███   ▓██ ░▄█ ▒
▒██▄█▓▒ ▒▒██▀▀█▄  ▒██   ██░░▓█▒  ░░██░░ ▓██▓ ░    ▒██    ▒██ ░██▄▄▄▄██ ▓██▒  ▐▌██▒░██▄▄▄▄██ ░▓█  ██▓▒▓█  ▄ ▒██▀▀█▄  
▒██▒ ░  ░░██▓ ▒██▒░ ████▓▒░░▒█░   ░██░  ▒██▒ ░    ▒██▒   ░██▒ ▓█   ▓██▒▒██░   ▓██░ ▓█   ▓██▒░▒▓███▀▒░▒████▒░██▓ ▒██▒
▒▓▒░ ░  ░░ ▒▓ ░▒▓░░ ▒░▒░▒░  ▒ ░   ░▓    ▒ ░░      ░ ▒░   ░  ░ ▒▒   ▓▒█░░ ▒░   ▒ ▒  ▒▒   ▓▒█░ ░▒   ▒ ░░ ▒░ ░░ ▒▓ ░▒▓░
░▒ ░       ░▒ ░ ▒░  ░ ▒ ▒░  ░      ▒ ░    ░       ░  ░      ░  ▒   ▒▒ ░░ ░░   ░ ▒░  ▒   ▒▒ ░  ░   ░  ░ ░  ░  ░▒ ░ ▒░
░░         ░░   ░ ░ ░ ░ ▒   ░ ░    ▒ ░  ░         ░      ░     ░   ▒      ░   ░ ░   ░   ▒   ░ ░   ░    ░     ░░   ░ 
            ░         ░ ░          ░                     ░         ░  ░         ░       ░  ░      ░    ░  ░   ░     
{Fore.GREEN}
1. Abyss Money Tracker
2. Incursion Tracker
    Choice: {Fore.RED}"""
        user_input = input(menu_text)

        if user_input == "1":
            clear()
            abyssMain(tracker)
        
        elif user_input == "2":
            clear()
            incursion(tracker)

        elif user_input.upper() == "Q":
            print("\n    goodbye\n")
            break  # Exit the loop and end the program

        else:
            clear()
            print(f"\n{Fore.RED}Invalid choice. Please enter 1 or 2.")
