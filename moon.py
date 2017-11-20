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
class Folder():
    path = attr.ib()
    @property
    def parent(self):
        return pathlib.Path(self.path).parent
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
    branch = attr.ib()
    def clone(self):
        if self.folder.exists(): self.folder.delete()
        git = sh.git.bake(_cwd=str(self.folder.parent))
        git.clone("--depth", 
                  "1", 
                  "-b", 
                  self.branch, 
                  self.url, 
                  self.folder.path)
    def uptodate(self):
        if not self.folder.exists(): return False
        git = sh.git.bake(_cwd=self.folder.path)
        git.fetch()
        return "is up-to-date" in git.status()

@traced
@attr.s
@logged
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

@traced
@attr.s
@logged
class Service:
    name = attr.ib()
    stack_name = attr.ib()
    definition = attr.ib()
    def __attrs_post_init__(self):
        self.repository = None
        if 'build' in self.definition:
            self.image = Image(self.definition['image'], self.definition['build'])
            if type(self.definition['build']) is str:
                url, branch = self.definition['build'].split('#')
            else:
                url, branch = self.definition['build']['context'].split('#')
            self.repository = Repository(
                                Folder(
                                    '/repo_' + stack_name + '_' + self.name), 
                                url=url,
                                branch=branch)

@traced
@attr.s
@logged
class Stack:
    name = attr.ib()
    filename = attr.ib(default=None)
    def __attrs_post_init__(self):
        self.services = []
        services = yaml.load(open(os.path.join('/instructions', self.filename)))['services']
        for name, definition in services.items():
            self.services.append(Service(name, self.name, definition))
    def add_to(self, swarm):
        swarm.add_stack(self)
    def remove_from(self, swarm):
        swarm.remove_stack(self)

@traced
@attr.s
@logged
class Network:
    name = attr.ib()
    def add_to(self, swarm):
        swarm.add_network(self)
    def remove_from(self, swarm):
        swarm.remove_network(self)

@traced
@attr.s
@logged
class Instructions:
    repository = attr.ib()
    filename = attr.ib()
    def refresh(self):
        self.repository.clone()
        filepath = os.path.join(self.repository.folder.path, self.filename)
        config = yaml.load(open(filepath))
        self.stacks = [ Stack(
                             name, 
                             os.path.join(self.repository.folder.path, filename)
                             )
                      for name, filename 
                      in config['stacks'].items() 
                      ]
        if 'networks' in config:
            self.networks = [ Network(name) for name in config['networks'] ]
        else:
            self.networks = []

@traced
@attr.s
@logged
class Swarm:
    @property
    def networks(self):
        name_index = 1
        output = sh.docker.network.ls()
        data = [ x.split() for x in output.split('\n')[1:] ]
        return [ Network(x[name_index]) for x in data if x ]
    @property
    def stacks(self):
        name_index = 0
        output = sh.docker.stack.ls()
        data = [ x.split() for x in output.split('\n')[1:] ]
        return [ Stack(x[name_index]) for x in data if x ]
    def add_network(self, network):
        sh.docker.network.create(network.name, '--scope', 'swarm', '--driver', 'overlay')
    def remove_network(self, network):
        sh.docker.network.rm(network.name)
    def add_stack(self, stack):
        sh.docker.stack.deploy("-c", stack.filename, stack.name)
    def remove_stack(self, stack):
        sh.docker.stack.rm(stack.name)

@traced
@attr.s
@logged
class Manager:
    def __attrs_post_init__(self):
        self.swarm = Swarm()
    def clean_stacks(self, instructions):
        instructions_stack_names = [ x.name for x in instructions.stacks ]
        undesired_stacks = [x for x in self.swarm.stacks if x.name not in instructions_stack_names and x.name != 'moon']
        for stack in undesired_stacks: stack.remove_from(self.swarm)
    def create_networks(self, instructions):
        for network in instructions.networks:
            if not any(running_network.name == network.name for running_network in self.swarm.networks):
                network.add_to(self.swarm)
    def link(self, url, branch, stacks_filename="moon-stacks.yml"):
        self.instructions = Instructions(
                            Repository(
                                Folder('/instructions'), 
                                url=url, 
                                branch=branch), 
                            filename=stacks_filename)
    def sync(self):
        if not self.instructions.repository.uptodate():
            self.instructions.refresh()
            for stack in self.instructions.stacks:
                stack.add_to(self.swarm)
        self.clean_stacks(self.instructions)
        self.create_networks(self.instructions)
        for stack in self.instructions.stacks:
            for service in stack.services:
                if service.repository:
                    if not service.repository.uptodate():
                        service.image.build()
                        service.image.push()
                        stack.add_to(self.swarm)
                        repository.clone()
    def monitor(self, cycle_time):
        while True:
            self.sync()
            time.sleep(int(cycle_time))

if __name__ == "__main__":
    manager = Manager()
    manager.link(
        os.environ['MOON_REPO'], 
        os.environ.get('MOON_BRANCH') or 'master')
    manager.monitor(
        os.environ.get('MOON_CYCLE') or '60')
