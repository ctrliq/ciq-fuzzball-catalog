# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_llama_4_scout"
name: "Llama 4 Scout"
template: vllm
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- OpenAI API
- Llama
- ai
- model
---
Serves Meta's Llama 4 Scout (MoE, 17B active / 16 experts, natively multimodal) from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/meta-llama/Llama-4-Scout-17B-16E-Instruct) validated.

- **Checkpoint**: `meta-llama/Llama-4-Scout-17B-16E-Instruct`
- **License**: llama4 (gated: requires accepting the license on HuggingFace)
- **Context preset**: 1048576 tokens
- **GPU fit**: an 8-GPU 80GB+ node per replica

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Llama 4 Scout"
fuzzball workflow catalog start "Llama 4 Scout" --values HfTokenSecret=secret://user/hf-token
fuzzball workflow catalog start "Llama 4 Scout" --values Volume=my-models,MaxReplicas=4
fuzzball workflow catalog start "Llama 4 Scout" --values Nodes=2,GpusPerNode=4,ExpertParallelism=auto
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

- The model supports up to 10M-token context; this entry presets 1M. Raise MaxContextSize only with the KV-cache memory to back it.
- The recipe defines no tool-call parser, so the preset adds vLLM's `llama4_pythonic` parser and its chat template on top of the recipe's flags; agent clients such as the OpenCode entry need it.
- The recipe disables prefix caching (--no-enable-prefix-caching), which lowers multi-turn throughput; part of the validated configuration.
