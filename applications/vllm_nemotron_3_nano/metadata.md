# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_nemotron_3_nano"
name: "Nemotron 3 Nano"
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
Serves NVIDIA Nemotron 3 Nano (MoE, 30B parameters / 3B active, BF16) from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) validated.

- **Checkpoint**: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`
- **License**: nvidia-nemotron-open-model-license
- **Context preset**: 262144 tokens
- **GPU fit**: one 80GB+ GPU per replica

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Nemotron 3 Nano"
fuzzball workflow catalog start "Nemotron 3 Nano" --values Volume=my-models,MaxReplicas=8
fuzzball workflow catalog start "Nemotron 3 Nano" --values Nodes=2,ExpertParallelism=auto
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

- The recipe's nano_v3 reasoning parser is a plugin file the stock vLLM image does not carry, so it is not preset (unlike Nemotron 3 Super's nemotron_v3 parser, which vLLM ships built in); see the recipe.
- The preset flags include --trust-remote-code, which lets vLLM execute Python from the downloaded model repository at load time (this architecture requires it). Removing it means overriding ExtraArgs with the remaining defaults.
- The tool-call parser (qwen3_coder) and --async-scheduling come from this model's own recipe; Nemotron 3 Super's recipe specifies different flags (qwen3_xml, fp8 KV cache) -- the divergence is upstream's, not an inconsistency here.
