import os
import sys
import json
import asyncio
from nicegui import app, ui, run
import launcher

def main():
    # Determine correct base path for static assets whether running as script or bundled .exe
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.getcwd()

    static_dir = os.path.join(base_path, 'static')

    # Host local static assets using the dynamic path
    app.add_static_files('/static', static_dir)

    CONFIG_FILE = os.path.join(os.getcwd(), "launcher_user_data.json")

    # Application State
    settings_state = {
        'allocated_ram': 4,
        'auto_mod_updates': True,
        'auto_launcher_updates': True,
        'update_reminders': False
    }

    account_state = {
        'username': '',
        'password': '',
        'logged_in_user': None
    }


    # --- PERSISTENCE & LOCAL SESSION HELPERS ---

    def save_app_data():
        """Saves settings and active session to JSON."""
        data = {
            'settings': settings_state,
            'logged_in_user': account_state['logged_in_user']
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Config Error] Failed to save application data: {e}")

    def load_app_data():
        """Loads settings and restores active user session on startup."""
        if not os.path.exists(CONFIG_FILE):
            return

        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'settings' in data:
                settings_state.update(data['settings'])

            if data.get('logged_in_user'):
                account_state['logged_in_user'] = data['logged_in_user']
                print(f"[Auto-Login] Restored session for user: {account_state['logged_in_user']}")

        except Exception as e:
            print(f"[Config Error] Failed to load persistent data: {e}")

    load_app_data()


    # Window control handler (Shuts down app server)
    def close_window():
        app.shutdown()


    # --- UI PROGRESS & STATUS UPDATERS ---

    def update_status(text: str):
        status_label.set_text(text)
        status_label.set_visibility(True)

    def update_progress(val: int):
        progress_bar.set_value(val / 100)
        progress_bar.set_visibility(True)

    def toggle_controls(enabled: bool):
        if enabled:
            play_btn.enable()
            verify_mods_btn.enable()
            verify_launcher_btn.enable()
        else:
            play_btn.disable()
            verify_mods_btn.disable()
            verify_launcher_btn.disable()


    # --- Dynamic Action Handlers ---

    async def handle_verify_mods():
        game_dir = os.path.abspath(os.path.join(os.getcwd(), ".minecraft"))
        toggle_controls(False)
        
        try:
            await run.io_bound(
                launcher.sync_and_verify_environment, 
                game_dir, 
                status_cb=update_status, 
                progress_cb=update_progress
            )
            update_status('Mod verification complete! All mods up to date.')
            update_progress(100)
        except Exception as e:
            update_status(f'Failed to verify mods: {e}')
        finally:
            toggle_controls(True)


    async def handle_verify_launcher():
        toggle_controls(False)
        update_status('Checking launcher configuration...')
        update_progress(25)
        
        try:
            manifest = await run.io_bound(launcher.fetch_github_manifest)
            update_progress(100)
            mc_ver = manifest.get('mc_version', launcher.DEFAULT_CONFIG['mc_version'])
            loader_ver = manifest.get('modloader', launcher.DEFAULT_CONFIG['neoforge_version'])
            update_status(f"Config verified — MC: {mc_ver}, ModLoader: {loader_ver}")
        except Exception as e:
            update_status(f'Failed to fetch launcher configuration: {e}')
        finally:
            toggle_controls(True)


    async def handle_launch():
        logged_in_user = account_state['logged_in_user']
        
        if not logged_in_user:
            ui.notify("Error: You must be logged in to start the game!", type='negative', icon='error')
            update_status("Error: Authentication required to launch.")
            return

        ram = settings_state['allocated_ram']
        game_dir = os.path.abspath(os.path.join(os.getcwd(), ".minecraft"))
        
        toggle_controls(False)
        update_status("Generating fresh session token...")

        try:
            import uuid
            new_token = str(uuid.uuid4())
            token_path = os.path.join(game_dir, "launcher_token.txt")

            os.makedirs(game_dir, exist_ok=True)
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(new_token)

            launcher.supabase.table("users").update({"token": new_token}).eq("username", logged_in_user).execute()
            update_status("Session token updated successfully!")
        except Exception as e:
            update_status(f"Warning: Failed to sync token to cloud: {e}")

        process = await run.io_bound(
            launcher.launch_game,
            game_dir,
            logged_in_user,
            ram,
            server_ip="91.197.6.180",
            port="25186",
            status_cb=update_status,
            progress_cb=update_progress
        )
        
        if process:
            update_status("Game running...")
            
            while process.poll() is None:
                await asyncio.sleep(1)
                
            update_status("Game closed. Ready to launch again.")
            progress_bar.set_visibility(False)
        else:
            update_status("Failed to start Minecraft process. Check logs.")
        
        toggle_controls(True)

    # UI Styling
    ui.add_head_html('''
    <style>
        html, body {
            overflow: hidden !important;
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            user-select: none;
        }

        ::-webkit-scrollbar {
            display: none;
        }

        body {
            background-image: url("/static/background.png");
            background-size: cover;
            background-position: center;
            background-color: #121212;
            color: #ffffff;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .nav-button {
            position: relative;
            display: flex !important;
            align-items: center !important;
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(8px);
            border-radius: 25px;
            padding: 8px;
            width: 50px;
            height: 50px;
            cursor: pointer;
            transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.2s ease;
        }

        .nav-button:hover {
            width: 120px;
            background: rgba(0, 0, 0, 0.85);
        }

        .nav-button img {
            width: 34px !important;
            height: 34px !important;
            min-width: 34px !important;
            min-height: 34px !important;
            display: block !important;
            flex-shrink: 0 !important;
            z-index: 2;
        }

        .nav-text {
            position: absolute;
            left: 54px;
            white-space: nowrap;
            font-size: 14px;
            color: #fff;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
            z-index: 1;
        }

        .nav-button:hover .nav-text {
            opacity: 1;
        }

        .btn-secondary {
            background-color: rgba(255, 255, 255, 0.15) !important;
            color: #fff !important;
            backdrop-filter: blur(4px);
            transition: transform 0.15s ease, background-color 0.2s ease !important;
        }

        .btn-secondary:hover {
            background-color: rgba(255, 255, 255, 0.25) !important;
            transform: translateY(-2px);
        }

        .btn-primary {
            background-color: #2563eb !important;
            color: #fff !important;
            transition: transform 0.15s ease, background-color 0.2s ease !important;
        }

        .btn-primary:hover {
            background-color: #1d4ed8 !important;
            transform: translateY(-2px);
        }

        .modal-card {
            background: rgba(20, 20, 20, 0.88) !important;
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 16px;
            color: #ffffff;
        }

        .custom-input .q-field__control {
            background: rgba(255, 255, 255, 0.08) !important;
            border-radius: 8px !important;
        }
        
        .custom-input input {
            color: #ffffff !important;
        }
    </style>
    ''')


    # --- Login & Registration Logic ---

    async def handle_login():
        username = account_state['username'].strip()
        password = account_state['password'].strip()

        if not username or not password:
            ui.notify('Please enter both username and password.', type='warning')
            return

        try:
            # 1. Check if the user exists in the database
            # (Note: If your Supabase table has RLS enabled, ensure you have a public policy or use an RPC function to check existence, 
            # otherwise we check via the authentication response below)
            user_check = launcher.supabase.table("users").select("username").eq("username", username).execute()
            
            user_exists = bool(user_check.data)

            import uuid
            new_token = str(uuid.uuid4())

            # 2. Attempt authentication via Supabase RPC
            response = launcher.supabase.rpc(
                "authenticate_and_update_token", 
                {
                    "p_username": username,
                    "p_password": password,
                    "p_new_token": new_token
                }
            ).execute()

            is_authenticated = response.data

            if is_authenticated:
                # Case 3: Username exists and passwords match = Login
                account_state['logged_in_user'] = username
                save_app_data()
                account_dialog.close()
                user_label.set_text(f"Logged in as: {username}")
                logged_in_banner.set_text(f"Already logged in as: {username}")
                logged_in_banner.set_visibility(True)
                ui.notify(f'Logged in successfully as {username}', type='positive')
                
            else:
                # Authentication failed. Let's figure out why:
                # Check if user exists based on our initial query OR handle RLS fallback
                if user_exists:
                    # Case 2: Username exists and password is wrong
                    ui.notify('Incorrect password! Please try again.', type='negative')
                else:
                    # Case 1: Username doesn't exist -> Prompt to create an account
                    account_dialog.close()
                    not_found_dialog.open()
                    
        except Exception as e:
            ui.notify(f'Login error: {e}', type='negative')

    async def create_account():
        username = account_state['username'].strip()
        password = account_state['password'].strip()
        
        if not username or not password:
            ui.notify('Username and password cannot be empty.', type='warning')
            return

        try:
            import uuid
            new_token = str(uuid.uuid4())

            # Call the secure Supabase RPC function to handle the registration
            launcher.supabase.rpc(
                "register_new_user",
                {
                    "p_username": username,
                    "p_password": password,
                    "p_new_token": new_token
                }
            ).execute()
            
            account_state['logged_in_user'] = username
            save_app_data()
            not_found_dialog.close()
            user_label.set_text(f"Logged in as: {username}")
            logged_in_banner.set_text(f"Already logged in as: {username}")
            logged_in_banner.set_visibility(True)
            ui.notify(f'Account created! Logged in as {username}', type='positive')
        except Exception as e:
            ui.notify(f'Failed to create account: {e}', type='negative')
            
    def handle_logout():
        account_state['logged_in_user'] = None
        save_app_data()
        user_label.set_text("Not logged in")
        logged_in_banner.set_visibility(False)
        ui.notify("Logged out successfully.", type='info')


    # --- Dialog Modals ---
    with ui.dialog() as not_found_dialog, ui.card().classes('modal-card w-96 p-6 gap-4 text-center items-center'):
        ui.icon('warning', size='48px').classes('text-amber-400 mt-2')
        ui.label('Account Not Found').classes('text-xl font-bold text-white -mt-1')
        ui.label("We couldn't find an account matching that username. Would you like to create a new account?").classes('text-xs text-gray-300 leading-relaxed')

        with ui.column().classes('w-full gap-2 mt-2'):
            ui.button('Create Account', on_click=create_account).classes('btn-primary w-full py-2.5 font-semibold rounded-lg')
            ui.button('Cancel', on_click=lambda: (
                not_found_dialog.close(),
                account_dialog.open()
            )).classes('btn-secondary w-full py-2 font-semibold rounded-lg')


    with ui.dialog() as account_dialog, ui.card().classes('modal-card w-96 p-6 gap-4'):
        with ui.row().classes('w-full justify-between items-center mb-1'):
            ui.label('Account Settings').classes('text-xl font-bold text-white')
            ui.button(icon='close', on_click=account_dialog.close).props('flat round dense').classes('text-gray-400 hover:text-white')

        logged_in_banner = ui.label(
            f"Already logged in as: {account_state['logged_in_user']}" if account_state['logged_in_user'] else ""
        ).classes('text-xs text-green-400 bg-green-950/60 p-2 rounded border border-green-800 text-center font-medium w-full')
        
        logged_in_banner.set_visibility(bool(account_state['logged_in_user']))

        ui.label('Log in or switch accounts').classes('text-xs text-gray-400 -mt-2 mb-1')

        with ui.column().classes('w-full gap-1'):
            ui.label('Username').classes('text-xs font-medium text-gray-300')
            ui.input(
                placeholder='Enter username',
                on_change=lambda e: account_state.update({'username': e.value})
            ).classes('custom-input w-full').props('outlined dark dense')

        with ui.column().classes('w-full gap-1'):
            ui.label('Password').classes('text-xs font-medium text-gray-300')
            ui.input(
                placeholder='Enter password',
                password=True,
                password_toggle_button=True,
                on_change=lambda e: account_state.update({'password': e.value})
            ).classes('custom-input w-full').props('outlined dark dense')

        with ui.column().classes('w-full gap-2 mt-2'):
            ui.button('Log In', on_click=handle_login).classes('btn-primary w-full py-2.5 font-semibold rounded-lg')
            ui.button('Log Out', on_click=handle_logout).classes('btn-secondary w-full py-2 font-semibold rounded-lg')


    with ui.dialog() as settings_dialog, ui.card().classes('modal-card w-96 p-6 gap-5'):
        with ui.row().classes('w-full justify-between items-center mb-1'):
            ui.label('Settings').classes('text-xl font-bold text-white')
            ui.button(icon='close', on_click=settings_dialog.close).props('flat round dense').classes('text-gray-400 hover:text-white')

        with ui.column().classes('w-full gap-1'):
            with ui.row().classes('w-full justify-between items-center'):
                ui.label('Allocated RAM').classes('text-sm font-medium text-gray-200')
                ram_label = ui.label(f"{settings_state['allocated_ram']} GB").classes('text-sm font-bold text-blue-400')
            
            ui.slider(
                min=2, max=16, step=1, 
                value=settings_state['allocated_ram'],
                on_change=lambda e: (settings_state.update({'allocated_ram': e.value}), ram_label.set_text(f"{e.value} GB"))
            ).props('color=blue').classes('w-full')

        ui.separator().classes('bg-white/10')

        with ui.row().classes('w-full justify-between items-center'):
            ui.label('Automatic Mod Updates').classes('text-sm font-medium text-gray-200')
            ui.switch(
                value=settings_state['auto_mod_updates'],
                on_change=lambda e: settings_state.update({'auto_mod_updates': e.value})
            ).props('color=blue')

        with ui.row().classes('w-full justify-between items-center'):
            ui.label('Automatic Launcher Updates').classes('text-sm font-medium text-gray-200')
            ui.switch(
                value=settings_state['auto_launcher_updates'],
                on_change=lambda e: settings_state.update({'auto_launcher_updates': e.value})
            ).props('color=blue')

        with ui.row().classes('w-full justify-between items-center'):
            ui.label('Update Reminders').classes('text-sm font-medium text-gray-200')
            ui.switch(
                value=settings_state['update_reminders'],
                on_change=lambda e: settings_state.update({'update_reminders': e.value})
            ).props('color=blue')

        ui.button('Save Settings', on_click=lambda: (
            save_app_data(),
            settings_dialog.close(),
            ui.notify(f"Settings saved! RAM: {settings_state['allocated_ram']} GB", type='positive')
        )).classes('btn-primary w-full py-2 mt-2 font-semibold rounded-lg')


    # --- Header Controls ---
    with ui.element('header').classes('absolute top-0 left-0 right-0 p-4 flex justify-between items-center z-50'):
        with ui.row().classes('gap-3'):
            with ui.element('button').classes('nav-button').on('click', account_dialog.open):
                ui.image('/static/account.png').classes('w-8 h-8 pointer-events-none')
                ui.label('Account').classes('nav-text')

            with ui.element('button').classes('nav-button').on('click', settings_dialog.open):
                ui.image('/static/settings.png').classes('w-8 h-8 pointer-events-none')
                ui.label('Settings').classes('nav-text')

        with ui.row().classes('gap-1'):
            ui.button(
                icon='close', 
                on_click=close_window
            ).props('flat round dense').classes('text-white hover:bg-red-600/80 w-9 h-9')


    # --- Main Launcher Section ---
    with ui.element('main').classes('w-full h-screen flex flex-col items-center justify-center gap-4 text-center'):
        ui.label('Songoda Launcher').classes('text-4xl font-bold drop-shadow-md text-white')
        
        current_user_text = f"Logged in as: {account_state['logged_in_user']}" if account_state['logged_in_user'] else "Not logged in"
        user_label = ui.label(current_user_text).classes('text-xs text-blue-300 font-medium -mt-2')

        with ui.column().classes('w-80 gap-2 items-stretch mt-2'):
            verify_mods_btn = ui.button('Verify Mod Updates', on_click=handle_verify_mods).classes('btn-secondary py-1.5 text-xs font-semibold rounded-md capitalize')
            verify_launcher_btn = ui.button('Verify Launcher Updates', on_click=handle_verify_launcher).classes('btn-secondary py-1.5 text-xs font-semibold rounded-md capitalize')
            
            status_label = ui.label("Ready to launch").classes('text-xs text-gray-300 mt-4 h-4 overflow-hidden text-ellipsis whitespace-nowrap')
            progress_bar = ui.linear_progress(value=0).props('color=blue track-color=grey-8').classes('w-full rounded-full h-2')
            progress_bar.set_visibility(False)
            
            play_btn = ui.button('Play', on_click=handle_launch).classes('btn-primary py-3 text-lg font-bold rounded-lg mt-2 capitalize')


if __name__ in {"__main__", "__mp_main__"}:
    # Run launcher via local web server mode using App Mode
    ui.run(
        main,
        title='Songoda Launcher',
        native=True,
        port=8080,
        reload=False,
        frameless=True
    )