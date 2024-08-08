import minecraft_launcher_lib as mc, uuid, subprocess, tkinter as tk, json, os, time, threading, psutil
from tkinter import ttk
from pypresence import Presence
from tkinter import messagebox
from tkinter import simpledialog

class Launcher:
    def __init__(self) -> None:
        self.game_dir = __file__.replace(r"\Launcher.py", "") + r"\.songodaMC"
        if not os.path.exists(self.game_dir):
            os.makedirs(self.game_dir)

        self.start_time = time.time()
        self.thread_stop = False

        self.Client_ID = "1190428235478081546"

        self.RPC = Presence(self.Client_ID)
        self.RPC.connect()

        self.RPC.update(
            state="Idle",
            details="In the launcher",
            start=self.start_time,
            large_image="large_image",
            large_text="Songoda Launcher",
        )

        self.main_menu()
    
    def main_menu(self):
        self.root = tk.Tk()
        self.root.geometry("500x300")
        self.root.title("Songoda Launcher")
        
        self.titleLabel = ttk.Label(self.root, anchor="center", text="Songoda Launcher", font=(30)).pack()
        
        self.usernameLabel = ttk.Label(self.root, text="Username:").pack()
        self.usernameFrame = ttk.Frame(self.root); self.usernameFrame.pack()
        self.usernameEntry = ttk.Combobox(self.usernameFrame, values=[x.get("username") for x in json.load(open("launcher.json", "r"))["Users"]]); self.usernameEntry.grid(row=0, column=1)
        self.newuserButton = ttk.Button(self.usernameFrame, text="+", command=self.new_user).grid(row=0, column=2)
        self.versionLabel = ttk.Label(self.root, text="Version:").pack()
        self.versionCombobox = ttk.Combobox(self.root, values=[version.get("id") for version in mc.utils.get_available_versions(self.game_dir) if version.get("type")=="release"]); self.versionCombobox.pack()
        self.buildLabel = ttk.Label(self.root, text="Build:").pack()
        self.buildCombobox = ttk.Combobox(self.root, values=["Vanilla", "Forge", "Fabric"]); self.buildCombobox.pack()
        self.launchButton = ttk.Button(self.root, width=30, text="Launch Minecraft", command=self.launch_minecraft).pack(pady=10)
        self.accountManagerButton = ttk.Button(self.root, width=30, text="Account Manager").pack()
        self.settingsButton = ttk.Button(self.root, width=30, text="Settings", command=self.settings).pack(pady=10)
        
        self.root.mainloop()

    def new_user(self):
        username = simpledialog.askstring("Songoda Launcher: New User", "Enter username: ")
        userUUID = str(uuid.uuid4())
        with open("launcher.json", "r") as file:
            data = json.load(file)
        data["Users"].append({
            "username": username,
            "uuid": userUUID
        })
        with open("launcher.json", "w") as file:
            json.dump(data, file)

    def update_memory(self, value):
        self.selectedMemory = int(float(value))
        self.actualMemoryLabel.config(text=f"{self.selectedMemory} MB")

    def settings(self):
        self.settings_root = tk.Tk()

        self.settings_root.geometry("500x300")
        self.settings_root.title("Songoda Launcher: Settings")
        self.memoryLabel = ttk.Label(self.settings_root, text="Memory:").pack()
        self.actualMemoryLabel = ttk.Label(self.settings_root, text=""); self.actualMemoryLabel.pack()
        maxmemory = psutil.virtual_memory().total/1024/1024
        memoryEntry = ttk.Scale(self.settings_root, from_=0, to=maxmemory, orient=tk.HORIZONTAL, command=self.update_memory, length=400); memoryEntry.pack()
        
    def launch_minecraft(self):
        versions = mc.utils.get_installed_versions(self.game_dir)
        for version in versions:
            if version.get("id") == self.versionCombobox.get():
                version = version.get("id")
                break
        else:
            if messagebox.askokcancel("Songoda Launcher: Error", "Selected version has not been installed, would you like to install it?") is True:
                if self.buildCombobox.get() == "Vanilla":
                    mc.install.install_minecraft_version(self.versionCombobox.get(), self.game_dir)
                elif self.buildCombobox.get() == "Forge":
                    mc.forge.install_forge_version(self.versionCombobox.get(), self.game_dir)
                elif self.buildCombobox.get() == "Fabric":
                    mc.fabric.install_fabric(self.versionCombobox.get(), self.game_dir)
                else:
                    messagebox.showerror("Songoda Launcher: Error", "Invalid version or build selected.")
                version = self.versionCombobox.get()
            else:
                return

        options = {
            "username": self.usernameEntry.get(),
            "uuid": str([x.get("uuid") for x in json.load(open("launcher.json", "r"))["Users"] if x.get("username") == self.usernameEntry.get()]),
            "jvmArguments": [f"-Xmx{self.selectedMemory}M", f"-Xms{self.selectedMemory}M"],
            "gameDirectory": self.game_dir
        }

        command = mc.command.get_minecraft_command(version, self.game_dir, options)
        
        self.root.withdraw()
        
        self.RPC.update(
            state="Playing Vanilla Minecraft",
            details=f"Minecraft {version}",
            start=self.start_time,
            large_image="large_image",
            large_text="Songoda Launcher",
            small_image="samll_image",
            small_text="Minecraft"
        )

        subprocess.call(command)

        self.RPC.update(
            state="Idle",
            details="In the launcher",
            start=self.start_time,
            large_image="large_image",
            large_text="Songoda Launcher",
        )

        self.root.deiconify()

if __name__ == "__main__":
    Launcher()