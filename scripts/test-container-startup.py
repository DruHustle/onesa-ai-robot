"""Actual image CMD/nonroot/port/authentication/shutdown using synthetic settings."""
import argparse
import json
import subprocess
import time
import uuid
parser = argparse.ArgumentParser()
parser.add_argument('image')
args = parser.parse_args()
def docker(*values,check=True):
 return subprocess.run(['docker',*values],check=check,text=True,capture_output=True).stdout.strip()
image = json.loads(docker('image','inspect',args.image))[0]['Config']
assert image['User'] == 'onesa'
assert image['Cmd'] == ['sh','/app/start.sh']
hash_value = docker('run','--rm','--entrypoint','python',args.image,'-c',"from robot_api.security import password_hash; print(password_hash('container-test-only-operator'))")
name='onesa-robot-startup-'+uuid.uuid4().hex[:12]
try:
 docker('run','-d','--name',name,'-e','PORT=10000','-e','ROBOT_OPERATOR_PASSWORD_HASH='+hash_value,args.image)
 for _ in range(40):
  probe=subprocess.run(['docker','exec',name,'python','-c',"import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:10000/api/v1/ready').status==200"],capture_output=True)
  if not probe.returncode:break
  time.sleep(.25)
 else:raise AssertionError('Image command did not become ready at assigned PORT')
 docker('exec',name,'python','-c',"import urllib.request,urllib.error; r=urllib.request.urlopen('http://127.0.0.1:10000/api/v1/health'); assert r.status==200\ntry: urllib.request.urlopen('http://127.0.0.1:10000/api/v1/status')\nexcept urllib.error.HTTPError as e: assert e.code==401\nelse: raise AssertionError('Unauthenticated state was exposed')")
 docker('stop','-t','10',name)
 assert docker('inspect','-f','{{.State.ExitCode}}',name)=='0'
finally:docker('rm','-f',name,check=False)
print('PASS: image nonroot/CMD/PORT/liveness/readiness/private status/SIGTERM')
