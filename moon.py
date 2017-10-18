#!/usr/bin/python3
import attr
import sh
import os
import logging
import yaml
import time
import re
import pathlib
import sys
from autologging import traced, logged, TRACE

logging.basicConfig(level=TRACE, stream=sys.stdout,
    format="%(levelname)s:%(name)s:%(funcName)s:%(message)s")



@traced
@attr.s
@logged
class Stack:
    name = attr.ib()
    compose_filename = attr.ib(default=None)

    def deploy(self):
        stdout = sh.docker.stack.deploy("-c", self.compose_filename, self.name)

    def remove(self):
        sh.docker.stack.rm(self.name)



@traced
@attr.s
@logged
class Folder():
    path = attr.ib()

    def delete(self):
        sh.rm("-r", self.path)

    def exists(self):
        return(os.path.isdir(self.path))



@traced
@attr.s
@logged
class Repository():
    folder = attr.ib()
    url = attr.ib()
    branch = attr.ib(default="master")

    def clone(self):
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



@traced
@attr.s
@logged
class Docker:
    tmp_folder_path = attr.ib(default="/tmp/moon-configuration/")
    stacks_filename = attr.ib(default="moon-stacks.yml")

    def __attrs_post_init__(self):
        self.tmp_folder = Folder(self.tmp_folder_path)

    def get_running_stacks(self):
        running_stacks = re.sub(
            r'\s+.*\n', 
            '\n',
            str(sh.docker.stack.ls())
        ).split()
        running_stacks.remove("NAME")
        return [Stack(x) for x in running_stacks]

    def get_running_networks(self):
        running_networks = re.sub(
            r'\s+.*\n', 
            '\n',
            str(sh.docker.network.ls())
        ).split()
        running_stacks.remove("NAME")
        return [Stack(x) for x in running_stacks]

    def build(self, options, image_name):
        args = ["-t", image_name]
        if type(options) is str:
            args.append(options)
        else:
            args.append(options['context'])
            if 'dockerfile' in options:
                args.extend([ "-f", options['dockerfile'] ])
            if 'args' in options:
                args.extend([ "--build-arg", '"'+" ".join(options['args'])+'"' ])
        sh.docker.build(args)

    def compose_build(self, compose_filename):
        services = yaml.load(open(os.path.join(self.tmp_folder_path, compose_filename)))['services']
        for service_name, service in services.items():
            if 'build' in service:
                image = Image(service['image'], service['build'])
                image.build()
                image.push()

    def fetch_config(self, url, branch):
        if self.tmp_folder.exists(): self.tmp_folder.delete()
        repo = Repository(self.tmp_folder, url=url, branch=branch)
        repo.clone()

    def init_config(self):
        config = yaml.load(
            open(os.path.join(self.tmp_folder.path, self.stacks_filename))
            )
        self.desired_stacks = config['stacks'] or {}
        self.desired_networks = config['networks'] or []

    def prune_stacks(self):
        running_stacks = self.get_running_stacks()
        desired_stacks = self.desired_stacks()
        undesired_stacks = [x for x in running_stacks if x.name not in desired_stacks and x.name != 'moon']
        for stack in undesired_stacks: stack.remove()

    def deploy_stacks(self):
        desired_stacks = self.desired_stacks()
        for name, compose_filename in desired_stacks.items():
            stack = Stack(name, os.path.join(self.tmp_folder_path, compose_filename))
            stack.deploy()

    def build_images(self):
        desired_stacks = self.desired_stacks()
        for name, compose_filename in desired_stacks.items():
            self.compose_build(compose_filename)

    def create_networks(self):
        sh.docker.create

    def sync(self, url, branch="master", stacks_filename="moon-stacks.yml"):
        self.fetch_config(url, branch)
        self.init_config()
        self.prune_stacks()
        self.build_images()
        self.create_networks()
        self.deploy_stacks()



class Image:
    name = attr.ib()
    options = attr.ib()

    def build(self):
        args = ["-t", self.name]
        if type(self.options) is str:
            args.append(self.options)
        else:
            args.append(self.options['context'])
            if 'dockerfile' in self.options:
                args.extend([ "-f", self.options['dockerfile'] ])
            if 'args' in self.options:
                args.extend([ "--build-arg", '"'+" ".join(self.options['args'])+'"' ])
        sh.docker.build(args)

    def push(self):
        sh.docker.push(self.name)



class Swarm:

    @property
    def networks(self):
        return [Network()]

    @property
    def stacks(self):
        return [Stack()]

    def add_network(Network):
        sh.docker.network.create(Network.name)

    def add_stack(Stack):


class Network:
    add_to(Swarm())
        Swarm.add_network(self)

class Stack:
    add_to(Swarm())
        Swarm.add_stack(self)



if __name__ == "__main__":
    docker = Docker()
    while True:
        branch = os.environ.get('MOON_BRANCH') or 'master'
        docker.sync(os.environ['MOON_REPO'], branch=branch)
        cycle_time = os.environ.get('MOON_CYCLE') or '60'
        logging.debug("Waiting {} seconds before next check".format(cycle_time))
        time.sleep(int(cycle_time))
