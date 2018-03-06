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
import hashlib
from autologging import traced, logged, TRACE

logging.basicConfig(level=logging.WARNING, stream=sys.stdout,
    format="%(levelname)s:%(name)s:%(funcName)s:%(message)s")
logger = logging.getLogger(__name__)

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
    url = attr.ib()
    branch = attr.ib()
    stack_name = attr.ib()
    service_name = attr.ib()
    def __attrs_post_init__(self):
        unique_id = hashlib.sha256((
                                    self.stack_name + '#' \
                                    + self.service_name + '#' \
                                    + self.url + '#' \
                                    + self.branch).encode('utf-8')).hexdigest()
        self.folder = Folder('/data/' + unique_id)
    def refresh(self):
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
    def __attrs_post_init__(self):
        if locations['build_location'] == 'localhost':
            self.shell = sh
        else:
            self.shell = sh.ssh.bake(
                locations['build_location'], 
                i=locations['private_key'], 
                T=True,
                o='StrictHostKeyChecking=no')
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
            try:
                for line in self.shell.docker.build(args, _iter=True):
                    if line: logger.info(line)
            except Exception as e:
                logger.warning(e)
                logger.warning(
                    'Building image {} failed. Skipping'\
                    .format(self.name))
                return False
            return True

    def push(self):
        self.shell.docker.push(self.name)

@traced
@attr.s
@logged
class Service:
    name = attr.ib()
    stack_name = attr.ib()
    definition = attr.ib()
    repository = None
    image = None
    def __attrs_post_init__(self):
        if 'build' in self.definition:
            self.image = Image(self.definition['image'], self.definition['build'])
            if type(self.definition['build']) is str:
                url, branch = self.definition['build'].split('#')
            else:
                url, branch = self.definition['build']['context'].split('#')
            self.repository = Repository(
                                stack_name=self.stack_name,
                                service_name=self.name,
                                url=url,
                                branch=branch)

@traced
@attr.s
@logged
class Stack:
    name = attr.ib()
    filename = attr.ib(default=None)
    def __attrs_post_init__(self):
        if self.filename != None:
            self.services = []
            services = yaml.load(open(os.path.join('/data/instructions', self.filename)))['services']
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
    def __attrs_post_init__(self):
        self.filepath = os.path.join(self.repository.folder.path, self.filename)
    @property
    def stacks(self):
        config = yaml.load(open(self.filepath))
        return [ Stack(
                             name, 
                             os.path.join(self.repository.folder.path, filename)
                             )
                      for name, filename 
                      in config['stacks'].items() 
                      ]
    @property
    def networks(self):
        config = yaml.load(open(self.filepath))
        if 'networks' in config:
            return [ Network(name) for name in config['networks'] ]
        else:
            return []
    def refresh(self):
        self.repository.refresh()
    def uptodate(self):
        return self.repository.uptodate()

@traced
@attr.s
@logged
class Swarm:
    def __attrs_post_init__(self):
        if locations['swarm_location'] == 'localhost':
            self.shell = sh
        else:
            self.shell = sh.ssh.bake(
                locations['swarm_location'], 
                i=locations['private_key'], 
                T=True,
                o='StrictHostKeyChecking=no')
    @property
    def networks(self):
        name_index = 1
        output = self.shell.docker.network.ls()
        data = [ x.split() for x in output.split('\n')[1:] ]
        return [ Network(x[name_index]) for x in data if x ]
    @property
    def stacks(self):
        name_index = 0
        output = self.shell.docker.stack.ls()
        data = [ x.split() for x in output.split('\n')[1:] ]
        return [ Stack(x[name_index]) for x in data if x ]
    def add_network(self, network):
        self.shell.docker.network.create(network.name, '--scope', 'swarm', '--driver', 'overlay')
    def remove_network(self, network):
        self.shell.docker.network.rm(network.name)
    def add_stack(self, stack):
        compose_file = sh.cat(stack.filename)
        self.shell.docker.stack.deploy(compose_file, '--compose-file', '-', stack.name)
    def remove_stack(self, stack):
        self.shell.docker.stack.rm(stack.name)

