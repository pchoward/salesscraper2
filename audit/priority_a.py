import os
import sale_sniffer as s
out = []
for name, base, handles in s.sport_shops():
    if name not in ("evo", "Fanatik", "Gear West", "Mike's Bikes", "Cambria"): continue
    out.append(f"### {name}: " + str(s.homepage_sale_collections(base, handles)))
with open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/stdout"), "a") as f: f.write("\n".join(out) + "\n")
print("\n".join(out))
