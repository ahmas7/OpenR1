"""
R1 - Desktop Agent
System tray, global hotkeys, background running
"""
import os
import sys
import threading
import asyncio
from pathlib import Path
from typing import Optional, Callable


class DesktopAgent:
    def __init__(self):
        self.running = False
        self.tray_icon = None
        self.hotkeys = {}
    
    def start_tray(self, app_name: str = "R1"):
        """Start system tray icon"""
        try:
            import pystray
            from PIL import Image, ImageDraw
            
            width = 64
            height = 64
            image = Image.new('RGB', (width, height), color=(236, 91, 19))
            draw = ImageDraw.Draw(image)
            draw.ellipse([16, 16, 48, 48], fill=(255, 255, 255))
            
            def on_click(icon, item):
                if str(item) == "Open R1":
                    import webbrowser
                    webbrowser.open("http://localhost:8000")
                elif str(item) == "Quit":
                    self.running = False
                    icon.stop()
            
            menu = pystray.Menu(
                pystray.MenuItem("Open R1", on_click),
                pystray.MenuItem("Quit", on_click)
            )
            
            self.tray_icon = pystray.Icon(app_name, image, app_name, menu)
            self.running = True
            self.tray_icon.run_detached()
            return True
        except ImportError:
            print("pystray not installed - tray disabled")
            return False
        except Exception as e:
            print(f"Tray error: {e}")
            return False
    
    def register_hotkey(self, key: str, callback: Callable):
        """Register global hotkey"""
        self.hotkeys[key] = callback
    
    def start_listener(self):
        """Start hotkey listener"""
        try:
            import keyboard
            
            for key, callback in self.hotkeys.items():
                keyboard.add_hotkey(key, callback)
            
            return True
        except ImportError:
            print("keyboard not installed - hotkeys disabled")
            return False
        except Exception as e:
            print(f"Hotkey error: {e}")
            return False
    
    def notify(self, title: str, message: str):
        """Send notification"""
        try:
            import win10toast
            win10toast.ToastNotifier().show_toast(title, message, duration=5)
        except:
            print(f"Notification: {title} - {message}")
    
    def watch_folder(self, folder: str, callback: Callable, extensions: list = None):
        """Watch folder for changes"""
        extensions = extensions or ["*"]
        
        def watch():
            import time
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class Handler(FileSystemEventHandler):
                def on_any_event(self, event):
                    if not event.is_directory:
                        ext = event.src_path.split('.')[-1] if '.' in event.src_path else ''
                        if '*' in extensions or ext in extensions:
                            callback(event.src_path, event.event_type)
            
            event_handler = Handler()
            observer = Observer()
            observer.schedule(event_handler, folder, recursive=True)
            observer.start()
            
            while self.running:
                time.sleep(1)
            
            observer.stop()
            observer.join()
        
        thread = threading.Thread(target=watch, daemon=True)
        thread.start()
        return thread


class BackgroundService:
    """Run R1 as background service"""
    
    def __init__(self):
        self.agent = DesktopAgent()
        self.data_dir = Path("E:/MYAI/R1/data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start desktop agent"""
        print("Starting R1 Desktop Agent...")
        
        self.agent.start_tray()
        
        self.agent.register_hotkey("ctrl+shift+r", lambda: self.restart_server())
        self.agent.register_hotkey("ctrl+shift+o", lambda: self.open_ui())
        
        self.agent.notify("R1", "Desktop Agent Started")
        
        print("R1 Desktop Agent running in background")
        print("Hotkeys: Ctrl+Shift+R (restart), Ctrl+Shift+O (open)")
        
        self.agent.running = True
        while self.agent.running:
            import time
            time.sleep(1)
    
    def restart_server(self):
        """Restart R1 server"""
        import subprocess
        subprocess.Popen(["python", "-m", "R1.api.server"], 
                       cwd=str(Path(__file__).parent))
        self.agent.notify("R1", "Server restarted")
    
    def open_ui(self):
        """Open web UI"""
        import webbrowser
        webbrowser.open("http://localhost:8000")


desktop_agent = DesktopAgent()
