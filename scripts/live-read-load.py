#!/usr/bin/env python3
"""Bounded GET-only capacity probe for the known live CT. Never sends OTP/SMS.

Runs on the CT against its verified private TLS origin. Open-loop arrivals have
a finite connection budget; dropped arrivals are reported, never hidden. Reports
contain timings/metadata, never bodies, cookies, phones or authentication keys.
"""
import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
import math
import os
from pathlib import Path
import queue
import re
import resource
import socket
import ssl
import statistics
import subprocess
import threading
import time
import uuid

ORIGIN = "192.168.1.123"
PREFIX = "begamnagam-internal-"
ALLOWED = {"/", "/help", "/privacy", "/profile", "/history", "/preferences", "/invitations", "/manage", "/r", "/healthz", "/api/v1/bootstrap", "/api/v1/messages", "/api/v1/operations/status", "/admin/login/", "/robots.txt", "/sitemap.xml", "/manifest.webmanifest"}
MIXED = ["/", "/help", "/", "/privacy", "/api/v1/bootstrap", "/api/v1/bootstrap", "/api/v1/bootstrap", "/api/v1/messages", "asset", "/"]
API_ONLY = ["/api/v1/bootstrap"] * 9 + ["/api/v1/messages"]
STAGES = [("load-5", 5, 40), ("load-15", 15, 40), ("load-30", 30, 60), ("stress-60", 60, 30), ("stress-100", 100, 30), ("stress-150", 150, 30), ("stress-225", 225, 30), ("stress-325", 325, 30), ("stress-450", 450, 30)]


def quantile(values, p):
    if not values:
        return None
    values = sorted(values)
    return round(values[max(0, math.ceil(len(values) * p) - 1)], 3)


