#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import stat
import subprocess
import tempfile
import tkinter as tk
from pathlib import Path
from shutil import which
from tkinter import ttk, messagebox
import socket
import threading
import time

HOME = str(Path.home())


def find_image_server_ip(timeout: float = 2.0) -> str | None:
    """Try to determine the image server IP from hostname and local network."""
    def add_host_ips(host: str, ips: set[str]):
        try:
            resolved = socket.gethostbyname_ex(host)[2]
            for ip in resolved:
                if ip and not ip.startswith("127."):
                    ips.add(ip)
        except OSError:
            pass

    try:
        # Try short hostname / FQDN first.
        hostname = socket.gethostname()
        fqdn = socket.getfqdn()
        ip_candidates: set[str] = set()

        add_host_ips(hostname, ip_candidates)
        if "." in hostname:
            add_host_ips(hostname.split(".")[0], ip_candidates)
        if fqdn and fqdn != hostname:
            add_host_ips(fqdn, ip_candidates)

        # Use hostname -I to get the local interface IP directly.
        local_ip = None
        try:
            output = subprocess.check_output(["hostname", "-I"], text=True, stderr=subprocess.DEVNULL).strip()
            for token in output.split():
                if token and not token.startswith("127."):
                    ip_candidates.add(token)
                    if local_ip is None:
                        local_ip = token
        except Exception:
            pass

        if local_ip:
            print(f"Local IP from hostname -I: {local_ip}")

        print(f"Hostname-derived IP candidates: {sorted(ip_candidates)}")
        for ip in sorted(ip_candidates):
            if _test_image_server(ip, 55555, timeout):
                print(f"Found image server by hostname lookup at {ip}:55555")
                return ip

        priority_ips = [
            "192.168.123.164",
            "172.17.45.95",
        ]
        for ip in priority_ips:
            if _test_image_server(ip, 55555, timeout):
                print(f"Found image server at {ip}:55555")
                return ip

        if local_ip and not local_ip.startswith("127."):
            print(f"Using local interface IP without port verification: {local_ip}")
            return local_ip

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()

        if local_ip and not local_ip.startswith("127."):
            if _test_image_server(local_ip, 55555, timeout):
                print(f"Found image server at local IP {local_ip}:55555")
                return local_ip
            if local_ip not in ip_candidates:
                ip_candidates.add(local_ip)

        if local_ip and local_ip.count('.') == 3:
            ip_parts = local_ip.split('.')
            subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}."
            print(f"Scanning subnet {subnet}0/24 for image server on port 55555...")
            for i in range(1, 255):
                ip = f"{subnet}{i}"
                if ip in ip_candidates or ip in priority_ips or ip == local_ip:
                    continue
                if _test_image_server(ip, 55555, timeout):
                    print(f"Found image server at {ip}:55555")
                    return ip

        if local_ip:
            print(f"Defaulting to local interface IP: {local_ip}")
            return local_ip

        print("No image server found on local network")
        return None

    except Exception as e:
        print(f"Error scanning for image server: {e}")
        return None


