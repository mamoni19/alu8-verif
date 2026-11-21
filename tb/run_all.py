"""One-command pipeline: model tests -> RTL smoke test -> multi-seed cocotb regression
-> (optional) mutation testing -> HTML report at sim/report.html.

Usage:
    python tb/run_all.py                 # 3 seeds, full (exhaustive on first seed), 20k random each
    python tb/run_all.py --quick         # skip exhaustive, 2k random vectors (~15 s)
    python tb/run_all.py --mutation      # also run the 20-mutant campaign
    python tb/run_all.py --seeds 5 --seed 100
Exit code 0 only if every step passes.
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "sim"
WINDOWS_IVERILOG = Path(r"C:\iverilog\bin")


def ensure_iverilog_on_path() -> bool:
    if shutil.which("iverilog"):
        return True
    if WINDOWS_IVERILOG.exists():
        os.environ["PATH"] += os.pathsep + str(WINDOWS_IVERILOG)
    return shutil.which("iverilog") is not None


def run(cmd, env=None):
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env=env)
    return p.returncode, p.stdout + p.stderr, time.time() - t0


# ----------------------------------------------------------------------------- steps
def step_model_tests():
    rc, out, dt = run([sys.executable, "-m", "pytest", "tb/test_model.py", "-q"])
    m = re.search(r"(\d+) passed", out)
    detail = f"{m.group(1)} model unit tests passed" if m and rc == 0 else "model tests FAILED"
    return {"name": "Golden model unit tests", "ok": rc == 0, "detail": detail, "secs": dt}


def step_smoke():
    SIM.mkdir(exist_ok=True)
    rc, out, dt = run(["iverilog", "-g2012", "-o", "sim/smoke.vvp", "rtl/alu8.v", "tb/tb_smoke.v"])
    if rc == 0:
        rc, out2, dt2 = run(["vvp", "sim/smoke.vvp"])
        out, dt = out2, dt + dt2
    ok = rc == 0 and "SMOKE TEST PASSED" in out
    return {"name": "RTL smoke test (Verilog TB)", "ok": ok,
            "detail": "SMOKE TEST PASSED" if ok else out.strip()[-300:], "secs": dt}


def parse_results(xml_path: Path):
    tests = []
    for tc in ET.parse(xml_path).getroot().iter("testcase"):
        failed = tc.find("failure") is not None or tc.find("error") is not None
        tests.append({"name": tc.get("name"), "time": float(tc.get("time", 0)), "ok": not failed})
    return tests


def step_regression(seed: int, quick: bool, random_n: int, exhaustive: bool):
    bdir = SIM / "runs" / f"seed{seed}"
    env = dict(os.environ, ALU_SEED=str(seed), ALU_RANDOM_N=str(random_n),
               ALU_SKIP_EXHAUSTIVE="0" if exhaustive else "1")
    rc, out, dt = run([sys.executable, "tb/run_sim.py", "--build-dir", str(bdir)], env=env)
    xml_path = bdir / "results.xml"
    tests = parse_results(xml_path) if xml_path.exists() else []
    ok = rc == 0 and bool(tests) and all(t["ok"] for t in tests)
    return {"name": f"cocotb regression, seed {seed}", "ok": ok, "secs": dt, "seed": seed,
            "exhaustive": exhaustive, "random_n": random_n, "tests": tests,
            "coverage": str(bdir / "coverage.yml"),
            "detail": f"{sum(t['ok'] for t in tests)}/{len(tests)} tests passed"
                      + ("" if exhaustive else " (exhaustive skipped)"),
            "log_tail": "" if ok else out[-1500:]}


def step_mutation():
    rc, out, dt = run([sys.executable, "tb/run_mutation.py"])
    jf = SIM / "mutation_results.json"
    data = json.loads(jf.read_text()) if jf.exists() else None
    ok = rc == 0 and data is not None
    detail = f"{data['killed']}/{data['total']} mutants killed" if data else out.strip()[-300:]
    return {"name": "Mutation testing", "ok": ok, "detail": detail, "secs": dt, "mutation": data}


# ----------------------------------------------------------------------------- report
CSS = """
body{font-family:Inter,Segoe UI,Arial,sans-serif;background:#0f1220;color:#e6e9f5;margin:0;padding:32px}
.wrap{max-width:980px;margin:auto}
h1{margin:0 0 4px;font-size:28px} h2{margin-top:36px;border-bottom:1px solid #2a3050;padding-bottom:6px}
.sub{color:#8e96b8;margin-bottom:24px}
.banner{padding:16px 20px;border-radius:12px;font-weight:600;font-size:18px;margin-bottom:24px}
.pass{background:linear-gradient(90deg,#0f3d2e,#14573f);color:#7dffc4}
.fail{background:linear-gradient(90deg,#4a1620,#6b1d2c);color:#ff9aa9}
table{width:100%;border-collapse:collapse;background:#161a2e;border-radius:10px;overflow:hidden}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #232845;font-size:14px}
th{background:#1c2140;color:#9fa8d6;font-weight:600}
.ok{color:#59f0a8;font-weight:600}.bad{color:#ff6b84;font-weight:600}
.bar{background:#232845;border-radius:6px;height:10px;width:140px;display:inline-block;vertical-align:middle}
.bar>i{display:block;height:100%;border-radius:6px;background:linear-gradient(90deg,#6c8cff,#59f0a8)}
pre{background:#161a2e;padding:12px;border-radius:8px;overflow:auto;font-size:12px}
"""


def badge(ok):
    return '<span class="ok">PASS</span>' if ok else '<span class="bad">FAIL</span>'


def load_coverage(path):
    try:
        data = yaml.safe_load(Path(path).read_text())
    except Exception:
        return []
    return [(k, v.get("coverage"), v.get("size"), v.get("cover_percentage", 0.0))
            for k, v in sorted(data.items()) if isinstance(v, dict)]


def build_report(steps, args, path: Path):
    all_ok = all(s["ok"] for s in steps)
    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>8-bit ALU Verification Report</title>"
         f"<style>{CSS}</style></head><body><div class='wrap'>",
         "<h1>8-bit ALU Verification Report</h1>",
         f"<div class='sub'>Generated {datetime.now():%Y-%m-%d %H:%M:%S} &middot; DUT: rtl/alu8.v "
         f"&middot; seeds: {args.seed}..{args.seed + args.seeds - 1}</div>",
         f"<div class='banner {'pass' if all_ok else 'fail'}'>"
         f"{'ALL CHECKS PASSED' if all_ok else 'FAILURES DETECTED'}</div>",
         "<h2>Pipeline summary</h2><table><tr><th>Step</th><th>Result</th><th>Detail</th><th>Time</th></tr>"]
    for s in steps:
        h.append(f"<tr><td>{html.escape(s['name'])}</td><td>{badge(s['ok'])}</td>"
                 f"<td>{html.escape(s['detail'])}</td><td>{s['secs']:.1f}s</td></tr>")
    h.append("</table>")

    regs = [s for s in steps if "tests" in s]
    if regs:
        names = [t["name"] for t in regs[0]["tests"]]
        h.append("<h2>Regression results per seed</h2><table><tr><th>Test</th>"
                 + "".join(f"<th>seed {r['seed']}</th>" for r in regs) + "</tr>")
        for i, n in enumerate(names):
            cells = ""
            for r in regs:
                t = r["tests"][i] if i < len(r["tests"]) else None
                skipped = n == "test_exhaustive" and not r["exhaustive"]
                cells += ("<td>skipped</td>" if skipped else f"<td>{badge(t['ok'])}</td>") if t else "<td>-</td>"
            h.append(f"<tr><td>{html.escape(n)}</td>{cells}</tr>")
        h.append("</table>")
        cov = load_coverage(regs[0]["coverage"])
        if cov:
            h.append(f"<h2>Functional coverage (seed {regs[0]['seed']})</h2>"
                     "<table><tr><th>Cover item</th><th>Bins hit</th><th>Coverage</th></tr>")
            for k, c, sz, pct in cov:
                h.append(f"<tr><td>{html.escape(k)}</td><td>{c}/{sz}</td><td>"
                         f"<span class='bar'><i style='width:{pct:.0f}%'></i></span> {pct:.1f}%</td></tr>")
            h.append("</table>")

    mut = next((s["mutation"] for s in steps if s.get("mutation")), None)
    if mut:
        h.append(f"<h2>Mutation testing: {mut['killed']}/{mut['total']} killed ({mut['score']:.0f}%)</h2>"
                 "<table><tr><th>ID</th><th>Injected bug</th><th>Result</th></tr>")
        for m in mut["mutants"]:
            cls = "ok" if m["status"] == "KILLED" else "bad"
            h.append(f"<tr><td>{m['id']}</td><td>{html.escape(m['desc'])}</td>"
                     f"<td class='{cls}'>{m['status']}</td></tr>")
        h.append("</table>")

    for s in steps:
        if s.get("log_tail"):
            h.append(f"<h2>Log tail: {html.escape(s['name'])}</h2><pre>{html.escape(s['log_tail'])}</pre>")
    h.append("</div></body></html>")
    path.write_text("\n".join(h), encoding="utf-8")


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip exhaustive, 2000 random vectors")
    ap.add_argument("--mutation", action="store_true", help="also run mutation testing")
    ap.add_argument("--seeds", type=int, default=3, help="number of random seeds")
    ap.add_argument("--seed", type=int, default=1, help="first seed value")
    args = ap.parse_args()

    if not ensure_iverilog_on_path():
        print("iverilog not found. Install Icarus Verilog and/or add it to PATH.")
        return 2

    random_n = 2000 if args.quick else 20000
    steps = []

    def record(s):
        steps.append(s)
        print(f"[{'PASS' if s['ok'] else 'FAIL'}] {s['name']}: {s['detail']} ({s['secs']:.1f}s)", flush=True)

    record(step_model_tests())
    record(step_smoke())
    for i in range(args.seeds):
        # Exhaustive stimulus is deterministic, so run it once (first seed) only.
        record(step_regression(args.seed + i, args.quick, random_n, exhaustive=(i == 0 and not args.quick)))
    if args.mutation:
        record(step_mutation())

    report = SIM / "report.html"
    build_report(steps, args, report)
    ok = all(s["ok"] for s in steps)
    print(f"\n{'ALL CHECKS PASSED' if ok else 'FAILURES DETECTED'}  ->  report: {report}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
