import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import math


class BluetoothApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bluetooth HC-05 Connection")

        # Serial connection placeholder
        self.bt_connection = None
        self.read_thread = None
        self.connected = False

        # Variables to hold speed data for plotting
        self.speed_data = []

        # Wheel radius in meters (adjust this based on your hardware)
        self.wheel_radius = 0.03  # Example radius, 10 cm. Modify as needed.

        # GUI Components
        self.create_widgets()

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

        # New action buttons
        self.stop_btn = ttk.Button(button_frame, text="Stop", command=lambda: self.send_command('t'), width=15)
        self.stop_btn.grid(row=2, column=1, padx=5, pady=10)

        self.brake_btn = ttk.Button(button_frame, text="Brake Mode", command=lambda: self.send_command('e'), width=15)
        self.brake_btn.grid(row=2, column=0, padx=5)

        self.accel_btn = ttk.Button(button_frame, text="Full Speed Forward", command=lambda: self.send_command('q'),
                                    width=15)
        self.accel_btn.grid(row=2, column=2, padx=5)

        # Speed plotting area
        self.plot_frame = tk.Frame(self.root)
        self.plot_frame.grid(row=6, column=0, columnspan=2, pady=10)

        # Initialize the plot
        self.fig, self.ax = plt.subplots()
        self.ax.set_title("Speed over Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Speed (m/s)")  # Updated to m/s
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack()

        # Set up the plot update interval (e.g., every 100ms)
        self.update_plot_interval = 100  # milliseconds
        self.root.after(self.update_plot_interval, self.update_plot)

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
            except Exception as e:
                self.log_message(f"Error reading from HC-05: {e}")
                self.connected = False
                break

    def process_speed_data(self, message):
        """Process speed data and convert RPM to m/s."""
        try:
            # Extract the RPM value from the message, e.g., s: 45
            rpm = float(message[2:].strip())
            speed_m_s = self.convert_rpm_to_m_s(rpm)
            self.speed_data.append(speed_m_s)

        except ValueError:
            self.log_message(f"Error processing speed data: {message}")

    def convert_rpm_to_m_s(self, rpm):
        """Convert RPM to m/s based on the wheel radius."""
        # Formula: Speed (m/s) = RPM * (2 * pi * radius) / 60
        return rpm * (2 * math.pi * self.wheel_radius) / 60

    def update_plot(self):
        """Update the plot continuously."""
        if self.speed_data:
            # Update the plot with new speed data
            self.ax.clear()
            self.ax.plot(self.speed_data, label="Speed", color='blue')
            self.ax.set_title("Speed over Time")
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Speed (m/s)")
            self.ax.legend()
            self.canvas.draw()

        # Call this method again after the defined interval
        self.root.after(self.update_plot_interval, self.update_plot)

    def send_command(self, command):
        try:
            self.bt_connection.write((command + '\n').encode('utf-8'))
            self.log_message(f"Sent: {repr(command)}")
        except Exception as e:
            messagebox.showerror("Send Error", f"Failed to send command: {e}")

    def log_message(self, message):
        self.logs_text.config(state="normal")
        self.logs_text.insert(tk.END, message + "\n")
        self.logs_text.see(tk.END)
        self.logs_text.config(state="disabled")

    def disconnect_bluetooth(self):
        """Manually disconnect from the Bluetooth device."""
        self.connected = False
        if self.bt_connection and self.bt_connection.is_open:
            self.bt_connection.close()
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.log_message("Disconnected from HC-05.")

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
