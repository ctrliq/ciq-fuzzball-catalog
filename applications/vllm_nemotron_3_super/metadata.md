# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_nemotron_3_super"
name: "Nemotron 3 Super"
template: vllm
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- OpenAI API
- Nemotron
- ai
- model
---
Serves NVIDIA Nemotron 3 Super (MoE, 120B parameters / 12B active, BF16) from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16) validated.

- **Checkpoint**: `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16`
- **License**: nvidia-nemotron-open-model-license
- **Context preset**: 262144 tokens
- **GPU fit**: an 8-GPU 80GB+ node per replica

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Nemotron 3 Super"
fuzzball workflow catalog start "Nemotron 3 Super" --values Volume=my-models,MaxReplicas=4
fuzzball workflow catalog start "Nemotron 3 Super" --values Nodes=2,GpusPerNode=4,ExpertParallelism=auto
```

Set `Nodes` above 1 with `ExpertParallelism=auto` to serve each replica across
several nodes; see the `vllm` entry description for what a multi-node replica
needs.

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.


## Notes

- The preset flags include --trust-remote-code, which lets vLLM execute Python from the downloaded model repository at load time (this architecture requires it). Removing it means overriding ExtraArgs with the remaining defaults.
- The recipe sets --kv-cache-dtype fp8, which quantizes the KV cache; part of the validated configuration, but it does affect numerical accuracy.
