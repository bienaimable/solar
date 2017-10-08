#!/usr/bin/python3
import attr
import sh
import os
import logging
import yaml
import time
import re
import pathlib
#logging.basicConfig(filename="moon.log", level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

@attr.s
class Stack:
    name = attr.ib()
    compose_filename = attr.ib(default=None)
    def deploy(self):
        logger.debug("Deploying stack {n} from compose file {c}".format(n=self.name, c=self.compose_filename))
        logger.debug(sh.docker.stack.deploy("-c", self.compose_filename, self.name))
    def remove(self):
        logger.debug("Removing stack {n}".format(n=self.name))
        logger.debug(sh.docker.stack.rm(self.name))
    def update(self):
        logger.debug("Updating stack {n}".format(n=self.name))
        services = yaml.load(open(self.compose_filename))['services']
        for service in services:
            logger.debug(sh.docker.service.update(self.name+'_'+service, '--detach=false'))

@attr.s
class Folder():
    path = attr.ib()
    def delete(self):
        logger.debug("Deleting folder {p}".format(p=self.path))
        sh.rm("-r", self.path)
    def exists(self):
        return(os.path.isdir(self.path))

@attr.s
class Repository():
    folder = attr.ib()
    url = attr.ib()
    branch = attr.ib(default="master")
    def clone(self):
        logger.debug("Cloning from {u}".format(u=self.url))
        git = sh.git.bake(_cwd=str(pathlib.Path(self.folder.path).parent))
        git.clone("--depth", 
                  "1", 
                  "-b", 
                  self.branch, 
                  self.url, 
                  self.folder.path)
    def uptodate(self):
        git = sh.git.bake(_cwd=self.folder.path)
        git.fetch()
        return "is up-to-date" in git.status()

@attr.s
class Docker:
    tmp_folder = attr.ib(default="/tmp/moon-configuration/")
    def get_running_stacks(self):
        running_stacks = re.sub(
            r'\s+.*\n', 
            '\n',
            str(sh.docker.stack.ls())
        ).split()
        running_stacks.remove("NAME")
        return [Stack(x) for x in running_stacks]
    def build(self, compose_filename):
        logger.debug("Checking for build steps in {c}".format(c=compose_filename))
        services = yaml.load(open(os.path.join(self.tmp_folder, compose_filename)))['services']
        for service_name, service in services.items():
            logger.debug("Checking for build step for {s}".format(s=service_name))
            if 'build' in service:
                logger.debug("Build step found")
                args = ["-t", service['image']]
                if type(service['build']) is str:
                    args.append(service['build'])
                else:
                    args.append(service['build']['context'])
                    if 'dockerfile' in service['build']:
                        args.extend([ "-f", service['build']['dockerfile'] ])
                    if 'args' in service['build']:
                        args.extend([ "--build-arg", '"'+" ".join(service['build']['args'])+'"' ])
                logger.debug("Build {a}".format(a=args))
                logger.debug(sh.docker.build(args))
                logger.debug(sh.docker.push(service['image']))
    def sync(self, url, branch="master", stacks_filename="moon-stacks.yml"):
        logger.debug("Syncing Docker stacks from {f} in {url}".format(f=stacks_filename, url=url))
        tmp_folder = Folder(self.tmp_folder)
        if tmp_folder.exists(): tmp_folder.delete()
        repo = Repository(tmp_folder, url=url, branch=branch)
        repo.clone()
        running_stacks = self.get_running_stacks()
        desired_stacks = yaml.load(
            open(os.path.join(tmp_folder.path, stacks_filename))
        )['stacks'] or {}
        undesired_stacks = [x for x in running_stacks if x.name not in desired_stacks]
        for stack in undesired_stacks: stack.remove()
        for name, compose_filename in desired_stacks.items():
            self.build(compose_filename)
            stack = Stack(name, os.path.join(self.tmp_folder, compose_filename))
            stack.deploy()
            #stack.update() # Removed because unnecessary

if __name__ == "__main__":
    docker = Docker()
    while True:
        branch = os.environ.get('MOON_BRANCH') or 'master'
        docker.sync(os.environ['MOON_REPO'], branch=branch)
        cycle_time = os.environ.get('MOON_CYCLE') or '60'
        logger.debug("Waiting {} seconds before next check".format(cycle_time))
        time.sleep(int(cycle_time))
