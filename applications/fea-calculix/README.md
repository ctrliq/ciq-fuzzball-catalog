# FEA Material Sweep — User Guide

Run a CalculiX structural analysis across two candidate materials simultaneously on Fuzzball. Get a full engineering report with stress, displacement, factor of safety, fatigue life, buckling, and more.

---

## Quick start (the short version)

1. Upload `FEA_FINAL_fztpl.json` to the Fuzzball Workflow Catalog
2. Upload your `.inp` model to GitHub Gist and copy the Raw URL
3. Go to Workflow Catalog → FEA FINAL → Run → fill in the form → Start
4. Wait ~10 minutes
5. Open the report (see Step 5 below)

---

## Step 1 — Upload the workflow to the catalog (admin, once only)

1. In the Fuzzball web UI, click **Workflow Catalog** in the left sidebar
2. Click **Upload** or **Import**
3. Select `FEA_FINAL_fztpl.json` from this package
4. It will appear as **FEA FINAL** in the catalog

This only needs to be done once. Everyone on the cluster can use it after that.

---

## Step 2 — Host your model on GitHub Gist

Your CalculiX `.inp` file needs to be at a public URL. GitHub Gist is free and takes 2 minutes.

1. Go to **[gist.github.com](https://gist.github.com)**
2. Click **+** (top right)
3. Set the filename to match your file — e.g. `my_model.inp`
4. Paste the full contents of your `.inp` file
5. Click **Create public gist**
6. On the next page click **Raw** (top right of the file box)
7. Copy the URL from your browser — it looks like:
```
https://gist.githubusercontent.com/your-username/abc123def/raw/my_model.inp
```

That is your model URL. You will paste it into the form in Step 3.

> **Use the Raw URL, not the regular Gist page URL.** The raw URL goes directly to the file.

> **To run the included example immediately**, use this pre-hosted cantilever beam URL:
> ```
> https://gist.githubusercontent.com/hhara-code/4fdfd6fa29f5100f5b4cafa7b95e7a0d/raw/cantilever_beam_500x20x10.inp
> ```
> Set AppliedForceN to `100` with this model.

---

## Step 3 — Run the workflow

1. In the Fuzzball web UI, click **Workflow Catalog**
2. Find **FEA FINAL** and click the **⋮ menu** (three dots) → **Run**
3. Fill in the form:

### InputFile
Paste your Gist Raw URL here.

### AppliedForceN
Total load in Newtons applied to your model.

| Model | AppliedForceN |
|---|---|
| cantilever_beam_500x20x10.inp | 100 |
| plate_with_hole.inp | 5000 |
| l_bracket_fillet.inp | 500 |

### OriginalYoungs and OriginalPoisson
These must **exactly match** what is hardcoded in your `.inp` file's `*ELASTIC` section. Open your file and look for:
```
*ELASTIC
210000., 0.3
```
Copy those numbers exactly — including any trailing dots. The defaults (`210000.` and `.3`) work for all three included models.

### Material 1 and Material 2
Fill in your two candidate materials. Common values:

| Material | E (MPa) | Poisson | Density (kg/m³) | Yield (MPa) | Cost ($/kg) |
|---|---|---|---|---|---|
| Steel A36 | 200000 | 0.26 | 7850 | 250 | 0.80 |
| Aluminum 6061 | 68900 | 0.33 | 2700 | 276 | 2.00 |
| Titanium Ti6Al4V | 113800 | 0.34 | 4430 | 880 | 35.00 |
| Stainless 316L | 193000 | 0.27 | 8000 | 170 | 3.50 |
| Carbon Fibre | 70000 | 0.10 | 1600 | 600 | 80.00 |

### Volume
Leave as `volume://user/FEA_RESULTS` — this uses the persistent volume you created.

4. Click **Start Workflow**

---

## Step 4 — Watch it run

Click on your workflow in the **Workflows** list. You will see these jobs running in sequence:

| Job | What it does | Time |
|---|---|---|
| prepare | Downloads your model, patches material values in | ~30 sec |
| fea-mat1 | Runs CalculiX solver — Material 1 | 2–15 min |
| fea-mat2 | Runs CalculiX solver — Material 2 (same time) | 2–15 min |
| report | Generates all charts and the HTML report | ~2 min |
| serve | Serves the report (stays running) | Until stopped |

Click on any job and then click the **Logs** tab to see what it's doing.

**The report is ready when the serve job shows as running.**

---

## Step 5 — Open the report

> **Note:** The Connect button in the Fuzzball UI may not appear depending on your cluster configuration. If it does appear next to the Rerun button when the serve job is running — click it and the report opens directly. If it does not appear, use the terminal method below.

**Terminal method** — open a terminal on your machine and run:

```bash
fuzzball workflow port-forward <workflow-id> serve 8080:8080
```

Then open **http://localhost:8080** in your browser.

Get the workflow ID from the URL bar in the Fuzzball UI — it's the long string like `66faaf22-0121-4d98-aa4b-0eb25b2744c2`.

Keep the terminal open while viewing the report. Close it when done.

---

## What the report shows

- **Material properties** — stiffness, yield strength, density, specific stiffness, strength-to-weight, cost per m³
- **FEA results** — Von Mises stress, principal stress σ1, displacement, factor of safety, force to yield
- **Part mass and cost** — calculated from actual mesh geometry and material density
- **Safety margin map** — factor of safety on every element as a 3D colour heatmap
- **Stress gradient** — how quickly stress drops from the hot spot, and whether it's localised or widespread
- **Fatigue life** — Goodman-corrected cycle life at operating stress (R=0.1 pulsating load)
- **Buckling load factor** — how many times the applied load before sudden geometric collapse
- **4-panel 3D visualisations** — boundary conditions, Von Mises heatmap, principal stress, displacement
- **Radar chart** — all metrics compared across both materials at once
- **Engineering recommendations** — automatically generated, calls out the best material for each criterion

**Factor of Safety colour coding:**
- 🟢 Green — FoS ≥ 2.0 (safe)
- 🟠 Orange — FoS 1.5–2.0 (caution, acceptable for many applications)
- 🔴 Red — FoS < 1.5 (redesign recommended)

---

## Included example models

| File | Geometry | Load direction | AppliedForceN |
|---|---|---|---|
| `cantilever_beam_500x20x10.inp` | 500×20×10mm horizontal beam, fixed left end | 100N downward at tip | 100 |
| `plate_with_hole.inp` | 100×100×5mm plate, 10mm central hole | 5000N tension | 5000 |
| `l_bracket_fillet.inp` | L-bracket, R=8mm fillet | 500N downward | 500 |

Upload any of these to GitHub Gist to get started immediately.

---

## Troubleshooting

### Prepare job fails — "No ELASTIC section found"
The `OriginalYoungs` or `OriginalPoisson` values in the form don't match your `.inp` file exactly. Open your file, find the line after `*ELASTIC`, and copy the numbers exactly as they appear — including trailing dots and leading dots (e.g. `210000.` not `210000`, `.3` not `0.3`).

### fea-mat1 or fea-mat2 job errors with "Job stopped responding"
The cluster ran out of resources. Set `CoresPerJob` to `2` in the form and try again.

### Von Mises stress shows N/A or 0.0
Your `.inp` file is missing stress output. Add this inside the `*STEP` block:
```
*EL PRINT, ELSET=EALL
S
*EL FILE, ELSET=EALL
S
```

### Buckling chart says "Not Applicable"
Your model is loaded in tension. Buckling only applies to models under compression or shear. Use the cantilever beam model to see real buckling numbers — the top surface is in compression under the downward tip load.

### Factor of Safety shows as millions
The solver didn't output stress data. See the Von Mises stress fix above.

### The Connect button doesn't appear
This is a cluster configuration issue — endpoint routing may not be enabled. Use the port-forward terminal method in Step 5, and ask your cluster admin to enable endpoint ingress. Tell them: *"The Connect button should appear next to the Rerun button when the serve job is running, but it doesn't show up despite the network endpoint being configured correctly in the template."*

### report job fails immediately
Check the fea-mat1 and fea-mat2 logs first. If those jobs failed, fix them before the report will work.

### The report page loads but charts are missing
Wait 30 seconds and refresh — the report server may still be starting up.

---

## Using your own CalculiX model

Any static structural `.inp` file works. Requirements:

1. `*ELASTIC` section with Young's modulus and Poisson's ratio on the very next line
2. `*BOUNDARY` for fixed supports, `*CLOAD` for applied point forces
3. Output requests inside `*STEP`:
```
*NODE PRINT, NSET=NALL
U
*EL PRINT, ELSET=EALL
S
*NODE FILE, NSET=NALL
U
*EL FILE, ELSET=EALL
S
```
4. Upload to GitHub Gist, copy the Raw URL, paste into InputFile in the form
5. Set `OriginalYoungs` and `OriginalPoisson` to match your file exactly

Supported element types: C3D8 (hex), C3D4 (tet), C3D10 (quadratic tet), C3D20 (quadratic hex).

---

## Adding analytical validation to your model

The report can compare FEA results against hand-calculated values and flag discrepancies. To enable this, add two comment lines anywhere in your `.inp` file:

```
** VALIDATION: sigma_nom=54.0 kt=2.12 sigma_peak=114.4
** VALIDATION: tip_disp=0.064
```

Where:
- `sigma_nom` = nominal stress from beam theory (M×c/I) in MPa
- `kt` = stress concentration factor for your geometry
- `sigma_peak` = Kt × sigma_nom
- `tip_disp` = analytical tip deflection in mm

The report will show PASS / WARNING / CAUTION for each check.

---

*FEA Material Sweep Workflow v11 — Built with CalculiX on Fuzzball*
