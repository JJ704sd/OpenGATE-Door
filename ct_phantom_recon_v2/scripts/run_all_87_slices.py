"""
run_all_87_slices.py  ——  全 87 切片 03-04-05-06 完整流程 (v2: 文件 log + status)
用法: D:\OpenGATE\env\python.exe scripts/run_all_87_slices.py [start_z] [end_z]
"""
import os
import sys
import subprocess
import time
import json
import warnings
warnings.filterwarnings("ignore")

base_dir = r"D:\OpenGATE\ct_phantom_recon_v2"
PY = r"D:\OpenGATE\env\python.exe"
SCRIPTS = ["03_proj_simulate.py", "04_reconstruct.py", "05_postprocess.py", "06_evaluate.py"]

# log + status 文件
LOG_FILE = os.path.join(base_dir, "output", "real_ct", "87_run.log")
STATUS_FILE = os.path.join(base_dir, "output", "real_ct", "87_run_status.json")

# 命令行参数: start_z end_z
start_z = int(sys.argv[1]) if len(sys.argv) > 1 else 0
end_z = int(sys.argv[2]) if len(sys.argv) > 2 else 87

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(msg):
    """写一行到 log 文件 + flush, 不走 stdout (避免 PowerShell pipe buffer 满)"""
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()

def write_status(state):
    """写 status JSON (current Z, done count, fail count, last_update)"""
    state["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
    state["pid"] = os.getpid()
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.flush()

log(f"=== run_all_87_slices.py start (Z={start_z}..{end_z-1}, PID={os.getpid()}) ===")
log(f"Python: {PY}")
log(f"Log: {LOG_FILE}")

t_start = time.time()
n_ok = 0
n_skip = 0  # 已存在的
n_fail = 0
fails = []

# 先看哪些 Z 已有 metrics_z<Z>.json, skip
existing = set()
for z in range(start_z, end_z):
    p = os.path.join(base_dir, "output", "real_ct", "06_eval", f"metrics_z{z:03d}.json")
    if os.path.exists(p):
        existing.add(z)
        n_skip += 1
log(f"Skip {n_skip} already-done Z: {sorted(existing)[:10]}{'...' if len(existing)>10 else ''}")

# 跑剩下
todo = [z for z in range(start_z, end_z) if z not in existing]
log(f"Todo {len(todo)} Z: {todo[:10]}{'...' if len(todo)>10 else ''}")

write_status({
    "state": "running",
    "start_z": start_z,
    "end_z": end_z,
    "done": list(existing),
    "todo": todo,
    "fails": [],
    "elapsed_sec": 0,
    "eta_sec": 0,
})

for i, z in enumerate(todo):
    z_t = time.time()
    env = os.environ.copy()
    env["Z_IDX"] = str(z)
    env["PYTHONUNBUFFERED"] = "0"  # 不必, 反正没 stdout

    z_ok = True
    fail_msg = ""
    for script in SCRIPTS:
        try:
            r = subprocess.run(
                [PY, os.path.join(base_dir, "scripts", script)],
                cwd=base_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if r.returncode != 0:
                z_ok = False
                fail_msg = f"{script} exit={r.returncode}: {r.stderr[-300:]}"
                break
        except subprocess.TimeoutExpired:
            z_ok = False
            fail_msg = f"{script} TIMEOUT 600s"
            break
        except Exception as e:
            z_ok = False
            fail_msg = f"{script} ERROR: {str(e)[:200]}"
            break

    dt = time.time() - z_t
    elapsed = time.time() - t_start
    n_done = n_skip + i + (1 if z_ok else 0)
    avg = elapsed / max(1, i + 1)
    eta = avg * (len(todo) - i - 1)

    status = "OK" if z_ok else "FAIL"
    log(f"[{i+1:>2}/{len(todo)}] Z={z:03d} {status}  ({dt:.1f}s, 总 {elapsed:.0f}s, ETA {eta:.0f}s)")

    if z_ok:
        n_ok += 1
    else:
        n_fail += 1
        fails.append({"z": z, "error": fail_msg})
        log(f"  → 失败: {fail_msg[:200]}")

    write_status({
        "state": "running",
        "start_z": start_z,
        "end_z": end_z,
        "done": list(existing) + [tz for tz in todo[:i+1] if tz not in existing and (z_ok or tz < z)],
        "todo": todo[i+1:],
        "fails": fails,
        "elapsed_sec": round(elapsed, 1),
        "eta_sec": round(eta, 1),
    })

total = time.time() - t_start
log(f"=== 完成: 成功 {n_ok}, 失败 {n_fail}, 总耗时 {total:.1f}s ({total/60:.1f} min) ===")

fail_zs = {f["z"] for f in fails}
done_zs = sorted(existing | {z for z in todo if z not in fail_zs})
write_status({
    "state": "done",
    "start_z": start_z,
    "end_z": end_z,
    "done": done_zs,
    "todo": [],
    "fails": fails,
    "elapsed_sec": round(total, 1),
    "eta_sec": 0,
})

if fails:
    log(f"失败列表: {[(f['z'], f['error'][:80]) for f in fails]}")
    sys.exit(1)
