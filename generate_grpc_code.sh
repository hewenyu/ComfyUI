#!/bin/bash
# This script generates the gRPC Python code from the .proto file.
# Ensure the output directory exists
mkdir -p comfy/generated
# Generate the Python code
python -m grpc_tools.protoc \
    -I./protos \
    --python_out=./comfy/generated \
    --grpc_python_out=./comfy/generated \
    ./protos/status_notifier.proto
# Create __init__.py to make the generated code a package
touch comfy/generated/__init__.py
echo "gRPC code generated successfully in comfy/generated" 