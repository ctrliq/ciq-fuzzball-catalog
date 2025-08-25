# **Fuzzball Workflow Templates**

### _Powered by [CIQ](https://ciq.co/)_

These template workflows form the basis for the Fuzzball Workflow Catalog.

For more information about Fuzzball, see the [official Fuzzball documentation](https://ui.stable.fuzzball.ciq.dev/docs/).

---

## Branches

### How Fuzzball Deployments Use This Repository

Fuzzball deployments fetch application templates from this repository if the
official application template catalog is enabled.
- **Stable deployments** pull from the corresponding `vMAJOR.MINOR` branch.
- **Unstable deployments** pull from the `main` branch.

Development occurs on the `main` branch. When a new Fuzzball minor release is
created, a corresponding `vMAJOR.MINOR` catalog branch will be created from
`main`.

---

## Contributing

### New Application Templates

- Submit pull requests for new applications to the `main` branch.
- After merging, the submitter is responsible for creating a PR to merge the
  corresponding commit into the current `vMAJOR.MINOR` branch to enable the app
  for current stable deployments.
- Application templates may also be ported to previous `vMAJOR.MINOR` releases.

### Fixes

- Submit fixes to application templates to the `main` branch.
- After acceptance, the submitter is responsible for submitting corresponding
  PRs for older branches of supported Fuzzball minor versions.

### Version Updates

- Submit updates to existing applications to the `main` branch.
- After merging, the submitter should open a corresponding PR for the current
  `vMAJOR.MINOR` branch.

---
