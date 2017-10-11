#!/bin/bash
# Clean Moon
docker stack rm moon
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
docker stack deploy -c moon.yml moon
