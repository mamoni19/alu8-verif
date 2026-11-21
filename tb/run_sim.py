"""Build the DUT with Icarus Verilog and run the cocotb regression.

Usage:  python tb/run_sim.py [--rtl path/to/dut.v] [--waves]
Exit code is non-zero if any test fails.
"""
import argparse
import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_results, get_runner

ROOT = Path(__file__).resolve().parents[1]
TB = ROOT / "tb"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtl", default=str(ROOT / "rtl" / "alu8.v"), help="DUT source file")
    ap.add_argument("--waves", action="store_true", help="dump waveforms (slow for big runs)")
    ap.add_argument("--build-dir", default=str(ROOT / "sim" / "build"))
    ap.add_argument("--results-xml", default=None, help="default: <build-dir>/results.xml")
    args = ap.parse_args()
    results_path = Path(args.results_xml) if args.results_xml else Path(args.build_dir) / "results.xml"
    os.environ.setdefault("ALU_COVERAGE_OUT", str(Path(args.build_dir) / "coverage.yml"))

    os.environ["PYTHONPATH"] = os.pathsep.join(
        [str(TB), str(ROOT / "model"), os.environ.get("PYTHONPATH", "")])
    sys.path.insert(0, str(TB))

    runner = get_runner("icarus")
    runner.build(sources=[Path(args.rtl)], hdl_toplevel="alu8",
                 build_dir=args.build_dir, always=True, waves=args.waves)
    results_xml = runner.test(hdl_toplevel="alu8", test_module="test_alu",
                              test_dir=str(TB), build_dir=args.build_dir, waves=args.waves,
                              results_xml=str(results_path))
    total, failed = get_results(results_xml)
    print(f"\n==> {total - failed}/{total} tests passed ({args.rtl})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
