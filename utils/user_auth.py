import json
import os

AUTH_FILE = os.path.join(os.path.dirname(__file__), "../data/users.json")

def load_users():
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, "r") as f:
            return json.load(f)
    return {}

def save_user(username, password):
    users = load_users()
    users[username] = password
    with open(AUTH_FILE, "w") as f:
        json.dump(users, f)

def validate_user(username, password):
    users = load_users()
    return users.get(username) == password