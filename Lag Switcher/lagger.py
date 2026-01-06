#!/usr/bin/env python3
"""
Network Lagger - A bandwidth limiting tool with GUI and keybind support
Supports Fedora Linux using tc (traffic control)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import json
import os
import re
import sys
import socket
from pathlib import Path

class NetworkLagger:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Network Lagger")
        self.root.geometry("580x450")
        self.root.resizable(False, False)
        
        # Dark theme colors
        self.bg_color = "#1e1e1e"
        self.fg_color = "#e0e0e0"
        self.frame_bg = "#2d2d2d"
        self.entry_bg = "#3c3c3c"
        self.entry_fg = "#ffffff"
        
        self.root.configure(bg=self.bg_color)
        
        # Configuration
        self.config_file = Path.home() / ".lagger_config.json"
        self.niri_config_file = Path.home() / ".config/niri/dms/lagger.kdl"
        self.socket_path = f"/tmp/lagger_{os.getuid()}.sock"
        self.is_lagging = False
        self.current_keybind = "Mod+L"
        self.bandwidth_limit = 100  # kbps
        self.available_interfaces = self.get_network_interfaces()
        self.interface = self.available_interfaces[0] if self.available_interfaces else "eth0"
        
        # Load configuration
        self.load_config()
        
        # Initialize Niri config if needed
        self.init_niri_config()
        
        # Socket server for IPC
        self.socket_server = None
        self.setup_socket_server()
        
        # Setup GUI
        self.setup_gui()
        
    def setup_socket_server(self):
        """Setup Unix socket server for IPC commands"""
        # Remove old socket if it exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        
        def socket_listener():
            try:
                self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket_server.bind(self.socket_path)
                self.socket_server.listen(1)
                
                while True:
                    try:
                        conn, _ = self.socket_server.accept()
                        data = conn.recv(1024).decode().strip()
                        
                        if data == "toggle":
                            self.root.after(0, self.toggle_lag)
                            conn.send(b"OK\n")
                        elif data == "enable":
                            self.root.after(0, self.enable_lag)
                            conn.send(b"OK\n")
                        elif data == "disable":
                            self.root.after(0, self.disable_lag)
                            conn.send(b"OK\n")
                        elif data == "status":
                            status = "active" if self.is_lagging else "inactive"
                            conn.send(f"{status}\n".encode())
                        else:
                            conn.send(b"ERROR: Unknown command\n")
                        
                        conn.close()
                    except:
                        break
            except Exception as e:
                print(f"Socket server error: {e}")
        
        thread = threading.Thread(target=socket_listener, daemon=True)
        thread.start()
    
    def get_network_interfaces(self):
        """Get list of available network interfaces (excluding loopback)"""
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
    
    def setup_gui(self):
        """Setup the GUI interface"""
        # Title
        title_label = tk.Label(
            self.root, 
            text="Network Lagger", 
            font=("Arial", 20, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        )
        title_label.pack(pady=20)
        
        # Status Frame
        status_frame = tk.LabelFrame(
            self.root, 
            text="Status", 
            padx=20, 
            pady=10,
            bg=self.frame_bg,
            fg=self.fg_color,
            font=("Arial", 10, "bold")
        )
        status_frame.pack(padx=20, pady=10, fill="x")
        
        self.status_label = tk.Label(
            status_frame, 
            text="Inactive", 
            font=("Arial", 14),
            fg="#ff5555",
            bg=self.frame_bg
        )
        self.status_label.pack()
        
        # Settings Frame
        settings_frame = tk.LabelFrame(
            self.root, 
            text="Settings", 
            padx=20, 
            pady=10,
            bg=self.frame_bg,
            fg=self.fg_color,
            font=("Arial", 10, "bold")
        )
        settings_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        # Network Interface
        interface_frame = tk.Frame(settings_frame, bg=self.frame_bg)
        interface_frame.pack(fill="x", pady=5)
        
        tk.Label(
            interface_frame, 
            text="Network Interface:", 
            width=20, 
            anchor="w",
            bg=self.frame_bg,
            fg=self.fg_color
        ).pack(side="left")
        self.interface_var = tk.StringVar(value=self.interface)
        
        # Style for combobox
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.TCombobox', 
            fieldbackground=self.entry_bg,
            background=self.entry_bg,
            foreground=self.entry_fg,
            arrowcolor=self.fg_color,
            bordercolor=self.entry_bg,
            lightcolor=self.entry_bg,
            darkcolor=self.entry_bg)
        style.map('Dark.TCombobox', 
            fieldbackground=[('readonly', self.entry_bg)],
            selectbackground=[('readonly', self.entry_bg)],
            selectforeground=[('readonly', self.entry_fg)])
        
        interface_dropdown = ttk.Combobox(
            interface_frame, 
            textvariable=self.interface_var,
            values=self.available_interfaces,
            state="readonly",
            width=15,
            style='Dark.TCombobox'
        )
        interface_dropdown.pack(side="left", fill="x", expand=True)
        
        # Bandwidth Limit
        bandwidth_frame = tk.Frame(settings_frame, bg=self.frame_bg)
        bandwidth_frame.pack(fill="x", pady=5)
        
        tk.Label(
            bandwidth_frame, 
            text="Bandwidth (0=Block all):", 
            width=20, 
            anchor="w",
            bg=self.frame_bg,
            fg=self.fg_color
        ).pack(side="left")
        self.bandwidth_var = tk.IntVar(value=self.bandwidth_limit)
        bandwidth_spinbox = tk.Spinbox(
            bandwidth_frame, 
            from_=0, 
            to=10000, 
            textvariable=self.bandwidth_var,
            width=10,
            bg=self.entry_bg,
            fg=self.entry_fg,
            buttonbackground=self.entry_bg,
            readonlybackground=self.entry_bg,
            insertbackground=self.entry_fg
        )
        bandwidth_spinbox.pack(side="left")
        
        # Keybind configuration
        keybind_frame = tk.Frame(settings_frame, bg=self.frame_bg)
        keybind_frame.pack(fill="x", pady=5)
        
        tk.Label(
            keybind_frame, 
            text="Niri Keybind:", 
            width=20, 
            anchor="w",
            bg=self.frame_bg,
            fg=self.fg_color
        ).pack(side="left")
        
        self.keybind_var = tk.StringVar(value=self.current_keybind)
        keybind_entry = tk.Entry(
            keybind_frame, 
            textvariable=self.keybind_var,
            bg=self.entry_bg,
            fg=self.entry_fg,
            insertbackground=self.entry_fg,
            width=12
        )
        keybind_entry.pack(side="left", padx=2)
        
        record_keybind_btn = tk.Button(
            keybind_frame, 
            text="Record", 
            command=self.record_keybind,
            bg="#5a5a5a",
            fg=self.fg_color,
            activebackground="#6a6a6a",
            activeforeground=self.fg_color,
            relief="flat",
            padx=8
        )
        record_keybind_btn.pack(side="left", padx=2)
        
        set_keybind_btn = tk.Button(
            keybind_frame, 
            text="Apply", 
            command=self.update_niri_keybind,
            bg="#ff79c6",
            fg="#1e1e1e",
            activebackground="#ff92d0",
            activeforeground="#1e1e1e",
            font=("Arial", 9, "bold"),
            relief="flat",
            padx=8
        )
        set_keybind_btn.pack(side="left", padx=2)
        
        unset_keybind_btn = tk.Button(
            keybind_frame, 
            text="Unset", 
            command=self.unset_niri_keybind,
            bg="#f1fa8c",
            fg="#1e1e1e",
            activebackground="#f5fc9f",
            activeforeground="#1e1e1e",
            font=("Arial", 9, "bold"),
            relief="flat",
            padx=8
        )
        unset_keybind_btn.pack(side="left", padx=2)
        
        # Buttons Frame
        buttons_frame = tk.Frame(settings_frame, bg=self.frame_bg)
        buttons_frame.pack(pady=15)
        
        # Sudo authenticate button
        sudo_btn = tk.Button(
            buttons_frame,
            text="Activate Sudo",
            command=self.activate_sudo,
            bg="#bd93f9",
            fg="#1e1e1e",
            activebackground="#d0a9ff",
            activeforeground="#1e1e1e",
            font=("Arial", 10, "bold"),
            relief="flat",
            width=12,
            height=2
        )
        sudo_btn.pack(side="left", padx=5)
        
        self.toggle_btn = tk.Button(
            buttons_frame,
            text="Enable Lag",
            command=self.toggle_lag,
            bg="#50fa7b",
            fg="#1e1e1e",
            activebackground="#5af78e",
            activeforeground="#1e1e1e",
            font=("Arial", 10, "bold"),
            relief="flat",
            width=12,
            height=2
        )
        self.toggle_btn.pack(side="left", padx=5)
        
        save_btn = tk.Button(
            buttons_frame,
            text="Save Settings",
            command=self.save_settings,
            bg="#8be9fd",
            fg="#1e1e1e",
            activebackground="#9ff5ff",
            activeforeground="#1e1e1e",
            font=("Arial", 10, "bold"),
            relief="flat",
            width=12,
            height=2
        )
        save_btn.pack(side="left", padx=5)
        
        # Info label
        info_label = tk.Label(
            self.root,
            text="Enter keybind (e.g., Mod+L, Mod+Shift+N) and click Set Keybind",
            font=("Arial", 9),
            fg="#6c6c6c",
            bg=self.bg_color
        )
        info_label.pack(pady=5)
        
    def load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.current_keybind = config.get('keybind', self.current_keybind)
                    self.bandwidth_limit = config.get('bandwidth', self.bandwidth_limit)
                    self.interface = config.get('interface', self.interface)
            except Exception as e:
                print(f"Error loading config: {e}")
                
    def save_config(self):
        """Save configuration to file"""
        try:
            config = {
                'keybind': self.current_keybind,
                'bandwidth': self.bandwidth_limit,
                'interface': self.interface
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def init_niri_config(self):
        """Initialize Niri config file if it doesn't exist"""
        if not self.niri_config_file.exists():
            self.niri_config_file.parent.mkdir(parents=True, exist_ok=True)
            script_path = os.path.abspath(__file__)
            config_content = f"""// Auto-generated by Network Lagger
// Keybind for toggling network lag

binds {{
    {self.current_keybind} {{ spawn "{script_path}" "--toggle"; }}
}}
"""
            try:
                with open(self.niri_config_file, 'w') as f:
                    f.write(config_content)
            except Exception as e:
                print(f"Error creating Niri config: {e}")
            
    def save_settings(self):
        """Save current settings"""
        self.interface = self.interface_var.get()
        self.bandwidth_limit = self.bandwidth_var.get()
        self.current_keybind = self.keybind_var.get()
        self.save_config()
        messagebox.showinfo("Success", "Settings saved successfully!")
    
    def record_keybind(self):
        """Open dialog to record a new keybind"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Keybind")
        dialog.geometry("350x180")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.bg_color)
        
        label = tk.Label(
            dialog,
            text="Press your desired key combination...\n(e.g., Super+L, Super+Shift+N)",
            wraplength=300,
            bg=self.bg_color,
            fg=self.fg_color,
            font=("Arial", 11)
        )
        label.pack(pady=20)
        
        recorded_label = tk.Label(
            dialog,
            text="",
            bg=self.bg_color,
            fg="#50fa7b",
            font=("Arial", 14, "bold")
        )
        recorded_label.pack(pady=10)
        
        info_label = tk.Label(
            dialog,
            text="Press Escape to cancel",
            bg=self.bg_color,
            fg="#6c6c6c",
            font=("Arial", 9)
        )
        info_label.pack()
        
        def on_key_press(event):
            # Build the keybind string in Niri format
            parts = []
            
            # Check modifiers
            if event.state & 0x4:  # Control
                parts.append("Ctrl")
            if event.state & 0x1:  # Shift
                parts.append("Shift")
            if event.state & 0x8:  # Alt
                parts.append("Alt")
            if event.state & 0x40:  # Mod4/Super/Windows key
                parts.append("Mod")
            
            # Get the key
            key = event.keysym
            
            # Cancel on Escape
            if key == "Escape":
                dialog.destroy()
                return
            
            # Ignore modifier keys by themselves
            if key in ["Control_L", "Control_R", "Shift_L", "Shift_R", 
                      "Alt_L", "Alt_R", "Super_L", "Super_R", "Meta_L", "Meta_R"]:
                return
            
            # Convert key name to proper format
            if len(key) == 1:
                key = key.upper()
            elif key.startswith("KP_"):  # Keypad keys
                key = key.replace("KP_", "")
            
            # Add the main key
            parts.append(key)
            
            # Create the full keybind string
            if len(parts) > 1 or (len(parts) == 1 and parts[0] not in ["Ctrl", "Shift", "Alt", "Mod"]):
                keybind = "+".join(parts)
                recorded_label.config(text=keybind)
                
                # Auto-close after a short delay
                dialog.after(500, lambda: self.finalize_keybind(keybind, dialog))
        
        dialog.bind("<KeyPress>", on_key_press)
        dialog.focus_set()
    
    def finalize_keybind(self, keybind, dialog):
        """Finalize the recorded keybind"""
        self.keybind_var.set(keybind)
        dialog.destroy()
    
    def update_niri_keybind(self):
        """Update Niri config file with new keybind"""
        keybind = self.keybind_var.get().strip()
        
        # Remove angle brackets if user entered them
        keybind = keybind.replace('<', '').replace('>', '')
        
        # Validate basic format (should contain letters/numbers and optionally Mod, Shift, Ctrl, Alt)
        if not keybind:
            messagebox.showerror("Error", "Please enter a keybind (e.g., Mod+L, Mod+Shift+N)")
            return
        
        self.current_keybind = keybind
        self.keybind_var.set(keybind)
        
        # Ensure the directory exists
        self.niri_config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create Niri config content (uncommented - active)
        script_path = os.path.abspath(__file__)
        config_content = f"""// Auto-generated by Network Lagger
