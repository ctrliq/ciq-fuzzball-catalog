import re, sys, os

INPUT  = sys.argv[1]
OUTPUT = "/data/patched.inp"

with open(INPUT, errors="ignore") as f:
    lines = f.readlines()

content = "".join(lines)

if "__YOUNGS__" in content:
    print("Already has placeholders, copying as-is")
    with open(OUTPUT, "w") as f:
        f.write(content)
    sys.exit(0)

out_lines   = []
i           = 0
patched     = False
has_density = any("*DENSITY" in l.upper() for l in lines)

while i < len(lines):
    line     = lines[i]
    stripped = line.strip()
    if stripped.upper().startswith("*ELASTIC") and not patched:
        out_lines.append(line)
        i += 1
        while i < len(lines):
            dl = lines[i]
            ds = dl.strip()
            if ds.startswith("**") or ds == "":
                out_lines.append(dl)
                i += 1
                continue
            vals = [v for v in re.split(r"[, \t]+", ds) if v]
            if len(vals) >= 2:
                print("Detected E=" + vals[0] + " nu=" + vals[1])
                out_lines.append("__YOUNGS__, __POISSON__\n")
                patched = True
                i += 1
                if not has_density:
                    out_lines.append("*DENSITY\n")
                    out_lines.append("__DENSITY__,\n")
                    print("Added *DENSITY section")
            else:
                out_lines.append(dl)
                i += 1
            break
    else:
        out_lines.append(line)
        i += 1

if not patched:
    print("WARNING: No *ELASTIC section found, writing as-is")
    with open(OUTPUT, "w") as f:
        f.writelines(lines)
else:
    with open(OUTPUT, "w") as f:
        f.writelines(out_lines)
    print("Patched OK: " + OUTPUT)

print("=== Material section preview ===")
with open(OUTPUT) as f:
    out = f.read()
idx = out.upper().find("*MATERIAL")
if idx >= 0:
    print(out[idx:idx+200])
