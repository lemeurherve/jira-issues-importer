import os
from version import __version__

class Config:
    def __init__(self, **entries):
        for k, v in entries.items():
            setattr(self, k, v)

    def __repr__(self):
        return f"Config({self.__dict__})"

def ask_dry_mode():
    reply = input("Dry-run? (nothing created in GitHub) [Y/n]: ").strip().lower()
    return (reply != "n")

def load_config(specs):
    """
    specs = [
        ("attr_name", "ENV_VAR", "Prompt text", default_value_or_None),
        ...
    ]
    Returns a Config instance with attributes based on specs.
    """
    values = {}

    for attr, env_var, prompt, default in specs:
        # Env var lookup
        value = os.getenv(env_var)

        if not value:
            # Build prompt string
            text = prompt
            if default is not None:
                text += f' [default "{default}"]'
            text += ": "

            user_value = input(text).strip()
            value = user_value or default

        values[attr] = value

    # Add version
    values["version"] = __version__

    values["dry_run"] = ask_dry_mode()

    return Config(**values)
