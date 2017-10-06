#!/bin/bash
# Start a registry
docker run -d \
  --restart=always \
  --name registry \
  -p 5000:5000 \
  registry:2
# Build from Moon Dockerfile
docker build \
  -t moon \
  .
# Run Moon
docker run \
  --restart=always \
  --detach \
  --name moon \
  -v /var/run/docker.sock:/var/run/docker.sock \
  moon