// Keybind for toggling network lag

binds {{
    {keybind} {{ spawn "{script_path}" "--toggle"; }}
}}
"""
        
        try:
            with open(self.niri_config_file, 'w') as f:
                f.write(config_content)
            
            self.save_config()
            messagebox.showinfo(
                "Success", 
                f"Keybind set to {keybind}!\n\n"
                f"Config saved to:\n{self.niri_config_file}\n\n"
                "Run: niri msg reload-config"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update Niri config:\n{str(e)}")
    
    def unset_niri_keybind(self):
        """Comment out keybind in Niri config file"""
        try:
            # Ensure the directory exists
            self.niri_config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get current keybind or use saved one
            keybind = self.keybind_var.get().strip() or self.current_keybind
            script_path = os.path.abspath(__file__)
            
            # Create commented config content (inactive)
            config_content = f"""// Auto-generated by Network Lagger
// Keybind for toggling network lag
// DISABLED - Click Apply to re-enable

// binds {{
//     {keybind} {{ spawn "{script_path}" "--toggle"; }}
// }}
"""
            
            with open(self.niri_config_file, 'w') as f:
                f.write(config_content)
            
            messagebox.showinfo(
                "Success", 
                f"Keybind disabled!\n\n"
                f"Config file updated (commented out):\n{self.niri_config_file}\n\n"
                "Run: niri msg reload-config\n\n"
                "Click Apply to re-enable the keybind."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to disable keybind:\n{str(e)}")
    
    def activate_sudo(self):
        """Authenticate sudo to cache credentials"""
        try:
            # Run a simple sudo command to authenticate
            result = subprocess.run(
                ['sudo', '-v'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                messagebox.showinfo("Success", "Sudo authentication successful!\nYou can now enable lag without entering password.")
            else:
                messagebox.showerror("Error", "Sudo authentication failed. Please check your password.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to authenticate sudo:\n{str(e)}")
        
    def check_keybind(self):
        """Check if the current keybind combination is pressed"""
        keybind_parts = [k.strip('<>') for k in self.current_keybind.split('+')]
        
        # Check if all keys in keybind are pressed
        if all(key in self.pressed_keys for key in keybind_parts):
            self.toggle_lag()
            # Clear pressed keys to avoid multiple triggers
            self.pressed_keys.clear()
            
    def toggle_lag(self):
        """Toggle network lag on/off"""
        if self.is_lagging:
            self.disable_lag()
        else:
            self.enable_lag()
            
    def enable_lag(self):
        """Enable network lag using tc"""
        interface = self.interface_var.get()
        bandwidth = self.bandwidth_var.get()
        
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
                self.is_lagging = True
                self.status_label.config(text="Active - Limiting Bandwidth", fg="#50fa7b")
                self.toggle_btn.config(text="Disable Lag", bg="#ff5555", fg="#ffffff")
                self.root.after(0, lambda: None)  # Force GUI update
            else:
                messagebox.showerror("Error", f"Failed to enable lag:\n{result.stderr}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to enable lag:\n{str(e)}")
            
    def disable_lag(self):
        """Disable network lag"""
        interface = self.interface_var.get()
        
        try:
            cmd = ['sudo', 'tc', 'qdisc', 'del', 'dev', interface, 'root']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.is_lagging = False
                self.status_label.config(text="Inactive", fg="#ff5555")
                self.toggle_btn.config(text="Enable Lag", bg="#50fa7b", fg="#1e1e1e")
                self.root.after(0, lambda: None)  # Force GUI update
            else:
                messagebox.showerror("Error", f"Failed to disable lag:\n{result.stderr}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to disable lag:\n{str(e)}")
            
    def run(self):
        """Run the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        """Handle application closing"""
        # Disable lag if active
        if self.is_lagging:
            self.disable_lag()
        
        # Clean up socket
        if self.socket_server:
            try:
                self.socket_server.close()
            except:
                pass
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
            
        self.root.destroy()

