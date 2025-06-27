# ================== IMPORTS AND DB SETUP ==================
import tkinter as tk
import random
import psycopg2
import csv
import os
import smtplib
import requests
import base64
from tkinter import filedialog
from utils.file_handler import load_questions
from score import ScoreTracker
from dotenv import load_dotenv
from ui import QuizUI
import pygame
from datetime import datetime
from email.message import EmailMessage

# ========== FETCH ENV VARIABLES FROM GITHUB WITHOUT LOCAL FILE ==========
def set_env_from_github(token, repo, env_path):
    api_url = f"https://api.github.com/repos/{repo}/contents/{env_path}"
    headers = {"Authorization": f"token {token}"}
    resp = requests.get(api_url, headers=headers)
    if resp.status_code == 200:
        content = resp.json()["content"]
        decoded = base64.b64decode(content).decode()
        for line in decoded.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            # Set env variable only for current process, not visible to other users or processes
            os.environ[key.strip()] = value.strip()
    else:
        print("Failed to fetch .env from GitHub:", resp.status_code, resp.text)
        raise Exception("Could not fetch .env from GitHub")

# ========== SET THESE VARIABLES ==========
load_dotenv(dotenv_path="data/detail.env")
THING = os.getenv("THING")  # Only use from local details.env
GITHUB_REPO = "RohithReddyP/envvar"
GITHUB_ENV_PATH = "details.env"      # path in repo (at root)

# Always fetch from GitHub using the token from local details.env
if not THING:
    print("Missing THING in data/details.env")
    exit(1)
set_env_from_github(THING, GITHUB_REPO, GITHUB_ENV_PATH)
# Now all other env vars are set from GitHub

# ========== ACCESS ENVIRONMENT VARIABLES DIRECTLY ==========
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT", 5432)

EMAIL_SENDER = os.getenv("EMAIL_ADDRESS")
EMAIL_PASS = os.getenv("EMAIL_PASSWORD")

# Check for missing environment variables (no print, just exit if missing)
missing_vars = []
for var, val in [
    ("DB_HOST", DB_HOST),
    ("DB_NAME", DB_NAME),
    ("DB_USER", DB_USER),
    ("DB_PASS", DB_PASS),
    ("DB_PORT", DB_PORT),
    ("EMAIL_ADDRESS", EMAIL_SENDER),
    ("EMAIL_PASSWORD", EMAIL_PASS),
]:
    if not val:
        missing_vars.append(var)

if missing_vars:
    print("Missing environment variables:", ", ".join(missing_vars))
    exit(1)

# Check DB connection details before connecting
if not all([DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT]):
    print("Database environment variables are not set properly.")
    print("Please set DB_HOST, DB_NAME, DB_USER, DB_PASS, and DB_PORT in your environment.")
    exit(1)

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
except Exception as e:
    print("Could not connect to the PostgreSQL server:")
    print(e)
    print("Please ensure the server is running and the connection details are correct.")
    exit(1)

cur = conn.cursor()

