# Moon deployment system
## System description
Moon is a minimalist continuous deployment system sitting on top of Docker swarm mode.
Make sure you understand the following concepts before moving forward:
* Docker: https://docs.docker.com/get-started/
* Docker Compose files: https://docs.docker.com/compose/compose-file/
* Docker swarm mode: https://docs.docker.com/engine/swarm/

Even if the system is described as several nodes, several or all the nodes can sit on the same machine.
After initial setup is done, the deployer only needs to be pointed to the git repository that contains the definition of the swarm.

### Repository
This is the git repository from where the instructions for the deployer will be retrieved. The deployer is expecting to find a moon-stacks.yml file in the root of this repository:
```yaml
    stacks:
        my_stack_name: path_to/compose_file_v3+.yml
        my_other_stack: path_to/other_compose_file.yml
    networks:
        - external_network_name
        - other_external_network
        - frontend
```
The deployer will create the external networks, and then build and deploy the stacks listed from their respective compose files. 

Example of a compose file:
```yaml
    version: "3.3"
    services:
        my_awesome_application:
            image: 192.168.154.37:5000/my_awesome_application
            ports:
                - "60906:5000"
            build:
                context:  https://gitlab.amazing.com/mr.fantastic/awesome_app.git#master
            networks:
                - frontend
    networks:
        frontend:
            external: true
```

Note that only repositories with no authentication (aka public) on HTTP/HTTPS are supported at this time.


### Deployer node
This is the node where the Moon deployer is living.
This machine must be able to reach the build node, the swarm manager, the registry and the repository.
Note that the deployer node doesn't need to be part of the main swarm.

### Build node
The machine where the build step and containerization of the apps happens. 
It needs to have access to all resources for the build, which usually means a web connection.
Note that the build node doesn't need to be part of the main swarm.

### Registry
This is where the Docker images will be pushed after they are built. 
The registry must be reachable by the swarm and the build node.

### Swarm
A network of Docker swarm nodes that will run the applications after they are built. 
It can be composed of one or several nodes, but it must have at least one manager node.

### Swarm manager node
The deployer needs to be able to connect to a swarm manager to issue commands to update the stacks on the swarm.




## How to install

- Make sure you have a recent version of Docker installed on the machines you are going to use. 
Visit https://docs.docker.com/install/ for instructions.

- (Optional) For convenience, you can add the relevant users to the docker group:
```bash
    sudo usermod -aG docker $USER
```

- Activate swarm mode on all the machines:
```bash
    docker swarm init
```

- Create a registry on a machine that all the other machines can reach:
```bash
    docker stop registry && docker rm registry
    docker run \
      --restart=always \
      --detach \
      --name registry \
      -p 5000:5000 \
      registry:2
```

- If you don't secure your registry with TLS then you may need to add it to the Docker Daemon configuration on all the machines to allow Docker to connect to it.
Create or modify /etc/docker/daemon.json on the client machine and add this line:
```json
    { "insecure-registries":["myregistry.example.com:5000"] }
```
Restart docker daemon:
```bash
    sudo /etc/init.d/docker restart
```

- Set up ssh keys. If any of the build node or the swarm manager node isn't the same machine as the deployer node, you will need to set up a private key for Moon to be able to ssh into the remote machines. 
The path to the private key needs to be provided to Moon in the MOON\_PRIVATE\_KEY environment variable. 
If you run Moon in a container as decribed below, you can use a Docker secret to pass the file to the container.
Public keys will also need to be uploaded to the remote hosts.
Here are instructions for Ubuntu: https://help.ubuntu.com/community/SSH/OpenSSH/Keys


- Create a compose file (moon.yml) to configure your deployer. 
Here is an example using a remote swarm manager, a private key provided as a Docker secret, and a syncing cycle of 30 seconds:
```yaml
    version: "3.3"
    services:
        moon:
            image: bienaimable/moon2
            deploy:
                restart_policy:
                    condition: any
                    delay: 120s
                    window: 30s
                placement:
                    constraints: [node.role == manager]
            secrets:
                - source: private_key
                  target: private_key
                  uid: '0'
                  gid: '0'
                  mode: 0600
            volumes:
                - /var/run/docker.sock:/var/run/docker.sock
                - data:/data
            environment:
                MOON_BUILD_LOCATION: localhost
                MOON_SWARM_LOCATION: f.pillot@192.168.154.37
                MOON_PRIVATE_KEY: '/run/secrets/private_key'
                MOON_REPO: https://f.pillot@gitlab.criteois.com/f.pillot/swarm-configuration-itservers.git
                MOON_BRANCH: master
                MOON_CYCLE: 30
    secrets:
        private_key:
            file: /home/user/.ssh/id_rsa
    volumes:
        data:
```
MOON\_REPO indicates the repository where the moon-stacks.yml file can be found. 
If not localhost, the MOON\_BUILD\_LOCATION and MOON\_SWARM\_LOCATION must include ssh user and machine address (username@machine-address.com).
MOON\_CYCLE is the minimum time in seconds before the deployer scans the repositories again. Since the deployer doesn't rely on webhooks or requests initiated by your git repository, setting MOON\_CYCLE to a very low value is not recommended. It could trigger anti-DOS measures from the repository software and get the deployer machine temporarily blacklisted. For the same reason, add a reasonable delay in the restart policy for the deployer.

- Start the Moon deployer:
```bash
    docker stack rm moon
    docker stack deploy -c moon.yml moon
```

- Check that moon is running properly and that it is spinning up the stacks defined in moon-stacks.yml.
On the swarm manager node, run the following commands to check state:
```bash
    docker stack ls
    docker ps
```
