# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "llm_client_server" # needs to be **unique** per application, changing results in a new application
name: "LLM client and server"
category: "ML_AND_AI"
tags:
- LLM
- inference
---
This workflow starts an OpenAI-compatible REST API server implemented with vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) using a model downloaded from HuggingFace ([Hugging Face](https://huggingface.co/)) in one job, and then runs a series of queries against the server from a second job in the same workflow.

See [Supported Models](https://docs.vllm.ai/en/stable/models/supported_models.html#supported-models) for a list of supported models.

Once queries are done, the server is shut down.
