"""
R1 Desktop GUI - Tkinter-based interface for the R1 assistant
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import asyncio
import threading
import queue
from datetime import datetime
from typing import Optional


class R1GUI:
    """Tkinter-based GUI for R1 Assistant"""

    def __init__(self, runtime=None):
        self.runtime = runtime
        self.root = None
        self.message_queue = queue.Queue()
        self.running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def _create_ui(self):
        """Create the user interface"""
        self.root = tk.Tk()
        self.root.title("R1 Assistant")
        self.root.geometry("900x700")
        self.root.minsize(600, 400)

        # Configure styles
        self.style = ttk.Style()
        self.style.configure("Header.TFrame", background="#2c3e50")
        self.style.configure("Header.TLabel", background="#2c3e50", foreground="white")

        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Header
        self._create_header(main_frame)

        # Chat area
        self._create_chat_area(main_frame)

        # Input area
        self._create_input_area(main_frame)

        # Status bar
        self._create_status_bar(main_frame)

        # Menu
        self._create_menu()

        # Bind window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_header(self, parent):
        """Create the header section"""
        header = ttk.Frame(parent, style="Header.TFrame", padding="10")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)

        # Logo/Title
        title = ttk.Label(
            header,
            text="R1 Assistant",
            style="Header.TLabel",
            font=("Segoe UI", 14, "bold")
        )
        title.grid(row=0, column=0, sticky="w")

        # Connection status
        self.status_label = ttk.Label(
            header,
            text="Connecting...",
            style="Header.TLabel",
            font=("Segoe UI", 9)
        )
        self.status_label.grid(row=0, column=1, sticky="e")

    def _create_chat_area(self, parent):
        """Create the chat display area"""
        chat_frame = ttk.LabelFrame(parent, text="Conversation", padding="5")
        chat_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)

        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            padx=10,
            pady=10,
            state="disabled"
        )
        self.chat_display.grid(row=0, column=0, sticky="nsew")

        # Configure tags for styling
        self.chat_display.tag_configure("user", foreground="#2c3e50", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_configure("assistant", foreground="#27ae60", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_configure("timestamp", foreground="#7f8c8d", font=("Segoe UI", 8))
        self.chat_display.tag_configure("system", foreground="#e74c3c", font=("Segoe UI", 9, "italic"))

    def _create_input_area(self, parent):
        """Create the input section"""
        input_frame = ttk.Frame(parent)
        input_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)

        # Message entry
        self.message_entry = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.message_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.message_entry.bind("<Return>", lambda e: self._send_message())

        # Send button
        send_btn = ttk.Button(
            input_frame,
            text="Send",
            command=self._send_message
        )
        send_btn.grid(row=0, column=1)

        # Quick actions
        actions_frame = ttk.Frame(parent)
        actions_frame.grid(row=3, column=0, sticky="ew")

        actions = [
            ("Clear", self._clear_chat),
            ("Save", self._save_conversation),
            ("Settings", self._show_settings),
            ("About", self._show_about),
        ]

        for i, (label, command) in enumerate(actions):
            btn = ttk.Button(actions_frame, text=label, command=command)
            btn.grid(row=0, column=i, padx=(0, 5))

    def _create_status_bar(self, parent):
        """Create the status bar"""
        self.status_bar = ttk.Label(
            parent,
            text="Ready",
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.grid(row=4, column=0, sticky="ew")

    def _create_menu(self):
        """Create the application menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Conversation", command=self._clear_chat)
        file_menu.add_command(label="Save Conversation...", command=self._save_conversation)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Dark Mode", command=self._toggle_theme)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _add_message(self, sender: str, message: str, msg_type: str = "normal"):
        """Add a message to the chat display"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        self.chat_display.configure(state="normal")

        # Add timestamp
        self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")

        # Add sender
        if sender == "user":
            self.chat_display.insert(tk.END, "You: ", "user")
        elif sender == "assistant":
            self.chat_display.insert(tk.END, "R1: ", "assistant")
        else:
            self.chat_display.insert(tk.END, f"{sender}: ", "system")

        # Add message
        self.chat_display.insert(tk.END, f"{message}\n\n")

        # Scroll to bottom
        self.chat_display.see(tk.END)
        self.chat_display.configure(state="disabled")

    def _send_message(self):
        """Send a message"""
        message = self.message_entry.get().strip()
        if not message:
            return

        self.message_entry.delete(0, tk.END)
        self._add_message("user", message)

        # Process message in background
        threading.Thread(
            target=self._process_message,
            args=(message,),
            daemon=True
        ).start()

    def _process_message(self, message: str):
        """Process a message using the runtime"""
        try:
            if self.runtime:
                # Use asyncio to run the async runtime
                result = asyncio.run(self._chat_with_runtime(message))
                self.message_queue.put(("assistant", result))
            else:
                self.message_queue.put(("assistant", "Runtime not available. Please start R1 server."))
        except Exception as e:
            self.message_queue.put(("system", f"Error: {str(e)}"))

    async def _chat_with_runtime(self, message: str) -> str:
        """Send message to runtime and get response"""
        if hasattr(self.runtime, 'chat'):
            response = await self.runtime.chat(message)
            return response.get("response", "No response")
        return "Runtime does not support chat"

    def _check_queue(self):
        """Check for messages from background threads"""
        try:
            while True:
                sender, message = self.message_queue.get_nowait()
                self._add_message(sender, message)
        except queue.Empty:
            pass

        if self.running:
            self.root.after(100, self._check_queue)

    def _clear_chat(self):
        """Clear the chat display"""
        self.chat_display.configure(state="normal")
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.configure(state="disabled")
        self._add_message("system", "Conversation cleared.")

    def _save_conversation(self):
        """Save the conversation to a file"""
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                self.chat_display.configure(state="normal")
                content = self.chat_display.get(1.0, tk.END)
                self.chat_display.configure(state="disabled")

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)

                messagebox.showinfo("Success", f"Conversation saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {str(e)}")

    def _show_settings(self):
        """Show settings dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Settings", font=("Segoe UI", 12, "bold")).pack(pady=10)

        # Model settings
        model_frame = ttk.LabelFrame(dialog, text="Model", padding="10")
        model_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(model_frame, text="Provider:").grid(row=0, column=0, sticky=tk.W)
        provider_var = tk.StringVar(value="ollama")
        ttk.Combobox(
            model_frame,
            textvariable=provider_var,
            values=["ollama", "gguf", "openai", "anthropic"],
            state="readonly"
        ).grid(row=0, column=1, sticky=tk.EW)

        ttk.Button(dialog, text="Save", command=dialog.destroy).pack(pady=20)

    def _show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About R1",
            "R1 Assistant\n\n"
            "A local-first AI assistant with:\n"
            "- Chat interface\n"
            "- Skills system\n"
            "- Tool integration\n"
            "- Memory persistence\n\n"
            "Version: 2.0.0"
        )

    def _toggle_theme(self):
        """Toggle between light and dark themes"""
        # Simple implementation - could be expanded
        messagebox.showinfo("Theme", "Dark mode toggle would be implemented here")

    def _on_close(self):
        """Handle window close"""
        self.running = False
        if self.root:
            self.root.destroy()

    def run(self):
        """Run the GUI application"""
        self._create_ui()
        self.running = True

        # Update status
        if self.runtime:
            self.status_label.configure(text="Connected")
            self.status_label.configure(foreground="#27ae60")
        else:
            self.status_label.configure(text="Standalone Mode")
            self.status_label.configure(foreground="#f39c12")

        # Add welcome message
        self._add_message(
            "assistant",
            "Hello! I'm R1. How can I help you today?"
        )

        # Start queue checker
        self._check_queue()

        # Run the main loop
        self.root.mainloop()


def run_gui(runtime=None):
    """Run the R1 GUI application"""
    gui = R1GUI(runtime=runtime)
    gui.run()


if __name__ == "__main__":
    run_gui()
