# -----------------------
# Activate venv .venv/bin/activate.fish   or   .venv/bin/activate
# -----------------------


import os
import threading
import time
import importlib.util
import customtkinter as ctk
from tkinter import messagebox
from tkinter import simpledialog
import json
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import re
import csv
import pyvisa

# -----------------------
# Config
# -----------------------
APP_NAME = "EGG_273A_Potentiostat"
DATA_FOLDER = "Data"
METHODS_FOLDER = "Methods"
WINDOW_SIZE = "900x640"
METHODS_PATHS = ["Methods/BuiltIn", "Methods/Custom"]

DEBUGGING = True

# -----------------------
# Helpers
# -----------------------
def module_exists(name):
    """Return True if module can be imported."""
    return importlib.util.find_spec(name) is not None

def safe_list_resources():
    """Try to list VISA resources if pyvisa available, else return []"""
    try:
        rm = pyvisa.ResourceManager()
        return list(rm.list_resources())
    except Exception:
        return []
def load_methods():
    """Load all method JSON files from both folders."""
    methods = []
    for folder in METHODS_PATHS:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if f.endswith(".json"):
                    path = os.path.join(folder, f)
                    try:
                        with open(path, "r") as file:
                            data = json.load(file)
                            methods.append(data)
                    except Exception as e:
                        print(f"Error reading {path}: {e}")
    return methods

class SafeFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._after_ids = []

    def safe_after(self, delay_ms, callback):
        after_id = self.after(delay_ms, callback)
        self._after_ids.append(after_id)
        return after_id

    def cancel_all_after(self):
        for after_id in self._after_ids:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()

