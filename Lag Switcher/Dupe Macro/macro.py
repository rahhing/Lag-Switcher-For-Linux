#!/usr/bin/env python3
import sys
import subprocess
import time
import threading
import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import platform

# --- DEPENDENCY CHECK ---
def check_dependencies():
    missing = []
    try: import pynput
    except ImportError: missing.append("pynput")
    if missing:
        root = tk.Tk(); root.withdraw()
        if messagebox.askyesno("Missing Dependencies", f"Install {', '.join(missing)}?"):
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", *missing])
            os.execv(sys.executable, [sys.executable] + sys.argv)
        sys.exit()

check_dependencies()
from pynput import keyboard

IS_LINUX = platform.system() == "Linux"

# --- CONFIGURATION ---
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "macro_config.json")
DEFAULT_CONFIG = {
    "click_cps": 10,
    "key_macro_trigger": "Key.f3",
    # Timeline defaults tuned per user request:
    # - Hold immediately for ~1.0s
    # - Small gap (~0.35s) then disconnect
    # - Stay offline ~1.5s then reconnect
    # - Start spamming for ~4.0s
    "macro_hold_start": 0.0,
    "macro_hold_len": 1.0,
    "macro_net_start": 1.35,
    "macro_net_len": 1.5,
    "macro_spam_start": 2.85,
    "macro_spam_len": 4.0,
    "overlay_enabled": True,
    "overlay_x": 20,
    "overlay_y": 20,
    "fallback_key": "",
    "network_interface": "",  # Auto-detect by default
    "bandwidth_limit": 100,   # kbps (0 = block all)
}  

# Debug flag to help troubleshoot overlay visibility
DEBUG_OVERLAY = True

state = {
    "is_lagging": False,
    "is_running_macro": False,
    "is_spamming": False,
    "is_holding": False,
    "overlay_ref": None,
    "config": DEFAULT_CONFIG.copy(),
    "capturing_fallback": False,
    "network_interface": None,
}  

# --- NETWORK FUNCTIONS (Linux tc-based, like lagger.py) ---

def get_network_interfaces():
    """Get list of available network interfaces (excluding loopback)"""
    if not IS_LINUX:
        return []
    try:
        result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
        interfaces = []
        for line in result.stdout.split('\n'):
            match = re.match(r'^\d+:\s+(\S+):', line)
            if match:
                iface = match.group(1)
                if iface != 'lo':  # Exclude loopback
                    interfaces.append(iface)
        return interfaces if interfaces else ["eth0"]
    except:
        return ["eth0", "wlan0"]

def init_network_interface():
    """Initialize network interface from config or auto-detect"""
    if not IS_LINUX:
        return None
    
    configured = state["config"].get("network_interface", "")
    if configured:
        return configured
    
    interfaces = get_network_interfaces()
    if interfaces:
        return interfaces[0]
    return "eth0"

# --- SYSTEM FUNCTIONS ---








def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                state["config"].update(json.load(f))
        except: pass

def save_config():
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(state["config"], f, indent=4)
    except: pass

# --- NET LOGIC ---
def disconnect_net():
    if state["is_lagging"]: return
    state["is_lagging"] = True
    
    if IS_LINUX:
        print(">> NET: Disconnecting using tc")
        enable_lag_linux()
    else:
        print(">> FALLBACK: pressing configured key to simulate disconnect")
        press_fallback_key()
    
    update_overlay()

def reconnect_net():
    if not state["is_lagging"]: return
    state["is_lagging"] = False
    
    if IS_LINUX:
        print(">> NET: Reconnecting using tc")
        disable_lag_linux()
    else:
        print(">> FALLBACK: pressing configured key to simulate reconnect")
        press_fallback_key()
    
    update_overlay()

