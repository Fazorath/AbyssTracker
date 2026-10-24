from colorama import Fore
import os

import sso


def settings():
    """Sign in, sign out and pick the active EVE character."""
    try:
        store = sso.TokenStore()
    except ImportError:
        print(f"\n{Fore.RED}Install the 'keyring' package to use sign-in.\n")
        return

    message = ""
    while True:
        os.system("CLS")
        active = store.active()
        characters = store.characters()
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
                character, tokens = sso.sign_in()
                store.save(character, tokens["refresh_token"])
                store.set_active(character.id)
                message = f"Signed in as {character.name}."
            except (sso.SignInError, sso.InvalidToken) as e:
                message = str(e)
        elif choice == "O" and active:
            try:
                sso.revoke(store.refresh_token(active.id))
            except Exception:
                pass  # still remove the local copy
            store.remove(active.id)
            message = f"Signed out {active.name}."
        elif choice.isdigit() and 1 <= int(choice) <= len(characters):
            store.set_active(characters[int(choice) - 1].id)
        else:
            message = "Invalid choice."
