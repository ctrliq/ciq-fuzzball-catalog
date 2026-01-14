# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "llm_client_server" # needs to be **unique** per application, changing results in a new application
name: "Local LLM chat"
category: "ML_AND_AI"
tags:
- LLM
- inference
---
This workflow starts an OpenAI-compatible REST API server implemented with vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) using a model downloaded from HuggingFace ([Hugging Face](https://huggingface.co/)) and provides a web-based chat interface. All processing is local.

See [Supported Models](https://docs.vllm.ai/en/stable/models/supported_models.html#supported-models) for a list of supported models.

The server will run until the workflow is cancelled.
