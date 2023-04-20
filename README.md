# kube-auto-gpt-operator
This is a Kubernetes operator, built using Kopf, that leverages OpenAI's GPT-powered generation capabilities to create a Kubernetes spec from a simple, human-readable description.

## Overview

Upon receiving the YAML, the operator sends the description to OpenAI, which then generates a Kubernetes spec. The operator applies the returned YAML, attempting to correct any errors and maintain consistency across updates.

```
kind: KubeAutoGpts
 apiVersion: kubeautogpt.io/v1
 metadata:
   name: redis
 spec:
   description: "create a redis namespace, and inside the namespace, create a redis cluster, backed by a stateful set, along with a service"
```

## Prerequisites
* A Kubernetes cluster (for testing purposes only).
* an openai api key (you can use gpt-3.5 if you don't have access to gpt-4, but the results aren't as reliable

```
export OPENAI_API_KEY=xxxxx
export GPT_MODEL=gpt-3.5-turbo-0301
```

## Usage
Start the operator locally:

```
kopf run handler.py --verbose
```
In another terminal, create a new KubeAutoGpt custom resource:
```
kubectl apply -f test.yaml
```

## Limitations
This PoC operator is meant for fun and experimentation only. It is not production-ready, and should not be deployed to real Kubernetes clusters. The generated specs may not always be accurate or secure, and the operator may not handle all edge cases or errors gracefully.