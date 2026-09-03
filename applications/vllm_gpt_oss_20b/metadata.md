# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_gpt_oss_20b"
name: "GPT-OSS 20B"
template: vllm
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- OpenAI API
- gpt-oss
- ai
- model
---
Serves OpenAI's gpt-oss-20b (MoE, 21B parameters / 3.6B active, MXFP4) -- the entry-tier gpt-oss from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/openai/gpt-oss-20b) validated.

- **Checkpoint**: `openai/gpt-oss-20b`
- **License**: apache-2.0
- **Context preset**: 131072 tokens
- **GPU fit**: one 16GB+ GPU per replica; at 16GB, lower MaxContextSize so the KV cache fits beside the ~13GB weights

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress). Note that gpt-oss also loads the
OpenAI harmony token encoding (`o200k_base`) at startup, which vLLM fetches
from the internet on first run. For an air-gapped replica, stage that encoding
on the volume and point vLLM at it with
`ExtraEnv=TIKTOKEN_ENCODINGS_BASE=/data/<dir>`. Set `Volume` to a persistent
volume to keep the checkpoint across workflow restarts.

```
fuzzball workflow catalog start "GPT-OSS 20B"
fuzzball workflow catalog start "GPT-OSS 20B" --values Volume=my-models,MaxReplicas=8
fuzzball workflow catalog start "GPT-OSS 20B" --values Nodes=2,ExpertParallelism=auto
```

Set `Nodes` above 1 with `ExpertParallelism=auto` to serve each replica across
several nodes; see the `vllm` entry description for what a multi-node replica
needs.

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.
