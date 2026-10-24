from colorama import Fore
import sso
from account import SIGN_IN_ERRORS, Account
from globals import clear


def settings():
    """Sign in, sign out and pick the active EVE character."""
    account = Account()
    message = ""
    while True:
        clear()
        try:
            active = account.active()
            characters = account.characters()
        except sso.SignInError as e:
            print(f"\n{Fore.RED}{e}\n")
            return
        print(f"{Fore.GREEN}Settings\n")
        print(f"Active character: {Fore.RED}{active.name if active else 'none'}{Fore.GREEN}")
        for i, c in enumerate(characters, 1):
            print(f"  {i}. {c.name}")
        if message:
            print(f"\n{Fore.RED}{message}{Fore.GREEN}")
        choice = input(
            f"\nS. Sign in with EVE SSO\nO. Sign out active character\n"
            f"1-{max(len(characters), 1)}. Switch active character\nB. Back\n    Choice: {Fore.RED}"
        ).strip().upper()
        message = ""

        if choice == "B":
            return
        elif choice == "S":
            try:
                message = f"Signed in as {account.sign_in().name}."
            except SIGN_IN_ERRORS as e:
                message = str(e)
        elif choice == "O" and active:
            message = f"Signed out {account.sign_out().name}."
        elif choice.isdigit() and 1 <= int(choice) <= len(characters):
            account.select(characters[int(choice) - 1].id)
        else:
            message = "Invalid choice."
