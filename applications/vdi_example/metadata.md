# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "virtual_desktop_application" # needs to be **unique** per application, changing results in a new application
name: "Virtual Desktop (VDI)"
category: "UTILITIES"
featured: true
tags:
- desktop
- interactive
keyart: keyart.jpg
---
Virtual Desktop Interface (VDI) based on the Xfce desktop environment.

You can specify a data volume (`DataVolume`) to be mounted for data management. It will be mounted
at /data. In addition an optional home volume can be specified (`HomeVolume`) to serve as a
persistent home directory (e.g. `volume://user/persistent-4/username`).