def enable_lag_linux():
    """Enable network lag using tc (like lagger.py)"""
    interface = state["network_interface"]
    if not interface:
        print(">> ERROR: No network interface configured")
        return
    
    bandwidth = state["config"].get("bandwidth_limit", 100)
    
    try:
        # Clear any existing rules
        subprocess.run(['sudo', 'tc', 'qdisc', 'del', 'dev', interface, 'root'], 
                     stderr=subprocess.DEVNULL)
        
        if bandwidth == 0:
            # Block all traffic with 100% packet loss
            cmd = [
                'sudo', 'tc', 'qdisc', 'add', 'dev', interface, 'root', 'netem',
                'loss', '100%'
            ]
        else:
            # Limit bandwidth with tbf
            cmd = [
                'sudo', 'tc', 'qdisc', 'add', 'dev', interface, 'root', 'tbf',
                'rate', f'{bandwidth}kbit',
                'burst', '32kbit',
                'latency', '400ms'
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f">> NET: Lag enabled on {interface} ({bandwidth} kbps)")
        else:
            print(f">> ERROR: Failed to enable lag: {result.stderr}")
            
    except Exception as e:
        print(f">> ERROR: Failed to enable lag: {e}")

def disable_lag_linux():
    """Disable network lag (like lagger.py)"""
    interface = state["network_interface"]
    if not interface:
        print(">> ERROR: No network interface configured")
        return
    
    try:
        cmd = ['sudo', 'tc', 'qdisc', 'del', 'dev', interface, 'root']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f">> NET: Lag disabled on {interface}")
        else:
            print(f">> ERROR: Failed to disable lag: {result.stderr}")
            
    except Exception as e:
        print(f">> ERROR: Failed to disable lag: {e}")

# --- INPUT DRIVER ---
# Use pynput for cross-platform mouse control
from pynput.mouse import Button, Controller as MouseController

mouse_controller = MouseController()

def click_mouse_fast():
    """Cross-platform mouse click using pynput"""
    mouse_controller.press(Button.left)
    # Robust hold time for games (20ms - 40ms)
    time.sleep(0.02 + (time.time() % 0.02))
    mouse_controller.release(Button.left)

# --- MACRO ENGINE ---
def run_complex_macro():
    if state["is_running_macro"]: return
    state["is_running_macro"] = True
    print(">> MACRO: STARTING TIMELINE")
    update_overlay()
    
    c = state["config"]
    # Load Timings
    hold_start = float(c.get("macro_hold_start", 0))
    hold_len   = float(c.get("macro_hold_len", 2.0))
    net_start  = float(c.get("macro_net_start", 1.5))
    net_len    = float(c.get("macro_net_len", 4.0))
    spam_start = float(c.get("macro_spam_start", 2.2))
    spam_len   = float(c.get("macro_spam_len", 3.0))
    cps        = int(c.get("click_cps", 10))

    # Task: Hold Click
    def task_hold():
        if hold_len <= 0: return
        time.sleep(hold_start)
        print(">> HOLD: DOWN")
        state["is_holding"] = True
        update_overlay()
        mouse_controller.press(Button.left)
        time.sleep(hold_len)
        print(">> HOLD: RELEASE")
        mouse_controller.release(Button.left)
        state["is_holding"] = False
        update_overlay()

    # Task: Network
    def task_net():
        if net_len <= 0: return
        time.sleep(net_start)
        disconnect_net()
        time.sleep(net_len)
        reconnect_net()

    # Task: Spam
    def task_spam():
        if spam_len <= 0: return
        time.sleep(spam_start)
        print(">> SPAM: START")
        state["is_spamming"] = True
        update_overlay()
        end_t = time.time() + spam_len
        interval = 1.0 / cps
        while time.time() < end_t:
            click_mouse_fast()
            # Adjust sleep to account for hold time (~0.03s)
            time.sleep(max(0, interval - 0.03))
        print(">> SPAM: END")
        state["is_spamming"] = False
        update_overlay()

    # Execute
    t1 = threading.Thread(target=task_hold)
    t2 = threading.Thread(target=task_net)
    t3 = threading.Thread(target=task_spam)
    t1.start(); t2.start(); t3.start()
    
    # Waiter
    def waiter():
        t1.join(); t2.join(); t3.join()
        state["is_running_macro"] = False
        print(">> MACRO: FINISHED")
        update_overlay()
    threading.Thread(target=waiter).start()

