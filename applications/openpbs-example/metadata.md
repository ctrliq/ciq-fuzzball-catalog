---
id: openpbs-example
name: OpenPBS Toyota Example
description: Example workflow for Toyota 
category: EXAMPLES
featured: false
tags:
  - pbs
  - openpbs
  - provisioner
---

# OpenPBS Example Workflow

This example workflow demonstrates how to use the OpenPBS provisioner in Fuzzball. OpenPBS (Portable Batch System) is an open-source workload manager and job scheduler that is commonly used in high-performance computing (HPC) environments.

## Overview

This workflow runs a simple three-stage pipeline that will automatically use OpenPBS provisioning when available:

1. **Pre-job**: Initial setup stage that runs for a configurable duration
2. **Main Job**: Primary computational workload (depends on pre-job completion)
3. **Post-job**: Cleanup/finalization stage (depends on main job completion)

Each stage demonstrates job dependencies and sequential execution in a PBS-managed environment.

## How It Works

This workflow uses **automatic provisioner selection**. When you run this workflow, Fuzzball's scheduler will:

1. Examine the resource requirements for each job (1 CPU core, 0.5GiB memory per job)
2. Evaluate all available provisioners in the cluster
3. Automatically select the best matching provisioner (including OpenPBS if configured)
4. Provision resources and execute the three-stage pipeline sequentially

No manual provisioner selection is needed - if OpenPBS is configured and can satisfy the resource requirements, it will be used automatically.

## Prerequisites

Before using this workflow, ensure that:

- At least one OpenPBS provisioner definition is configured in your Fuzzball cluster
- The PBS queue has sufficient resources to satisfy the job requirements
- Your account has permissions to submit jobs through Fuzzball

## Configuration

You can customize the duration of each stage:

- **Pre-job Duration**: Number of seconds for the pre-job to run (default: 5 seconds)
- **Main Job Duration**: Number of seconds for the main job to run (default: 10 seconds)
- **Post-job Duration**: Number of seconds for the post-job to run (default: 5 seconds)

## Workflow Structure

```
pre (5s) → job (10s) → post (5s)
```

Each job:
- Uses the Alpine Linux container image
- Runs a simple shell script that displays its stage name and sleeps for the configured duration
- Allocates minimal resources (1 CPU core, 0.5GiB memory)
- Demonstrates proper job dependency chaining

## Use Case

This workflow is ideal for:

- Demonstrating OpenPBS integration in Fuzzball with zero configuration
- Testing PBS provisioner functionality with a multi-stage pipeline
- Showcasing job dependencies and sequential execution on PBS-managed nodes
- Validating that PBS queues are properly configured and accessible
