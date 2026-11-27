# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "ciq/utilities/virtual_desktop_application"
name: "Virtual Desktop (VDI)"
category: "UTILITIES"
featured: true
tags:
- desktop
- interactive
keyart: keyart.jpg
---
Virtual Desktop Interface (VDI) based on the Xfce desktop environment with GPU-accelerated 3D rendering through VirtualGL.

By default one GPU is allocated. Use `GPUs` to request more, or set it to 0 for a CPU-only
desktop without hardware-accelerated rendering (e.g. `--values GPUs=0`).

You can specify a data volume (`DataVolume`) to be mounted for data management. It will be mounted
at /data. In addition an optional home volume can be specified (`HomeVolume`) to serve as a
persistent home directory. Give each volume by the name of a persistent volume (e.g. `my-home`),
or `ephemeral` for a scratch volume discarded when the workflow ends.
