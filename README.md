🎛️ Blender DAW








A modular Digital Audio Workstation integrated directly into Blender.

📌 Overview

Blender DAW is an experimental addon that transforms Blender into a modular Digital Audio Workstation (DAW), enabling music production directly inside the 3D environment.

The goal is to unify audio production and visual workflows, creating a hybrid creative pipeline inside a single software ecosystem.

The project includes:

🔊 A custom-built audio engine (currently experimental)

🧩 Modular architecture

🎹 MIDI-based workflow

🔄 External audio processing integration

🏗️ Architecture
Blender DAW
│
├── Core Audio Engine (Experimental)
├── MIDI System (Piano Roll)
├── Mixer Module
├── Sampler Module
├── Audio Converter
│   └── AudioMax (External Plugin)
└── UI Integration (Splash Session + Panels)
🚀 Features
Module	Status
🎹 Piano Roll	🟡 In Development
🎚️ Control Mixer	🟡 Partial
🎛️ Sampler	🟡 Partial
🔄 Audio Converter	🟢 Functional (via AudioMax)
🔊 Custom Audio Engine	🔴 Experimental
🖥️ Dedicated Splash Screen Session	🟢 Active
🧩 Modular System	🟡 Expanding
🔌 External Dependency

The Audio Converter module relies on:

Audio Max for Blender 5.0
🔗 https://github.com/ItaloNicacioDev/audio_max_for_blender5.0

This plugin is responsible for auxiliary audio processing and optimization inside Blender.

⚠️ Beta Notice

This project is currently in active BETA development.

Some features may not function properly.

Certain modules may be incomplete or temporarily disabled.

The custom audio engine is still under testing.

Structural changes may occur between versions.

Use in production environments is not recommended at this stage.

🎯 Project Goals

Integrate music production into Blender

Develop a fully modular open-source DAW system

Enable advanced synchronization between audio and animation

Expand MIDI capabilities

Explore experimental VST integration

📦 Installation (Preview)

Download or clone the repository

Install it as a Blender addon

Install the AudioMax plugin

Enable both addons in
Edit → Preferences → Add-ons

🗺️ Roadmap

 Audio engine optimization

 Advanced MIDI implementation

 Multi-track export

 Experimental VST support

 Dedicated DAW-style workspace

 Performance improvements

🤝 Contributing

Contributions, feedback, and experimental ideas are welcome.

This project aims to push the boundaries of Blender as a multimedia production platform.
