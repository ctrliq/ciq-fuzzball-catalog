# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "boltz2-affinity-fixed" # needs to be **unique** per application, changing results in a new application
name: "Boltz-2 affinity screen of a fixed component library"
category: "OTHER"
---
Boltz-2 ([GitHub](https://github.com/jwohlwend/boltz/tree/main), [preprint](https://www.biorxiv.org/content/10.1101/2025.06.14.659707v1.full)) is a biomolecular foundation model that combines the prediction of molecular structures with binding affinity estimates with accuracy comparable to physics-based free-energy perturbation (FEP) methods.

This workflow allows you to screen a library of chemical compounts in smiles format against a single protein. It assumes that a multiple sequence
alignment (MSA) in the `.csv` format used by Boltz-2 is provided to reduce repeated calculations.

The compound library is a `.csv` format file with two required columns: `id` and `smiles`. Any other columns are ignored.
