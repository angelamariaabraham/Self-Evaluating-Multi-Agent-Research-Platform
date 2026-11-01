import csv, sys, statistics as st

topic = sys.argv[1]
start = sys.argv[2]                       # e.g. 2026-10-24T22:00
end = sys.argv[3] if len(sys.argv) > 3 else "9999"

rows = []
for f in ("runs.csv", "runs_pending.csv"):
    try:
        for r in csv.reader(open(f, encoding="utf-8")):
            if r and r[0][:2] == "20" and r[1] == topic and start <= r[0] <= end:
                rows.append(r)
    except FileNotFoundError:
        pass
rows.sort()

print("time | claims | faithfulness | claim_eq_span | failed")
for r in rows:
    print(r[0], r[2], r[3], r[4], r[5] or "-")

f = [float(r[3]) for r in rows]
c = [int(r[2]) for r in rows]
print("\nruns:", len(rows), " dates:", rows[0][0][:10], "to", rows[-1][0][:10])
print(f"faithfulness mean {st.mean(f):.3f}  sample SD {st.stdev(f):.3f}  range {min(f):.3f}-{max(f):.3f}")
print(f"claims       mean {st.mean(c):.1f}  sample SD {st.stdev(c):.1f}  range {min(c)}-{max(c)}")