def _test_image_server(ip: str, port: int, timeout: float) -> bool:
    """Test if image server is running on given IP and port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False


def find_terminal():
    candidates = [
        ("xterm", lambda title, script: ["xterm", "-T", title, "-e", "bash", script]),
        ("x-terminal-emulator", lambda title, script: ["x-terminal-emulator", "-T", title, "-e", "bash", script]),
        ("konsole", lambda title, script: ["konsole", "-p", f"tabtitle={title}", "-e", "bash", script]),
        ("xfce4-terminal", lambda title, script: ["xfce4-terminal", "--title", title, "--command", f"bash {shlex.quote(script)}"]),
    ]
    for name, builder in candidates:
        if which(name):
            return builder
    return None


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("XR Teleop Simple Launcher")
        self.root.geometry("780x640")

        self.sim_env = tk.StringVar(value="unitree_sim_env")
        self.sim_env.trace_add("write", lambda *args: self.refresh())
        self.teleop_env = tk.StringVar(value="tv")
        self.teleop_env.trace_add("write", lambda *args: self.refresh())
        self.sim_path = tk.StringVar(value=f"{HOME}/unitree_sim_isaaclab")
        self.sim_path.trace_add("write", lambda *args: self.refresh())
        self.teleop_path = tk.StringVar(value=f"{HOME}/afsluttende_projekt/repos/xr_teleoperate/teleop")
        self.teleop_path.trace_add("write", lambda *args: self.refresh())
        self.img_ip = tk.StringVar(value="192.168.123.164")
        self.img_ip.trace_add("write", lambda *args: self.refresh())

        self.input_mode = tk.StringVar(value="hand")
        self.input_mode.trace_add("write", lambda *args: self.refresh())
        self.ee = tk.StringVar(value="dex3")
        self.ee.trace_add("write", lambda *args: self.refresh())
        self.arm = tk.StringVar(value="G1_29")
        self.arm.trace_add("write", lambda *args: self.refresh())
        self.display_mode = tk.StringVar(value="immersive")
        self.display_mode.trace_add("write", lambda *args: self.refresh())
        self.device = tk.StringVar(value="cpu")
        self.device.trace_add("write", lambda *args: self.refresh())
        self.task = tk.StringVar(value="Isaac-PickPlace-Cylinder-G129-Dex3-Joint")
        self.task.trace_add("write", lambda *args: self.refresh())
        self.robot_type = tk.StringVar(value="g129")
        self.robot_type.trace_add("write", lambda *args: self.refresh())

        self.enable_cameras = tk.BooleanVar(value=True)
        self.enable_cameras.trace_add("write", lambda *args: self.refresh())
        self.enable_dex3_dds = tk.BooleanVar(value=True)
        self.enable_dex3_dds.trace_add("write", lambda *args: self.refresh())
        self.headless = tk.BooleanVar(value=False)
        self.headless.trace_add("write", lambda *args: self.refresh())
        self.record = tk.BooleanVar(value=False)
        self.record.trace_add("write", lambda *args: self.refresh())
        self.motion = tk.BooleanVar(value=False)
        self.motion.trace_add("write", lambda *args: self.refresh())

        # Auto-detect image server IP on startup
        self.auto_detect_image_ip()
        
        self.build()
        self.refresh()  # Initial preview update

    def auto_detect_image_ip(self):
        """Automatically detect image server IP"""
        def detect():
            ip = find_image_server_ip()
            if ip:
                self.img_ip.set(ip)
                print(f"Auto-detected image server IP: {ip}")
                # Update preview in main thread
                self.root.after(0, self.refresh)
            else:
                print("Could not auto-detect image server IP, keeping current value")
        
        # Run detection in background thread to avoid blocking UI
        thread = threading.Thread(target=detect, daemon=True)
        thread.start()

    def manual_detect_image_ip(self):
        """Manually trigger image server IP detection"""
        def detect():
            self.root.after(0, lambda: self.root.config(cursor="watch"))
            try:
                ip = find_image_server_ip()
                if ip:
                    self.img_ip.set(ip)
                    self.root.after(0, lambda: messagebox.showinfo("Success", f"Found image server at: {ip}"))
                    self.root.after(0, self.refresh)
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Not Found", "Could not find image server on local network"))
            finally:
                self.root.after(0, lambda: self.root.config(cursor=""))

        thread = threading.Thread(target=detect, daemon=True)
        thread.start()

    def build(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="XR Teleop Simple Launcher",
            font=("TkDefaultFont", 16, "bold")
        ).pack(anchor="w", pady=(0, 10))

        p = ttk.LabelFrame(outer, text="Paths / env", padding=10)
        p.pack(fill="x", pady=6)
        self.row(p, 0, "Sim env", self.sim_env, 30)
        self.row(p, 1, "Teleop env", self.teleop_env, 30)
        self.row(p, 2, "Sim path", self.sim_path, 70)
        self.row(p, 3, "Teleop path", self.teleop_path, 70)
        
        # Custom row for Image server IP with auto-detect button
        ttk.Label(p, text="Image server IP").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=4)
        ip_frame = ttk.Frame(p)
        ip_frame.grid(row=4, column=1, sticky="ew", pady=4)
        ttk.Entry(ip_frame, textvariable=self.img_ip, width=20).pack(side="left", fill="x", expand=True)
        ttk.Button(ip_frame, text="Auto-detect", command=self.manual_detect_image_ip).pack(side="right", padx=(6, 0))
        p.grid_columnconfigure(1, weight=1)

        s = ttk.LabelFrame(outer, text="Simulation", padding=10)
        s.pack(fill="x", pady=6)
        self.row(s, 0, "Device", self.device, 20)
        self.row(s, 1, "Task", self.task, 60)
        self.row(s, 2, "Robot type", self.robot_type, 20)

        sr = ttk.Frame(s)
        sr.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Checkbutton(sr, text="Enable cameras", variable=self.enable_cameras).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(sr, text="Enable Dex3 DDS", variable=self.enable_dex3_dds).pack(side="left", padx=(0, 14))

        t = ttk.LabelFrame(outer, text="Teleop", padding=10)
        t.pack(fill="x", pady=6)
        self.combo_row(t, 0, "Input mode", self.input_mode, ["hand", "controller"])
        self.combo_row(t, 1, "Arm", self.arm, ["G1_29", "G1_23", "H1_2", "H1"])
        self.combo_row(t, 2, "EE", self.ee, ["dex3", "dex1", "inspire_ftp", "inspire_dfx", "brainco"])
        self.combo_row(t, 3, "Display", self.display_mode, ["immersive", "ego", "pass-through"])

        tr = ttk.Frame(t)
        tr.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Checkbutton(tr, text="Headless", variable=self.headless).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(tr, text="Record", variable=self.record).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(tr, text="Motion", variable=self.motion).pack(side="left", padx=(0, 14))

        b = ttk.Frame(outer)
        b.pack(fill="x", pady=8)
        ttk.Button(b, text="Open SIM terminal", command=self.open_sim).pack(side="left", padx=(0, 8))
        ttk.Button(b, text="Open TELEOP terminal", command=self.open_teleop).pack(side="left", padx=(0, 8))
        ttk.Button(b, text="Open BOTH terminals", command=self.open_both).pack(side="left", padx=(0, 8))

        ttk.Button(b, text="🛑 Stop SIM", command=self.stop_sim).pack(side="left", padx=(10, 8))
        ttk.Button(b, text="🛑 Stop TELEOP", command=self.stop_teleop).pack(side="left", padx=(0, 8))
        ttk.Button(b, text="☠️ Stop ALL", command=self.stop_all).pack(side="left", padx=(0, 8))

        self.preview = tk.Text(outer, height=16, wrap="word")
        self.preview.pack(fill="both", expand=True, pady=(8, 0))
        ttk.Button(outer, text="Refresh preview", command=self.refresh).pack(anchor="e", pady=(8, 0))
        self.refresh()

    def row(self, parent, r, label, var, width):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(parent, textvariable=var, width=width).grid(row=r, column=1, sticky="ew", pady=4)
        parent.grid_columnconfigure(1, weight=1)

    def combo_row(self, parent, r, label, var, values):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", padx=(0, 12), pady=4)
        box = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
        box.grid(row=r, column=1, sticky="ew", pady=4)
        parent.grid_columnconfigure(1, weight=1)

    def sim_cmd(self):
        args = [
            "python sim_main.py",
            f"--device {shlex.quote(self.device.get().strip())}",
            f"--task {shlex.quote(self.task.get().strip())}",
            f"--robot_type {shlex.quote(self.robot_type.get().strip())}",
        ]
        if self.enable_cameras.get():
            args.append("--enable_cameras")
        if self.enable_dex3_dds.get():
            args.append("--enable_dex3_dds")

        return " && ".join([
            "source ~/miniconda3/etc/profile.d/conda.sh",
            f"conda activate {shlex.quote(self.sim_env.get().strip())}",
            f"cd {shlex.quote(self.sim_path.get().strip())}",
            " ".join(args),
        ])

    def teleop_cmd(self):
        args = [
            "python teleop_hand_and_arm.py",
            f"--input-mode {shlex.quote(self.input_mode.get().strip())}",
            f"--display-mode {shlex.quote(self.display_mode.get().strip())}",
            f"--arm {shlex.quote(self.arm.get().strip())}",
            f"--ee {shlex.quote(self.ee.get().strip())}",
            "--sim",
            f"--img-server-ip {shlex.quote(self.img_ip.get().strip())}",
        ]
        if self.headless.get():
            args.append("--headless")
        if self.record.get():
            args.append("--record")
        if self.motion.get():
            args.append("--motion")

        return " && ".join([
            "source ~/miniconda3/etc/profile.d/conda.sh",
            f"conda activate {shlex.quote(self.teleop_env.get().strip())}",
            f"cd {shlex.quote(self.teleop_path.get().strip())}",
            " ".join(args),
        ])

    def refresh(self):
        text = (
            "SIM terminal command:\n\n"
            + self.sim_cmd()
            + "\n\nTELEOP terminal command:\n\n"
            + self.teleop_cmd()
        )
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)

    def write_script(self, title: str, command: str) -> str:
        content = f"""#!/usr/bin/env bash
