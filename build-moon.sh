#!/bin/bash
# Build from Moon Dockerfile
docker build \
  -t moon \
  .
# Push Moon
docker login
docker tag moon bienaimable/moon2
docker push bienaimable/moon2
