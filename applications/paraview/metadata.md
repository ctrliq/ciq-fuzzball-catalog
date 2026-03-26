# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "paraview_application" # needs to be **unique** per application, changing results in a new application
name: "ParaView"
category: "VISUALIZATION"
featured: true
tags:
- desktop
- interactive
- gpu
keyart: keyart.jpg
---
ParaView is an open-source application for interactive scientific visualization of large datasets. It runs as a persistent service in a web-accessible Xfce desktop environment — no port-forwarding required. ParaView opens automatically when the desktop session starts.

Set `DataVolume` to a Fuzzball volume (e.g. `volume://user/persistent-4/username`) to mount your datasets at `/data`. An optional `HomeVolume` can be specified to persist ParaView settings, state files, and Python scripts across sessions (e.g. `volume://user/persistent-4/username`). Without a home volume an ephemeral home directory is used.

Set `GPUs` to `1` to allocate an NVIDIA GPU and enable hardware-accelerated rendering via VirtualGL. Without a GPU, ParaView uses Mesa software rendering, which is sufficient for smaller datasets but will be slower for large or complex scenes. If you need to restart
paraview use `launch-paraview.sh [PARAVIEW OPTIONS]`.
