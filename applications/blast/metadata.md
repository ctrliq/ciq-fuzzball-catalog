# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "blast_application" # needs to be **unique** per application, changing results in a new application
name: "BLAST"
category: "OTHER"
featured: true
---
The BLAST example workflow provides a Fuzzball template to retrieve query sequences and either:

- Create a custom database  
- Fetch a named BLAST database from NCBI  

Public databases are cached in a persistent volume. Custom databases can also be saved for later use.  

> **Note:** Some BLAST databases are large and may be costly to store.
