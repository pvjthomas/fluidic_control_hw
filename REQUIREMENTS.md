# Microfluidics Instrument Control System — Project Requirements

## 1. Project Overview

This project is a fork of [ClarkLabUCB/NewEraPumps_Python3](https://github.com/ClarkLabUCB/NewEraPumps_Python3), which itself descends from the original [AbateLab/Pump-Control-Program](https://github.com/AbateLab/Pump-Control-Program). The goal is to extend the codebase into a well-architected, multi-language, hardware-agnostic instrument control platform for microfluidics laboratory use, supporting syringe pumps (New Era and third-party), pressure controllers (single and multi-channel), inline flow sensors, and camera integration.

---

## 2. Goals

- Maintain and improve the existing Python 3 / PyQt5 pump control GUI
- Introduce a hardware abstraction layer enabling fake/simulated instruments for development and testing without physical hardware
- Support syringe pumps from New Era and other manufacturers through a generic pump interface
- Support pressure controllers (single-channel and multi-channel) as a first-class instrument type alongside pumps
- Support optional inline flow sensors per fluid line, with both display and closed-loop feedback capability
- Add camera integration for live monitoring, image-triggered pump control, and timestamped image capture
- Produce a parallel C++ implementation of the pump control library
- Support multiple New Era pump models, not just the NE-500
- Support all major platforms: Windows, macOS, and Linux (including Raspberry Pi)
- Maintain a single repository with clearly separated language subdirectories

---

## 3. Functional Requirements

### 3.1 Pump Control (Core)

| ID | Requirement |
|----|-------------|
| PC-01 | The system shall support running and stopping all connected pumps simultaneously, and a timed auto-stop mode (run all pumps, stop after elapsed time) |
| PC-02 | The system shall support stopping individual pumps by pump ID |
| PC-03 | The system shall support setting priming at a configurable fast rate and flow rate per individual pump in µL/hr, and updating flow rates while running |
| PC-04 | The system shall support setting and reading syringe diameter per pump, but updating syringe parameters only possible when pumps are stopped.
| PC-05 | The system shall support infuse (forward) and withdraw (reverse) directions |
| PC-06 | The system shall support auto-discovery of connected pumps on a serial network |
| PC-07 | Flow rates above 5000 µL/hr shall be automatically converted to mL/hr for pump command formatting |

### 3.2 Hardware Support

| ID | Requirement |
|----|-------------|
| HW-01 | The system shall support New Era NE-500 pumps (baseline, inherited from ClarkLab) |
| HW-02 | The system shall support additional New Era pump models including NE-1000, NE-1010, NE-1600, and NE-4000 |
| HW-03 | Pump model differences (command set variations, max rate limits, syringe size ranges) shall be encapsulated per-model |
| HW-04 | The COM/serial port shall be configurable at runtime via the GUI or a config file, not hardcoded |
| HW-05 | The system shall support up to 10 pumps tethered in a serial network (pump IDs 0–9) |
| HW-06 | Baud rate shall be configurable (default: 19200) |
| HW-07 | The system shall support Harvard Apparatus syringe pumps (Pump 11 Elite, PHD Ultra, PHD 2000 series) via plain ASCII serial commands over USB/RS-232 |
| HW-08 | Adding further third-party pump brands shall require only implementing `PumpInterface`; no changes to the GUI or higher-level logic shall be needed |
| HW-09 | The system shall support the **Elveflow OB1** (MK3+, MK4) pressure controller via the Elveflow SDK (Windows DLL / NI-VISA); the OB1 exposes up to 4 independently configurable pressure channels |
| HW-10 | The system shall support the **Fluigent MFCS** pressure controller family via the Fluigent `fgt-SDK`, which provides native shared libraries for Windows, macOS, and Linux |
| HW-11 | The system shall support both single-channel and multi-channel pressure controller models under the same `PressureControllerInterface` |
| HW-12 | Pressure setpoints and readbacks shall be expressed in mbar; driver implementations shall handle any unit conversion required by specific hardware |
| HW-13 | The system shall support **Sensirion SLF3x** flow sensors (SLF3C-1300F, SLF3S-1300F, SLF3S-4000B, SLF3S-0600F) via the SCC1-USB cable, which appears as a virtual COM port and is accessed through Sensirion's `sensirion-uart-scc1` Python driver |
| HW-14 | Each fluid line in the system shall optionally include an inline flow sensor; the sensor is not required for the system to function |

### 3.3 Hardware Abstraction Layer

| ID | Requirement |
|----|-------------|
| HAL-01 | A `PumpInterface` abstract base class shall define the contract for all syringe pump operations |
| HAL-02 | A `RealPump` class shall implement `PumpInterface` using actual serial communication |
| HAL-03 | A `FakePump` class shall implement `PumpInterface` entirely in memory, with no hardware dependency |
| HAL-04 | `FakePump` shall log all commands it would send to a console or file |
| HAL-05 | `FakePump` shall simulate realistic pump state (rates, direction, running/stopped) |
| HAL-06 | `FakePump` shall be selectable at launch via a CLI flag (`--fake`) or config setting |
| HAL-07 | The GUI and all higher-level logic shall depend only on `PumpInterface`, never on a concrete implementation |
| HAL-08 | A `PressureControllerInterface` abstract base class shall define the contract for pressure controller operations: `set_pressure(channel, mbar)`, `get_pressure(channel)`, `stop(channel)`, `stop_all()` |
| HAL-09 | A `FakePressureController` class shall implement `PressureControllerInterface` in memory, simulating channel state |
| HAL-10 | A `FlowSensorInterface` abstract base class shall define the contract for flow sensor operations: `get_flow_rate()`, `get_units()`, `reset_volume()` |
| HAL-11 | A `FakeFlowSensor` class shall implement `FlowSensorInterface`, returning configurable simulated values |
| HAL-12 | Flow sensors shall be associated with a specific fluid line at configuration time; a line with no sensor configured shall behave identically to one that has a sensor, except sensor-specific fields will show "N/A" |
| HAL-13 | The same abstraction pattern shall be applied to cameras (see Section 3.5) |

### 3.4 Graphical User Interface

| ID | Requirement |
|----|-------------|
| GUI-01 | The GUI shall be implemented in PyQt5 |
| GUI-02 | Each connected syringe pump shall be displayed as a row with: pump ID, syringe size selector, content label, flow rate input, current flow rate display, and Prime button |
| GUI-03 | Each pressure controller shall be displayed with: device label, per-channel pressure setpoint inputs, current pressure readback per channel, and a Stop All button for that device |
| GUI-04 | Each fluid line with a flow sensor shall display the live measured flow rate and cumulative volume alongside the pump or pressure controller row for that line; lines without a sensor shall show "N/A" in those fields |
| GUI-05 | The GUI shall display a status bar showing overall running vs. stopped state |
| GUI-06 | The GUI shall display a command bar showing the last issued command |
| GUI-07 | Run/Update and Stop buttons shall appear at the top of the GUI |
| GUI-08 | Spacebar shall trigger a Stop All shortcut (all pumps and all pressure controllers) |
| GUI-09 | The GUI shall support a timer mode: a configurable countdown after which all pumps and pressure controllers stop |
| GUI-10 | The COM port and pump count shall be configurable from the GUI or a startup dialog, not hardcoded in source |
| GUI-11 | The GUI shall indicate clearly when running in fake/simulation mode |
| GUI-12 | Instrument panels (pumps, pressure controllers, flow sensors, camera) shall be independently collapsible so the GUI scales to the instruments actually in use |
| GUI-13 | The front panel shall include a **Sequence** panel with the following controls: Load File, current step name and index (e.g. "Step 3 of 12"), step duration countdown, Previous Step, Next Step, Rewind X seconds, Forward X seconds, and an editable field to set X (default: 10 s) |
| GUI-14 | When a sequence is loaded and running, the current step's target values shall be reflected in the instrument rows (flow rates, pressures) as read-only fields; manual override shall be possible but shall prompt the user that it will break sequence synchronisation |
| GUI-15 | The sequence panel shall display a progress bar showing elapsed time within the current step and total sequence elapsed time |

### 3.5 Sequence / Protocol Engine

The sequence engine treats every controllable output — whether a syringe pump line or a pressure controller channel — as a **channel** identified by a unique string name (e.g. `oil`, `buffer`, `pressure_1`). Channel names are declared in the runtime configuration and map to a specific `PumpInterface` or `PressureControllerInterface` instance. The protocol file refers only to channel names, not to instrument types, keeping the spreadsheet human-readable and hardware-agnostic.

| ID | Requirement |
|----|-------------|
| SEQ-01 | The system shall support loading a protocol file describing a named sequence of steps, where each step sets target values for one or more channels |
| SEQ-02 | Supported file formats shall be CSV (`.csv`) and Excel (`.xlsx`); both shall produce identical behaviour |
| SEQ-03 | Each row in the protocol file represents one step; required columns are `step_name` (string) and `duration_s` (float, seconds); all other columns are channel setpoint columns |
| SEQ-04 | Each channel setpoint column shall be named after the channel (e.g. `oil`, `buffer`, `pressure_1`); the unit of the value is determined by the channel type: µL/hr for pump channels, mbar for pressure channels |
| SEQ-05 | Empty or blank cells in a channel column shall be interpreted as "no change" — the channel continues at its current setpoint for that step |
| SEQ-06 | The sequence engine shall execute steps automatically in order: at the start of each step all non-empty channel setpoints are applied simultaneously, then the engine waits for `duration_s` before advancing to the next step |
| SEQ-07 | The operator shall be able to jump to the next step at any time using a **Next Step** button; the remaining duration of the current step is discarded and the next step's setpoints are applied immediately |
| SEQ-08 | The operator shall be able to jump to the previous step at any time using a **Previous Step** button; the previous step's setpoints are re-applied and its timer restarts from zero |
| SEQ-09 | The operator shall be able to seek forward by X seconds using a **Fwd X s** button; if the seek would exceed the remaining step duration the engine advances to the next step (applying that step's setpoints) and continues counting from there |
| SEQ-10 | The operator shall be able to seek backward by X seconds using a **Back X s** button; if X exceeds the elapsed time within the current step the timer clamps to zero (beginning of the current step) without re-applying setpoints |
| SEQ-11 | The seek increment X shall be editable from the front panel at any time; the field shall accept positive numeric values in seconds; default shall be 10 s |
| SEQ-12 | The sequence shall support **Pause** and **Resume**; while paused the step timer freezes and all channel setpoints are held; the operator may still use Next/Prev/Fwd/Back buttons while paused |
| SEQ-13 | When the final step's duration elapses the sequence shall end and all channels shall be commanded to their zero/stop state unless a special `end_action` column is present in the file specifying an alternative (e.g. `hold`) |
| SEQ-14 | The sequence engine shall emit a timestamped log entry for every event: step start, step end, Next, Previous, Fwd X, Back X, Pause, Resume, and sequence end |
| SEQ-15 | The system shall validate the protocol file on load and report all errors before execution begins; errors include: unrecognised channel names, non-numeric `duration_s`, negative durations, and setpoint values outside the channel's configured min/max range |
| SEQ-16 | A `SequenceRunner` class shall implement the sequence engine independently of the GUI so it can be driven from scripts or automated tests |
| SEQ-17 | `SequenceRunner` shall accept a dictionary mapping channel names to `PumpInterface` or `PressureControllerInterface` instances; it shall work identically with real and fake instruments |
| SEQ-18 | Template files (`protocol_template.csv` and `protocol_template.xlsx`) shall be included in the repository with realistic example channel names, step names, durations, and setpoints, and inline comments explaining each column |

### 3.6 Flow Sensors

| ID | Requirement |
|----|-------------|
| FS-01 | The system shall support reading instantaneous flow rate from an inline flow sensor on any configured fluid line |
| FS-02 | The system shall support reading cumulative dispensed volume from a flow sensor |
| FS-03 | The system shall support resetting the cumulative volume counter on a flow sensor |
| FS-04 | Flow sensor presence per line shall be declared in the runtime configuration file; absence of a sensor on a line shall not cause errors |
| FS-05 | Flow sensor readings shall be polled at a configurable interval (default: 100 ms) |
| FS-06 | The system shall support closed-loop control: if measured flow rate deviates from setpoint by more than a configurable threshold, the system shall adjust the pump rate or pressure setpoint to compensate |
| FS-07 | Closed-loop control shall be independently enable/disable-able per line at runtime |
| FS-08 | Closed-loop control parameters (tolerance, correction gain, max correction step) shall be configurable per line |
| FS-09 | A `FakeFlowSensor` shall accept a configurable noise level and drift rate to enable realistic closed-loop testing without hardware |

### 3.7 Pressure Controllers

| ID | Requirement |
|----|-------------|
| PRC-01 | The system shall support setting a target pressure on any channel of a pressure controller |
| PRC-02 | The system shall support reading back the actual pressure on any channel |
| PRC-03 | The system shall support stopping (zeroing) pressure on an individual channel |
| PRC-04 | The system shall support stopping all channels of a pressure controller simultaneously |
| PRC-05 | A single `PressureControllerInterface` instance may represent a device with one or more channels; the number of channels shall be reported by the driver at connection time |
| PRC-06 | Multiple independent pressure controller devices may be connected simultaneously, each managed as a separate interface instance |
| PRC-07 | Pressure setpoints and readbacks shall be in mbar; driver implementations shall handle any unit conversion required by specific hardware |
| PRC-08 | The system shall support a timed auto-stop mode for pressure controllers (matching PC-10 for pumps) |
| PRC-09 | A `FakePressureController` shall simulate per-channel pressure state with configurable ramp-up lag to allow realistic GUI testing |

### 3.8 Camera Integration

| ID | Requirement |
|----|-------------|
| CAM-01 | A `CameraInterface` abstract base class shall define the contract for all camera operations (`start`, `stop`, `get_frame`) |
| CAM-02 | An `OpenCVCamera` class shall implement `CameraInterface` using OpenCV (`cv2`) |
| CAM-03 | A `FakeCamera` class shall implement `CameraInterface`, returning synthetic or static test images |
| CAM-04 | The GUI shall include a camera panel displaying a live feed updated at approximately 30 fps using a `QTimer` |
| CAM-05 | The system shall support saving image frames to disk, with filenames timestamped and annotated with current instrument state (pump rates, pressure setpoints, flow sensor readings, running/stopped) |
| CAM-06 | The system shall support image-triggered pump or pressure control: when a new image file appears in a watched directory, a configurable instrument action is triggered |
| CAM-07 | Image-triggered action parameters and watched directory shall be configurable at runtime |
| CAM-08 | The camera panel shall be optional — the application shall run normally if no camera is connected or configured |

---

## 4. Non-Functional Requirements

### 4.1 Platform Support

| ID | Requirement |
|----|-------------|
| PLT-01 | The Python implementation shall run on Windows 10/11, macOS 12+, and Linux (Ubuntu 20.04+) |
| PLT-02 | The Python implementation shall run on Raspberry Pi (Raspberry Pi OS, 64-bit) |
| PLT-03 | The C++ implementation shall compile on Windows (MSVC / MinGW), macOS (clang), and Linux (gcc) |
| PLT-04 | No paths, COM port names, or system-specific assumptions shall be hardcoded in source |

### 4.2 Language and Dependencies

| ID | Requirement |
|----|-------------|
| DEP-01 | Python implementation shall target Python 3.9 or later |
| DEP-02 | Python dependencies shall be declared in `requirements.txt` |
| DEP-03 | Python GUI shall use PyQt5 |
| DEP-04 | New Era and Harvard Apparatus serial communication shall use `pyserial` |
| DEP-05 | Camera integration shall use `opencv-python` |
| DEP-06 | Sensirion SLF3x flow sensor integration shall use Sensirion's `sensirion-uart-scc1` Python package |
| DEP-07 | Elveflow OB1 integration shall use the Elveflow SDK (DLL + Python bindings, distributed separately by Elveflow); the driver wrapper shall gracefully fail to import on systems where the SDK is not installed, and the OB1 instrument type shall be unavailable rather than crashing |
| DEP-08 | Fluigent MFCS integration shall use the Fluigent `fgt-SDK` Python package (`fluigent-sdk` on PyPI), which supports Windows, macOS, and Linux natively |
| DEP-09 | Harvard Apparatus integration shall reference the `pumpy3` open-source library as a reference implementation; the project shall wrap it behind `PumpInterface` rather than using it directly |
| DEP-10 | Protocol file loading shall use `pandas` for CSV parsing and `openpyxl` as the Excel engine; both shall be declared in `requirements.txt` |
| DEP-11 | C++ serial communication shall use `boost::asio` or platform `termios`/Win32, with clear compile-time selection |
| DEP-12 | C++ GUI (if implemented) shall use Qt5 or Qt6 |
| DEP-13 | C++ build system shall use CMake |

### 4.3 Code Quality

| ID | Requirement |
|----|-------------|
| QA-01 | All Python code shall pass `flake8` linting with no errors |
| QA-02 | All Python code shall include type hints (PEP 484) on public functions |
| QA-03 | All C++ code shall compile without warnings at `-Wall -Wextra` |
| QA-04 | Dead code and commented-out blocks inherited from upstream shall be removed |
| QA-05 | The codebase shall include a `tests/` directory with tests that run entirely using fake instruments (`FakePump`, `FakePressureController`, `FakeFlowSensor`, `FakeCamera`) — no hardware required |

### 4.4 Repository Structure

| ID | Requirement |
|----|-------------|
| REPO-01 | The repository shall use a single-repo, multi-language layout |
| REPO-02 | Python code shall live under `python/` |
| REPO-03 | C++ code shall live under `cpp/` |
| REPO-04 | Shared documentation shall live at the root level |
| REPO-05 | A `README.md` at the root shall describe both implementations and how to get started |
| REPO-06 | A `CONTRIBUTING.md` shall describe the branch strategy and how to add new pump models |

---

## 5. Repository Layout (Target)

```
microfluidics-control/
├── README.md
├── REQUIREMENTS.md
├── CONTRIBUTING.md
├── python/
│   ├── requirements.txt
│   ├── core/
│   │   ├── pump_interface.py                  # Abstract pump base class
│   │   ├── pumps/
│   │   │   ├── new_era.py                     # New Era driver (NE-500, NE-1000, etc.)
│   │   │   ├── harvard_apparatus.py           # Harvard Apparatus driver (Pump 11, PHD Ultra)
│   │   │   └── fake_pump.py                   # Fake/simulator
│   │   ├── pressure_controller_interface.py   # Abstract pressure controller base class
│   │   ├── pressure_controllers/
│   │   │   ├── elveflow_ob1.py                # Elveflow OB1 driver (wraps Elveflow SDK DLL)
│   │   │   ├── fluigent_mfcs.py               # Fluigent MFCS driver (wraps fgt-SDK)
│   │   │   └── fake_pressure_controller.py    # Fake/simulator
│   │   ├── flow_sensor_interface.py           # Abstract flow sensor base class
│   │   ├── flow_sensors/
│   │   │   ├── sensirion_slf3x.py             # Sensirion SLF3x driver (sensirion-uart-scc1)
│   │   │   └── fake_flow_sensor.py            # Fake/simulator
│   │   ├── camera_interface.py                # Abstract camera base class
│   │   ├── cameras/
│   │   │   ├── opencv_camera.py               # Real OpenCV camera
│   │   │   └── fake_camera.py                 # Fake camera
│   │   └── sequence_runner.py                 # Protocol/sequence engine (GUI-independent)
│   ├── gui/
│   │   └── main_window.py                     # PyQt5 GUI
│   ├── config/
│   │   └── default_config.yaml                # Runtime configuration
│   ├── templates/
│   │   ├── protocol_template.csv              # Example sequence file (CSV)
│   │   └── protocol_template.xlsx             # Example sequence file (Excel)
│   └── tests/
│       ├── test_fake_instruments.py
│       └── test_sequence_runner.py
└── cpp/
    ├── CMakeLists.txt
    ├── include/
    │   ├── pump_interface.hpp
    │   ├── new_era.hpp
    │   ├── pressure_controller_interface.hpp
    │   └── flow_sensor_interface.hpp
    ├── src/
    │   ├── new_era.cpp
    │   └── main.cpp
    └── tests/
        └── test_fake_instruments.cpp
```

---

## 6. Out of Scope (v1)

- Additional third-party pump brands beyond New Era and Harvard Apparatus
- Additional pressure controller brands beyond Elveflow OB1 and Fluigent MFCS
- Additional flow sensor brands beyond Sensirion SLF3x
- Sequence looping / repeat-N-times (linear single-pass only in v1)
- Ramp interpolation between step setpoints (step changes only; ramps are v2)
- Web-based GUI or remote control over network
- Data logging to database (flat file / CSV logging is in scope)
- Automated flow calibration routines
- Full PID closed-loop control (simple proportional correction per FS-06 to FS-08 is in scope)
- Python bindings wrapping the C++ library (possible future direction)

---

## 7. SDK and External Dependency Notes

| Instrument | SDK / Library | License | Platform |
|---|---|---|---|
| New Era pumps | `pyserial` (direct ASCII serial) | MIT | All |
| Harvard Apparatus pumps | `pyserial` + `pumpy3` reference | MIT | All |
| Elveflow OB1 | Elveflow SDK DLL + Python bindings (proprietary, distributed by Elveflow on purchase) | Proprietary | Windows primary; UART mode for Linux/Mac |
| Fluigent MFCS | `fluigent-sdk` (`fgt-SDK` on GitHub) | Open source | Windows, macOS, Linux |
| Sensirion SLF3x | `sensirion-uart-scc1` (PyPI) | BSD | All (via SCC1-USB virtual COM port) |
| Camera | `opencv-python` | Apache 2.0 | All |

**Important notes:**
- The Elveflow OB1 driver requires the Elveflow ESI software to be installed and the SDK DLL to be present on the system. The driver module shall detect this at import time and raise a clear `ImportError` with installation instructions if the SDK is not found, rather than crashing the whole application.
- The Fluigent `fgt-SDK` is the recommended path for cross-platform use; it covers the MFCS, LineUP, and FRP families through a single unified API.
- The Sensirion SCC1-USB cable installs as a virtual COM port (FTDI-based); the `sensirion-uart-scc1` package handles the SHDLC protocol internally.

---

## 8. Inherited Baseline (ClarkLabUCB)

The following capabilities are inherited from the ClarkLabUCB fork and must be preserved and not regressed:

- Python 3 compatible serial communication (`pyserial`, bytes encoding)
- PyQt5 GUI with per-pump syringe size, label, flow rate, and prime controls
- Infuse/withdraw direction control via `INF`/`WDR` commands
- `set_pump_number` utility script
- Support for 1 mL, 3 mL, 5 mL, and 10 mL Becton Dickinson syringe sizes

---

## 9. Revision History

| Version | Date | Notes |
|---------|------|-------|
| 0.1 | 2026-04-14 | Initial requirements, based on fork of ClarkLabUCB/NewEraPumps_Python3 |
| 0.2 | 2026-04-14 | Added flow sensor, pressure controller, and generic pump interface requirements; expanded GUI and HAL sections; updated repo layout |
| 0.3 | 2026-04-14 | Named specific hardware targets: Harvard Apparatus pumps, Elveflow OB1, Fluigent MFCS, Sensirion SLF3x; added SDK dependency notes and platform caveats per brand |
| 0.4 | 2026-04-14 | Added sequence/protocol engine (SEQ-01 to SEQ-18): CSV/XLSX upload, channel abstraction (pumps and pressure controller channels unified by name), auto-advance with manual override buttons (Next, Prev, Fwd X, Back X), editable seek increment, pause/resume, validation, GUI sequence panel, headless `SequenceRunner` class, template files |
