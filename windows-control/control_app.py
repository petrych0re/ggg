import os
import sys
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

APP_DIR = Path.home() / "TelegramAIControl"
ENV_FILE = APP_DIR / ".env"
APP_DIR.mkdir(parents=True, exist_ok=True)

class ControlApp:
    def __init__(self, root):
        self.root = root
        root.title("Telegram AI Bot Control")
        root.geometry("820x620")
        root.minsize(700, 500)
        self.proc = None
        self.q = queue.Queue()
        self.bot_path = tk.StringVar(value=str(Path.cwd() / "bot.py"))
        self.env_path = tk.StringVar(value=str(ENV_FILE))
        self.status = tk.StringVar(value="Stopped")
        self._build()
        self._poll()
        self.load_env()

    def _build(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Telegram AI Bot Control", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Jalankan bot di komputer ini. Jangan bagikan file .env atau token.").pack(anchor="w", pady=(2, 12))
        row = ttk.Frame(outer); row.pack(fill="x", pady=3)
        ttk.Label(row, text="File bot.py", width=12).pack(side="left")
        ttk.Entry(row, textvariable=self.bot_path).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(row, text="Pilih...", command=self.pick_bot).pack(side="left")
        row = ttk.Frame(outer); row.pack(fill="x", pady=3)
        ttk.Label(row, text="File .env", width=12).pack(side="left")
        ttk.Entry(row, textvariable=self.env_path).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(row, text="Pilih...", command=self.pick_env).pack(side="left")
        buttons = ttk.Frame(outer); buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="Start Bot", command=self.start).pack(side="left")
        ttk.Button(buttons, text="Stop Bot", command=self.stop).pack(side="left", padx=6)
        ttk.Button(buttons, text="Buat / Edit .env", command=self.edit_env).pack(side="left")
        ttk.Button(buttons, text="Buka Folder Konfigurasi", command=self.open_folder).pack(side="left", padx=6)
        ttk.Label(outer, textvariable=self.status, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(outer, text="Log bot").pack(anchor="w")
        self.log = tk.Text(outer, height=18, wrap="word", state="disabled", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, pady=(4, 0))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def pick_bot(self):
        p = filedialog.askopenfilename(title="Pilih bot.py", filetypes=[("Python file", "*.py"), ("All files", "*.*")])
        if p: self.bot_path.set(p)

    def pick_env(self):
        p = filedialog.asksaveasfilename(title="Pilih atau buat file .env", initialdir=str(APP_DIR), initialfile=".env", defaultextension="")
        if p: self.env_path.set(p); self.load_env()

    def load_env(self):
        p = Path(self.env_path.get())
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# Isi konfigurasi bot di sini. Jangan commit file ini ke GitHub.\nTELEGRAM_BOT_TOKEN=\nOPENAI_API_KEY=\nMYSQL_HOST=127.0.0.1\nMYSQL_PORT=3306\nMYSQL_USER=root\nMYSQL_PASSWORD=\nMYSQL_DATABASE=telegram_ai\nADMIN_ID=0\nOPENAI_MODEL=gpt-4.1-mini\n", encoding="utf-8")

    def edit_env(self):
        self.load_env()
        try:
            if sys.platform == "win32": os.startfile(self.env_path.get())
            else: messagebox.showinfo("File .env", f"Edit file ini dengan text editor:\n{self.env_path.get()}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def open_folder(self):
        try:
            if sys.platform == "win32": os.startfile(str(Path(self.env_path.get()).parent))
        except Exception as e: messagebox.showerror("Error", str(e))

    def start(self):
        if self.proc and self.proc.poll() is None:
            messagebox.showinfo("Bot", "Bot sudah berjalan."); return
        bot = Path(self.bot_path.get())
        envp = Path(self.env_path.get())
        if not bot.is_file():
            messagebox.showerror("File tidak ditemukan", "Pilih file bot.py yang benar."); return
        if not envp.is_file():
            self.load_env()
        env = os.environ.copy()
        try:
            for line in envp.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
            self.proc = subprocess.Popen([sys.executable, str(bot)], cwd=str(bot.parent), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            self.status.set("Running")
            self.write_log(f"--- Started: {bot} ---")
            threading.Thread(target=self._read_output, daemon=True).start()
        except Exception as e:
            self.status.set("Error")
            messagebox.showerror("Gagal menjalankan bot", str(e))

    def _read_output(self):
        p = self.proc
        if not p or not p.stdout: return
        for line in p.stdout: self.q.put(line)
        code = p.wait()
        self.q.put(f"\n[Bot berhenti dengan kode {code}]")
        self.q.put("__STOPPED__")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.write_log("Meminta bot berhenti...")
        else:
            self.status.set("Stopped")

    def _poll(self):
        try:
            while True:
                line = self.q.get_nowait()
                if line == "__STOPPED__": self.status.set("Stopped")
                else: self.write_log(line)
        except queue.Empty: pass
        self.root.after(150, self._poll)

    def close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno("Keluar", "Bot masih berjalan. Hentikan bot dan keluar?"): return
            self.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    try: ttk.Style().theme_use("vista")
    except tk.TclError: pass
    ControlApp(root)
    root.mainloop()
