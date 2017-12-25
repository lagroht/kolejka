# vim:ts=4:sts=4:sw=4:expandtab

import copy
import datetime
import dateutil.parser
import glob
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from kolejka.common.settings import OBSERVER_SOCKET, TASK_SPEC, RESULT_SPEC, WORKER_HOSTNAME, WORKER_REPOSITORY, WORKER_DIRECTORY
from kolejka.common import KolejkaTask, KolejkaResult
from kolejka.common import ControlGroupSystem

def silent_call(*args, **kwargs):
    kwargs['stdin'] = kwargs.get('stdin', subprocess.DEVNULL)
    kwargs['stdout'] = kwargs.get('stderr', subprocess.DEVNULL)
    kwargs['stderr'] = kwargs.get('stdout', subprocess.DEVNULL)
    return subprocess.run(*args, **kwargs)

def stage0(task_path, result_path, temp_path=None, consume_task_folder=False):
    cgs = ControlGroupSystem()
    task = KolejkaTask(task_path)
    if not task.id:
        task.id = uuid.uuid4().hex
        logging.warning('Assigned id {} to the task'.format(task.id))
    if not task.image:
        logging.error('Task does not define system image')
        sys.exit(1)
    if not task.args:
        logging.error('Task does not define args')
        sys.exit(1)
    if not task.files.is_local:
        logging.error('Task contains non-local files')
        sys.exit(1)
#TODO: sanitize limits (enforce some sensible limits)

    docker_task = 'kolejka_worker_{}'.format(task.id)

    docker_cleanup  = [
        [ 'docker', 'kill', docker_task ],
        [ 'docker', 'rm', docker_task ],
    ]

    with tempfile.TemporaryDirectory(dir=temp_path) as jailed_path:
