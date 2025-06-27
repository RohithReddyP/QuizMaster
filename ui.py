import tkinter as tk
from tkinter import ttk
import pygame
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.animation as animation
import csv
from tkinter import filedialog
import os

class QuizUI:
    def __init__(self, master, on_start_quiz, username, on_logout, on_view_history, fetch_results_func):
        self.on_view_history = on_view_history
        self.fetch_results_func = fetch_results_func

        self.root = master
        self.root.configure(bg="#001f3f")
        self.root.bind("<Escape>", lambda e: self.root.attributes('-fullscreen', False))

        self.on_start_quiz = on_start_quiz
        self.on_logout = on_logout
        self.username = username

        self.timer_label = None
        self.remaining_time = 0
        self.timer_id = None
        self.selected = None
        self.submit_btn = None
        self.time_up_handler = None

        self.style = ttk.Style()
        self.style.configure("Cool.TRadiobutton", font=("Segoe UI", 14), padding=8)

        self.container = tk.Frame(self.root, bg="#001f3f")
        self.container.pack(fill="both", expand=True)

        # Add a dedicated main content frame inside container for dynamic content
        self.main_content = tk.Frame(self.container, bg="#001f3f")
        self.main_content.pack(fill="both", expand=True)

        pygame.mixer.init()
        self.sounds = {
            "click": pygame.mixer.Sound("assets/click.wav"),
            "correct": pygame.mixer.Sound("assets/correct.wav"),
            "wrong": pygame.mixer.Sound("assets/wrong.wav"),
            "timeout": pygame.mixer.Sound("assets/timeout.mp3")
        }

    def play_sound(self, name):
        try:
            self.sounds[name].play()
        except Exception as e:
            print(f"Sound error: {e}")

    def animate_fade_in(self, widget, delay=10, steps=20):
        widget.attributes('-alpha', 0.0)
        alpha = 0.0
        def fade():
            nonlocal alpha
            alpha += 1 / steps
            if alpha <= 1:
                widget.attributes('-alpha', alpha)
                widget.after(delay, fade)
        fade()

    def show_popup(self, title, message, button_text="OK", callback=None, sound=None):
        if sound:
            self.play_sound(sound)

        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.geometry("400x200")
        popup.configure(bg="white")
        popup.resizable(False, False)
        popup.attributes('-alpha', 0.0)
        self.animate_fade_in(popup)

        frame = tk.Frame(popup, bg="white", padx=20, pady=20)
        frame.pack(expand=True, fill="both")

        tk.Label(frame, text=title, font=("Segoe UI", 16, "bold"), fg="#2c3e50", bg="white").pack(pady=(0, 10))
        tk.Label(frame, text=message, font=("Segoe UI", 12), fg="#34495e", bg="white", wraplength=350, justify="center").pack(pady=(0, 20))

        tk.Button(frame, text=button_text, font=("Segoe UI", 11), bg="#007bff", fg="white",
                  activebackground="#0056b3", width=12,
                  command=lambda: (popup.destroy(), callback() if callback else None)).pack()

        popup.grab_set()
        self.root.wait_window(popup)

    def show_feedback_popup(self, on_submit):
        popup = tk.Toplevel(self.root)
        popup.title("Rate Your Experience")
        popup.geometry("420x400")  # Bigger size
        popup.configure(bg="#f5f5f5")
        popup.resizable(False, False)
        popup.grab_set()

        frame = tk.Frame(popup, bg="#f5f5f5", padx=20, pady=20)
        frame.pack(expand=True, fill="both")

        tk.Label(frame, text="🌟 Rate Your Quiz Experience", font=("Segoe UI", 15, "bold"), bg="#f5f5f5").pack(pady=(0, 15))

        rating = tk.IntVar()
        stars_frame = tk.Frame(frame, bg="#f5f5f5")
        stars_frame.pack(pady=5)

        def set_rating(val):
            rating.set(val)
            for i in range(5):
                star_buttons[i].config(text="★" if i < val else "☆")

        star_buttons = []
        for i in range(5):
            btn = tk.Button(stars_frame, text="☆", font=("Segoe UI", 22), bg="#f5f5f5", fg="#ffcc00",
                            bd=0, activebackground="#f5f5f5", command=lambda i=i: set_rating(i + 1))
            btn.pack(side="left", padx=3)
            star_buttons.append(btn)

        liked = tk.BooleanVar(value=True)
        like_frame = tk.Frame(frame, bg="#f5f5f5")
        like_frame.pack(pady=(10, 5))

        def select_like():
            liked.set(True)
            like_btn.config(relief="sunken")
            dislike_btn.config(relief="raised")

        def select_dislike():
            liked.set(False)
            like_btn.config(relief="raised")
            dislike_btn.config(relief="sunken")

        like_btn = tk.Button(like_frame, text="👍 Like", width=10, font=("Segoe UI", 11),
                             command=select_like, bg="#d4edda", fg="#155724", relief="sunken")
        like_btn.pack(side="left", padx=10)

        dislike_btn = tk.Button(like_frame, text="👎 Dislike", width=10, font=("Segoe UI", 11),
                                command=select_dislike, bg="#f8d7da", fg="#721c24", relief="raised")
        dislike_btn.pack(side="left", padx=10)

        tk.Label(frame, text="Leave a note (optional):", font=("Segoe UI", 11), bg="#f5f5f5").pack(pady=(15, 5))
        note_text = tk.Text(frame, height=4, width=42, font=("Segoe UI", 10))
        note_text.pack(pady=(0, 10))

        def on_submit_click():
            on_submit(rating.get(), liked.get(), note_text.get("1.0", tk.END).strip())
            popup.destroy()

        tk.Button(frame, text="Submit Feedback", font=("Segoe UI", 12, "bold"), width=20,
                  bg="#007bff", fg="white", activebackground="#0056b3", command=on_submit_click).pack(pady=10)

    def show_welcome(self):
        self.clear()
        self.play_sound("click")

        # --- Remove gradient, use solid white background for widget ---
        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()
        # Remove gradient canvas
        self.main_content.configure(bg="#001f3f")  # fallback background

        # --- Main content frame, centered, full screen ---
        frame = tk.Frame(self.main_content, bg="white", padx=80, pady=60)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        # --- Animated QuizMaster title ---
        title_label = tk.Label(
            frame,
            text="QuizMaster",
            font=("Segoe UI Black", 38, "bold"),
            bg="white",
            fg="#6c63ff"
        )
        title_label.pack(pady=(0, 16))

        def animate_title(i=0):
            colors = ["#6c63ff", "#007bff", "#17a2b8", "#ffc107", "#dc3545"]
            title_label.config(fg=colors[i % len(colors)])
            frame.after(400, lambda: animate_title(i + 1))
        animate_title()

        # --- Welcome text ---
        tk.Label(
            frame,
            text=f"Welcome, {self.username}!",
            font=("Montserrat", 28, "bold"),
            bg="white",
            fg="#22223b"
        ).pack(pady=(0, 28))

        # --- Buttons with modern style and hover ---
        def style_btn(btn, bg, fg, hover_bg):
            btn.configure(
                bg=bg, fg=fg, activebackground=hover_bg, activeforeground=fg,
                relief="flat", bd=0, font=("Segoe UI", 18, "bold"), cursor="hand2", highlightthickness=0
            )
            def on_enter(e): btn.config(bg=hover_bg)
            def on_leave(e): btn.config(bg=bg)
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

        btn1 = tk.Button(frame, text="🚀 Start Quiz", width=24,
                         command=lambda: (self.play_sound("click"), self.on_start_quiz()))
        style_btn(btn1, "#6c63ff", "white", "#5548c8")
        btn1.pack(pady=16)

        btn2 = tk.Button(frame, text="📈 View Progress", width=24,
                         command=lambda: (self.play_sound("click"), self.display_line_graph()))
        style_btn(btn2, "#17a2b8", "white", "#138496")
        btn2.pack(pady=8)

        btn3 = tk.Button(frame, text="💾 Download Results", width=24,
                         command=lambda: (self.play_sound("click"), self.download_results()))
        style_btn(btn3, "#ffc107", "#212529", "#e0a800")
        btn3.pack(pady=8)

        btn4 = tk.Button(frame, text="⏻ Logout", width=24,
                         command=lambda: (self.play_sound("click"), self.on_logout()))
        style_btn(btn4, "#dc3545", "white", "#c82333")
        btn4.pack(pady=16)

        # --- Footer ---
        tk.Label(frame, text="QuizMaster Pro Edition(Dev:Potha Rohith Reddy)", font=("Segoe UI", 14, "italic"),
                 bg="white", fg="#888").pack(pady=(28, 0))

    def show_progress(self):
        # This method wraps display_line_graph to ensure it is called on the correct widget
        self.display_line_graph()

    def download_results(self):
        # Fetch all quiz results for the current user
        results = self.fetch_results_func(self.username)
        if not results:
            self.show_popup("No Data", "You have no quiz results to download.")
            return

        # Ask user where to save the CSV
        save_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save quiz results as CSV",
            initialfile=f"{self.username}_quiz_results.csv"
        )
        if not save_path:
            return

        # Prepare new results as a set of tuples for uniqueness
        new_rows = set(
            (row[0], row[1], row[2].strftime("%Y-%m-%d %H:%M:%S"))
            for row in results
        )

        # If file exists, read existing rows to avoid duplicates
        existing_rows = set()
        if os.path.isfile(save_path):
            with open(save_path, mode="r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                headers = next(reader, None)
                for row in reader:
                    if len(row) == 3:
                        existing_rows.add(tuple(row))

        # Only add new rows that are not already in the file
        rows_to_write = new_rows - existing_rows

        # Write header if file does not exist, else append
        write_header = not os.path.isfile(save_path)
        with open(save_path, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["Total Questions", "Correct Answers", "Attempted At"])
            for row in sorted(rows_to_write, key=lambda x: x[2]):
                writer.writerow(row)

        if rows_to_write:
            self.show_popup("Success", f"New results appended to:\n{save_path}")
        else:
            self.show_popup("No New Results", "All your results are already in the CSV file.")

    def display_line_graph(self):
        self.clear()
        results = self.fetch_results_func(self.username)
        if not results:
            self.show_popup("No Data", "You have no quiz history to visualize.")
            return

        scores = [r[1] for r in results[::-1]]
        questions = [r[0] for r in results[::-1]]
        labels = [f"Q{i+1}" for i in range(len(results))]

        fig, ax = plt.subplots(figsize=(7, 5))
        canvas = FigureCanvasTkAgg(fig, master=self.main_content)
        canvas.get_tk_widget().pack(fill='both', expand=True)

        line1, = ax.plot([], [], 'g-o', label="Correct")
        line2, = ax.plot([], [], 'r--x', label="Total")
        ax.set_xlim(0, len(labels) - 1)
        ax.set_ylim(0, max(questions + [1]))
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_title("User Quiz Progress")
        ax.set_xlabel("Attempts")
        ax.set_ylabel("Questions")
        ax.legend()

        def update(frame):
            x = list(range(frame + 1))
            line1.set_data(x, scores[:frame + 1])
            line2.set_data(x, questions[:frame + 1])
            return line1, line2

        ani = animation.FuncAnimation(fig, update, frames=len(labels), interval=800, blit=True, repeat=False)
        canvas.draw()

        tk.Button(self.main_content, text="Back", font=("Segoe UI", 12), bg="#6c757d", fg="white",
                  command=lambda: (self.play_sound("click"), self.show_welcome())).pack(pady=10)

    def show_question(self, question, options, on_submit, question_index, total_questions, on_timeout=None):
        self.clear()
        self.main_content.update_idletasks()  # Force geometry update after clearing

        frame = tk.Frame(self.main_content, bg="white", padx=30, pady=30, bd=2, relief="ridge")
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        progress = int((question_index + 1) / total_questions * 100)
        ttk.Progressbar(frame, value=progress, maximum=100, length=300).pack(pady=(0, 20))

        tk.Label(frame, text=f"Question {question_index + 1} of {total_questions}",
                 font=("Segoe UI", 14, "italic"), bg="white", anchor="w").pack(fill="x")

        tk.Label(frame, text=question, font=("Segoe UI", 18, "bold"), wraplength=900,
                 bg="white", justify="left").pack(anchor="w", pady=(20, 10))

        self.selected = tk.StringVar(value="")

        for opt in options:
            ttk.Radiobutton(frame, text=opt, variable=self.selected, value=opt,
                            style="Cool.TRadiobutton").pack(anchor="w", pady=6)

        self.timer_label = tk.Label(frame, text="Time: 20", font=("Segoe UI", 14), fg="red", bg="white")
        self.timer_label.pack(pady=15)

        self.submit_btn = tk.Button(frame, text="Submit", font=("Segoe UI", 14, "bold"),
                                    bg="#28a745", fg="white", activebackground="#218838",
                                    activeforeground="white", width=12,
                                    command=lambda: self.submit_wrapper(on_submit))
        self.submit_btn.pack(pady=10)

        self.start_timer(20)

        self.time_up_handler = on_timeout  # Store the timeout handler for use in update_timer

    
    def start_timer(self, seconds):
        self.remaining_time = seconds
        self.update_timer()

    def update_timer(self):
        # Prevent updating timer_label if it has been destroyed
        if not hasattr(self, "timer_label") or not self.timer_label.winfo_exists():
            return
        self.timer_label.config(text=f"Time: {self.remaining_time}")
        if self.remaining_time > 0:
            self.remaining_time -= 1
            self.timer_id = self.root.after(1000, self.update_timer)
        else:
            self.submit_btn.config(state="disabled")
            self.show_popup("⏰ Time's Up", "Time's up for this question! Click OK to continue.",
                            "Next", callback=self.time_up_handler, sound="timeout")

    def submit_wrapper(self, on_submit, time_up=False):
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        self.submit_btn.config(state="disabled")
        self.play_sound("timeout" if time_up else "click")
        on_submit(self.selected.get() if not time_up else "")

    def clear(self):
        try:
            if hasattr(self, "main_content") and self.main_content.winfo_exists():
                # Only destroy children widgets, do not destroy self.main_content itself
                children = self.main_content.winfo_children()
                for widget in children:
                    widget.destroy()
                self.main_content.update_idletasks()  # Ensure geometry is updated after clearing
        except Exception as e:
            print(f"Error clearing main_content widgets: {e}")

    def ensure_main_content(self):
        if not hasattr(self, "main_content") or not self.main_content.winfo_exists():
            # Recreate main_content frame if missing or destroyed
            self.main_content = tk.Frame(self.container, bg="#001f3f")
            self.main_content.pack(fill="both", expand=True)

    def show_question(self, question, options, on_submit, question_index, total_questions, on_timeout=None):
        self.ensure_main_content()
        self.clear()
        self.main_content.update_idletasks()  # Force geometry update after clearing

        frame = tk.Frame(self.main_content, bg="white", padx=30, pady=30, bd=2, relief="ridge")
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        progress = int((question_index + 1) / total_questions * 100)
        ttk.Progressbar(frame, value=progress, maximum=100, length=300).pack(pady=(0, 20))

        tk.Label(frame, text=f"Question {question_index + 1} of {total_questions}",
                 font=("Segoe UI", 14, "italic"), bg="white", anchor="w").pack(fill="x")

        tk.Label(frame, text=question, font=("Segoe UI", 18, "bold"), wraplength=900,
                 bg="white", justify="left").pack(anchor="w", pady=(20, 10))

        self.selected = tk.StringVar(value="")

        for opt in options:
            ttk.Radiobutton(frame, text=opt, variable=self.selected, value=opt,
                            style="Cool.TRadiobutton").pack(anchor="w", pady=6)

        self.timer_label = tk.Label(frame, text="Time: 20", font=("Segoe UI", 14), fg="red", bg="white")
        self.timer_label.pack(pady=15)

        self.submit_btn = tk.Button(frame, text="Submit", font=("Segoe UI", 14, "bold"),
                                    bg="#28a745", fg="white", activebackground="#218838",
                                    activeforeground="white", width=12,
                                    command=lambda: self.submit_wrapper(on_submit))
        self.submit_btn.pack(pady=10)

        self.start_timer(20)

        self.time_up_handler = on_timeout  # Store the timeout handler for use in update_timer
