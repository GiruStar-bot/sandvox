"""Entities on the 1,730 regions by area share (MODERN_PLAN 1.3), from Natural Earth's de-facto admin-0 polygons.
  python3 -I tools/modern/build_entity_cells.py --ne <ne_10m_admin_0_countries.geojson> --entities data/modern/entities.json \
      --regions data/modern/regions.json --out data/modern/entity_regions.json
Each grid cell (1.40625 degrees) is sampled at SUB x SUB points at the sample centres; a point takes the entity whose polygon holds it (even-odd
rule per polygon, rasterised by scan lines). A region's share of an entity is the entity's samples over the region's samples that fall in any
entity (DERIVED). An entity with no sample in any region takes its area (cylindrical equal-area shoelace) as a share of the region holding its
label point (or the nearest region centre), the region's other shares scaled down to make room. Land borders: two entities are neighbours
when two 4-adjacent samples on land carry them."""
import argparse, hashlib, json, math

SUB = 8
R_KM = 6371.0088


def rings_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def ring_area_km2(ring):
    # cylindrical equal-area: x = R lambda, y = R sin(phi); shoelace
    s = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = math.radians(ring[i][0]), math.sin(math.radians(ring[i][1]))
        x1, y1 = math.radians(ring[i + 1][0]), math.sin(math.radians(ring[i + 1][1]))
        s += x0 * y1 - x1 * y0
    return abs(s) * 0.5 * R_KM * R_KM


def fill_polygon(grid, NX, NY, dlon, dlat, polygon, value):
    """Even-odd fill of one polygon (outer ring + holes) into grid[row][col] at the sample centres."""
    rows = {}
    for ring in polygon:
        n = len(ring)
        for i in range(n - 1):
            x0, y0 = ring[i]
            x1, y1 = ring[i + 1]
            if y0 == y1:
                continue
            lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
            r0 = max(0, math.ceil((lo + 90.0) / dlat - 0.5))
            r1 = min(NY - 1, math.floor((hi + 90.0) / dlat - 0.5))
            for r in range(r0, r1 + 1):
                yc = -90.0 + (r + 0.5) * dlat
                if not (lo <= yc < hi):
                    continue
                xc = x0 + (yc - y0) * (x1 - x0) / (y1 - y0)
                rows.setdefault(r, []).append(xc)
    for r, xs in rows.items():
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            c0 = max(0, math.ceil((xs[k] + 180.0) / dlon - 0.5))
            c1 = min(NX - 1, math.floor((xs[k + 1] + 180.0) / dlon - 0.5))
            row = grid[r]
            for c in range(c0, c1 + 1):
                row[c] = value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ne", required=True)
    ap.add_argument("--entities", required=True)
    ap.add_argument("--regions", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = open(a.ne, "rb").read()
    fs = json.loads(raw.decode("utf-8"))["features"]
    ent = json.load(open(a.entities, encoding="utf-8"))
    reg = json.load(open(a.regions, encoding="utf-8"))
    W, H = reg["W"], reg["H"]
    NX, NY = W * SUB, H * SUB
    dlon, dlat = 360.0 / NX, 180.0 / NY
    index = {e["key"]: i for i, e in enumerate(ent["entities"])}
    grid = [[-1] * NX for _ in range(NY)]
    area = [0.0] * len(index)
    for f in fs:
        k = ent["feature_entity"].get(f["properties"]["ADM0_A3"])
        if k is None:
            continue
        e = index[k]
        for poly in rings_of(f["geometry"]):
            area[e] += ring_area_km2(poly[0]) - sum(ring_area_km2(h) for h in poly[1:])
            fill_polygon(grid, NX, NY, dlon, dlat, poly, e)
    cell_region = {}
    for r in reg["regions"]:
        for c in r["cells"]:
            cell_region[c] = r["id"]
    counts = [dict() for _ in reg["regions"]]
    land_samples = [0] * len(reg["regions"])
    for c, rid in cell_region.items():
        x, y = c % W, c // W
        for sy in range(SUB):
            row = grid[y * SUB + sy]
            for sx in range(SUB):
                e = row[x * SUB + sx]
                land_samples[rid] += 1
                if e >= 0:
                    counts[rid][e] = counts[rid].get(e, 0) + 1
    seen = set()
    for cd in counts:
        seen.update(cd)
    shares = []
    for rid, cd in enumerate(counts):
        tot = sum(cd.values())
        shares.append({e: n / tot for e, n in cd.items()} if tot else {})
    tiny = []
    for e in range(len(index)):
        if e in seen:
            continue
        lx, ly = ent["entities"][e]["label"]
        cx = min(W - 1, int((lx + 180.0) / (360.0 / W)))
        cy = min(H - 1, int((ly + 90.0) / (180.0 / H)))
        rid = cell_region.get(cy * W + cx)
        if rid is None:
            rid = min(reg["regions"], key=lambda r: (r["center"][0] - lx) ** 2 + (r["center"][1] - ly) ** 2)["id"]
        s = min(1.0, area[e] / reg["regions"][rid]["area_km2"])
        sh = {k: v * (1.0 - s) for k, v in shares[rid].items()}
        sh[e] = sh.get(e, 0.0) + s
        shares[rid] = sh
        tiny.append({"entity": ent["entities"][e]["key"], "region": rid, "share": s})
    nb = set()
    for y in range(NY):
        row = grid[y]
        up = grid[y + 1] if y + 1 < NY else None
        for x in range(NX):
            e = row[x]
            if e < 0:
                continue
            e2 = row[(x + 1) % NX]
            if e2 >= 0 and e2 != e:
                nb.add((min(e, e2), max(e, e2)))
            if up is not None and up[x] >= 0 and up[x] != e:
                nb.add((min(e, up[x]), max(e, up[x])))
    unmatched = [rid for rid, cd in enumerate(counts) if not cd]
    out = {"sub": SUB, "source": {"ne_sha256": hashlib.sha256(raw).hexdigest()},
           "regions": [[[e, round(v, 9)] for e, v in sorted(sh.items())] for sh in shares],
           "entity_area_km2": [round(v, 3) for v in area], "tiny_entities": tiny, "land_borders": sorted([list(p) for p in nb]),
           "regions_without_entity": unmatched,
           "rule": "DERIVED: area share from 8x8 samples per cell on NE de-facto polygons; tiny entities by area at their label point"}
    json.dump(out, open(a.out, "w", encoding="utf-8"), separators=(",", ":"), sort_keys=True)
    open(a.out, "a").write("\n")
    print("ENTITY_REGIONS regions %d without entity %d; entities sampled %d, tiny %d; land borders %d" % (len(shares), len(unmatched), len(seen), len(tiny), len(nb)))


if __name__ == "__main__":
    main()
