# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/nim_flux_webui_application"
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

- **nim**: The NVIDIA NIM inference server, which serves the Flux model via an OpenAI-compatible HTTP API. By default, CPU offloading is enabled for text encoders; VAE and DiT layer offloading are available as optional settings to help operation with limited GPU memory.
- **nim-stub**: A lightweight OpenAI-compatible adapter that bridges Open WebUI's chat and model-discovery APIs to the NIM image generation endpoint.
- **open-webui**: The Open WebUI interface, pre-configured for image generation via the stub. No login is required by default.

Requires an NGC API key secret for pulling the NIM container and authenticating inference requests. Model weights are cached in a persistent volume to avoid re-downloading on subsequent runs.

**Container images.** `NimImageUri`, `OpenWebUIImage` and `StubImage` each take a full image
reference, so a site without access to public registries can point all three at its own
copies. `OpenWebUIImage` and `StubImage` must have an explicit tag or digest and a lowercase
repository path. The NIM image is pulled with `NgcOciSecret`. For a mirror of the other two
that requires credentials, set `ImageSecret` to a Fuzzball image secret; it goes with both
pulls, so each must then name its registry host (`docker://docker.io/<namespace>/<name>:<tag>`
for Docker Hub), both the same one, and that host must be one of the secret's trusted
domains. If `ImageSecret` is the same secret as `NgcOciSecret`, `NimImageUri` must name that
host too. `OpenWebUIImage` replaces the earlier
`OpenWebUIVersion` value: saved overrides of that value no longer apply.

> **Prerequisites:** Before running this workflow you must accept the model EULA on Hugging Face (visit the model page and click "Agree and access repository"). A Hugging Face token with read access is also required and must be stored as a Fuzzball secret referenced by `HuggingFaceTokenSecret`.
