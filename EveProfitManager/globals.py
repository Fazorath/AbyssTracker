import math
import os

from colorama import Fore


def clear():
    """Clear the terminal on Windows, macOS and Linux."""
    os.system("cls" if os.name == "nt" else "clear")


def askNumber(prompt, minimum=None, maximum=None):
    """
    Keep asking until the user enters a valid number.

    Args:
        prompt (str): Text shown before the input.
        minimum (float, optional): Lowest accepted value.
        maximum (float, optional): Highest accepted value.

    Returns:
        float: The number entered.
    """
    while True:
        try:
            value = float(input(f"{Fore.GREEN}{prompt}: {Fore.RED}"))
        except ValueError:
            value = math.nan
        if not math.isfinite(value):
            print(f"{Fore.YELLOW}Please enter a number\n")
        elif minimum is not None and value < minimum:
            print(f"{Fore.YELLOW}Please enter a number of at least {minimum:g}\n")
        elif maximum is not None and value > maximum:
            print(f"{Fore.YELLOW}Please enter a number no higher than {maximum:g}\n")
        else:
            return value


def askChoice(prompt, options, default=None):
    """
    Show a numbered list and keep asking until the user picks one.

    Args:
        prompt (str): Text shown before the input.
        options (list[str]): Choices to number from 1.
        default (int, optional): Index picked when the user just presses Enter.

    Returns:
        int: Index of the chosen option.
    """
    for i, option in enumerate(options, 1):
        print(f"{Fore.GREEN}{i}. {option}")
    hint = f" [{options[default]}]" if default is not None else ""
    while True:
        answer = input(f"{Fore.GREEN}{prompt}{hint}: {Fore.RED}").strip()
        if not answer and default is not None:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        print(f"{Fore.YELLOW}Please enter a number from 1 to {len(options)}\n")


title = """
 ██▓███   ██▀███   ▒█████    █████▒██▓▄▄▄█████▓    ███▄ ▄███▓ ▄▄▄       ███▄    █  ▄▄▄        ▄████ ▓█████  ██▀███  
▓██░  ██▒▓██ ▒ ██▒▒██▒  ██▒▓██   ▒▓██▒▓  ██▒ ▓▒   ▓██▒▀█▀ ██▒▒████▄     ██ ▀█   █ ▒████▄     ██▒ ▀█▒▓█   ▀ ▓██ ▒ ██▒
▓██░ ██▓▒▓██ ░▄█ ▒▒██░  ██▒▒████ ░▒██▒▒ ▓██░ ▒░   ▓██    ▓██░▒██  ▀█▄  ▓██  ▀█ ██▒▒██  ▀█▄  ▒██░▄▄▄░▒███   ▓██ ░▄█ ▒
▒██▄█▓▒ ▒▒██▀▀█▄  ▒██   ██░░▓█▒  ░░██░░ ▓██▓ ░    ▒██    ▒██ ░██▄▄▄▄██ ▓██▒  ▐▌██▒░██▄▄▄▄██ ░▓█  ██▓▒▓█  ▄ ▒██▀▀█▄  
▒██▒ ░  ░░██▓ ▒██▒░ ████▓▒░░▒█░   ░██░  ▒██▒ ░    ▒██▒   ░██▒ ▓█   ▓██▒▒██░   ▓██░ ▓█   ▓██▒░▒▓███▀▒░▒████▒░██▓ ▒██▒
▒▓▒░ ░  ░░ ▒▓ ░▒▓░░ ▒░▒░▒░  ▒ ░   ░▓    ▒ ░░      ░ ▒░   ░  ░ ▒▒   ▓▒█░░ ▒░   ▒ ▒  ▒▒   ▓▒█░ ░▒   ▒ ░░ ▒░ ░░ ▒▓ ░▒▓░
░▒ ░       ░▒ ░ ▒░  ░ ▒ ▒░  ░      ▒ ░    ░       ░  ░      ░  ▒   ▒▒ ░░ ░░   ░ ▒░  ▒   ▒▒ ░  ░   ░  ░ ░  ░  ░▒ ░ ▒░
░░         ░░   ░ ░ ░ ░ ▒   ░ ░    ▒ ░  ░         ░      ░     ░   ▒      ░   ░ ░   ░   ▒   ░ ░   ░    ░     ░░   ░ 
            ░         ░ ░          ░                     ░         ░  ░         ░       ░  ░      ░    ░  ░   ░     
"""