#TODO jailed_path size remains unlimited
        logging.debug('Using {} as temporary directory'.format(jailed_path))
        jailed_task_path = os.path.join(jailed_path, 'task')
        os.makedirs(jailed_task_path, exist_ok=True)
        jailed_result_path = os.path.join(jailed_path, 'result')
        os.makedirs(jailed_result_path, exist_ok=True)

        jailed = KolejkaTask(os.path.join(jailed_path, 'task'))
        jailed.load(task.dump())
        jailed.files.clear()
        volumes = list()
        if os.path.exists(OBSERVER_SOCKET):
            volumes.append((OBSERVER_SOCKET, OBSERVER_SOCKET, 'rw'))
        volumes.append((jailed_result_path, os.path.join(WORKER_DIRECTORY, 'result'), 'rw'))
        for key, val in task.files.items():
            if key != TASK_SPEC:
                src_path = os.path.join(task.path, val.path)
                dst_path = os.path.join(jailed_path, 'task', key)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                if consume_task_folder:
                    shutil.move(src_path, dst_path)
                else:
                    shutil.copy(src_path, dst_path)
                jailed.files.add(key)
        jailed.files.add(TASK_SPEC)
        jailed.commit()
        volumes.append((jailed.path, os.path.join(WORKER_DIRECTORY, 'task'), 'rw'))
        if consume_task_folder:
            shutil.rmtree(task_path)
        for spath in [ os.path.dirname(__file__) ]:
            stage1 = os.path.join(spath, 'stage1.sh')
            if os.path.isfile(stage1):
                volumes.append((stage1, os.path.join(WORKER_DIRECTORY, 'stage1.sh'), 'ro'))
                break
        for spath in [ os.path.dirname(__file__) ]:
            stage2 = os.path.join(spath, 'stage2.py')
            if os.path.isfile(stage2):
                volumes.append((stage2, os.path.join(WORKER_DIRECTORY, 'stage2.py'), 'ro'))
                break

        docker_call  = [ 'docker', 'run' ]
        docker_call += [ '--detach' ]
        docker_call += [ '--name', docker_task ]
        docker_call += [ '--entrypoint', os.path.join(WORKER_DIRECTORY, 'stage1.sh') ]
        for key, val in task.environment.items():
            docker_call += [ '--env', '{}={}'.format(key, val) ]
        docker_call += [ '--hostname', WORKER_HOSTNAME ]
        docker_call += [ '--init' ]
        if task.limits.cpus is not None:
            docker_call += [ '--cpuset-cpus', ','.join([str(c) for c in cgs.limited_cpuset(cgs.full_cpuset(), task.limits.cpus, task.limits.cpus_offset)]) ]
        if task.limits.memory is not None:
            docker_call += [ '--memory', str(task.limits.memory) ]
        if task.limits.storage is not None:
            docker_call += [ '--storage-opt', 'size='+str(task.limits.storage) ]
        if task.limits.network is not None:
            if not task.limits.network:
                docker_call += [ '--network=none' ]
        docker_call += [ '--memory-swap', str(0) ]
        docker_call += [ '--cap-add', 'SYS_NICE' ]
        if task.limits.pids is not None:
            docker_call += [ '--pids-limit', str(task.limits.pids) ]
        if task.limits.time is not None:
            docker_call += [ '--stop-timeout', str(int(math.ceil(task.limits.time.total_seconds()))) ]
        for v in volumes:
            docker_call += [ '--volume', '{}:{}:{}'.format(os.path.realpath(v[0]), v[1], v[2]) ]
        docker_call += [ '--workdir', WORKER_DIRECTORY ]
        docker_call += [ WORKER_REPOSITORY.rstrip('/')+ '/' + task.image ]
        docker_call += [ '--debug' ]
        docker_call += [ '/opt/kolejka/task' ]
        docker_call += [ '/opt/kolejka/result' ]
        logging.debug('Docker call : {}'.format(docker_call))

        for docker_clean in docker_cleanup:
            silent_call(docker_clean)

        if os.path.exists(result_path):
            shutil.rmtree(result_path)
        os.makedirs(result_path, exist_ok=True)
        result = KolejkaResult(result_path)
        result.id = task.id
        result.limits = task.limits
        result.stdout = task.stdout
        result.stderr = task.stderr

        start_time = datetime.datetime.now()
        docker_run = subprocess.run(docker_call, stdout=subprocess.PIPE)
        cid = str(docker_run.stdout, 'utf-8').strip()
        logging.debug('Started container {}'.format(cid))

        while True:
            docker_state_run = subprocess.run(['docker', 'inspect', '--format', '{{json .State}}', cid], stdout=subprocess.PIPE)
            state = json.loads(str(docker_state_run.stdout, 'utf-8'))
            try:
                result.stats.update(cgs.name_stats(cid))
            except:
                pass
            time.sleep(0.1)
            if not state['Running']:
                result.result = state['ExitCode']
                try:
                    result.stats.time = dateutil.parser.parse(state['FinishedAt']) - dateutil.parser.parse(state['StartedAt'])
                except:
                    results.stats.time = None
                break
        subprocess.run(['docker', 'logs', cid], stdout=subprocess.PIPE)

        stop_time = datetime.datetime.now()
        if result.stats.time is None:
            result.stats.time = stop_time - start_time
        result.stats.pids.usage = None
        result.stats.memory.usage = None


        for dirpath, dirnames, filenames in os.walk(jailed_result_path):
            for filename in filenames:
                abspath = os.path.join(dirpath, filename)
                realpath = os.path.realpath(abspath)
                if realpath.startswith(os.path.realpath(jailed_result_path)+'/'):
                    relpath = abspath[len(jailed_result_path)+1:]
                    if relpath != RESULT_SPEC:
                        destpath = os.path.join(result.path, relpath)
                        os.makedirs(os.path.dirname(destpath), exist_ok=True)
                        shutil.move(realpath, destpath)
                        result.files.add(relpath)
                        print('#### * *')
                        print('#  '+relpath)
                        print('#### * *')
                        print()
                        with open(destpath, 'r') as file_file:
                            print(file_file.read())
        result.commit()
        os.chmod(result.spec_path, 0o640)
        print('#### * *')
        print('#  '+RESULT_SPEC)
        print('#### * *')
        print()
        with open(result.spec_path, 'r') as file_file:
            print(file_file.read())

        for docker_clean in docker_cleanup:
            silent_call(docker_clean)

        #cgs.name_close(docker_task) #THIS CLEANS CGROUPS AND WORKS FOR ROOT USER ONLY

def execute(args):
    stage0(args.task, args.result, temp_path=args.temp, consume_task_folder=args.consume)

def config_parser(parser):
    parser.add_argument("task", type=str, help='task folder')
    parser.add_argument("result", type=str, help='result folder')
    parser.add_argument("--temp", type=str, help='temp folder')
    parser.add_argument("--consume", action="store_true", default=False, help='consume task folder') 
    parser.set_defaults(execute=execute)

def main():
    import argparse
    import logging

    parser = argparse.ArgumentParser(description='KOLEJKA worker')
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help='show more info')
    parser.add_argument("-d", "--debug", action="store_true", default=False, help='show debug info')
    config_parser(parser)
    args = parser.parse_args()
    level = logging.WARNING
    if args.verbose:
        level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    logging.basicConfig(level=level)
    args.execute(args)

if __name__ == '__main__':
    main()
