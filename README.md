# Fluidic Control

A hardware-agnostic control framework for automated fluidic and microfluidic systems.

The project provides a common software architecture for controlling fluid-handling hardware, running timed experimental protocols, simulating hardware for development and testing, and providing an operator GUI. The current implementation supports **New Era NE-500 syringe pumps** and simulated pumps, with the architecture designed to expand to pressure controllers, flow sensors, valves, imaging systems, and closed-loop control.

## Features

* Hardware-independent pump interface
* New Era NE-500 serial pump control
* Stateful simulated hardware for development without physical instruments
* Multi-pump control
* CSV/XLSX experimental protocol execution
* Named logical fluid channels
* Timed sequence execution with pause, resume, stop, and seek
* PyQt operator GUI
* GUI-independent sequence engine
* Automated tests using simulated hardware
* Architecture intended for additional actuators and sensors

## Architecture

The software separates **experimental logic** from **specific hardware implementations**.

```text
                    Experimental Protocol
                            |
                     Sequence Runner
                            |
                    Logical Channels
                     "oil", "sample",
                     "wash", etc.
                            |
                 Hardware Abstraction Layer
                     /              \
                    /                \
             Simulated             Physical
              Hardware              Hardware
                                      |
                                New Era Pumps
                                      |
                                    Serial
```

A protocol should describe **what the fluidic system should do**, rather than how a particular vendor's hardware performs the operation.

For example:

```text
oil = 500 µL/hr
sample = 100 µL/hr
```

Higher-level experimental logic therefore does not need to know the serial commands, pump addresses, or vendor-specific implementation used to produce those flows.

## Project Structure

```text
fluidic_control_hw/
├── python/
│   ├── core/
│   │   ├── pumps/
│   │   │   ├── fake_pump.py
│   │   │   └── new_era.py
│   │   ├── pump_interface.py
│   │   └── sequence_runner.py
│   │
│   ├── gui/
│   │
│   ├── config/
│   │
│   ├── templates/
│   │
│   └── tests/
│
├── cpp/
├── REQUIREMENTS.md
└── README.md
```

### Core

Contains the hardware interfaces, device implementations, and protocol execution logic.

The core control code is intentionally independent of the GUI so that the same control architecture can eventually be used from a desktop application, automated test system, command-line application, or higher-level instrument orchestrator.

### GUI

Provides the operator interface for manually controlling hardware and executing fluidic protocols.

### Tests

Hardware-independent tests use simulated devices so control and sequencing logic can be exercised without requiring physical pumps.

## Hardware Abstraction

Physical and simulated pumps implement a common pump interface.

```text
                  PumpInterface
                  /           \
                 /             \
          FakePump          NewEraPump
                              |
                         Serial network
                        /      |       \
                     Pump 0  Pump 1   Pump 2
```

`FakePump` provides a stateful simulation of pump behavior, allowing development and automated testing without connecting physical hardware.

`NewEraPump` communicates with one or more New Era syringe pumps over a serial connection.

This separation allows higher-level software to operate against either simulated or real hardware.

## Protocol Execution

Fluidic experiments can be described as sequences of timed steps.

For example:

| Step        | Duration |  oil | sample |
| ----------- | -------: | ---: | -----: |
| Prime       |     10 s | 1000 |      0 |
| Load sample |     30 s |  300 |    100 |
| Wash        |     20 s |  500 |      0 |

The `SequenceRunner` is independent of the GUI and is responsible for:

1. Loading and validating protocols
2. Applying channel setpoints
3. Tracking sequence timing
4. Moving between protocol steps
5. Handling pause, resume, stop, and seek operations
6. Reporting sequence state through callbacks

Protocols can therefore be tested against simulated hardware before being executed on a physical system.

## Simulation and Testing

Simulation is treated as part of the control architecture rather than as a separate application.

The same higher-level software can operate against:

```text
Protocol
   |
Sequence Runner
   |
   +------ FakePump
   |
   +------ NewEraPump
```

This enables automated testing of protocol behavior without physical hardware and provides a path toward more detailed simulation of sensors and fluidic dynamics.

Run the Python tests with:

```bash
cd python
pytest
```

## New Era Syringe Pump Control

The current physical hardware implementation supports New Era NE-500 OEM syringe pumps.

The driver handles operations including:

* pump discovery
* syringe diameter configuration
* infusion and withdrawal rates
* starting and stopping pumps
* priming
* multiple pumps on a serial network

Vendor-specific serial communication is contained within the New Era implementation rather than exposed to the sequence or GUI layers.

## Design Goals

The project is being developed around several principles:

**Hardware independence**

Experimental protocols should not depend on a specific hardware vendor.

**Separation of concerns**

Hardware communication, orchestration, protocol execution, and user interfaces should remain separate.

**Simulation-first testing**

Higher-level software should be testable without requiring an assembled instrument.

**Composable instrumentation**

Pumps, pressure controllers, sensors, valves, and imaging components should be capable of being assembled into larger fluidic systems.

**Progressive hardware integration**

Control logic should be testable first with simulated hardware and then exercised against physical devices with minimal changes to higher-level software.

## Roadmap

Planned extensions include:

* Generic logical actuator/channel abstraction
* Pressure-controller support
* Inline flow sensors
* Valve control
* Closed-loop flow and pressure regulation
* Configurable channel limits and units
* Improved hardware fault detection and recovery
* Behavioral simulation of fluidic components
* Camera/image-triggered protocol actions
* Additional hardware drivers
* Headless instrument operation

A future closed-loop system could use the same architecture to combine actuators and sensors:

```text
          Target Flow
              |
              v
          Controller
              |
              v
       Pressure / Pump
              |
              v
        Fluidic System
              |
              v
         Flow Sensor
              |
              +---------- feedback --------+
```

## Motivation

Automated laboratory instruments often combine hardware from multiple vendors while experimental protocols need to remain independent of those implementation details.

This project explores an architecture in which vendor-specific device drivers sit beneath reusable logical fluid channels and protocol orchestration. This makes it possible to develop and test experimental workflows against simulated hardware, replace physical components without rewriting protocol logic, and progressively build toward more complex closed-loop instrumentation.

## Status

This project is under active development.

The current implementation focuses on syringe-pump control, simulated hardware, protocol sequencing, and the operator GUI. Pressure control, sensing, closed-loop control, and additional instrumentation are planned extensions.