def parse_key_string(k_str):
    if k_str.startswith("Key."):
        attr = k_str.split(".")[1]
        return getattr(keyboard.Key, attr, None)
    return k_str


def key_to_string(key):
    """Convert a pynput key into a storable string."""
    try:
        if hasattr(key, 'char') and key.char is not None:
            return key.char
        return str(key)
    except:
        return str(key)


def press_fallback_key():
    """Press the configured fallback key via pynput Controller."""
    fk = state["config"].get("fallback_key")
    if not fk:
        if DEBUG_OVERLAY: print(">> FALLBACK: no key configured")
        return
    k = parse_key_string(fk)
    controller = keyboard.Controller()
    try:
        controller.press(k)
        time.sleep(0.05)
        controller.release(k)
        if DEBUG_OVERLAY: print(f">> FALLBACK: pressed {fk}")
    except Exception as e:
        if DEBUG_OVERLAY: print(">> FALLBACK: press failed:", e)


def on_key_press(key):
    # If we're capturing a key for the fallback assignment, don't trigger the macro
    if state.get("capturing_fallback"):
        return
    try:
        target = parse_key_string(state["config"].get("key_macro_trigger", "Key.f3"))
        if key == target or (hasattr(key, 'char') and key.char == target):
            threading.Thread(target=run_complex_macro).start()
    except: pass

# --- UI ---
THEME = {"bg": "#0a0a0a", "fg": "#00ff41", "warning": "#ff3333", "font_main": ("Consolas", 10), "font_header": ("Consolas", 14, "bold"), "font_mono": ("Consolas", 9)}

class HackerButton(tk.Button):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.config(bg="black", fg=THEME["fg"], activebackground=THEME["fg"], activeforeground="black", font=THEME["font_main"], bd=1, relief="solid")