# ================== TABLE CREATION ==================
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT NOT NULL
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS quiz_results (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    total_questions INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS feedback (
    username TEXT PRIMARY KEY,
    rating INTEGER,
    liked BOOLEAN,
    feedback_note TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    username TEXT,
    comment TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    username TEXT,
    report TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS password_resets (
    id SERIAL PRIMARY KEY,
    username TEXT,
    email TEXT,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
conn.commit()
pygame.mixer.init()

# ================== PASSWORD RESET HELPER ==================
def send_otp_email(to_email, otp):
    print(f"Attempting to send OTP to: {to_email}")
    msg = EmailMessage()
    msg.set_content(f"""
Dear User,

Your One-Time Password (OTP) for resetting your QuizMaster account password is: {otp}

This OTP is valid for a short time. Please do not share this code with anyone.

If you did not request a password reset, please ignore this email.

Best regards,
QuizMaster Team
""")
    msg["Subject"] = "QuizMaster Password Reset OTP"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASS)
            smtp.send_message(msg)
        print("OTP email sent successfully.")
        return True
    except Exception as e:
        print("Email error:", e)
        return False

def reset_password_flow(root, prompt_login):
    win = tk.Toplevel(root)
    win.title("Forgot Password")
    center_window(win, 400, 250)
    win.configure(bg="white")
    tk.Label(win, text="Enter your email:", font=("Segoe UI", 11), bg="white").pack(pady=10)
    email_entry = tk.Entry(win, font=("Segoe UI", 11), width=30)
    email_entry.pack()

    def send_otp():
        email = email_entry.get().strip()
        if not email:
            return
        cur.execute("SELECT username FROM users WHERE email=%s", (email,))
        user_row = cur.fetchone()
        if not user_row:
            show_popup(root, "Error", "Not a valid registered email.")
            return
        # Insert into password_resets table
        cur.execute("INSERT INTO password_resets (username, email) VALUES (%s, %s)", (user_row[0], email))
        conn.commit()
        otp = str(random.randint(100000, 999999))
        if send_otp_email(email, otp):
            win.destroy()
            verify_otp_popup(root, user_row[0], email, otp, prompt_login)
        else:
            show_popup(root, "Error", "Failed to send OTP. Please try again.")

    tk.Button(win, text="Send OTP", font=("Segoe UI", 11), bg="blue", fg="white", command=send_otp).pack(pady=15)

def verify_otp_popup(root, username, email, otp, prompt_login):
    win = tk.Toplevel(root)
    win.title("Verify OTP")
    center_window(win, 400, 300)
    win.configure(bg="white")
    tk.Label(win, text="Enter the OTP sent to your email:", bg="white", font=("Segoe UI", 11)).pack(pady=10)
    otp_entry = tk.Entry(win, font=("Segoe UI", 11), width=30)
    otp_entry.pack()
    tk.Label(win, text="Enter new password:", bg="white", font=("Segoe UI", 11)).pack(pady=10)
    new_pass = tk.Entry(win, font=("Segoe UI", 11), width=30, show="*")
    new_pass.pack()

    def verify():
        if otp_entry.get() == otp:
            if username:
                cur.execute("UPDATE users SET password=%s WHERE username=%s", (new_pass.get().strip(), username))
                conn.commit()
                show_popup(root, "Success", "Password reset successfully!")
                win.destroy()
                prompt_login()
            else:
                show_popup(root, "Success", "OTP verified! (No user update performed)")
                win.destroy()
        else:
            show_popup(root, "Error", "Invalid OTP.")

    tk.Button(win, text="Verify & Reset", font=("Segoe UI", 11), bg="green", fg="white", command=verify).pack(pady=20)

def play_correct_if_full(score, total):
    if score == total:
        try:
            pygame.mixer.Sound("assets/correct.wav").play()
        except Exception as e:
            print("Sound error:", e)

def save_user_pg(username, password, email):
    try:
        cur.execute("INSERT INTO users (username, password, email) VALUES (%s, %s, %s)", (username, password, email))
        conn.commit()
        return True
    except psycopg2.Error:
        conn.rollback()
        return False

def validate_user_pg(username, password):
    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    return cur.fetchone() is not None

def user_exists_pg(username):
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    return cur.fetchone() is not None

def save_quiz_result_pg(username, total_questions, correct_answers):
    cur.execute("INSERT INTO quiz_results (username, total_questions, correct_answers) VALUES (%s, %s, %s)",
                (username, total_questions, correct_answers))
    conn.commit()

def fetch_user_results_pg(username):
    cur.execute("SELECT total_questions, correct_answers, created_at FROM quiz_results WHERE username=%s ORDER BY created_at DESC", (username,))
    return cur.fetchall()

def save_user_result_csv_local(username, total_questions, correct_answers):
    save_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        title="Save quiz result as CSV"
    )
    if not save_path:
        return
    file_exists = os.path.isfile(save_path)
    with open(save_path, mode="a", newline="") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Username", "Total Questions", "Correct Answers"])
        writer.writerow([username, total_questions, correct_answers])

def has_given_feedback(username):
    cur.execute("SELECT 1 FROM feedback WHERE username=%s", (username,))
    return cur.fetchone() is not None

def save_feedback(username, rating, liked, note):
    try:
        cur.execute("INSERT INTO feedback (username, rating, liked, feedback_note) VALUES (%s, %s, %s, %s)",
                    (username, rating, liked, note))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Feedback save error:", e)

def save_comment(username, comment_text):
    try:
        cur.execute("INSERT INTO comments (username, comment) VALUES (%s, %s)", (username, comment_text))
        conn.commit()
    except:
        conn.rollback()

def save_report(username, report_text):
    try:
        cur.execute("INSERT INTO reports (username, report) VALUES (%s, %s)", (username, report_text))
        conn.commit()
    except:
        conn.rollback()

def show_feedback_popup(ui, username):
    def submit_feedback(rating, liked, note):
        save_feedback(username, rating, liked, note)
        ui.show_popup("Thank You!", "Your feedback has been recorded.", "OK")
    ui.show_feedback_popup(lambda rating, liked, note: submit_feedback(rating, liked, note))

# ================== MAIN FUNCTION ==================
def main():
    print("QuizMaster GUI starting...")  # Add this line
    root = tk.Tk()
    root.title("Quiz Game")
    # Remove forced fullscreen, allow window manager controls
    root.configure(bg="#001f3f")
    root.geometry("1200x800")  # Start with a large window, but resizable

    # Add maximize/restore button in the title bar area
    is_fullscreen = {"value": False}
    def toggle_fullscreen():
        is_fullscreen["value"] = not is_fullscreen["value"]
        root.attributes("-fullscreen", is_fullscreen["value"])

    # Add a maximize button in the top right corner of the root window
    def add_maximize_button():
        btn = tk.Button(root, text="🗖", font=("Segoe UI", 12), bg="#6c63ff", fg="white",
                        bd=0, relief="flat", activebackground="#5548c8", cursor="hand2",
                        command=toggle_fullscreen)
        btn.place(relx=1.0, x=-40, y=10, anchor="ne")
    add_maximize_button()

    username = ""
    ui = None
    session_attempts = []

    # --- Helper to clear main window content ---
    def clear_root():
        for widget in root.winfo_children():
            widget.destroy()

    def do_logout():
        nonlocal username, ui
        username = ""
        ui = None
        clear_root()
        prompt_login()

    def show_history():
        results = fetch_user_results_pg(username)
        popup = tk.Toplevel(root)
        popup.title("Past Scores")
        center_window(popup, 400, 300)
        popup.configure(bg="#ffffff")
        frame = tk.Frame(popup, bg="#ffffff", padx=10, pady=10)
        frame.pack(expand=True, fill="both")
        tk.Label(frame, text="Previous Quiz Attempts", font=("Segoe UI", 14, "bold"), bg="#ffffff").pack(pady=(0,10))
        for row in results:
            tk.Label(frame, text=f"{row[2].strftime('%Y-%m-%d %H:%M')} - {row[1]}/{row[0]}", bg="#ffffff", font=("Segoe UI", 11)).pack(anchor="w")

    def open_comment_popup():
        popup = tk.Toplevel(root)
        popup.title("Comment")
        center_window(popup, 400, 250)
        popup.configure(bg="white")
        tk.Label(popup, text="Write your comment below:", bg="white", font=("Segoe UI", 12)).pack(pady=10)
        comment_box = tk.Text(popup, height=5, width=40)
        comment_box.pack(pady=5)
        def submit_comment():
            comment_text = comment_box.get("1.0", "end").strip()
            if comment_text:
                save_comment(username, comment_text)
                popup.destroy()
        tk.Button(popup, text="Submit", command=submit_comment, bg="#28a745", fg="white").pack(pady=10)

    def open_report_popup():
        popup = tk.Toplevel(root)
        popup.title("Report")
        center_window(popup, 400, 250)
        popup.configure(bg="white")
        tk.Label(popup, text="Describe your issue below:", bg="white", font=("Segoe UI", 12)).pack(pady=10)
        report_box = tk.Text(popup, height=5, width=40)
        report_box.pack(pady=5)
        def submit_report():
            report_text = report_box.get("1.0", "end").strip()
            if report_text:
                save_report(username, report_text)
                popup.destroy()
        tk.Button(popup, text="Submit", command=submit_report, bg="#dc3545", fg="white").pack(pady=10)

    def start_quiz():
        # Ask for question count first, then show description, then start quiz
        def after_question_count(total_q):
            if not total_q:
                return
            def show_description():
                # Use ui.clear() instead of clear_root() to avoid destroying ui frames
                if ui:
                    ui.clear()
                desc_frame = tk.Frame(root, bg="white")
                desc_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=1, relheight=1)

                # Back arrow button (top-left)
                arrow_btn = tk.Button(
                    root, text="←", font=("Segoe UI", 16, "bold"), bg="white", fg="#007bff", bd=0,
                    cursor="hand2", activebackground="white", activeforeground="#0056b3",
                    command=lambda: [desc_frame.destroy(), arrow_btn.destroy(), ui.show_welcome()]
                )
                arrow_btn.place(x=10, y=10)
                # Remove arrow button when desc_frame is destroyed
                desc_frame.bind("<Destroy>", lambda e: arrow_btn.destroy())

                # Heading
                tk.Label(
                    desc_frame,
                    text="Description",
                    font=("Segoe UI", 28, "bold"),
                    bg="white",
                    fg="#2c3e50"
                ).pack(pady=(60, 30))

                # Description text
                desc_text = (
                    "• Each question carries 1 point.\n"
                    "• Try to answer as many as you can!\n"
                    "• Your score will be shown at the end.\n"
                )
                tk.Label(
                    desc_frame,
                    text=desc_text,
                    font=("Segoe UI", 16),
                    bg="white",
                    fg="#222"
                ).pack(pady=(0, 20))

                # Red warning about timer
                tk.Label(
                    desc_frame,
                    text="⚠ Each question has only 20 seconds!",
                    font=("Segoe UI", 15, "bold"),
                    bg="white",
                    fg="red"
                ).pack(pady=(0, 40))

                # Start button
                tk.Button(
                    desc_frame,
                    text="Start",
                    font=("Segoe UI", 16, "bold"),
                    bg="#28a745",
                    fg="white",
                    activebackground="#218838",
                    width=14,
                    command=lambda: [desc_frame.destroy(), root.after_idle(lambda: ask_and_start(total_q))]
                ).pack()

            def ask_and_start(total_q):
                all_questions = load_questions()
                questions = random.sample(all_questions, k=min(total_q, len(all_questions)))
                tracker = ScoreTracker(len(questions))
                idx = [0]
                user_answers = []

                # --- Helper to show score popup ---
                def show_score_popup(ui_ref):
                    score = tracker.get_score()
                    total = len(questions)
                    play_correct_if_full(score, total)
                    save_quiz_result_pg(username, total, score)
                    session_attempts.append({"username": username, "total": total, "correct": score})

                    pop = tk.Toplevel(root)
                    pop.title("Quiz Completed")
                    pop.geometry("420x220")
                    pop.configure(bg="#ffffff")
                    pop.grab_set()
                    frame = tk.Frame(pop, bg="#ffffff", padx=20, pady=20)
                    frame.pack(expand=True, fill="both")
                    tk.Label(frame, text="🎉 Quiz Completed!", font=("Segoe UI", 16, "bold"), bg="#ffffff").pack(pady=(10, 5))
                    tk.Label(frame, text=f"You scored {score} out of {total}.", font=("Segoe UI", 13), fg="#333", bg="#ffffff").pack()

                    btn_frame = tk.Frame(frame, bg="#ffffff")
                    btn_frame.pack(pady=20)

                    def show_solution_attached():
                        pop.destroy()
                        show_solution_in_main()

                    tk.Button(btn_frame, text="Back to Home", font=("Segoe UI", 11), width=16,
                              bg="#007bff", fg="white", activebackground="#0056b3",
                              command=pop.destroy).pack(side="left", padx=8)
                    tk.Button(btn_frame, text="View Solution", font=("Segoe UI", 11), width=16,
                              bg="#28a745", fg="white", activebackground="#218838",
                              command=show_solution_attached).pack(side="left", padx=8)

                    root.wait_window(pop)
                    if not has_given_feedback(username):
                        show_feedback_popup(ui_ref, username)

                # --- Solution attached to main window ---
                def show_solution_in_main():
                    if ui:
                        ui.clear()
                    sol_frame = tk.Frame(ui.main_content, bg="white")
                    sol_frame.pack(fill="both", expand=True)
                    idx_var = [0]

                    def render(idx):
                        for widget in sol_frame.winfo_children():
                            widget.destroy()
                        q = questions[idx]
                        user_ans = user_answers[idx] if idx < len(user_answers) else ""
                        correct_ans = q["answer"]

                        # Centered content frame
                        center = tk.Frame(sol_frame, bg="white")
                        center.place(relx=0.5, rely=0.5, anchor="center")

                        tk.Label(center, text=f"Question {idx+1} of {len(questions)}", font=("Segoe UI", 13, "bold"), bg="white").pack(pady=(18, 8))
                        tk.Label(center, text=q["question"], font=("Segoe UI", 15, "bold"), bg="white", wraplength=650, justify="left").pack(pady=(0, 18))

                        # Points label
                        if user_ans == "":
                            tk.Label(center, text="-1 point (not answered)", font=("Segoe UI", 13, "bold"), fg="#dc3545", bg="white").pack(pady=(0, 10))
                        elif user_ans == correct_ans:
                            tk.Label(center, text="+1 point", font=("Segoe UI", 13, "bold"), fg="#28a745", bg="white").pack(pady=(0, 10))
                        else:
                            tk.Label(center, text="-1 point", font=("Segoe UI", 13, "bold"), fg="#dc3545", bg="white").pack(pady=(0, 10))

                        for opt in q["options"]:
                            if opt == correct_ans:
                                bg = "#d4edda"
                                fg = "#155724"
                            elif opt == user_ans and user_ans != correct_ans and user_ans != "":
                                bg = "#f8d7da"
                                fg = "#721c24"
                            else:
                                bg = "white"
                                fg = "#222"
                            border = 2 if opt == correct_ans or (opt == user_ans and user_ans != correct_ans and user_ans != "") else 1
                            tk.Label(center, text=opt, font=("Segoe UI", 13), bg=bg, fg=fg,
                                     anchor="w", justify="left", padx=12, pady=6, bd=border, relief="solid", width=70).pack(pady=3, anchor="w")

                        nav_frame = tk.Frame(center, bg="white")
                        nav_frame.pack(pady=20)
                        if idx > 0:
                            tk.Button(nav_frame, text="Previous", font=("Segoe UI", 11), width=12,
                                      bg="#6c757d", fg="white", command=lambda: [idx_var.__setitem__(0, idx-1), render(idx-1)]).pack(side="left", padx=8)
                        if idx < len(questions) - 1:
                            tk.Button(nav_frame, text="Next", font=("Segoe UI", 11), width=12,
                                      bg="#6c63ff", fg="white", command=lambda: [idx_var.__setitem__(0, idx+1), render(idx+1)]).pack(side="left", padx=8)
                        if idx == len(questions) - 1:
                            tk.Button(nav_frame, text="Back to Home", font=("Segoe UI", 11), width=16,
                                      bg="#007bff", fg="white", activebackground="#0056b3",
                                      command=lambda: [ui.clear(), ui.show_welcome()]).pack(side="left", padx=8)

                    render(0)

                # --- New: handle timeout and go to next question ---
                def handle_timeout():
                    user_answers.append("")
                    idx[0] += 1
                    if idx[0] < len(questions):
                        current = questions[idx[0]]
                        if ui:
                            ui.show_question(current["question"], current["options"], submit, idx[0], len(questions), on_timeout=handle_timeout)
                    else:
                        show_score_popup(ui)

                # --- Submit answer handler ---
                def submit(ans):
                    user_answers.append(ans)
                    if ans == questions[idx[0]]["answer"]:
                        tracker.increment()
                    idx[0] += 1
                    if idx[0] < len(questions):
                        current = questions[idx[0]]
                        if ui:
                            ui.show_question(current["question"], current["options"], submit, idx[0], len(questions), on_timeout=handle_timeout)
                    else:
                        show_score_popup(ui)
                # --- Show first question, pass on_timeout handler ---
                current = questions[idx[0]]
                if ui:
                    ui.show_question(current["question"], current["options"], submit, idx[0], len(questions), on_timeout=handle_timeout)

            show_description()

        # Ask for question count, then proceed
        total_q = ask_question_count(root)
        after_question_count(total_q)

    def prompt_login():
        clear_root()
        # --- Main login/register choice frame (not popup) ---
        frame = tk.Frame(root, bg="white", padx=30, pady=30, bd=2, relief="ridge")
        frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(frame, text="Welcome to QuizMaster", font=("Segoe UI", 16, "bold"), fg="#2c3e50", bg="white").pack(pady=(0, 20))
        tk.Button(frame, text="Login", width=14, font=("Segoe UI", 12), bg="#007bff", fg="white", command=lambda: open_login()).pack(pady=10)
        tk.Button(frame, text="Register", width=14, font=("Segoe UI", 12), bg="#28a745", fg="white", command=lambda: open_register()).pack(pady=10)

        def open_login():
            clear_root()
            login_frame = tk.Frame(root, bg="white", padx=40, pady=40, bd=2, relief="ridge")
            login_frame.place(relx=0.5, rely=0.5, anchor="center")
            # Back arrow button (Unicode arrow), more left cornered (relative to root)
            arrow_btn = tk.Button(
                root, text="←", font=("Segoe UI", 16, "bold"), bg="white", fg="#007bff", bd=0,
                cursor="hand2", activebackground="white", activeforeground="#0056b3",
                command=lambda: [clear_root(), prompt_login()]
            )
            arrow_btn.place(x=10, y=10)  # Place at top-left of root window
            # Remove arrow button when login_frame is destroyed
            login_frame.bind("<Destroy>", lambda e: arrow_btn.destroy())
            tk.Label(login_frame, text="Login to QuizMaster", font=("Segoe UI", 18, "bold"), fg="#2c3e50", bg="white").pack(pady=(0, 28))
            tk.Label(login_frame, text="Username:", font=("Segoe UI", 13), bg="white").pack(anchor="w")
            name_entry = tk.Entry(login_frame, font=("Segoe UI", 12), width=34)
            name_entry.pack(pady=(0, 14))
            tk.Label(login_frame, text="Password:", font=("Segoe UI", 13), bg="white").pack(anchor="w")
            pass_entry = tk.Entry(login_frame, font=("Segoe UI", 12), width=34, show="*")
            pass_entry.pack()
            def handle_login():
                nonlocal username, ui
                uname = name_entry.get().strip()
                pwd = pass_entry.get().strip()
                if not validate_user_pg(uname, pwd):
                    show_popup(root, "Invalid Login", "Incorrect username or password.")
                    return
                clear_root()
                username = uname
                ui = QuizUI(root, start_quiz, username, do_logout, show_history, fetch_user_results_pg)
                btn_frame = tk.Frame(ui.container, bg="white")
                btn_frame.pack(anchor="ne", pady=5, padx=10)
                tk.Button(btn_frame, text="Comment", command=open_comment_popup, bg="orange", fg="white").pack(side="top", pady=2)
                tk.Button(btn_frame, text="Report", command=open_report_popup, bg="red", fg="white").pack(side="top", pady=2)
                ui.show_welcome()
            tk.Button(login_frame, text="Login", width=16, font=("Segoe UI", 12), bg="#007bff", fg="white", command=handle_login).pack(pady=28)
            tk.Button(login_frame, text="Forgot Password?", font=("Segoe UI", 10, "underline"), fg="blue", bg="white", bd=0, cursor="hand2", command=lambda: [clear_root(), reset_password_flow(root, prompt_login)]).pack()

        def open_register():
            clear_root()
            reg_frame = tk.Frame(root, bg="white", padx=40, pady=40, bd=2, relief="ridge")
            reg_frame.place(relx=0.5, rely=0.5, anchor="center")
            # Back arrow button (Unicode arrow), more left cornered (relative to root)
            arrow_btn = tk.Button(
                root, text="←", font=("Segoe UI", 16, "bold"), bg="white", fg="#007bff", bd=0,
                cursor="hand2", activebackground="white", activeforeground="#0056b3",
                command=lambda: [clear_root(), prompt_login()]
            )
            arrow_btn.place(x=10, y=10)  # Place at top-left of root window
            # Remove arrow button when reg_frame is destroyed
            reg_frame.bind("<Destroy>", lambda e: arrow_btn.destroy())
            tk.Label(reg_frame, text="Register for QuizMaster", font=("Segoe UI", 18, "bold"), fg="#2c3e50", bg="white").pack(pady=(0, 28))
            tk.Label(reg_frame, text="Username:", font=("Segoe UI", 13), bg="white").pack(anchor="w")
            name_entry = tk.Entry(reg_frame, font=("Segoe UI", 12), width=34)
            name_entry.pack(pady=(0, 14))
            tk.Label(reg_frame, text="Password:", font=("Segoe UI", 13), bg="white").pack(anchor="w")
            pass_entry = tk.Entry(reg_frame, font=("Segoe UI", 12), width=34, show="*")
            pass_entry.pack()
            tk.Label(reg_frame, text="Email:", font=("Segoe UI", 13), bg="white").pack(anchor="w", pady=(14,0))
            email_entry = tk.Entry(reg_frame, font=("Segoe UI", 12), width=34)
            email_entry.pack(pady=(0, 14))
            def handle_register():
                uname = name_entry.get().strip()
                pwd = pass_entry.get().strip()
                email = email_entry.get().strip()
                if not uname or not pwd or not email:
                    show_popup(root, "Missing Info", "Please enter username, password, and email.")
                    return
                if user_exists_pg(uname):
                    show_popup(root, "Already Exists", "Username already exists. Choose another.")
                    return
                if save_user_pg(uname, pwd, email):
                    def after_success():
                        clear_root()
                        prompt_login()  # Show login/register choice again
                    show_popup(root, "Success", f"User '{uname}' registered successfully.", "Login Now")
                    root.after(100, after_success)
                else:
                    show_popup(root, "Error", "Registration failed. Try again.")
            tk.Button(reg_frame, text="Register", width=16, font=("Segoe UI", 12), bg="#28a745", fg="white", command=handle_register).pack(pady=28)

    prompt_login()
    root.mainloop()
    cur.close()
    conn.close()