def send_command(command):
    """Send a command to running lagger instance"""
    socket_path = f"/tmp/lagger_{os.getuid()}.sock"
    
    if not os.path.exists(socket_path):
        print("Error: Lagger GUI is not running. Please start it first.")
        sys.exit(1)
    
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(socket_path)
        client.send(f"{command}\n".encode())
        response = client.recv(1024).decode().strip()
        client.close()
        print(response)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    # Check for CLI arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lstrip('-')
        
        if command in ['toggle', 'enable', 'disable', 'status']:
            sys.exit(send_command(command))
        elif command == 'help':
            print("Network Lagger CLI")
            print("\nUsage:")
            print("  ./lagger.py           - Start GUI")
            print("  ./lagger.py --toggle  - Toggle lag on/off")
            print("  ./lagger.py --enable  - Enable lag")
            print("  ./lagger.py --disable - Disable lag")
            print("  ./lagger.py --status  - Check status")
            print("\nFor Niri: Add to your config.kdl:")
            print('  binds {')
            print(f'    Mod+L {{ spawn "{os.path.abspath(__file__)}" "--toggle"; }}')
            print('  }')
            sys.exit(0)
        else:
            print(f"Unknown command: {command}")
            print("Use --help for usage information")
            sys.exit(1)
    
    # Start GUI
    app = NetworkLagger()
    app.run()