class Overlay(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        # Set attributes in a robust way across Tk versions/platforms
        try:
            self.wm_attributes("-topmost", True)
        except Exception:
            try:
                self.attributes("-topmost", True)
            except Exception:
                pass
        # Clamp overlay coordinates to the primary monitor so it's not off-screen
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
        except Exception:
            sw, sh = 1920, 1080
        ox = int(state["config"].get("overlay_x", 20))
        oy = int(state["config"].get("overlay_y", 20))
        ox = max(0, min(ox, max(0, sw - 50)))
        oy = max(0, min(oy, max(0, sh - 20)))
        state["config"]["overlay_x"] = ox
        state["config"]["overlay_y"] = oy
        if DEBUG_OVERLAY: print(f"Overlay: init clamped to {ox},{oy} screen={sw}x{sh}")
        self.config(bg="black")
        self.lbl_status = tk.Label(self, text="NET: ONLINE", font=("Consolas", 10, "bold"), bg="black", fg=THEME["fg"])
        self.lbl_status.pack(anchor="w")
        self.lbl_macro = tk.Label(self, text="", font=("Consolas", 10, "bold"), bg="black", fg=THEME["warning"])
        self.lbl_macro.pack(anchor="w")
        self.lbl_click = tk.Label(self, text="", font=("Consolas", 10, "bold"), bg="black", fg=THEME["fg"])
        self.lbl_click.pack(anchor="w")
        self.geometry(f"150x70+{state['config']['overlay_x']}+{state['config']['overlay_y']}")
        if DEBUG_OVERLAY: print("Overlay: geometry set ->", self.geometry())
        # Allow dragging by clicking either the toplevel or its labels
        self.bind("<Button-1>", self.start_move); self.bind("<B1-Motion>", self.do_move); self.bind("<ButtonRelease-1>", self.stop_move)
        self.lbl_status.bind("<Button-1>", self.start_move); self.lbl_status.bind("<B1-Motion>", self.do_move); self.lbl_status.bind("<ButtonRelease-1>", self.stop_move)
        self.lbl_macro.bind("<Button-1>", self.start_move); self.lbl_macro.bind("<B1-Motion>", self.do_move); self.lbl_macro.bind("<ButtonRelease-1>", self.stop_move)
        self.lbl_click.bind("<Button-1>", self.start_move); self.lbl_click.bind("<B1-Motion>", self.do_move); self.lbl_click.bind("<ButtonRelease-1>", self.stop_move)
    
    def start_move(self, event): self.x = event.x; self.y = event.y
    def do_move(self, event):
        x = self.winfo_x() + (event.x - self.x); y = self.winfo_y() + (event.y - self.y)
        self.geometry(f"+{x}+{y}")
    def stop_move(self, event):
        state["config"]["overlay_x"] = self.winfo_x(); state["config"]["overlay_y"] = self.winfo_y()
        save_config()

def update_overlay():
    if not state["overlay_ref"] or not state["overlay_ref"].winfo_exists(): return
    ov = state["overlay_ref"]
    if state["config"]["overlay_enabled"]:
        ov.deiconify()
        # Ensure overlay is above the main window
        try:
            ov.wm_attributes("-topmost", True)
        except Exception:
            try: ov.attributes("-topmost", True)
            except: pass
        try: ov.lift()
        except: pass
        if DEBUG_OVERLAY:
            try:
                print("update_overlay: exists=", ov.winfo_exists(), "mapped=", ov.winfo_ismapped(), "visible_geometry=", ov.geometry())
            except Exception:
                print("update_overlay: overlay present (winfo checks failed)")
        ov.lbl_status.config(text="NET: OFFLINE" if state["is_lagging"] else "NET: ONLINE", fg=THEME["warning"] if state["is_lagging"] else THEME["fg"])
        ov.lbl_macro.config(text="MACRO: RUNNING" if state["is_running_macro"] else "")
        # Click state: prioritize hold, then spam
        click_text = ""
        click_fg = THEME["fg"]
        if state.get("is_holding"):
            click_text = "CLICK: HOLD"
            click_fg = THEME["warning"]
        elif state.get("is_spamming"):
            click_text = "CLICK: SPAM"
            click_fg = THEME["fg"]
        ov.lbl_click.config(text=click_text, fg=click_fg)
    else: ov.withdraw()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MACRO CONTROLLER"); self.geometry("380x650"); self.configure(bg=THEME["bg"]); self.attributes("-topmost", True)
        
        tk.Label(self, text="[ TIMELINE MACRO ]", font=THEME["font_header"], bg=THEME["bg"], fg=THEME["fg"]).pack(pady=(20,0))
        tk.Label(self, text="BY HIIMACHICKEN", font=("Consolas", 8, "bold"), bg=THEME["bg"], fg="#333").pack(pady=(0,2))
        tk.Label(self, text="FIXES BY BOGI", font=("Consolas", 8, "bold"), bg=THEME["bg"], fg="#333").pack(pady=(0))
        
        self.frame = tk.Frame(self, bg=THEME["bg"]); self.frame.pack(fill="both", expand=True, padx=20)
        self.build_ui()
        # Defer overlay creation until the main window is ready to avoid focus/attribute issues
        self.after(50, self.create_overlay)

    def create_overlay(self):
        state["overlay_ref"] = Overlay(self)
        ov = state["overlay_ref"]
        # Reassert topmost and lift so overlay isn't hidden by the main window
        try:
            ov.wm_attributes("-topmost", True)
        except Exception:
            try: ov.attributes("-topmost", True)
            except: pass
        try: ov.lift()
        except: pass
        # Ensure overlay visibility reflects saved config
        update_overlay()

    def build_ui(self):
        keys = [chr(i) for i in range(97, 123)] + [str(i) for i in range(10)] + [f"Key.f{i}" for i in range(1, 13)]
        
        def add_section(txt): tk.Label(self.frame, text=txt, bg=THEME["bg"], fg="#888", font=("Consolas", 9, "bold")).pack(anchor="w", pady=(10,2))
        def add_entry(txt, key):
            f = tk.Frame(self.frame, bg=THEME["bg"]); f.pack(fill="x", pady=2)
            tk.Label(f, text=txt, bg=THEME["bg"], fg="white", width=18, anchor="w").pack(side="left")
            e = tk.Entry(f, bg="#222", fg="white", font=THEME["font_mono"]); e.insert(0, str(state["config"].get(key, ""))); e.pack(side="left", fill="x", expand=True)
            return e

        # Global Settings
        tk.Label(self.frame, text="TRIGGER KEY:", bg=THEME["bg"], fg=THEME["fg"], font=THEME["font_mono"]).pack(anchor="w")
        self.cb_trig = ttk.Combobox(self.frame, values=keys, font=THEME["font_mono"]); self.cb_trig.set(state["config"]["key_macro_trigger"]); self.cb_trig.pack(fill="x", pady=2)
        
        tk.Label(self.frame, text="CLICKS PER SECOND (CPS):", bg=THEME["bg"], fg=THEME["fg"], font=THEME["font_mono"]).pack(anchor="w", pady=(10,0))
        self.s_cps = tk.Scale(self.frame, from_=1, to=30, orient="horizontal", bg=THEME["bg"], fg="white", highlightthickness=0, troughcolor="#222"); self.s_cps.set(state["config"]["click_cps"]); self.s_cps.pack(fill="x")

        # Timeline
        add_section("--- 1. HOLD CLICK ---")
        self.e_h_st = add_entry("Start Delay (s):", "macro_hold_start")
        self.e_h_ln = add_entry("Duration (s):", "macro_hold_len")
        
        add_section("--- 2. NETWORK ---")
        self.e_n_st = add_entry("Start Delay (s):", "macro_net_start")
        self.e_n_ln = add_entry("Offline Time (s):", "macro_net_len")
        
        add_section("--- 3. SPAM CLICK ---")
        self.e_s_st = add_entry("Start Delay (s):", "macro_spam_start")
        self.e_s_ln = add_entry("Duration (s):", "macro_spam_len")

        # Linux Network Settings
        if IS_LINUX:
            add_section("--- LINUX NETWORK ---")
            
            # Network Interface
            f_iface = tk.Frame(self.frame, bg=THEME["bg"]); f_iface.pack(fill="x", pady=2)
            tk.Label(f_iface, text="Interface:", bg=THEME["bg"], fg="white", width=18, anchor="w").pack(side="left")
            
            available_ifaces = get_network_interfaces()
            current_iface = state.get("network_interface") or (available_ifaces[0] if available_ifaces else "eth0")
            self.cb_iface = ttk.Combobox(f_iface, values=available_ifaces, font=THEME["font_mono"])
            self.cb_iface.set(current_iface)
            self.cb_iface.pack(side="left", fill="x", expand=True)
            
            # Bandwidth Limit
            f_bw = tk.Frame(self.frame, bg=THEME["bg"]); f_bw.pack(fill="x", pady=2)
            tk.Label(f_bw, text="Bandwidth (kbps):", bg=THEME["bg"], fg="white", width=18, anchor="w").pack(side="left")
            self.e_bandwidth = tk.Entry(f_bw, bg="#222", fg="white", font=THEME["font_mono"])
            self.e_bandwidth.insert(0, str(state["config"].get("bandwidth_limit", 100)))
            self.e_bandwidth.pack(side="left", fill="x", expand=True)
            
            tk.Label(self.frame, text="(0 = block all traffic)", bg=THEME["bg"], fg="#666", font=("Consolas", 8)).pack(anchor="w")
            
            # Sudo authenticate button
            HackerButton(self.frame, text="ACTIVATE SUDO", command=self.activate_sudo).pack(fill="x", pady=2)

        # INPUT FALLBACK (always used)
        add_section("--- INPUT FALLBACK ---")
        f_fb = tk.Frame(self.frame, bg=THEME["bg"]); f_fb.pack(fill="x", pady=2)
        tk.Label(f_fb, text="Fallback Key:", bg=THEME["bg"], fg="white", width=18, anchor="w").pack(side="left")
        self.btn_fallback_key = HackerButton(f_fb, text=f"{state['config'].get('fallback_key','<none>')}", command=self.capture_fallback_key)
        self.btn_fallback_key.pack(side="left", fill="x", expand=True)

        # Buttons
        f_btn = tk.Frame(self.frame, bg=THEME["bg"]); f_btn.pack(fill="x", pady=20)
        HackerButton(f_btn, text="SAVE SETTINGS", command=self.save).pack(fill="x", pady=2)
        self.btn_ov = HackerButton(f_btn, text="DISABLE OVERLAY", command=self.toggle_ov); self.btn_ov.pack(fill="x", pady=2)
        HackerButton(f_btn, text="RELOAD TOOL", command=lambda: os.execv(sys.executable, [sys.executable] + sys.argv), bg="#330000").pack(fill="x", pady=2)

    def save(self):
        c = state["config"]
        c["key_macro_trigger"] = self.cb_trig.get()
        c["click_cps"] = self.s_cps.get()
        try:
            c["macro_hold_start"] = float(self.e_h_st.get())
            c["macro_hold_len"] = float(self.e_h_ln.get())
            c["macro_net_start"] = float(self.e_n_st.get())
            c["macro_net_len"] = float(self.e_n_ln.get())
            c["macro_spam_start"] = float(self.e_s_st.get())
            c["macro_spam_len"] = float(self.e_s_ln.get())
            
            if IS_LINUX:
                c["network_interface"] = self.cb_iface.get()
                state["network_interface"] = self.cb_iface.get()
                c["bandwidth_limit"] = int(self.e_bandwidth.get())
        except: pass
        save_config()
        messagebox.showinfo("Saved", "Settings Updated!")

    def toggle_ov(self):
        state["config"]["overlay_enabled"] = not state["config"]["overlay_enabled"]
        self.btn_ov.config(text="DISABLE OVERLAY" if state["config"]["overlay_enabled"] else "ENABLE OVERLAY")
        update_overlay(); save_config()

    def activate_sudo(self):
        """Authenticate sudo to cache credentials (Linux only)"""
        if not IS_LINUX:
            messagebox.showinfo("Info", "Sudo authentication is only needed on Linux")
            return
        
        try:
            result = subprocess.run(['sudo', '-v'], capture_output=True, text=True)
            
            if result.returncode == 0:
                messagebox.showinfo("Success", "Sudo authentication successful!\nYou can now use network control without entering password.")
            else:
                messagebox.showerror("Error", "Sudo authentication failed. Please check your password.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to authenticate sudo:\n{str(e)}")



    def capture_fallback_key(self):
        if state.get("capturing_fallback"):
            return
        state["capturing_fallback"] = True
        self.btn_fallback_key.config(text="PRESS ANY KEY...")
        def on_press(k):
            state["config"]["fallback_key"] = key_to_string(k)
            save_config()
            self.after(0, lambda: self.btn_fallback_key.config(text=f"Fallback Key: {state['config'].get('fallback_key')}"))
            state["capturing_fallback"] = False
            return False
        # Start a one-shot listener on a separate thread
        threading.Thread(target=lambda: keyboard.Listener(on_press=on_press).start()).start()

if __name__ == "__main__":
    load_config()
    
    # Initialize network interface for Linux
    if IS_LINUX:
        state["network_interface"] = init_network_interface()
        print(f">> Using network interface: {state['network_interface']}")
    
    keyboard.Listener(on_press=on_key_press).start()
    App().mainloop()