# -----------------------
# Loading Frame
# -----------------------
class LoadingFrame(SafeFrame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.container = ctk.CTkFrame(self, width=620, height=240)
        self.container.place(relx=0.5, rely=0.45, anchor="center")

        ctk.CTkLabel(self.container, text=APP_NAME, font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(12,6))

        self.status_label = ctk.CTkLabel(self.container, text="Preparing...", anchor="w")
        self.status_label.pack(fill="x", padx=18, pady=(6,4))

        self.progress = ctk.CTkProgressBar(self.container, width=560)
        self.progress.set(0.0)
        self.progress.pack(padx=18, pady=(6,12))

        self.detail_label = ctk.CTkLabel(self.container, text="", anchor="w", wraplength=560, text_color="#9aa0a6")
        self.detail_label.pack(fill="x", padx=18, pady=(0,8))

        # Start loader thread
        self.safe_after(300, self.start_loading)

    def start_loading(self):
        thread = threading.Thread(target=self._do_loading, daemon=True)
        thread.start()

    def _update_ui(self, step_text, detail_text=None, progress=None):
        # Thread-safe UI updates via .after
        def _upd():
            self.status_label.configure(text=step_text)
            if detail_text is not None:
                self.detail_label.configure(text=detail_text)
            if progress is not None:
                self.progress.set(progress)
        self.safe_after(0, _upd)

    def _do_loading(self):
        steps = [
            ("Checking folders", f"Ensuring '{DATA_FOLDER}' and '{METHODS_FOLDER}' exist."),
            ("Probing required packages", "Checking pyvisa, matplotlib, csv, time..."),
            ("Scanning for VISA devices", "Looking for connected instruments (if pyvisa installed)."),
            ("Finalizing", "Setting up UI...")
        ]

        # Step 1: Ensure folders
        self._update_ui(steps[0][0], steps[0][1], 0.05)
        time.sleep(0.35)
        os.makedirs(DATA_FOLDER, exist_ok=True)
        os.makedirs(METHODS_FOLDER, exist_ok=True)
        time.sleep(0.2)
        self._update_ui(steps[0][0], f"Folders ready: '{DATA_FOLDER}', '{METHODS_FOLDER}'", 0.15)
        time.sleep(0.25)

        # Step 2: Check modules
        self._update_ui(steps[1][0], "Checking: pyvisa, matplotlib, customtkinter", 0.25)
        time.sleep(0.25)
        mods = {
            "pyvisa": module_exists("pyvisa"),
            "matplotlib": module_exists("matplotlib"),
            "csv": module_exists("csv"),  # always True
            "time": module_exists("time"),  # always True
        }
        detail = ", ".join(f"{k}: {'OK' if v else 'Missing'}" for k, v in mods.items())
        self._update_ui(steps[1][0], detail, 0.45)
        time.sleep(0.45)

        # Step 3: Scan VISA devices (if available)
        self._update_ui(steps[2][0], steps[2][1], 0.55)
        devices = []
        if mods["pyvisa"]:
            devices = safe_list_resources()
            devs_text = f"Found {len(devices)} device(s): {devices}" if devices else "No VISA devices found."
        else:
            devs_text = "pyvisa not installed — skipping device scan."
        self._update_ui(steps[2][0], devs_text, 0.75)
        time.sleep(0.6)

        # Step 4: Finalize
        self._update_ui(steps[3][0], "Launching main UI...", 0.95)
        time.sleep(0.5)

        # Prepare state to pass to main page
        initial_state = {
            "pyvisa_installed": mods["pyvisa"],
            "matplotlib_installed": mods["matplotlib"],
            "visa_devices": devices
        }

        # Short pause so progress bar is visible
        self._update_ui("Done", "Opening application...", 1.0)
        time.sleep(0.4)

        # Switch to main page in main thread
        self.safe_after(0, lambda: self.controller.on_loading_done(initial_state))
    
    def destroy(self):
        # cancel all after callbacks
        self.cancel_all_after()
        super().destroy()

# -----------------------
# Main App / Pages
# -----------------------
class MainPage(ctk.CTkFrame):
    def __init__(self, master, controller, initial_state):
        super().__init__(master)
        self.controller = controller
        self.initial_state = initial_state

        # VISA Resource Manager
        self.rm = pyvisa.ResourceManager('@py') ##Change to '@py'
        self.device = None

        # layout: left status bar + main area
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Main tab view
        self.tabview = ctk.CTkTabview(self, width=600)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=(8,16), pady=16)
        self.tabview.add("Config")
        self.tabview.add("Methods")
        self.tabview.add("New Method")

        self._build_config_tab()
        self._build_methods_tab()
        self._build_new_method_tab()

        # Left status indicator (rounded rectangle-like)
        self.status_frame = ctk.CTkFrame(self, width=80, corner_radius=20)
        self.status_frame.grid(row=0, column=0, sticky="ns", padx=(16,8), pady=16)
        self.status_frame.grid_propagate(False)

        # Inner colored indicator (we'll change its bg)
        self.indicator = ctk.CTkFrame(self.status_frame, width=36, height=500, corner_radius=18)
        self.indicator.place(relx=0.5, rely=0.5, anchor="center")

        # Disconnect button below indicator
        self.disconnect_btn = ctk.CTkButton(self.status_frame, text="⏏", command=self._ask_disconnect, state="disable",
                                            width=40, height=40, corner_radius=20, fg_color=self.status_frame.cget("fg_color"))#, hover_color=self.tabview.cget("fg_color"))
        self.disconnect_btn.place(relx=0.5, rely=0.95, anchor="center")

        # set initial status color based on initial_state
        self._update_status_color()

    def _build_config_tab(self):
        frame = self.tabview.tab("Config")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Configuration / Connection", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12,6))

        # Data user/project selection area
        row = 1
        ctk.CTkLabel(frame, text="User:").grid(row=row, column=0, sticky="w", padx=12, pady=(8,2))
        self.user_combo = ctk.CTkComboBox(frame, values=self._list_users(), command=self._on_user_selected)
        self.user_combo.configure(state="readonly")
        self.user_combo.grid(row=row+1, column=0, sticky="we", padx=12)
        self.new_user_btn = ctk.CTkButton(frame, text="New User", command=self._new_user_popup)
        self.new_user_btn.grid(row=row+1, column=1, padx=6)

        ctk.CTkLabel(frame, text="Project:").grid(row=row+2, column=0, sticky="w", padx=12, pady=(8,2))
        self.project_combo = ctk.CTkComboBox(frame, values=self._list_projects())
        self.project_combo.grid(row=row+3, column=0, sticky="we", padx=12)
        self.new_proj_btn = ctk.CTkButton(frame, text="New Project", command=self._new_project_popup)
        self.new_proj_btn.grid(row=row+3, column=1, padx=6)

        #self.user_combo.bind("<<ComboboxSelected>>", self._on_user_selected)

        ctk.CTkLabel(frame, text="Experiment name:").grid(row=row+4, column=0, sticky="w", padx=12, pady=(8,2))
        self.experiment_entry = ctk.CTkEntry(frame, placeholder_text="experiment_name")
        self.experiment_entry.grid(row=row+5, column=0, sticky="we", padx=12, pady=(0,12))

        # Device selection
        ctk.CTkLabel(frame, text="Available devices (VISA):").grid(row=row+6, column=0, sticky="w", padx=12, pady=(6,2))
        self.device_combo = ctk.CTkComboBox(frame, values=self.initial_state.get("visa_devices", []), command=self._refresh_devices)
        self.device_combo.configure(state="readonly")
        self.device_combo.set("Refresh devices")
        self.device_combo.grid(row=row+7, column=0, sticky="we", padx=12, pady=(0,6))

        # Buttons
        self.refresh_btn = ctk.CTkButton(frame, text="Refresh", command=self._refresh_devices)
        self.refresh_btn.grid(row=row+7, column=1, sticky="we", padx=12, pady=(0,6))
        self.connect_btn = ctk.CTkButton(frame, text="Connect", command=self._connect_device, state="normal" if self.initial_state.get("visa_devices") else "disabled")
        self.connect_btn.grid(row=row+8, column=0, sticky="we", padx=12, pady=(0,6))

        #btn_frame = ctk.CTkFrame(frame)
        #btn_frame.grid(row=row+8, column=0, columnspan=2, sticky="we", padx=12, pady=12)
        #self.refresh_btn = ctk.CTkButton(btn_frame, text="Refresh", command=self._refresh_devices)
        #self.refresh_btn.pack(side="left", padx=(0,8))
        #self.connect_btn = ctk.CTkButton(btn_frame, text="Connect", command=self._connect_device, state="normal" if self.initial_state.get("visa_devices") else "disabled")
        #self.connect_btn.pack(side="left", padx=(0,8))

    def _build_methods_tab(self):
        f = self.tabview.tab("Methods")

        # --- Load methods ---
        self.methods = load_methods()
        method_names = [m["name"] for m in self.methods] if self.methods else ["No methods found"]

        # --- Top frame for dropdown + button ---
        top_frame = ctk.CTkFrame(f)
        top_frame.pack(fill="x", padx=12, pady=12)

        # Dropdown to select method
        self.method_combo = ctk.CTkComboBox(top_frame, values=method_names, width=250)
        self.method_combo.set("Select a method")
        self.method_combo.pack(side="left", padx=(0, 10))

        # Button to show process
        def show_process():
            selected_name = self.method_combo.get()
            method = next((m for m in self.methods if m["name"] == selected_name), None)
            if method:
                messagebox.showinfo(
                    f"Process: {method['name']}",
                    method["process"]
                )
            else:
                messagebox.showwarning("Warning", "Select a valid method first.")

        show_btn = ctk.CTkButton(top_frame, text="Show Process", command=show_process)
        show_btn.pack(side="left", padx=5)

        # --- Middle frame with plot (left) and inputs (right) ---
        middle_frame = ctk.CTkFrame(f)
        middle_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Left frame for matplotlib plot
        plot_frame = ctk.CTkFrame(middle_frame)
        plot_frame.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=6)

        self.fig, self.ax = plt.subplots(figsize=(5, 4))
        self.ax.set_xlabel("Voltage (mV)")
        self.ax.set_ylabel("Current (A)")
        self.ax.grid(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Right frame for method inputs (for now blank)
        self.inputs_frame = ctk.CTkScrollableFrame(middle_frame, width=300, height=400, label_text="Method Inputs")
        self.inputs_frame.pack(side="left", fill="both", expand=False, padx=(6, 0), pady=6)
        self.inputs_frame.grid_columnconfigure(0, weight=1)
        self.inputs_frame.grid_columnconfigure(1, weight=1)

        # Dictionary to store input widgets keyed by JSON "variable"
        self.input_widgets = {}

        # Function to populate inputs based on selected method
        def update_inputs(event=None):
            # clear old widgets
            for widget in self.inputs_frame.winfo_children():
                widget.destroy()
            self.input_widgets.clear()

            selected_name = self.method_combo.get()
            method = next((m for m in self.methods if m["name"] == selected_name), None)
            if not method:
                return

            row = 0
            for inp in method.get("inputs", []):
                label = ctk.CTkLabel(
                    self.inputs_frame,
                    text=inp["label"],
                    wraplength=250,  # wrap long labels
                    anchor="w"
                )
                label.grid(row=row, column=0, sticky="w", padx=6, pady=4)

                entry = ctk.CTkEntry(self.inputs_frame)
                entry.insert(0, str(inp.get("default", "")))
                entry.grid(row=row, column=1, sticky="we", padx=6, pady=4)

                self.input_widgets[inp["variable"]] = entry
                row += 1

            # Add Run button
            run_btn = ctk.CTkButton(self.inputs_frame, text="Run Method", command=run_method)
            run_btn.grid(row=row, column=0, columnspan=2, pady=(12, 4), sticky="we")

            # Add progress bar under button
            self.progress_bar = ctk.CTkProgressBar(self.inputs_frame)
            self.progress_bar.grid(row=row+1, column=0, columnspan=2, sticky="we", padx=6, pady=(0, 6))
            self.progress_bar.set(0.0)

        # Bind dropdown change
        self.method_combo.configure(command=update_inputs)

        def split_commands(cmd_str):
            """Split by commas but ignore commas inside parentheses."""
            res = []
            current = ""
            parens = 0
            for c in cmd_str:
                if c == '(':
                    parens += 1
                elif c == ')':
                    parens -= 1
                if c == ',' and parens == 0:
                    res.append(current)
                    current = ""
                else:
                    current += c
            if current:
                res.append(current)
            return res

        def parse_process(process_str):
            s = process_str.replace(" ", "").replace("\n", "")
            repeat_pattern = re.compile(r'REPEAT\((\w+)\)\{(.*?)\}(?=:|$)')
            repeat_matches = repeat_pattern.findall(s)
            parsed = []

            for repeat_var, inner_content in repeat_matches:
                for_blocks = re.findall(r'FOR_RANGEV\(([^,]+),([^,]+),([^)]+)\)\{(.*?)\}', inner_content)
                for_list = []

                for start_var, end_var, step_var, commands_str in for_blocks:
                    commands_raw = split_commands(commands_str)
                    commands = []

                    for cmd in commands_raw:
                        cmatch = re.match(r'(\w+)\((.*)\)', cmd)
                        if not cmatch:
                            continue
                        cmd_type = cmatch.group(1).upper()
                        cmd_param = cmatch.group(2)

                        if cmd_type == "MEAN":
                            commands.append({"mean": cmd_param})
                        elif cmd_type == "DELAY":
                            commands.append({"delay": cmd_param})
                        elif cmd_type == "OUTPUT":
                            outputs = {}
                            pairs = split_commands(cmd_param)
                            for pair in pairs:
                                if '=' in pair:
                                    key, val = pair.split('=', 1)
                                    outputs[key] = val
                            commands.append({"outputs": outputs})

                    for_list.append({
                        "start": start_var,
                        "end": end_var,
                        "step": step_var,
                        "commands": commands
                    })

                parsed.append({
                    "repeats": repeat_var,
                    "for_loops": for_list
                })

            return parsed

        def describe_process(parsed_process, input_widgets, show_messagebox=True):
            """
            Print and/or show a message box with a description
            of what the parsed process will do.
            """
            def get_val(var):
                """Return float/int from entry if exists."""
                w = input_widgets.get(var)
                if not w:
                    return var  # fallback to variable name if not found
                val = w.get()
                try:
                    if '.' in val:
                        return float(val)
                    else:
                        return int(val)
                except Exception:
                    return val

            description_lines = []
            description_lines.append("🧩 Process Description:\n" + "-"*40)

            for repeat_block in parsed_process:
                repeat_var = repeat_block["repeats"]
                repeat_val = get_val(repeat_var)
                description_lines.append(f"🔁 REPEAT ({repeat_var}) → {repeat_val} times")

                for for_loop in repeat_block["for_loops"]:
                    start_val = get_val(for_loop["start"])
                    end_val = get_val(for_loop["end"])
                    step_val = get_val(for_loop["step"])

                    description_lines.append(f"  ➤ FOR_RANGEV {for_loop['start']}={start_val}, {for_loop['end']}={end_val}, {for_loop['step']}={step_val}")
                    description_lines.append("    {")

                    for cmd in for_loop["commands"]:
                        if "mean" in cmd:
                            r = get_val(cmd["mean"])
                            description_lines.append(f"      • MEAN({cmd['mean']}) → Average for {r} repetitions")
                        elif "delay" in cmd:
                            d = get_val(cmd["delay"])
                            description_lines.append(f"      • DELAY({cmd['delay']}) → Wait {d} seconds")
                        elif "outputs" in cmd:
                            outputs = cmd["outputs"]
                            out_str = ', '.join([f"{k} = {v}" for k, v in outputs.items()])
                            description_lines.append(f"      • OUTPUT({out_str})")
                    description_lines.append("    }")
                    description_lines.append("")
            description_lines.append("-"*40)

            final_description = "\n".join(description_lines)

            # Print to console too
            print(final_description)

            continue_method = True

            # Optionally show in a messagebox
            if show_messagebox:
                continue_method = messagebox.askyesno("Process Description", final_description)

            return continue_method

        #Set Voltage
        def setVoltage(voltage):
            if DEBUGGING:
                print(f"Set Voltage of {voltage}mV")
            else:
                self.device.write(f"SETE {V}")

        #Read current
        def readCurrent():
            if DEBUGGING:
                response = [10,-2]
            else:
                self.device.write("READI")
                response = self.device.read().strip().split(',')
            
            if len(response) == 2:
                value, exp = map(float, response)
                current = value * (10 ** exp)
                print(f"Current: {current}A")
            else:
                print("No Current")
            return current

        # Run method simulation
        def run_method():
            selected_name = self.method_combo.get()
            method = next((m for m in self.methods if m["name"] == selected_name), None)
            if not method:
                messagebox.showwarning("Warning", "Select a valid method first.")
                return

            print(f"Running method: {method['name']}")

            # Parse the process
            process_parsed = parse_process(method["process"])
            
            if not continue_method:
                return

            def task():
                # --- Check user/project/experiment ---
                user = self.user_combo.get()
                project = self.project_combo.get()
                experiment_name = self.experiment_entry.get().strip()

                if not user or not project or not experiment_name:
                    messagebox.showwarning("Missing info", "Please select a user, project and enter an experiment name.")
                    return

                # Print structured description before running
                continue_method = describe_process(process_parsed, self.input_widgets, show_messagebox=True)

                # --- Create CSV folder and filename ---
                project_path = os.path.join(DATA_FOLDER, user, project)
                os.makedirs(project_path, exist_ok=True)

                # Generate unique filename with increment
                base_fname = f"{experiment_name}.csv"
                existing_files = [f for f in os.listdir(project_path) if f.startswith(experiment_name) and f.endswith(".csv")]
                if existing_files:
                    numbers = [int(re.search(r"_(\d+)\.csv$", f).group(1)) for f in existing_files if re.search(r"_(\d+)\.csv$", f)]
                    next_num = max(numbers, default=0) + 1
                    fname = f"{experiment_name}_{next_num:03d}.csv"
                else:
                    fname = f"{experiment_name}_001.csv"

                csv_path = os.path.join(project_path, fname)
                print(f"Writing data to: {csv_path}")

                study_voltages = []
                study_currents = []

                self.ax.cla()                # clear axes
                self.ax.set_title("Measurement")  # optional: reset title
                self.ax.set_xlabel("Voltage (mV)")
                self.ax.set_ylabel("Current (A)")
                self.canvas.draw_idle()

                print("task started")
                total_steps = 0

                with open(csv_path, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Voltage (mV)", "Current (A)"])
                    for repeat_block in process_parsed:
                        repeat_var = repeat_block["repeats"]
                        cycles_widget = self.input_widgets.get(repeat_var)
                        cycles_val = int(cycles_widget.get()) if cycles_widget else 1

                        for for_loop in repeat_block["for_loops"]:
                            start_widget = self.input_widgets.get(for_loop["start"])
                            end_widget = self.input_widgets.get(for_loop["end"])
                            step_widget = self.input_widgets.get(for_loop["step"])

                            start_val = float(start_widget.get()) if start_widget else 0.0
                            end_val = float(end_widget.get()) if end_widget else 1.0
                            step_val = float(step_widget.get()) if step_widget else 0.1

                            steps_in_loop = int(abs(end_val - start_val) / abs(step_val)) + 1  # include last step
                            total_steps += cycles_val * steps_in_loop

                    print(f"Total simulation steps: {total_steps}")

                    step_counter = 0

                    for repeat_block in process_parsed:
                        repeat_var = repeat_block.get("repeat_var", "C")
                        cycles_widget = self.input_widgets.get(repeat_var)
                        cycles_val = int(cycles_widget.get()) if cycles_widget else 1

                        print(f"🔁 Repeat ({repeat_var}) → {cycles_val} times")
                        for c in range(cycles_val):
                            print(f"  Cycle {c+1}/{cycles_val}")

                            for for_loop in repeat_block["for_loops"]:
                                # Safely get input values
                                start_val = float(self.input_widgets.get(for_loop["start"]).get()) if for_loop["start"] in self.input_widgets else 0
                                end_val = float(self.input_widgets.get(for_loop["end"]).get()) if for_loop["end"] in self.input_widgets else 1
                                step_val = float(self.input_widgets.get(for_loop["step"]).get()) if for_loop["step"] in self.input_widgets else 0.1

                                print(f"    ➤ For Loop: {for_loop['start']}={start_val} → {for_loop['end']}={end_val} step {step_val}")

                                # Parse commands
                                delay_val = 0
                                r_val = 1
                                outputs = []

                                for cmd in for_loop["commands"]:
                                    if "mean" in cmd:
                                        param = cmd["mean"]
                                        r_widget = self.input_widgets.get(param)
                                        r_val = int(r_widget.get()) if r_widget else 1
                                        print(f"      • Average for {r_val} repetitions ({param})")
                                    elif "delay" in cmd:
                                        param = cmd["delay"]
                                        d_widget = self.input_widgets.get(param)
                                        delay_val = float(d_widget.get()) if d_widget else 1.0
                                        print(f"      • Delay for {delay_val} s ({param})")
                                        time.sleep(delay_val * 0.1)  # simulate shorter delay for UI

                                # Determine direction
                                if start_val < end_val:
                                    V_values = [v for v in frange(start_val, end_val, step_val)]
                                else:
                                    V_values = [v for v in frange(start_val, end_val, -abs(step_val))]

                                # Loop over voltage range
                                for V in V_values:
                                    print(f"        → Voltage = {V:.3f}")
                                    setVoltage(V)
                                    time.sleep(float(delay_val / 2))

                                    currents = []
                                    for _ in range(r_val):
                                        time.sleep(float(delay_val / (2 * r_val)))
                                        currents.append(readCurrent())

                                    I_mean = sum(currents) / len(currents)

                                    # --- Write to CSV ---
                                    writer.writerow([V, I_mean])
                                    f.flush()

                                    # Store and plot
                                    study_voltages.append(V)
                                    study_currents.append(I_mean)
                                    self.ax.plot(study_voltages, study_currents, 'bo-')
                                    self.canvas.draw_idle()

                                    step_counter += 1
                                    self.progress_bar.set(step_counter / total_steps)
                                    self.update_idletasks()

                print("✅ Process complete.")
                self.progress_bar.set(1.0)
                messagebox.showinfo("Finished", "Method simulation completed!")

            # Utility for float ranges
            def frange(start, stop, step):
                vals = []
                x = start
                if step > 0:
                    while x <= stop:
                        vals.append(x)
                        x += step
                else:
                    while x >= stop:
                        vals.append(x)
                        x += step
                return vals

            # Run on background thread
            threading.Thread(target=task, daemon=True).start()

    def _build_new_method_tab(self):
        f = self.tabview.tab("New Method")
        ctk.CTkLabel(f, text="New Method Designer (pseudo-code editor)", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=12, pady=12)
        self.new_method_text = ctk.CTkTextbox(f, width=600, height=300)
        self.new_method_text.pack(padx=12, pady=8)

        save_btn = ctk.CTkButton(f, text="Save Method", command=self._save_new_method)
        save_btn.pack(padx=12, pady=8, anchor="e")

    # -------------------------
    # Simple actions / helpers
    # -------------------------
    def _list_users(self):
        users = []
        try:
            users = [d for d in os.listdir(DATA_FOLDER) if os.path.isdir(os.path.join(DATA_FOLDER, d))]
        except Exception:
            users = []
        return users

    def _list_projects(self):
        projects = []
        try:
            user = self.user_combo.get()  # <-- get current combo value
            projects = [
                d for d in os.listdir(os.path.join(DATA_FOLDER, user))
                if os.path.isdir(os.path.join(DATA_FOLDER, user, d))
            ]
        except Exception:
            projects = []
        return projects

    def _on_user_selected(self, event=None):
        self.reload_project_combo()

    def reload_project_combo(self):
        if not hasattr(self, "project_combo"):
            print("Project combo not yet created — skipping reload.")
            return

        projects = self._list_projects()
        if projects:
            self.project_combo.configure(values=projects, state="readonly")
            self.project_combo.set(projects[0])
        else:
            self.project_combo.set("No projects found")
            self.project_combo.configure(values=[], state="disabled")

    def _new_user_popup(self):
        name = simpledialog.askstring("New User", "Enter new user/folder name:")
        if name:
            path = os.path.join(DATA_FOLDER, name)
            try:
                os.makedirs(path, exist_ok=True)
                self.user_combo.configure(values=self._list_users())
                messagebox.showinfo("Created", f"Created folder: {path}")
                self.user_combo.set(name)
                self.reload_project_combo()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _new_project_popup(self):
        user = self.user_combo.get()
        if not user:
            messagebox.showwarning("Select user", "Please select a user folder first.")
            return
        name = simpledialog.askstring("New Project", "Enter new project/folder name:")
        if name:
            path = os.path.join(DATA_FOLDER, user, name)
            try:
                os.makedirs(path, exist_ok=True)
                messagebox.showinfo("Created", f"Created folder: {path}")
                self.reload_project_combo()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _refresh_devices(self):
        # refresh VISA device list
        devices = safe_list_resources()
        self.device_combo.configure(values=devices)
        # adjust connect button
        if devices:
            self.connect_btn.configure(state="normal")
            self.device_combo.set(devices[0])
        else:
            self.device_combo.set("No devices found")
            self.connect_btn.configure(state="disabled")
        # update status colour
        self._update_status_color()

    def _connect_device(self):
        dev = self.device_combo.get()
        if not dev:
            messagebox.showwarning("No device", "Select a device first.")
            return
        # For now, attempt to open resource to test connection (non-blocking quick test)
        try:
            self.device = self.rm.open_resource(dev)
            self.device.read_termination = '\r\n'
            self.device.write_termination = '\r\n'
            self.device.timeout = 5000

            # Initialize device
            self.device.write("MODE 2")  # potentiostat mode
            self.device.write("CELL 1")  # turn cell ON


            # attempt ID or IDN
            try:
                # Query ID, Version, Error
                self.device.write("ID")
                dev_id = self.device.read().strip()

                self.device.write("VER")
                version = self.device.read().strip()

                self.device.write("ERR")
                error = self.device.read().strip()

                messagebox.showinfo("Connected",
                            f"Connected to {dev_name}\n\n"
                            f"ID: {dev_id}\n"
                            f"Version: {version}\n"
                            f"Error: {error}")
            except Exception as e:
                messagebox.showerror("Connection Error", str(e))

            # Mark as connected (for now simply set the indicator and enable disconnect)
            self._set_connected(True)
            messagebox.showinfo("Connected", f"Connection test to {dev} completed (quick test).")
        except Exception as e:
            messagebox.showerror("Connection failed", f"Could not open {dev}:\n{e}")
            self._set_connected(False)

    def _set_connected(self, connected: bool):
        if connected:
            self.disconnect_btn.configure(state="normal", fg_color=self.cget("fg_color"))
            # store state if needed
            self.controller.connected = True
        else:
            self.disconnect_btn.configure(state="disabled", fg_color=self.status_frame.cget("fg_color"))
            self.controller.connected = False
        self._update_status_color()

    def _ask_disconnect(self):
        if not getattr(self.controller, "connected", False):
            return
        if messagebox.askyesno("Disconnect", "Are you sure you want to disconnect the device?"):
            # Here we would safely send the "CELL 0" or close instrument safely.
            if self.device:
                try:
                    self.device.write("CELL 0")  # turn cell OFF
                    self.device.close()
                except:
                    pass
            self.device = None
            self._set_connected(False)
            messagebox.showinfo("Disconnected", "Device disconnected.")
            self._update_status_color()

    def _save_new_method(self):
        text = self.new_method_text.get("0.0", "end").strip()
        if not text:
            messagebox.showwarning("Empty", "Method text is empty.")
            return
        # save to Methods/Custom with timestamp name
        import datetime
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = os.path.join(METHODS_FOLDER, f"custom_method_{stamp}.txt")
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Saved", f"Method saved: {fname}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_status_color(self):
        # Decide color:
        # - red: pyvisa missing or no devices found
        # - blue: devices found but not connected
        # - green: connected
        connected = self.device
        devices = self.device_combo.cget("values") or []

        if connected:
            color = "#2ecc71"  # green
        elif devices:
            color = "#3498db"  # blue
        else:
            color = "#e74c3c"  # red

        # apply color to indicator
        self.indicator.configure(fg_color=color)
    
    class MainPage(ctk.CTkFrame):
        def destroy(self):
            # destroy matplotlib canvas safely
            if hasattr(self, "canvas"):
                self.canvas.get_tk_widget().destroy()
                plt.close(self.fig)  # close the figure
            super().destroy()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # store after IDs
        self._after_ids = []

        self.title(APP_NAME)
        self.geometry(WINDOW_SIZE)
        self.resizable(False, False)
        # center window on screen
        self.eval('tk::PlaceWindow . center')

        self.connected = False
        self.loading_frame = LoadingFrame(self, self)
        self.loading_frame.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self, event=None):
        if hasattr(self, "main_page"):
            if hasattr(self.main_page, "canvas"):
                self.main_page.canvas.get_tk_widget().destroy()
            if hasattr(self.main_page, "fig"):
                plt.close(self.main_page.fig)
            self.main_page.destroy()
        if hasattr(self, "loading_frame"):
            self.loading_frame.destroy()
        self.after(50, self.destroy)  # destroy root slightly later

    def on_loading_done(self, initial_state):
        # destroy loading and show main page
        #self.configure(fg_color=APP_BG)
        self.loading_frame.pack_forget()
        self.main_page = MainPage(self, self, initial_state)
        self.main_page.pack(fill="both", expand=True)

if __name__ == "__main__":
    ctk.set_appearance_mode("Light")  # or "Dark"
    ctk.set_default_color_theme("dark-blue")
    app = App()
    app.mainloop()
