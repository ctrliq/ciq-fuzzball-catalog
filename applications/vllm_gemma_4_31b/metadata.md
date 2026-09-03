# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_gemma_4_31b"
name: "Gemma 4 31B"
template: vllm
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- OpenAI API
- Gemma
- ai
- model
---
Serves Google's Gemma 4 31B instruction-tuned model, natively multimodal from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/Google/gemma-4-31B-it) validated.

- **Checkpoint**: `google/gemma-4-31B-it`
- **License**: apache-2.0
- **Context preset**: 262144 tokens
- **GPU fit**: one 80GB GPU per replica; lower MaxContextSize if the KV cache does not fit beside the ~62GB weights

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Gemma 4 31B"
fuzzball workflow catalog start "Gemma 4 31B" --values Volume=my-models,MaxReplicas=8
fuzzball workflow catalog start "Gemma 4 31B" --values Nodes=2
```

Set `Nodes` above 1 to serve each replica across several nodes; see the `vllm`
entry description for what a multi-node replica needs.

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.

## Notes

- The recipe also passes a tool chat template by container-relative path (--chat-template examples/tool_chat_template_gemma4.jinja); it is not preset because the served working directory differs. To use it, override ExtraArgs with the preset defaults plus this flag.
- MemoryPerNode is 64GiB where other 1-GPU presets use 32GiB: this checkpoint ships its 62GB as only two safetensors shards (the larger 50GB), and loading it was observed to OOM at 32GiB. Host memory must fit the largest single shard; multi-shard checkpoints stream within the 32GiB tier.
