# Potentiostat Control Suite

**Potentiostat Control Suite** is a Python-based desktop application designed to interface with laboratory potentiostats, including legacy models such as the **EG&G 273A**.  
The app provides a modern and intuitive UI for experiment setup, device communication, and data management.

---

## 🔹 Key Features

- **Real-time device status** using PyVISA  
  - Red = No device detected  
  - Blue = Device detected but not connected  
  - Green = Device connected  

- **Automatic folder structure** for organized experiment data**


- Configuration menu for:
- User selection and creation
- Project selection and creation
- Experiment naming
- Device selection and connection

- Secure instrument interaction
- Prevent disconnect attempts when no device is connected
- Warning dialog before disconnecting an active device

- Loading screen that checks:
- PyVISA import success
- Matplotlib import success
- Existence of `Data/` and `Methods/` directories

- Clean tabbed UI for:
- Configuration
- Methods
- New Method creation

---

## 🛠 Built With

- Python
- Tkinter / CustomTkinter (GUI)
- PyVISA (Instrument communication)
- Matplotlib (Plotting)
- CSV (Data logging)

---

## 🎯 Project Goal

Provide open-source, flexible, and extendable control software for electrochemical experiments, enabling collaboration, usability, and reproducible results in laboratory environments.

---

### ✅ Status

🚧 In active development — Contributions welcome!

---

## 📌 Future Roadmap

- ✅ UI Foundation
- ⏳ Device communication core
- ⏳ Method execution engine
- ⏳ Real-time visualization
- ⏳ Export to PDF reports

---

## 📜 License

MIT License

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to modify.

---

