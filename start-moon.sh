#!/bin/bash
# Clean Moon
docker stop moon && docker rm moon
# Clean Registry
docker stop registry && docker rm registry
# Start a registry
docker run \
  --restart=always \
  --detach \
  --name registry \
  -p 5000:5000 \
  registry:2
# Run Moon
docker run \
  --restart=always \
  --detach \
  --name moon \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e "MOON_REPO=https://f.pillot@gitlab.criteois.com/f.pillot/swarm-configuration-itservers.git" \
  -e "MOON_BRANCH=master" \
  -e "MOON_CYCLE=60" \
  bienaimable/moon2
