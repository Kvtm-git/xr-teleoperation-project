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

HOME = str(Path.home())


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
        self.teleop_env = tk.StringVar(value="tv")
        self.sim_path = tk.StringVar(value=f"{HOME}/unitree_sim_isaaclab")
        self.teleop_path = tk.StringVar(value=f"{HOME}/afsluttende_projekt/repos/xr_teleoperate/teleop")
        self.img_ip = tk.StringVar(value="172.17.45.95")

        self.input_mode = tk.StringVar(value="hand")
        self.ee = tk.StringVar(value="dex3")
        self.arm = tk.StringVar(value="G1_29")
        self.display_mode = tk.StringVar(value="immersive")
        self.device = tk.StringVar(value="cpu")
        self.task = tk.StringVar(value="Isaac-PickPlace-Cylinder-G129-Dex3-Joint")
        self.robot_type = tk.StringVar(value="g129")

        self.enable_cameras = tk.BooleanVar(value=True)
        self.enable_dex3_dds = tk.BooleanVar(value=True)
        self.headless = tk.BooleanVar(value=False)
        self.record = tk.BooleanVar(value=False)
        self.motion = tk.BooleanVar(value=False)

        self.build()

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
        self.row(p, 4, "Image server IP", self.img_ip, 30)

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