set -e
{command}
echo
echo "Press Enter to close..."
read dummy
"""
        fd, path = tempfile.mkstemp(prefix="xr_launcher_", suffix=".sh")
        os.close(fd)
        Path(path).write_text(content, encoding="utf-8")
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        return path

    def _open_terminal(self, title, cmd):
        builder = find_terminal()
        if not builder:
            messagebox.showerror("No terminal found", "Install xterm, konsole, xfce4-terminal, or x-terminal-emulator.")
            return
        script = self.write_script(title, cmd)
        subprocess.Popen(builder(title, script))

    def open_sim(self):
        self.refresh()
        self._open_terminal("XR SIM", self.sim_cmd())

    def open_teleop(self):
        self.refresh()
        self._open_terminal("XR TELEOP", self.teleop_cmd())

    def open_both(self):
        self.open_sim()
        self.root.after(1500, self.open_teleop)

    def stop_sim(self):
        subprocess.Popen("pkill -f sim_main.py", shell=True)

    def stop_teleop(self):
        subprocess.Popen("pkill -f teleop_hand_and_arm.py", shell=True)

    def stop_all(self):
        subprocess.Popen("pkill -f sim_main.py", shell=True)
        subprocess.Popen("pkill -f teleop_hand_and_arm.py", shell=True)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()