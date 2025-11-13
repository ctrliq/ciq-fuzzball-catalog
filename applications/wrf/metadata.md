# Copyright 2025 CIQ, Inc. All rights reserved

---
id: "wrf_application" # needs to be **unique** per application, changing results in a new application
name: "WRF + WPS"
category: "WEATHER_AND_CLIMATE"
featured: true
tags:
- weather
- meteorology
- NCAR
- MPI
---

WRF (Weather Research and Forecasting) – A mesoscale numerical weather prediction system. This workflow runs the public Hurricane Matthew case end-to-end: retrieves high‑resolution static geography data, downloads meteorological GRIB inputs and namelist files, performs WPS preprocessing (geogrid, ungrib, metgrid), executes real.exe for domain initialization, runs a multi-node MPI wrf.exe forecast, and optionally archives and exports wrfout* model output files as a compressed tarball. An optional animation step converts model outputs into an MP4 video for quick visualization.
