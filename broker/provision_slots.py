"""
THIS SCRIPT SHOULD ONLY BE RUN TO CREATE THE SLOTS
you can do: ls "C:/Users/ignsock/AppData/Local/hermes/profiles" to check that the slots exist on the machine
"""

import sys
HERMES_AGENT = r"C:\Users\ignsock\AppData\Local\hermes\hermes-agent"
SLOTS = ["slot0", "slot1", "slot2"]
sys.path.insert(0, HERMES_AGENT)
from hermes_cli.profiles import create_profile

def main():
    for name in SLOTS:
        try:
            print(f"created  {name} -> {create_profile(name, clone_config=True, no_alias=True)}")
        except FileExistsError:
            print(f"{name} already exists")
        except Exception as e:
            print(f"FAILED   {name}: {type(e).__name__}: {e}")
            return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())