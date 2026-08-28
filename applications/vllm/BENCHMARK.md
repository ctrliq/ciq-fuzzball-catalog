# Expert parallelism vs. tensor parallelism — throughput comparison

This file records how to compare the expert-parallel layout
(`ExpertParallelism=true`: attention data-parallel, experts expert-parallel)
against the tensor-parallel default (`ExpertParallelism=false`) for a MoE model
on a single node, so the comparison is reproducible when images, models, or
hardware change.

**Results are not filled in yet.** Expert parallelism requires at least two
GPUs per replica — a single GPU has nothing to shard experts across — so these
numbers need a multi-GPU node, which was not available when the layout was
implemented. The methodology below is published ahead of the results; treat the
tables as a blocker to close, not as a comparison already made.

## Methodology

One workflow per configuration, identical except for `ExpertParallelism`:

```sh
fuzzball workflow catalog start vllm --name bench-ep --values \
  Model=hf://openai/gpt-oss-20b,GpusPerReplica=2,ExpertParallelism=true,Proxy=false,MinReplicas=1,MaxReplicas=1
fuzzball workflow catalog start vllm --name bench-tp --values \
  Model=hf://openai/gpt-oss-20b,GpusPerReplica=2,ExpertParallelism=false,Proxy=false,MinReplicas=1,MaxReplicas=1
```

- `Proxy=false` and a fixed single replica (`MinReplicas=MaxReplicas=1`), so
  the pool endpoint measures a single vLLM instance with no proxy hop and no
  autoscaler interference.
- Load generator: `vllm bench serve` (available inside the vLLM image), run
  against the pool endpoint with the ShareGPT default dataset, at
  concurrency levels 8, 32, and 128; 3 minutes of steady state per level
  after a 1-minute warmup.
- Repeat with `GpusPerReplica=4` if a 4-GPU node is available — EP-vs-TP
  differences grow with GPU count.
- Record for each run: output tokens/s (total), TTFT p50/p99, and ITL p50/p99
  as reported by `vllm bench serve`.

## Environment

| Field | Value |
|---|---|
| Cluster | TBD (Vultr) |
| GPU model / count per node | TBD |
| vLLM image | docker://vllm/vllm-openai:v0.10.1 |
| Model | hf://openai/gpt-oss-20b |
| Date | TBD |

## Results — GpusPerReplica=2

| Concurrency | Layout | Output tok/s | TTFT p50 / p99 (ms) | ITL p50 / p99 (ms) |
|---|---|---|---|---|
| 8 | EP (`ExpertParallelism=true`) | TBD | TBD | TBD |
| 8 | TP (`ExpertParallelism=false`) | TBD | TBD | TBD |
| 32 | EP | TBD | TBD | TBD |
| 32 | TP | TBD | TBD | TBD |
| 128 | EP | TBD | TBD | TBD |
| 128 | TP | TBD | TBD | TBD |

## Results — GpusPerReplica=4 (if hardware available)

Same table shape as above. TBD.

## Interpretation notes

- EP shards only the expert weights; attention weights are replicated per DP
  rank, so per-GPU memory headroom differs between the two layouts — compare
  `GpuMemoryUtilization`-driven KV-cache sizes in the vLLM startup logs when
  reading the numbers.
- The expected pattern (per llm-d): EP wins on throughput for MoE models at
  moderate-to-high concurrency; TP can win on TTFT at low concurrency.