# ================== POPUP UTILITIES ==================
def ask_question_count(root):
    result = {"value": None}
    popup = tk.Toplevel(root)
    popup.title("Select Question Count")
    center_window(popup, 350, 200)
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)
    popup.grab_set()
    frame = tk.Frame(popup, bg="#ffffff", padx=20, pady=20)
    frame.pack(expand=True, fill="both")
    tk.Label(frame, text="How many questions do you want?", font=("Segoe UI", 13, "bold"), bg="#ffffff").pack(pady=(0, 10))
    entry = tk.Entry(frame, font=("Segoe UI", 12), width=10, justify="center")
    entry.pack(pady=5)
    entry.focus()
    def confirm():
        try:
            num = int(entry.get())
            if 1 <= num <= 50:
                result["value"] = num
                popup.destroy()
        except:
            entry.delete(0, tk.END)
    tk.Button(frame, text="Start Quiz", font=("Segoe UI", 11), bg="#28a745", fg="white", width=14,
              activebackground="#218838", command=confirm).pack(pady=15)
    root.wait_window(popup)
    return result["value"]

def show_popup(root, title, message, button_text="OK"):
    popup = tk.Toplevel(root)
    popup.title(title)
    center_window(popup, 350, 180)
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)
    popup.grab_set()
    frame = tk.Frame(popup, bg="#ffffff", padx=20, pady=20)
    frame.pack(expand=True, fill="both")
    tk.Label(frame, text=title, font=("Segoe UI", 14, "bold"), bg="#ffffff").pack(pady=(0, 10))
    tk.Label(frame, text=message, font=("Segoe UI", 11), bg="#ffffff", wraplength=300).pack()
    tk.Button(frame, text=button_text, font=("Segoe UI", 10), width=12,
              bg="#007bff", fg="white", activebackground="#0056b3", command=popup.destroy).pack(pady=15)
    root.wait_window(popup)

def center_window(win, width, height):
    win.update_idletasks()
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")

if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
