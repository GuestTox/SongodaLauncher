# 🚀 Songoda Launcher

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![NiceGUI](https://img.shields.io/badge/NiceGUI-UI%2FFramework-orange.svg?style=for-the-badge&logo=python&logoColor=white)](https://nicegui.io/)
[![Supabase](https://img.shields.io/badge/Supabase-Backend%20%2F%20Auth-green.svg?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A modern, high-performance, custom-built Minecraft launcher featuring automated mod synchronization, dynamic cryptographic session token management, cloud authentication, and a sleek frameless web-based GUI.

</div>

---

## ✨ Key Features

*   **🔒 Secure Cloud Authentication & Token Sync**: Integrated with **Supabase** backend via custom RPC functions for secure user registration, password hashing, and dynamic session token generation.
*   **⚡ Automated Mod Sync & Hashing**: Automatically compares local mod files against a remote GitHub manifest using **SHA-256/SHA-512 cryptographic verification**, handling multithreaded downloads (`ThreadPoolExecutor`) and cleaning up obsolete files.
*   **🎮 Seamless Environment Management**: Automatically provisions the correct base Minecraft version, installs and configures **NeoForge**, and passes secure command-line tokens to the game client.
*   **🎨 Sleek Custom GUI**: Built using **NiceGUI** with a custom Tailwind/CSS dark-mode interface, featuring blur-filters, frameless window controls, dynamic progress bars, and localized user session persistence.

---

## 🛠️ Tech Stack

*   **Frontend/UI**: Python, NiceGUI, HTML5/CSS3 (Tailwind CSS principles, custom animations & blur-effects).
*   **Backend & Database**: Supabase (PostgreSQL, RPC functions, Row-Level security paradigms).
*   **Game Integration**: `minecraft-launcher-lib`, subprocess process management, multithreading (`concurrent.futures`).

---

## 📂 Project Structure

```text
SongodaLauncher/
│
├── main.py          # NiceGUI frontend interface, state management, and event loops
├── launcher.py      # Core launcher logic, mod hashing, NeoForge installer, and Supabase RPCs
├── static/          # UI assets (backgrounds, icons)
└── README.md        # Project documentation
