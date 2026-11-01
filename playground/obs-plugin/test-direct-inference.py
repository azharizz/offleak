import os, subprocess, time
from pathlib import Path
p=Path('playground/.cache/direct-filter')
uid=os.getuid()
a=f'/tmp/offleak-direct-test-input-{uid}.sock'
b=f'/tmp/offleak-direct-test-output-{uid}.sock'
for x in (a,b):
 if os.path.lexists(x): raise SystemExit(f'occupied: {x}')
log=open(p/'real-worker.log','w')
worker=subprocess.Popen(['playground/.venv/bin/python','playground/obs-plugin/direct_worker.py','--input-socket',a,'--output-socket',b,'--delay','1','--fps','15'], stdout=log,stderr=subprocess.STDOUT)
try:
 for i in range(120):
  if os.path.exists(a) and os.path.exists(b): break
  if worker.poll() is not None: raise SystemExit(f'worker exited {worker.returncode}')
  time.sleep(.25)
 else: raise SystemExit('worker sockets not ready')
 env=dict(os.environ,OFFLEAK_DIRECT_LONG='1')
 with open(p/'real-harness.log','w') as output:
  result=subprocess.run([str(p/'test-direct-filter'),str(p/'offleak-direct-test.so')],env=env,stdout=output,stderr=subprocess.STDOUT,timeout=100)
 if result.returncode or worker.poll() is not None:
  raise RuntimeError(f'harness exit {result.returncode}; worker exit {worker.poll()}')
 samples = [line.split() for line in (p/'real-harness.log').read_text().splitlines() if line.startswith('sample ')]
 if not any(int(parts[1]) >= 240 and int(parts[2]) > 200 for parts in samples):
  raise AssertionError('real detector did not return the synthetic source to the filter')
 print('real detector processed synthetic source through direct filter: ok', flush=True)
finally:
 worker.terminate()
 try: worker.wait(timeout=10)
 except subprocess.TimeoutExpired: worker.kill(); worker.wait()
 log.close()
 for x in (a,b):
  if os.path.exists(x): os.unlink(x)
