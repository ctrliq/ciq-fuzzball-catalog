# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "nim_flux_webui_application"
name: "NVIDIA NIM Flux Image Generation with Open WebUI"
category: "ML_AND_AI"
tags:
- genAI
- image-generation
- nvidia-nim
- open-webui
---

Deploys an NVIDIA NIM image generation service (Flux family models) paired with an Open WebUI frontend for interactive, browser-based image generation.

The workflow runs three persistent services:

- **nim**: The NVIDIA NIM inference server, which serves the Flux model via an OpenAI-compatible HTTP API. CPU offloading is enabled for VAE, DiT layers, and text encoders to allow operation with limited GPU memory.
- **nim-stub**: A lightweight OpenAI-compatible adapter that bridges Open WebUI's chat and model-discovery APIs to the NIM image generation endpoint.
- **open-webui**: The Open WebUI interface, pre-configured for image generation via the stub. No login is required by default.

Requires an NGC API key secret for pulling the NIM container and authenticating inference requests. Model weights are cached in a persistent volume to avoid re-downloading on subsequent runs.

> **Prerequisites:** Before running this workflow you must accept the model EULA on Hugging Face (visit the model page and click "Agree and access repository"). A Hugging Face token with read access is also required and must be stored as a Fuzzball secret referenced by `HuggingFaceTokenSecret`.
