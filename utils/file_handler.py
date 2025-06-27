import json
import csv
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "../data/questions.json")
USER_TRACK = os.path.join(os.path.dirname(__file__), "../user_track.csv")

def load_questions():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_user_result(username, total, score):
    header = ["Username", "Total Questions", "Correct Answers"]
    row = [username, total, score]
    file_exists = os.path.exists(USER_TRACK)

    with open(USER_TRACK, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow(row)