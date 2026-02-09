# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "open-webui" # needs to be **unique** per application, changing results in a new application
name: "Open WebUI"
category: "ML_AND_AI"
tags:
- LLM
- RAG
- Ollama
- chat
- genAI
---
Modern GPU-accelerated AI platform combining Open WebUI and Ollama for document chat and retrieval-augmented generation (RAG).

This workflow provides a complete AI assistant stack with:
- **Open WebUI**: User-friendly chat interface with document upload and RAG capabilities
- **Ollama**: Local LLM inference engine with model management
- **GPU Acceleration**: Optimized for NVIDIA GPUs

## Language Model Selection

The workflow uses Ollama for LLM inference. You can configure which model to use via the **LLMModel** parameter.

**Recommendations based on GPU memory:**
- **llama3.1:8b-instruct-q4_K_M** (default) - Standard GPUs with <40GiB memory
- **mixtral:8x7b-instruct-v0.1-q4_K_M** - Medium GPUs with 40-70GiB memory
- **llama3.1:70b-instruct-q4_K_M** - Large GPUs with >70GiB memory

You can also specify any other Ollama-compatible model (e.g., llama2, codellama, mistral). See [Ollama Library](https://ollama.com/library) for available models.

## Access Scope

The Open WebUI service endpoint is accessible by the submitting user by default;
but it can be changed to be accessible by anyone in the same group or
organization.

## Container Versions

The workflow allows you to specify container versions for both Ollama and Open WebUI:
- **OllamaVersion** (default: 0.15.0) - Ollama container version for LLM inference
- **OpenWebUIVersion** (default: v0.7.2) - Open WebUI interface version

You can override these to use newer versions or pin to specific releases for reproducibility.

## Stack Verification

The workflow includes an optional verification step to test the complete stack:
- **TestPrompt** (default: "Say Hello, world!") - Prompt used to verify Ollama and the LLM are working correctly
- Leave empty to skip the verification job entirely for faster deployment
- Customize the prompt to test specific model capabilities or response formats

When enabled, the verify-stack job tests API connectivity, model availability, and generates a sample response before providing access URLs.

## Features

- **Document Upload**: Support for PDFs, DOCX, TXT, MD, CSV, and more
- **RAG (Retrieval-Augmented Generation)**: Chat with your documents using semantic search
- **Persistent Storage**: Models and conversation history persist across sessions
- **Web Interface**: Access via browser with automatic endpoint configuration
- **Model Caching**: Models stay loaded in GPU for 24 hours for fast inference
- **Embedding Models**: Automatic download of nomic-embed-text for RAG

## Getting Started

1. Launch the workflow with your chosen LLM model
2. Wait for initial model download
3. Navigate to the Open WebUI endpoint provided
4. Upload documents and start chatting

The services will persist until the workflow is cancelled.
