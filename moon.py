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
class Stack:
    name = attr.ib()
    compose_filename = attr.ib(default=None)

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

    def __attrs_post_init__(self):
        self.repository.clone()
        filepath = os.path.join(self.repository.folder.path, self.filename)
        config = yaml.load(open(filepath))
        self.stacks = [ Stack(
                             name, 
                             os.path.join(self.repository.folder.path, compose_filename)
                             )
                      for name, compose_filename 
                      in config['stacks'].items() 
                      ]
        if 'networks' in config:
            self.networks = [ Network(name) for name in config['networks'] ]
        else
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
        sh.docker.network.create(network.name)

    def remove_network(self, network):
        sh.docker.network.rm(network.name)

    def add_stack(self, stack):
        sh.docker.stack.deploy("-c", stack.compose_filename, stack.name)

    def remove_stack(self, stack):
        sh.docker.stack.rm(stack.name)



@traced
@attr.s
@logged
class Manager:
    config_folder_path = attr.ib(default="/tmp/moon-configuration/")

    def __attrs_post_init__(self):
        self.swarm = Swarm()

    def compose_build(self, compose_filename):
        services = yaml.load(open(os.path.join(self.config_folder_path, compose_filename)))['services']
        for service_name, service in services.items():
            if 'build' in service:
                image = Image(service['image'], service['build'])
                image.build()
                image.push()

    def clean_stacks(self, instructions):
        instructions_stack_names = [ x.name for x in instructions.stacks ]
        undesired_stacks = [x for x in self.swarm.stacks if x.name not in instructions_stack_names and x.name != 'moon']
        for stack in undesired_stacks: stack.remove_from(self.swarm)

    def build_images(self, instructions):
        for stack in instructions.stacks:
            self.compose_build(stack.compose_filename)

    def create_networks(self, instructions):
        running_networks = [ x.name for x in self.swarm.networks ]
        print(running_networks)
        time.sleep(5)
        for network in instructions.networks:
            if network.name not in running_networks:
                network.add_to(self.swarm)

    def deploy_stacks(self, instructions):
        for stack in instructions.stacks:
            stack.add_to(self.swarm)

    def sync(self, url, branch, stacks_filename="moon-stacks.yml"):
        folder = Folder(self.config_folder_path)
        repository = Repository(folder, url=url, branch=branch)
        instructions = Instructions(repository, filename=stacks_filename)
        self.clean_stacks(instructions)
        self.build_images(instructions)
        self.create_networks(instructions)
        self.deploy_stacks(instructions)



if __name__ == "__main__":
    manager = Manager()
    while True:
        branch = os.environ.get('MOON_BRANCH') or 'master'
        print(branch)
        manager.sync(os.environ['MOON_REPO'], branch=branch)
        cycle_time = os.environ.get('MOON_CYCLE') or '60'
        logging.debug("Waiting {} seconds before next check".format(cycle_time))
        time.sleep(int(cycle_time))
