"""
gui/app.py — NOVA graphical interface (tkinter).

Features:
  - Scrolled chat log
  - Text input + Send (Enter key)
  - Microphone button (runs STT in background thread)
  - Commands processed via nova.process_command() on worker thread
"""
import tkinter as tk
from tkinter import scrolledtext
import threading
from utils.logger import get_logger

logger = get_logger("gui")

def run_gui(nova):
    root = tk.Tk()
    root.title("NOVA — Voice Assistant")
    root.geometry("700x560")
    root.configure(bg="#0d0d0d")
    root.resizable(False, False)

    # ── Header ───────────────────────────────────────────────
    header = tk.Label(root, text="N O V A", font=("Courier", 28, "bold"),
                      fg="#00ffcc", bg="#0d0d0d")
    header.pack(pady=(20, 2))

    subtitle = tk.Label(root, text="Next-gen Operative Voice Assistant",
                        font=("Courier", 10), fg="#555555", bg="#0d0d0d")
    subtitle.pack()

    # ── Chat log ─────────────────────────────────────────────
    chat_box = scrolledtext.ScrolledText(
        root, wrap=tk.WORD, width=80, height=18,
        bg="#111111", fg="#cccccc", font=("Courier", 10),
        insertbackground="white", borderwidth=0
    )
    chat_box.pack(padx=20, pady=15)
    chat_box.config(state=tk.DISABLED)

    # ── Status ───────────────────────────────────────────────
    status_var = tk.StringVar(value="Ready")
    status_label = tk.Label(root, textvariable=status_var,
                            font=("Courier", 9), fg="#00ffcc", bg="#0d0d0d")
    status_label.pack()

    # ── Input Row ────────────────────────────────────────────
    input_frame = tk.Frame(root, bg="#0d0d0d")
    input_frame.pack(fill=tk.X, padx=20, pady=10)

    entry = tk.Entry(input_frame, font=("Courier", 12), bg="#1a1a1a",
                     fg="white", insertbackground="white", borderwidth=0,
                     relief=tk.FLAT)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0, 10))

    # ── Helper: append to chat ───────────────────────────────
    def append_chat(speaker, message):
        chat_box.config(state=tk.NORMAL)
        chat_box.insert(tk.END, f"{speaker}: {message}\n")
        chat_box.see(tk.END)
        chat_box.config(state=tk.DISABLED)

    # ── Helper: run command in background ────────────────────
    def run_command(text):
        if not text:
            return
        append_chat("You", text)
        status_var.set("Thinking...")

        def task():
            result = nova.process_command(text)
            root.after(0, lambda: append_chat("NOVA", result["response"]))
            root.after(0, lambda: status_var.set("Ready"))
            if result.get("exit"):
                root.after(1000, root.destroy)

        threading.Thread(target=task, daemon=True).start()

    # ── Send button (type) ───────────────────────────────────
    def send_command(event=None):
        text = entry.get().strip()
        entry.delete(0, tk.END)
        run_command(text)

    send_btn = tk.Button(input_frame, text="Send", font=("Courier", 11),
                         bg="#00ffcc", fg="#0d0d0d", activebackground="#00cc99",
                         borderwidth=0, padx=16, pady=6, command=send_command)
    send_btn.pack(side=tk.RIGHT)
    entry.bind("<Return>", send_command)

    # ── Mic button (voice) ───────────────────────────────────
    mic_listening = {"active": False}

    def toggle_mic():
        if mic_listening["active"]:
            return  # already listening, ignore double click

        mic_listening["active"] = True
        mic_btn.config(text="🔴 Listening...", bg="#ff4444", fg="white")
        status_var.set("Listening... speak now!")

        def listen_task():
            try:
                from voice.speech_recognition_engine import get_speech_engine
                engine = get_speech_engine(language=nova.language)
                text = engine.listen()

                if text:
                    root.after(0, lambda: run_command(text))
                else:
                    root.after(0, lambda: status_var.set("Didn't catch that. Try again."))
            except Exception as e:
                logger.error(f"Mic error: {e}")
                root.after(0, lambda: status_var.set(f"Mic error: {e}"))
            finally:
                root.after(0, lambda: mic_btn.config(
                    text="🎤 Speak", bg="#1a1a1a", fg="#00ffcc"))
                root.after(0, lambda: status_var.set("Ready"))
                mic_listening["active"] = False

        threading.Thread(target=listen_task, daemon=True).start()

    mic_btn = tk.Button(root, text="🎤 Speak", font=("Courier", 11),
                        bg="#1a1a1a", fg="#00ffcc",
                        activebackground="#222222",
                        borderwidth=0, padx=20, pady=8,
                        command=toggle_mic)
    mic_btn.pack(pady=(0, 15))

    # ── Greet on open ────────────────────────────────────────
    def on_start():
        msg = nova.responses.greeting()
        append_chat("NOVA", msg)
        threading.Thread(target=nova.say, args=(msg,), daemon=True).start()

    root.after(500, on_start)
    root.mainloop()