@traced
@attr.s
@logged
class Manager:
    def __attrs_post_init__(self):
        self.swarm = Swarm()
    def link(self, url, branch, stacks_filename="moon-stacks.yml"):
        self.instructions = Instructions(
                            Repository(
                                stack_name='moon',
                                service_name='moon',
                                url=url, 
                                branch=branch), 
                            filename=stacks_filename)
    def clean_stacks(self, instructions):
        for running_stack in self.swarm.stacks:
            if running_stack.name != 'moon'\
            and not any(stack.name == running_stack.name
                       for stack in instructions.stacks):
                logger.info('Removing stack {}'.format(running_stack.name))
                running_stack.remove_from(self.swarm)
                logger.info('Stack {} removed'.format(running_stack.name))
    def create_networks(self, instructions):
        for network in instructions.networks:
            if not any(running_network.name == network.name 
                       for running_network in self.swarm.networks):
                logger.info('Adding network {}'.format(network.name))
                network.add_to(self.swarm)
                logger.info('Network {} added'.format(network.name))
    def check_instructions_repository(self, instructions):
        if not self.instructions.uptodate():
            logger.info('Instructions not up-to-date. Refreshing everything...')
            logger.info('Pulling new instructions...')
            self.instructions.refresh()
            logger.info('Removing dangling stacks...')
            self.clean_stacks(instructions)
            logger.info('Creating missing networks...')
            self.create_networks(instructions)
            for stack in instructions.stacks:
                for service in stack.services:
                    if service.repository:
                        logger.info(
                            'Building service {} in stack {}...'\
                            .format(
                                service.name,
                                stack.name))
                        success = service.image.build()
                        if success:
                            logger.info(
                                'Pushing service image {} from stack {}...'\
                                .format(
                                    service.name,
                                    stack.name))
                            service.image.push()
                        service.repository.refresh()
                logger.info(
                    'Deploying stack {}...'\
                    .format(stack.name))
                stack.add_to(self.swarm)
            logger.info('System refreshed')
    def check_stack_repositories(self, instructions):
        for stack in instructions.stacks:
            redeploy = False
            for service in stack.services:
                if service.repository:
                    if not service.repository.uptodate():
                        redeploy = True
                        logger.info(
                            'Service {} in stack {} not up-to-date. Refreshing...'\
                            .format(
                                service.name,
                                stack.name))
                        logger.info(
                            'Building service {} in stack {}...'\
                            .format(
                                service.name,
                                stack.name))
                        success = service.image.build()
                        if success:
                            logger.info(
                                'Pushing service image {} from stack {}...'\
                                .format(
                                    service.name,
                                    stack.name))
                            service.image.push()
                        service.repository.refresh()
            if redeploy:
                logger.info(
                    'Deploying stack {}...'\
                    .format(stack.name))
                stack.add_to(self.swarm)
                logger.info(
                    'Stack {} refreshed'\
                    .format(stack.name))

    def sync(self):
        self.check_instructions_repository(self.instructions)
        self.check_stack_repositories(self.instructions)
    def monitor(self, cycle_time):
        while True:
            self.sync()
            time.sleep(int(cycle_time))


locations = {}
locations['build_location'] = os.environ.get('MOON_BUILD_LOCATION') or 'localhost'
locations['swarm_location'] = os.environ.get('MOON_SWARM_LOCATION') or 'localhost'
locations['private_key'] = os.environ.get('MOON_PRIVATE_KEY')
debug_mode = True if os.environ.get('MOON_DEBUG') and os.environ.get('MOON_DEBUG').lower() == 'true' else False
if debug_mode:
    logger.setLevel(TRACE)
else:
    logger.setLevel(logging.INFO)

if __name__ == "__main__":
    manager = Manager()
    manager.link(
        os.environ['MOON_REPO'], 
        os.environ.get('MOON_BRANCH') or 'master')
    manager.monitor(
        os.environ.get('MOON_CYCLE') or '60')
