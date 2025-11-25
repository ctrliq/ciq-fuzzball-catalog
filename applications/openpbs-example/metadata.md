# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: dependency-example
name: Dependent Jobs Example
category: EXAMPLES
featured: false
tags:
  - dependencies
  - example
  - workflow
---
Example workflow for demonstrating dependent jobs in Fuzzball


# Job Dependency Example Workflow

This example workflow demonstrates how to create dependent jobs in Fuzzball. It shows how to chain multiple jobs together so they execute in a specific order, with each job waiting for its dependencies to complete before starting.

## Overview

This workflow runs a simple three-stage pipeline that demonstrates job dependency chaining:

1. **Pre-job**: Initial setup stage that runs for a configurable duration
2. **Main Job**: Primary computational workload (depends on pre-job completion)
3. **Post-job**: Cleanup/finalization stage (depends on main job completion)

Each stage demonstrates how to properly configure job dependencies to ensure sequential execution.

## How It Works

This workflow uses Fuzzball's `requires` field to establish dependencies between jobs:

1. The **pre** job runs first (no dependencies)
2. The **job** stage waits for **pre** to complete (requires: pre)
3. The **post** stage waits for **job** to complete (requires: job)

When you submit this workflow, Fuzzball's scheduler will:

1. Examine the dependency chain
2. Execute jobs in the correct order
3. Ensure each job only starts after its dependencies have successfully completed

## Prerequisites

Before using this workflow, ensure that:

- Your Fuzzball cluster has available compute resources
- Your account has permissions to submit workflows through Fuzzball

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
- Demonstrates proper job dependency chaining using the `requires` field

## Use Case

This workflow is ideal for:

- Learning how to create dependent jobs in Fuzzball workflows
- Understanding the `requires` field and dependency syntax
- Testing multi-stage pipeline execution with sequential dependencies
- Serving as a template for more complex workflows with dependency chains