def command(arguments, data=None):
    result = subprocess.run(arguments, input=data, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError("Metadata command failed; private diagnostics withheld")
    return result.stdout


def inspect_containers():
    # Ignore transient Compose `run --rm` helpers; only replacing/restarting a
    # real product service invalidates the fixed-service comparison.
    core = {PREFIX + service + "-1" for service in ["proxy", "frontend", "backend", "worker", "beat", "postgres", "redis", "rabbitmq"]}
    optional = {PREFIX + "frontend" + str(i) + "-1" for i in range(2, 7)}
    three = {PREFIX + service + "-1" for service in ["frontend2", "frontend3"]}
    present = set(command(["docker", "ps", "-a", "--format", "{{.Names}}", "--filter", "label=com.docker.compose.project=begamnagam-internal"]).decode().splitlines())
    assert core <= present, "A required product container is missing"
    assert (present & optional) in [set(), three, optional], "Incomplete frontend replica set"
    names = sorted(core | (present & optional))
    return json.loads(command(["docker", "inspect", *names]))


def counters(path):
    return {line.split()[0]: int(line.split()[1]) for line in path.read_text().splitlines()}


class Client:
    def __init__(self, context, sessions, transport="private-tls"):
        self.context, self.sessions, self.cookies, self.connections = context, sessions, {}, {}
        self.last_used = {}
        self.transport = transport

    def call(self, path, body=False):
        assert path in ALLOWED or re.fullmatch(r"/_next/static/[A-Za-z0-9_./-]+\.(?:js|css)", path)
        started = time.perf_counter()
        try:
            port = 443 if self.transport != "loopback" else (8000 if path.startswith(("/api/", "/admin/")) or path == "/healthz" else 3000)
            # Direct servers have short keepalive lifetimes (Gunicorn2s, Node
            # about5s). Evict idle sockets before reuse; a stale pool socket is
            # a client error, not a server capacity failure. No failed request
            # is retried, and HTTP/timeout errors remain visible.
            idle_budget = 60 if port == 443 else (1 if port == 8000 else 3)
            evicted = port in self.connections and started - self.last_used.get(port, 0) > idle_budget
            if evicted:
                self.connections.pop(port).close()
            if port not in self.connections:
                if self.transport == "public-edge":
                    connection = http.client.HTTPSConnection("begamnagam.ir", context=self.context, timeout=5)
                    # Keep the real hostname/SNI and certificate verification;
                    # route TCP to the existing LAN edge, never bypass TLS.
                    connection._create_connection = lambda address, timeout=5, source_address=None: socket.create_connection(("192.168.1.6", address[1]), timeout, source_address)
                    self.connections[port] = connection
                else:
                    self.connections[port] = http.client.HTTPSConnection(ORIGIN, context=self.context, timeout=5) if port == 443 else http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            connection = self.connections[port]
            headers = {"User-Agent": "BegamNagam-GET-only-capacity-probe/1.0", "Accept-Encoding": "gzip", "Accept": "*/*"}
            if self.transport == "loopback":
                # A diagnostic on the actual host's loopback, acting as the
                # trusted proxy. This is not a measurement of proxy/TLS/WAN.
                headers.update({"Host": "begamnagam.ir", "X-Forwarded-Proto": "https"})
            if self.cookies:
                headers["Cookie"] = "; ".join(k + "=" + v for k, v in self.cookies.items())
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            first_byte = time.perf_counter()
            raw = response.read(2 * 1024 * 1024 + 1)
            assert len(raw) <= 2 * 1024 * 1024
            self.last_used[port] = time.perf_counter()
            for key, value in response.getheaders():
                if key.lower() == "set-cookie":
                    parsed = SimpleCookie(); parsed.load(value)
                    for name, item in parsed.items():
                        if name in {"sessionid", "csrftoken"}:
                            self.cookies[name] = item.value
                            if name == "sessionid":
                                self.sessions.add(item.value)
            row = {"status": response.status, "ms": (time.perf_counter() - started) * 1000, "ttfb_ms": (first_byte - started) * 1000, "bytes": len(raw), "exception": None, "idle_socket_evicted": evicted}
            if body:
                row["body"] = gzip.decompress(raw) if response.getheader("Content-Encoding") == "gzip" else raw
                row["headers"] = dict((k.lower(), v) for k, v in response.getheaders() if k.lower() in {"content-type", "content-security-policy", "cache-control", "strict-transport-security", "x-frame-options"})
            return row
        except Exception as error:
            self.close()
            return {"status": 0, "ms": (time.perf_counter() - started) * 1000, "ttfb_ms": None, "bytes": 0, "exception": type(error).__name__}

    def close(self):
        for connection in self.connections.values(): connection.close()
        self.connections = {}; self.last_used = {}


class Probe:
    def __init__(self, args):
        self.args = args
        root_mount = next(line.split() for line in Path('/proc/mounts').read_text().splitlines() if line.split()[1] == '/')
        assert not {'ro', 'emergency_ro'} & set(root_mount[3].split(',')), 'Refusing live load: root filesystem is read-only; repair storage first'
        self.root = Path(args.output); self.root.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.context = ssl.create_default_context() if args.transport == "public-edge" else ssl.create_default_context(cafile=args.ca_file)
        self.sessions = set()
        self.capacity = args.max_inflight
        self.clients = [Client(self.context, self.sessions, args.transport) for _ in range(self.capacity)]
        self.available = queue.Queue()
        for client in self.clients: self.available.put(client)
        self.executor = ThreadPoolExecutor(max_workers=self.capacity)
        self.stop = threading.Event(); self.done = threading.Event(); self.lock = threading.Lock()
        self.recent = deque(maxlen=5000); self.rows = []; self.samples = []; self.phase_name = "idle"
        self.reason = None; self.catastrophic = False; self.asset = None
        self.initial = inspect_containers()
        assert all(row["State"]["Running"] and row["State"].get("Health", {}).get("Status") in {None, "healthy"} for row in self.initial)
        self.groups = {}
        for row in self.initial:
            relative = Path("/proc", str(row["State"]["Pid"]), "cgroup").read_text().strip().split("::", 1)[1]
            path = Path("/sys/fs/cgroup") / relative.lstrip("/")
            assert path.is_dir() and path.resolve().is_relative_to("/sys/fs/cgroup")
            self.groups[row["Name"].removeprefix("/").removeprefix(PREFIX).removesuffix("-1")] = {"path": path, "limit": row["HostConfig"]["Memory"], "oom": counters(path / "memory.events").get("oom_kill", 0)}
        self.started = time.perf_counter()
        self.metadata = {"started_utc": datetime.now(timezone.utc).isoformat(), "version": str(Path("/opt/begamnagam/current").resolve()), "effective_cpu_affinity": len(os.sched_getaffinity(0)), "cpu_max": Path("/sys/fs/cgroup/cpu.max").read_text().strip(), "memory_max": Path("/sys/fs/cgroup/memory.max").read_text().strip(), "proc_memtotal_kib": int(re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text()).group(1)), "generator_on_target": True, "network_scope": "private TLS via Traefik" if args.transport == "private-tls" else "HTTP loopback direct Next/Django; proxy/TLS excluded", "max_inflight": self.capacity, "arrival_model": "open-loop; bounded pool; dropped arrivals reported", "private_tls_verified": args.transport == "private-tls", "provider_endpoints_exercised": False, "authenticated_journey_exercised": False}
        self.metadata.update(probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), background="shared live CT; periodic and operator jobs can overlap")
        self.metadata.update(core_service_count=len(self.initial), selected_stages=selected_stages(args), slo_p95_ms=args.slo_p95_ms)
        if args.transport == "public-edge": self.metadata.update(network_scope="verified public-domain TLS via LAN central Nginx then CT; internet uplink excluded", tls_verified=True, edge_cpu_observed=False)

    def abort(self, reason, catastrophic=False):
        if catastrophic:
            self.catastrophic = True
        if not self.stop.is_set():
            self.reason = reason; self.stop.set()
            print(json.dumps({"event": "guard_stop", "phase": self.phase_name, "reason": reason}), flush=True)

    def monitor(self):
        previous, last, old_tool_cpu = {}, time.perf_counter(), time.process_time()
        root_cpu = counters(Path("/sys/fs/cgroup/cpu.stat"))["usage_usec"]
        health = Client(self.context, set(), self.args.transport); unhealthy = 0; latency_bad = 0; memory_bad = Counter(); tick = 0
        with (self.root / "metrics.jsonl").open("w") as output:
            while not self.done.wait(1):
                now = time.perf_counter(); delta = now - last
                sample = {"t": now - self.started, "phase": self.phase_name, "containers": {}}
                tool_cpu = time.process_time(); sample["generator_observer_cores"] = (tool_cpu - old_tool_cpu) / delta
                old_tool_cpu = tool_cpu
                current_root_cpu = counters(Path("/sys/fs/cgroup/cpu.stat"))["usage_usec"]
                sample["ct_total_cores"] = (current_root_cpu - root_cpu) / 1e6 / delta; root_cpu = current_root_cpu
                for name, config in self.groups.items():
                    p = config["path"]
                    try:
                        usage = counters(p / "cpu.stat")["usage_usec"]; raw_memory = int((p / "memory.current").read_text()); stats = counters(p / "memory.stat"); events = counters(p / "memory.events")
                    except OSError:
                        self.abort("container_cgroup_disappeared:" + name, True); continue
                    working = max(0, raw_memory - stats.get("inactive_file", 0))
                    sample["containers"][name] = {"cores": max(0, (usage - previous.get(name, usage)) / 1e6 / delta), "working_mib": working / 1024**2, "raw_mib": raw_memory / 1024**2, "limit_mib": config["limit"] / 1024**2, "oom_kill": events.get("oom_kill", 0)}
                    previous[name] = usage
                    if events.get("oom_kill", 0) > config["oom"]: self.abort("oom_kill:" + name, True)
                    memory_bad[name] = memory_bad[name] + 1 if working > config["limit"] * .90 else 0
                    if memory_bad[name] >= 3 and not (name == "proxy" and self.args.transport == "loopback"):
                        self.abort("working_memory_above_90_percent:" + name)
                with self.lock:
                    window = [r for r in self.recent if now - r["finished"] <= 10]
                if len(window) >= 20:
                    p95 = quantile([r["ms"] for r in window], .95)
                    sample["rolling_p95_ms"] = p95
                    errors = sum(not r["ok"] for r in window)
                    if errors / len(window) > .01: self.abort("unexpected_error_rate_above_1_percent")
                    latency_bad = latency_bad + 1 if p95 > 2000 else 0
                    if latency_bad >= 2: self.abort("rolling_p95_above_2000ms")
                output.write(json.dumps(sample) + "\n"); output.flush(); self.samples.append(sample); last = now
                tick += 1
                if tick % 5 == 0:
                    result = health.call("/healthz"); unhealthy = unhealthy + 1 if result["status"] != 200 else 0
                    if unhealthy >= 2: self.abort("two_failed_health_checks", True)
                if tick % 10 == 0:
                    current = inspect_containers()
                    if {r["Id"] for r in current} != {r["Id"] for r in self.initial} or any(r["RestartCount"] != next(x["RestartCount"] for x in self.initial if x["Id"] == r["Id"]) for r in current):
                        self.abort("container_changed_or_restarted", True)
        health.close()

    def smoke(self, label):
        client = Client(self.context, self.sessions, self.args.transport); result = []
        for path, expected in [("/", 200), ("/help", 200), ("/privacy", 200), ("/profile", 200), ("/manage", 200), ("/r", 200), ("/robots.txt", 200), ("/sitemap.xml", 200), ("/manifest.webmanifest", 200), ("/healthz", 200), ("/api/v1/bootstrap", 200), ("/api/v1/messages", 401), ("/api/v1/operations/status", 403), ("/admin/login/", 200)]:
            row = client.call(path, body=True)
            assert row["status"] == expected, "Smoke status mismatch for " + path
            if path == "/":
                self.asset = re.search(rb'(?:src|href)="(/_next/static/[^"]+\.(?:js|css))"', row["body"]).group(1).decode()
                assert "'nonce-" in row["headers"].get("content-security-policy", "")
            if path == "/api/v1/bootstrap":
                bootstrap = json.loads(row["body"]); assert bootstrap["demo_mode"] is False and bootstrap["otp_is_real"] is True and bootstrap["payment_backend"] == "disabled" and not bootstrap["authenticated"]
            result.append({"path": path, "status": row["status"], "ms": round(row["ms"], 3)})
        row = client.call(self.asset); assert row["status"] == 200
        result.append({"path": self.asset, "status": 200, "ms": round(row["ms"], 3)})
        client.close(); print(json.dumps({"event": label, "checks": len(result), "result": "PASS"}), flush=True)
        return result

    def request(self, client, path, scheduled, phase):
        started = time.perf_counter()
        row = client.call(path)
        row.update(path=path, phase=phase, lag_ms=(started - scheduled) * 1000, finished=time.perf_counter(), ok=row["status"] == (401 if path == "/api/v1/messages" else 200))
        with self.lock: self.rows.append(row); self.recent.append(row)
        self.available.put(client)

    def stage(self, label, rps, duration, paths):
        self.phase_name = label; self.recent.clear(); offset = len(self.rows); start = time.perf_counter(); deadline = start + duration; offered = dropped = 0
        print(json.dumps({"event": "stage_start", "phase": label, "rps": rps, "seconds": duration}), flush=True)
        while not self.stop.is_set():
            scheduled = start + offered / rps
            if scheduled >= deadline: break
            if time.perf_counter() < scheduled: self.stop.wait(scheduled - time.perf_counter())
            if self.stop.is_set(): break
            path = paths[offered % len(paths)]; path = self.asset if path == "asset" else path; offered += 1
            try: client = self.available.get_nowait()
            except queue.Empty: dropped += 1
            else: self.executor.submit(self.request, client, path, scheduled, label)
            if offered >= rps * 5 and dropped / offered > .05:
                self.abort("more_than_5_percent_arrivals_dropped_at_" + str(self.capacity) + "_inflight")
        ended = min(deadline, time.perf_counter()); active = ended - start
        while self.available.qsize() < self.capacity and time.perf_counter() - ended < 12: time.sleep(.05)
        if self.available.qsize() < self.capacity: self.abort("requests_not_drained_after_12_seconds", True)
        rows = [r for r in self.rows[offset:] if r["phase"] == label]; samples = [s for s in self.samples if s["phase"] == label]
        result = {"phase": label, "offered_rps": rps, "planned_seconds": duration, "active_seconds": round(active, 3), "offered": offered, "completed": len(rows), "dropped": dropped, "errors": sum(not r["ok"] for r in rows), "status_counts": dict(Counter(str(r["status"]) for r in rows)), "successful_rps_during_window": round(sum(r["ok"] and r["finished"] <= ended for r in rows) / active, 3), "p50_ms": quantile([r["ms"] for r in rows], .5), "p95_ms": quantile([r["ms"] for r in rows], .95), "p99_ms": quantile([r["ms"] for r in rows], .99), "schedule_lag_p95_ms": quantile([r["lag_ms"] for r in rows], .95), "response_mbps": round(sum(r["bytes"] for r in rows) * 8 / active / 1e6, 3), "stop_reason": self.reason if self.stop.is_set() else None, "containers": {}}
        # Safety guards stop harmful pressure; this stricter acceptance criterion
        # decides whether a completed observation qualifies for a soak candidate.
        # Zero drops is intentional: a saturated generator cannot prove capacity.
        result["slo_pass"] = bool(not result["stop_reason"] and active >= duration - .1 and len(rows) == offered and dropped == 0 and result["errors"] == 0 and result["p95_ms"] is not None and result["p95_ms"] <= self.args.slo_p95_ms and result["schedule_lag_p95_ms"] <= 10)
        for name in self.groups:
            series = [s["containers"][name] for s in samples if name in s["containers"]]
            if series: result["containers"][name] = {"mean_cores": round(statistics.mean(s["cores"] for s in series), 4), "peak_cores": round(max(s["cores"] for s in series), 4), "peak_working_mib": round(max(s["working_mib"] for s in series), 2), "limit_mib": series[0]["limit_mib"]}
        result["generator_observer_peak_cores"] = round(max((s["generator_observer_cores"] for s in samples), default=0), 4)
        result["ct_peak_cores"] = round(max((s["ct_total_cores"] for s in samples), default=0), 4)
        result["by_path"] = {path: {"completed": len(group), "errors": sum(not r["ok"] for r in group), "p50_ms": quantile([r["ms"] for r in group], .5), "p95_ms": quantile([r["ms"] for r in group], .95)} for path in sorted(set(r["path"] for r in rows)) for group in [[r for r in rows if r["path"] == path]]}
        print(json.dumps({"event": "stage_result", **{k:v for k,v in result.items() if k not in {"containers", "by_path"}}}), flush=True)
        (self.root / (label + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        return result

    def recovery(self):
        self.phase_name = "recovery"; time.sleep(20)
        health = Client(self.context, set(), self.args.transport); checks = [health.call("/healthz")["status"] for _ in range(3)]; health.close()
        assert checks == [200] * 3, "Health did not recover"
        return checks

    def cleanup_sessions(self):
        script = """import django,json,sys;django.setup()
from django.contrib.sessions.models import Session
keys=json.load(sys.stdin)
rows=Session.objects.filter(session_key__in=keys)
assert all('_auth_user_id' not in row.get_decoded() for row in rows)
count=rows.count();rows.delete();print(json.dumps({'own_anonymous_sessions_removed':count}))
"""
        return json.loads(command(["docker", "exec", "-i", PREFIX + "backend-1", "python", "-c", script], json.dumps(sorted(self.sessions)).encode()))

    def run(self):
        def watch():
            try: self.monitor()
            except Exception as error: self.abort("monitoring_failed:" + type(error).__name__, True)
        output = {"metadata": self.metadata, "stages": []}; thread = threading.Thread(target=watch, daemon=True); thread.start()
        try:
            output["smoke_before"] = self.smoke("smoke_before")
            self.phase_name = "warmup"
            for client in self.clients:
                row = client.call("/api/v1/bootstrap"); assert row["status"] == 200
            self.phase_name = "idle_baseline"; time.sleep(20)
            for label, rps, seconds in selected_stages(self.args):
                output["stages"].append(self.stage(label, rps, seconds, MIXED))
                if self.stop.is_set(): break
                self.phase_name = "between_stages"; time.sleep(3)
            output["mixed_stop_reason"] = self.reason
            output["recovery_after_mixed"] = self.recovery()
            if not self.catastrophic and not self.args.skip_api:
                self.stop.clear(); self.reason = None; self.recent.clear()
                for rps in [25, 75, 150, 250]:
                    output["stages"].append(self.stage("api-" + str(rps), rps, 30, API_ONLY))
                    if self.stop.is_set(): break
                    self.phase_name = "between_stages"; time.sleep(3)
                output["api_stop_reason"] = self.reason
                output["recovery_after_api"] = self.recovery()
            output["smoke_after"] = self.smoke("smoke_after")
        finally:
            self.executor.shutdown(wait=True)
            for client in self.clients: client.close()
            self.done.set(); thread.join(timeout=8)
            try: output["session_cleanup"] = self.cleanup_sessions()
            except Exception as error: output["session_cleanup_error"] = type(error).__name__
            after = inspect_containers()
            output["containers_unchanged"] = {r["Id"] for r in after} == {r["Id"] for r in self.initial}
            output["restart_delta"] = sum(r["RestartCount"] - next(x["RestartCount"] for x in self.initial if x["Id"] == r["Id"]) for r in after if r["Id"] in {x["Id"] for x in self.initial})
            output["healthy_after"] = all(r["State"]["Running"] and r["State"].get("Health", {}).get("Status") in {None, "healthy"} for r in after)
            output["completed_utc"] = datetime.now(timezone.utc).isoformat()
            for row in self.rows: row["finished"] = round(row["finished"] - self.started, 6)
            with (self.root / "requests.jsonl").open("w") as target:
                for row in self.rows: target.write(json.dumps(row) + "\n")
            (self.root / "summary.json").write_text(json.dumps(output, indent=2) + "\n")
            print(json.dumps({"event": "finished", "stages": len(output["stages"]), "healthy_after": output["healthy_after"], "restart_delta": output["restart_delta"]}), flush=True)


def selected_stages(args):
    if args.rates:
        return [("custom-" + str(rate), rate, args.stage_seconds or 60) for rate in args.rates]
    stages = STAGES if args.stages == "all" else [stage for stage in STAGES if stage[0].startswith("stress-")]
    return [(label, rate, args.stage_seconds or seconds) for label, rate, seconds in stages]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ack-live-get-only", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--ca-file", default="/opt/begamnagam/shared/root.crt")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--transport", choices=["private-tls", "loopback", "public-edge"], default="private-tls")
    parser.add_argument("--max-inflight", type=int, default=32)
    parser.add_argument("--stages", choices=["all", "stress-only"], default="all")
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--rates", help="Explicit comma-separated GET arrival rates, 1..2000; overrides --stages")
    parser.add_argument("--stage-seconds", type=int, help="Duration of each mixed stage, 10..3600; use a single rate for a soak")
    parser.add_argument("--slo-p95-ms", type=int, default=500, help="Acceptance SLO; safety stop remains at 2000ms")
    args = parser.parse_args()
    try:
        args.rates = [int(item) for item in args.rates.split(",")] if args.rates else None
    except ValueError:
        parser.error("--rates must be comma-separated integers")
    if args.rates and (len(set(args.rates)) != len(args.rates) or not all(1 <= rate <= 2000 for rate in args.rates)):
        parser.error("--rates must contain unique rates in 1..2000")
    if args.stage_seconds is not None and not 10 <= args.stage_seconds <= 3600:
        parser.error("--stage-seconds must be 10..3600")
    if not 1 <= args.max_inflight <= 256: parser.error("Connection budget must be 1..256")
    if not 1 <= args.slo_p95_ms <= 2000: parser.error("--slo-p95-ms must be 1..2000")
    if args.plan:
        print(json.dumps({"method": "GET only", "transport": args.transport, "mixed": MIXED, "stages": selected_stages(args), "max_inflight": args.max_inflight, "skip_api": args.skip_api, "slo_p95_ms": args.slo_p95_ms, "stops": ["p95>2s", "errors>1%", "memory>90%", "OOM/restart", "health failures", "dropped arrivals>5%"]}, indent=2));return
    if not args.ack_live_get_only: parser.error("Explicit --ack-live-get-only required")
    Probe(args).run()


if __name__ == "__main__":
    main()
