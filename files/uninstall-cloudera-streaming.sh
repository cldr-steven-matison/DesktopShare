#!/bin/bash
# Simple Helm Uninstall Script for Cloudera Streaming Operators

echo "🧹 Starting uninstall of Cloudera Streaming Operators..."

# Uninstall in recommended reverse order
helm uninstall cfm-operator --namespace cfm-streaming || true
helm uninstall cloudera-surveyor --namespace cld-streaming || true
helm uninstall schema-registry --namespace cld-streaming || true
helm uninstall csa-operator --namespace cld-streaming || true
helm uninstall strimzi-cluster-operator --namespace cld-streaming || true

# Optional: also uninstall cert-manager if you installed it
helm uninstall cert-manager --namespace cert-manager || true

echo "✅ All Helm releases uninstalled."