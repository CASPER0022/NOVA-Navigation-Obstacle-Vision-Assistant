"""Summarize the CSV logs written by metrics_logger.MetricsLogger.

Usage:
    python analyze_metrics.py [--log-dir logs] [--json]
    python analyze_metrics.py --compare logs_before logs_after

See metrics_plan.md for what each metric means and how it's collected.
"""
import argparse
import csv
import json
import os
import statistics
import sys


def _read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def summarize(log_dir):
    """Compute summary stats from a metrics log directory. Returns a JSON-able dict."""
    latency_rows = _read_rows(os.path.join(log_dir, "alert_latency.csv"))
    tts_rows = _read_rows(os.path.join(log_dir, "tts_events.csv"))
    fps_rows = _read_rows(os.path.join(log_dir, "fps.csv"))

    summary = {"log_dir": log_dir}

    latencies = [float(r["latency_sec"]) for r in latency_rows]
    inference_durations = [float(r["inference_duration_sec"]) for r in latency_rows]
    summary["alert_latency"] = {
        "count": len(latencies),
        "mean_sec": statistics.mean(latencies) if latencies else None,
        "p50_sec": _percentile(latencies, 50),
        "p95_sec": _percentile(latencies, 95),
        "max_sec": max(latencies) if latencies else None,
        "mean_inference_duration_sec": statistics.mean(inference_durations) if inference_durations else None,
    }

    attempts = sum(1 for r in tts_rows if r["event_type"] == "attempt")
    successes = sum(1 for r in tts_rows if r["event_type"] == "success")
    errors = sum(1 for r in tts_rows if r["event_type"] == "error")
    summary["tts"] = {
        "attempts": attempts,
        "successes": successes,
        "errors": errors,
        "failure_rate": (errors / attempts) if attempts else None,
    }

    fps_values = [float(r["fps"]) for r in fps_rows]
    summary["fps"] = {
        "samples": len(fps_values),
        "mean": statistics.mean(fps_values) if fps_values else None,
        "min": min(fps_values) if fps_values else None,
        "max": max(fps_values) if fps_values else None,
    }

    return summary


def _fmt(value, suffix="", digits=3):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}{suffix}"


def print_report(summary):
    print(f"Metrics summary for: {summary['log_dir']}")
    print()

    lat = summary["alert_latency"]
    print(f"Alert latency (n={lat['count']}):")
    print(f"  mean:      {_fmt(lat['mean_sec'], 's')}")
    print(f"  p50:       {_fmt(lat['p50_sec'], 's')}")
    print(f"  p95:       {_fmt(lat['p95_sec'], 's')}")
    print(f"  max:       {_fmt(lat['max_sec'], 's')}")
    print(f"  mean inference duration: {_fmt(lat['mean_inference_duration_sec'], 's')}")
    print()

    tts = summary["tts"]
    print(f"TTS reliability:")
    print(f"  attempts:  {tts['attempts']}")
    print(f"  successes: {tts['successes']}")
    print(f"  errors:    {tts['errors']}")
    print(f"  failure rate: {_fmt(tts['failure_rate'], '', 4) if tts['failure_rate'] is not None else 'n/a'}")
    print()

    fps = summary["fps"]
    print(f"Display FPS (n={fps['samples']}):")
    print(f"  mean: {_fmt(fps['mean'], '', 1)}")
    print(f"  min:  {_fmt(fps['min'], '', 1)}")
    print(f"  max:  {_fmt(fps['max'], '', 1)}")


def print_comparison(before, after):
    def delta(b, a):
        if b is None or a is None:
            return "n/a"
        d = a - b
        sign = "+" if d >= 0 else ""
        return f"{sign}{d:.3f}"

    print(f"Comparing {before['log_dir']} (before) -> {after['log_dir']} (after)")
    print()

    b_lat, a_lat = before["alert_latency"], after["alert_latency"]
    print("Alert latency:")
    print(f"  mean:  {_fmt(b_lat['mean_sec'], 's')} -> {_fmt(a_lat['mean_sec'], 's')}  (delta {delta(b_lat['mean_sec'], a_lat['mean_sec'])}s)")
    print(f"  p95:   {_fmt(b_lat['p95_sec'], 's')} -> {_fmt(a_lat['p95_sec'], 's')}  (delta {delta(b_lat['p95_sec'], a_lat['p95_sec'])}s)")
    print()

    b_tts, a_tts = before["tts"], after["tts"]
    b_rate = b_tts["failure_rate"]
    a_rate = a_tts["failure_rate"]
    print("TTS failure rate:")
    b_rate_s = _fmt(b_rate, "", 4) if b_rate is not None else "n/a"
    a_rate_s = _fmt(a_rate, "", 4) if a_rate is not None else "n/a"
    print(f"  {b_rate_s} -> {a_rate_s}  (delta {delta(b_rate, a_rate)})")
    print()

    b_fps, a_fps = before["fps"], after["fps"]
    print("Mean FPS:")
    print(f"  {_fmt(b_fps['mean'], '', 1)} -> {_fmt(a_fps['mean'], '', 1)}  (delta {delta(b_fps['mean'], a_fps['mean'])})")


def main():
    parser = argparse.ArgumentParser(description="Summarize NOVA metrics logs (see metrics_plan.md).")
    parser.add_argument("--log-dir", default="logs", help="Directory of metrics CSVs (default: logs)")
    parser.add_argument("--compare", metavar="AFTER_DIR",
                         help="Compare --log-dir (treated as 'before') against this directory ('after')")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a text report")
    args = parser.parse_args()

    if not os.path.isdir(args.log_dir):
        print(f"error: log directory not found: {args.log_dir}", file=sys.stderr)
        sys.exit(1)

    if args.compare:
        if not os.path.isdir(args.compare):
            print(f"error: log directory not found: {args.compare}", file=sys.stderr)
            sys.exit(1)
        before = summarize(args.log_dir)
        after = summarize(args.compare)
        if args.json:
            print(json.dumps({"before": before, "after": after}, indent=2))
        else:
            print_comparison(before, after)
        return

    summary = summarize(args.log_dir)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_report(summary)


if __name__ == "__main__":
    main()
