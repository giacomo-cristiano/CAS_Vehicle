import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import math
import os
import csv
from datetime import datetime

class BluetoothApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bluetooth HC-05 Connection")

        # Serial connection placeholder
        self.bt_connection = None
        self.read_thread = None
        self.connected = False

        # Variables for plotting and control
        self.speed_data = []
        self.abs_speed_data = []
        self.abs_zeros_count = 0
        self.is_plotting = True
        self.start_time = 0
        self.latest_rpm = None
        self.latest_speed = None

        # # File for speed data (real-time timestamp)
        # timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # self.speed_csv_filename = f"speed_profile_{timestamp}.csv"
        # self.init_csv(self.speed_csv_filename, ["Time (s)", "Speed (m/s)"])

        # Placeholder for ABS CSV file
        self.abs_csv_filename = None

        # Wheel radius in meters (adjust based on your hardware)
        self.wheel_radius = 0.033  # Example radius, 10 cm. Modify as needed.

        # GUI Components
        self.create_widgets()

    def init_csv(self, filename, headers):
        """Initialize a CSV file with headers."""
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)

    def create_widgets(self):
        # Port selection
        tk.Label(self.root, text="COM Port:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.port_var = tk.StringVar()
        self.port_dropdown = ttk.Combobox(self.root, textvariable=self.port_var, width=30)
        self.port_dropdown['values'] = self.get_available_ports()
        self.port_dropdown.grid(row=0, column=1, padx=10, pady=5)

        # Baud rate entry
        tk.Label(self.root, text="Baud Rate:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.baud_entry = ttk.Entry(self.root, width=20)
        self.baud_entry.insert(0, "9600")  # Default baud rate
        self.baud_entry.grid(row=1, column=1, padx=10, pady=5)

        # Connect and Disconnect buttons
        connect_frame = tk.Frame(self.root)
        connect_frame.grid(row=2, column=0, columnspan=2, pady=10)

        self.connect_btn = ttk.Button(connect_frame, text="Connect", command=self.connect_bluetooth)
        self.connect_btn.grid(row=0, column=0, padx=5)

        self.disconnect_btn = ttk.Button(connect_frame, text="Disconnect", command=self.disconnect_bluetooth,
                                         state="disabled")
        self.disconnect_btn.grid(row=0, column=1, padx=5)

        # Logs display
        tk.Label(self.root, text="Logs:").grid(row=3, column=0, columnspan=2)
        self.logs_text = tk.Text(self.root, height=10, width=50, state="disabled")
        self.logs_text.grid(row=4, column=0, columnspan=2, padx=10, pady=5)

        # Command buttons
        button_frame = tk.Frame(self.root)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)

        # Direction control buttons (W, A, S, D)
        tk.Button(button_frame, text="W", command=lambda: self.send_command('w'), width=10).grid(row=0, column=1,
                                                                                                 padx=5)
        tk.Button(button_frame, text="A", command=lambda: self.send_command('a'), width=10).grid(row=1, column=0,
                                                                                                 padx=5)
        tk.Button(button_frame, text="S", command=lambda: self.send_command('s'), width=10).grid(row=1, column=1,
                                                                                                 padx=5)
        tk.Button(button_frame, text="D", command=lambda: self.send_command('d'), width=10).grid(row=1, column=2,
                                                                                                 padx=5)

        # Additional action buttons
        self.stop_btn = ttk.Button(button_frame, text="Stop", command=lambda: self.send_command('t'), width=15)
        self.stop_btn.grid(row=2, column=1, padx=5, pady=10)

        self.brake_btn = ttk.Button(button_frame, text="Brake Mode", command=lambda: self.send_command('e'), width=15)
        self.brake_btn.grid(row=2, column=0, padx=5)

        self.accel_btn = ttk.Button(button_frame, text="Full Speed Forward", command=lambda: self.send_command('q'),
                                    width=15)
        self.accel_btn.grid(row=2, column=2, padx=5)

        # Speed plotting area (fix plot_frame reference and layout)
        self.plot_frame = tk.Frame(self.root)
        self.plot_frame.grid(row=6, column=0, columnspan=2, pady=10)

        # Initialize the first plot
        self.fig, (self.ax, self.ax2) = plt.subplots(1, 2, figsize=(10, 4))

        # Plot 1: Speed Profile
        self.ax.set_title("Speed over Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Speed (m/s)")

        # Plot 2: ABS Speed
        self.ax2.set_title("ABS Speed (RPM)")
        self.ax2.set_xlabel("Time (ms)")
        self.ax2.set_ylabel("RPM")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack()

        # Set up the plot update interval
        self.update_plot_interval = 100  # milliseconds
        self.root.after(self.update_plot_interval, self.update_plot)

        # Plot control buttons
        plot_control_frame = tk.Frame(self.root)
        plot_control_frame.grid(row=7, column=0, columnspan=2, pady=5)

        self.resume_pause_btn = ttk.Button(plot_control_frame, text="Pause Plotting", command=self.toggle_plotting,
                                           width=15)
        self.resume_pause_btn.grid(row=0, column=0, padx=5)

        self.save_plot_btn = ttk.Button(plot_control_frame, text="Save Plot", command=self.save_plot, width=15)
        self.save_plot_btn.grid(row=0, column=1, padx=5)

        self.clear_plot_btn = ttk.Button(plot_control_frame, text="Clear Plot", command=self.clear_plot, width=15)
        self.clear_plot_btn.grid(row=0, column=2, padx=5)

        # Speed display section
        speed_frame = tk.LabelFrame(self.root, text="Speed Data", padx=10, pady=10)
        speed_frame.grid(row=8, column=0, columnspan=2, pady=10, padx=10, sticky="ew")

        tk.Label(speed_frame, text="RPM:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.rpm_label = tk.Label(speed_frame, text="N/A", width=15, anchor="w")
        self.rpm_label.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(speed_frame, text="Speed (m/s):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.speed_label = tk.Label(speed_frame, text="N/A", width=15, anchor="w")
        self.speed_label.grid(row=1, column=1, padx=5, pady=5)

        # Set up the plot update interval (e.g., every 100ms)
        self.update_plot_interval = 100  # milliseconds
        self.root.after(self.update_plot_interval, self.update_plot)

        # ABS indicator light
        self.abs_indicator = tk.Label(self.root, text="ABS OFF", bg="red", fg="white", width=15)
        self.abs_indicator.grid(row=9, column=0, columnspan=2, pady=5)

    def get_available_ports(self):
        """Fetch the list of available COM ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect_bluetooth(self):
        # Get port and baud rate
        port = self.port_var.get().strip()
        baud_rate = self.baud_entry.get().strip()

        if not port or not baud_rate:
            messagebox.showwarning("Input Error", "Please select a COM port and enter a baud rate.")
            return

        try:
            # Establish the connection
            self.bt_connection = serial.Serial(port, int(baud_rate), timeout=1)
            self.connected = True
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.log_message(f"Connected to {port} at {baud_rate} baud.")

            # File for speed data (real-time timestamp)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.speed_csv_filename = f"speed_profile_{timestamp}.csv"
            self.init_csv(self.speed_csv_filename, ["Time (s)", "Speed (m/s)"])

            # Start the read thread
            self.read_thread = threading.Thread(target=self.read_from_bluetooth, daemon=True)
            self.read_thread.start()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {e}")

    def read_from_bluetooth(self):
        while self.connected:
            try:
                if self.bt_connection.in_waiting > 0:
                    message = self.bt_connection.readline().decode('utf-8').strip()
                    if message:
                        if message.startswith("s:"):  # Handle speed data
                            self.process_speed_data(message)
                        elif message.startswith("l:"):  # Display logs starting with l:
                            self.log_message(message)
                        elif message.startswith("abs:"):
                            self.process_abs_data(message)
            except Exception as e:
                self.log_message(f"Error reading from HC-05: {e}")
                self.connected = False
                break

    def process_speed_data(self, message):
        """Process speed data and convert RPM to m/s."""
        try:
            rpm = float(message[2:].strip())
            self.latest_rpm = rpm
            self.latest_speed = self.convert_rpm_to_m_s(rpm)

            # Update the labels for RPM and speed
            self.rpm_label.config(text=f"{self.latest_rpm:.2f}")
            self.speed_label.config(text=f"{self.latest_speed:.2f}")

            # Append speed data to plot and CSV
            elapsed_time = int(time.time() - self.start_time)
            self.speed_data.append((elapsed_time, self.latest_speed))
            self.write_to_csv(self.speed_csv_filename, [elapsed_time, self.latest_speed])

            # Keep only the last 60 seconds of data for plotting
            self.speed_data = self.speed_data[-60:]
        except ValueError:
            self.log_message(f"Invalid speed data: {message}")

    def convert_rpm_to_m_s(self, rpm):
        """Convert RPM to m/s based on the wheel radius."""
        return rpm * (2 * math.pi * self.wheel_radius) / 60

    def process_abs_data(self, message):
        """Process ABS data (starting with 'abs:')."""
        try:
            rpm = float(message[4:].strip())  # Strip "abs:" prefix
            current_time = time.time()

            # Track last received time for ABS data
            self.abs_last_received_time = current_time

            timestamp_ms = int((current_time - self.start_time) * 1000)  # Time in ms
            timestamp_formatted = f"{timestamp_ms} ms"

            # Log data to ABS CSV file
            if self.abs_csv_filename is None:
                abs_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                self.abs_csv_filename = f"abs_speed_profile_{abs_timestamp}.csv"
                self.init_csv(self.abs_csv_filename, ["Time (ms)", "Speed (RPM)"])

            self.write_to_csv(self.abs_csv_filename, [timestamp_formatted, rpm])

            # Append ABS speed data to plot
            self.abs_speed_data.append((timestamp_ms, rpm))

            # Keep only the last 60 data points (600ms at 10ms intervals)
            self.abs_speed_data = self.abs_speed_data[-60:]

            if self.abs_last_received_time:
                # Check if 20ms have passed since the last ABS message
                if (time.time() - self.abs_last_received_time) > 0.02:
                    self.stop_abs_logging()

            # Check for consecutive 0 RPM
            if rpm == 0:
                self.abs_zeros_count += 1
                if self.abs_zeros_count >= 20:  # Stop after 20 consecutive zeros
                    self.stop_abs_logging()
            else:
                self.abs_zeros_count = 0

            # Turn on ABS indicator light
            self.toggle_abs_indicator(True)

        except ValueError:
            self.log_message(f"Invalid ABS data: {message}")

    def update_plot(self):
        """Update the plot with new data."""
        if self.is_plotting:
            # Update Speed Profile Plot
            self.ax.clear()
            self.ax.set_title("Speed over Time")
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Speed (m/s)")
            if self.speed_data:
                times, speeds = zip(*self.speed_data)
                self.ax.plot(times, speeds, label="Speed (m/s)")
                self.ax.legend()

            # Update ABS Speed Plot
            self.ax2.clear()
            self.ax2.set_title("ABS Speed (RPM)")
            self.ax2.set_xlabel("Time (ms)")
            self.ax2.set_ylabel("RPM")
            # self.ax2.set_xlim(0, 600)  # Always show 600ms on the x-axis
            if self.abs_speed_data:
                times, speeds = zip(*self.abs_speed_data)
                self.ax2.plot(times, speeds, label="ABS Speed (RPM)")
                self.ax2.legend()

        self.canvas.draw()
        self.root.after(self.update_plot_interval, self.update_plot)

    def stop_abs_logging(self):
        """Stop ABS data logging, reset counters, and clear data."""
        self.abs_csv_filename = None  # Reset ABS file
        self.abs_speed_data.clear()  # Clear plot data
        self.abs_zeros_count = 0  # Reset zero count
        self.toggle_abs_indicator(False)  # Turn off ABS indicator

    def toggle_plotting(self):
        """Toggle the plotting state."""
        self.is_plotting = not self.is_plotting
        self.resume_pause_btn.config(text="Resume Plotting" if not self.is_plotting else "Pause Plotting")

    def toggle_abs_indicator(self, is_on):
        """Toggle the ABS indicator light."""
        if is_on:
            self.abs_indicator.config(text="ABS ON", bg="green")
        else:
            self.abs_indicator.config(text="ABS OFF", bg="red")

    def save_plot(self):
        """Save the current plot to the local folder."""
        file_name = os.path.join(os.getcwd(), "speed_plot.png")
        self.fig.savefig(file_name)
        messagebox.showinfo("Plot Saved", f"Plot saved as {file_name}")

    def clear_plot(self):
        """Clear the plot and reset time."""
        self.speed_data.clear()
        self.start_time = time.time()  # Reset the start time
        self.ax.clear()
        self.ax.set_title("Speed over Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Speed (m/s)")
        self.canvas.draw()

    def send_command(self, command):
        """Send a command to the Bluetooth device."""
        if self.bt_connection and self.connected:
            try:
                self.bt_connection.write(command.encode('utf-8'))
                self.log_message(f"Sent: {command}")
            except Exception as e:
                self.log_message(f"Error sending command: {e}")

    def write_to_csv(self, filename, row):
        """Write a row of data to the specified CSV file."""
        with open(filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(row)

    def log_message(self, message):
        """Log a message to the logs window."""
        if message.startswith("l:"):
            message = message[2:]  # Strip "l:" prefix
        self.logs_text.config(state="normal")
        self.logs_text.insert("end", message + "\n")
        self.logs_text.config(state="disabled")
        self.logs_text.see("end")

    def disconnect_bluetooth(self):
        """Disconnect from the Bluetooth device."""
        if self.connected and self.bt_connection:
            self.connected = False
            self.bt_connection.close()
            self.log_message("Disconnected from HC-05.")
            self.connect_btn.config(state="normal")
            self.disconnect_btn.config(state="disabled")

    def close_connection(self):
        """Automatically disconnect on closing the app."""
        self.disconnect_bluetooth()
        self.root.destroy()


# Initialize the app
if __name__ == "__main__":
    root = tk.Tk()
    app = BluetoothApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_connection)  # Ensure the connection is closed on exit
    root.mainloop()
