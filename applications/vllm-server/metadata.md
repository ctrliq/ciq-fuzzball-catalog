# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "vllm_inference_server" # needs to be **unique** per application, changing results in a new application
name: "vLLM inference server"
category: "ML_AND_AI"
tags:
- LLM
- inference
---
This workflow starts a vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) inference server using a model downloaded from HuggingFace ([Hugging Face](https://huggingface.co/))
and exposes an OpenAI API through a public server endpoint.

See [Supported Models](https://docs.vllm.ai/en/stable/models/supported_models.html#supported-models) for a list of supported models.

The server will run until the workflow is cancelled.
