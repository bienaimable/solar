# Moon deployment system
## System description
The entire system can sit in one machine or be spread over several ones.
### Deployer location
This is the machine where the Moon deployer is living. 
This machine must be able to reach the build location, the swarm manager, and the repository.
Note that the moon node doesn't need to be part of the main swarm.

### Build location
The machine where the build step and containerization of the apps happens. 
It needs to have access to all resources for the build, which usually means a web connection.
Note that the build location node doesn't need to be part of the main swarm.

### Repository
This is where the Docker images will be pushed after they are built. 
The repository must be reachable by the swarm.

### Swarm
A network of Docker swarm nodes that will run the applications after they are built. 
It can be composed of one or several nodes, but it must have at least one manager node.

### Swarm manager location
The deployer needs to be able to connect to a swarm manager to issue commands to update the stacks on the swarm.




## How to install

- Make sure you have a recent version of Docker installed on the machines you are going to use. 
Visit https://docs.docker.com/install/ for instructions.

- (Optional) For convenience, you can add the relevant users to the docker group:
```
sudo usermod -aG docker $USER
```

- Activate swarm mode on all the machines:
```
docker swarm init
```

- Create a registry on a machine that your swarm can reach
```
docker stop registry && docker rm registry
docker run \
  --restart=always \
  --detach \
  --name registry \
  -p 5000:5000 \
  registry:2
```

- Set up ssh keys
If any of the build location or the swarm manager location isn't the same machine as the deployer location, you will need to set up a private key for Moon to be able to ssh into the remote machines. 
The path to the private key needs to be provided to Moon in the MOON\_PRIVATE\_KEY environment variable. 
If you run Moon in a container as decribed below, you can use a Docker secret to pass the file to the container.
Private keys will need to be uploaded to the remote hosts.
Here are instructions for Ubuntu: https://help.ubuntu.com/community/SSH/OpenSSH/Keys



- Create a compose file (moon.yml) to configure your deployer. 
Here is an example using a remote swarm manager, a private key provided as a Docker secret, and a syncing cycle of 30 seconds:
```
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
Here is a example of moon-stacks.yml listing the compose files for each stack to be run on the swarm:
```
stacks:
    nginx_scope_feedback: stacks/nginx_scope_feedback.yml
    elk: stacks/elk.yml
    metis_develop: stacks/metis_develop.yml
    metis_db: stacks/metis_db.yml
    db_setup_metis: stacks/db_setup_metis.yml
    gunslinger: stacks/gunslinger.yml
    forecaxter: stacks/forecaxter.yml
networks:
    - frontend
    - metis_db
```

- Start the Moon deployer:
```
docker stack rm moon
docker stack deploy -c moon.yml moon
```

- Check that moon is running properly and that it is spinning up the stacks defined in moon-stacks.yml.
On the swarm manager node, run the following commands to check state:
```
docker stack ls
docker ps
```
