#!/usr/bin/env python3
import kopf
import kubernetes.client
import openai
import os
import yaml


# Define the group, version, and plural name of the custom resource
GROUP = "kubeautogpt.io"
VERSION = "v1"
PLURAL = "kubeautogpts"


# function to apply the crd definition for the kubeautogpts custom resource to the cluster
def apply_crd():
    crd_spec = {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {"name": f"{PLURAL}.{GROUP}"},
        "spec": {
            "group": GROUP,
            "names": {
                "kind": "KubeAutoGpts",
                "listKind": "KubeAutoGptsList",
                "plural": PLURAL,
                "singular": "kubeautogpts",
            },
            "scope": "Namespaced",
            "versions": [
                {
                    "name": VERSION,
                    "schema": {
                        "openAPIV3Schema": {
                            "type": "object",
                            "properties": {
                                "spec": {
                                    "type": "object",
                                    "properties": {
                                        "description": {"type": "string"},
                                        "expectedObjects": {"type": "string"},
                                        "dryRun": {"type": "boolean", "default": True},
                                    },
                                },
                                "status": {
                                    "type": "object",
                                    "properties": {
                                        "createdObjects": {
                                            "type": "array",
                                            "items": {"type": "object"},
                                        },
                                        "error": {"type": "string"},
                                        "comments": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "created": {"type": "object"},
                                        "updated": {"type": "object"},
                                    },
                                },
                            },
                        }
                    },
                    "served": True,
                    "storage": True,
                }
            ],
        },
    }

    api_instance = None
    try:
        kubernetes.config.load_incluster_config()
        api_instance = kubernetes.client.CustomObjectsApi()
    except kubernetes.config.ConfigException as e1:
        try:
            kubernetes.config.load_kube_config()
            api_instance = kubernetes.client.CustomObjectsApi()
        except kubernetes.config.ConfigException as e2:
            raise Exception(f"Cannot authenticate neither in-cluster, nor via kubeconfig.")

    try:
        api_instance.create_cluster_custom_object(
            group="apiextensions.k8s.io",
            version="v1",
            plural="customresourcedefinitions",
            body=crd_spec,
        )
    except:
        pass


def remove_codeblock_formatting(text):
    # Split the text into lines
    stripped = text.strip()
    lines = stripped.split("\n")

    # Check if the text is wrapped in a markdown code block
    if lines[0].strip() == "```" and lines[-1].strip() == "```":
        # Remove the code block formatting by removing the first and last lines
        return "\n".join(lines[1:-1]).strip()
    # Return the original text if it is not wrapped in acode block
    return text.strip()


# use the openai api to generate a spec for the expected objects based on the description
def generate_spec(openai_client, description):
    messages = [
        {
            "role": "system",
            "content": """
            You are a helpful assistant whose job it is to read a description of some thing that needs to be
            created on a kubernetes cluster and return the yaml spec for the objects that need to be created.
            I'm going to be parsing your response with a computer program, so it's extremely important that you do not include any additional explanation
            or context or markdown formatting.  ONLY RETURN THE YAML SPEC FOR THE OBJECTS.  You may include ONE additional yaml object
            in the following format, if you have additional comments to share.  This will be parsed by the computer program to add notes for the user.
            ---
            comments:
              - "This will not work without credentials for the foo service saved as a secret called foo-credentials in the foo namespace."
              - "Other comments, questions, or suggestions"
 """,
        },
    ]
    messages += [
        {
            "role": "user",
            "content": """I need to deploy an nginx container open on port 8080 along with a service
    """,
        },
        {
            "role": "assistant",
            "content": """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 80
  type: LoadBalancer
""",
        },
    ]
    messages += [{"role": "user", "content": description}]
    response = openai_client.ChatCompletion.create(
        model=os.environ["GPT_MODEL"], messages=messages
    )
    return remove_codeblock_formatting(response["choices"][0]["message"]["content"])


def update_spec(openai_client, current_spec, description):
    messages = [
        {
            "role": "system",
            "content": """
            You are a helpful assistant whose job it is to read a description of some thing that needs to be modified
            on a kubernetes cluster and return the updated yaml spec for the objects that need to be created.  I'm going to send
            you the current spec and a description of what should be changed.  Please return the updated yaml, including everything
            in the original yaml, even if it hasn't been changed.  It's possible that nothing at all needs to be changed, but you still
            should return the entire spec as it was originally sent to you.
            
            I'm going to be parsing your response with a computer program, so it's extremely important that you do not include any additional explanation
            or context or markdown formatting.  ONLY RETURN THE YAML SPEC FOR THE OBJECTS.
            You may include ONE additional yaml object
            in the following format, if you have additional comments to share.  This will be parsed by the computer program to add notes for the user.
            ---
            comments:
              - "This will not work without credentials for the foo service saved as a secret called foo-credentials in the foo namespace."
              - "Other comments, questions, or suggestions"
 """,
        },
    ]
    messages += [
        {
            "role": "user",
            "content": """Current spec:
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 80
  type: LoadBalancer
Updated description:
            I need to deploy an nginx container open on port 8080 along with a service, and it should have 3 replicas.
    """,
        },
        {
            "role": "assistant",
            "content": """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 80
  type: LoadBalancer
""",
        },
    ]
    messages += [
        {
            "role": "user",
            "content": f"""
Current spec:
{current_spec}
Updated description:
{description}""",
        }
    ]
    response = openai_client.ChatCompletion.create(
        model=os.environ["GPT_MODEL"], messages=messages
    )
    return remove_codeblock_formatting(response["choices"][0]["message"]["content"])


def ask_for_help(openai_client, current_spec, description, error):
    messages = [
        {
            "role": "system",
            "content": """
            You are a helpful assistant whose job it is to read a description of something that needs to be installed 
            on a kubernetes cluster and we've run into an error while trying to apply it.  Please return updated yaml with any 
            errors correct.  VERY IMPORTANT: ONLY RETURN YAML.  Return ALL of the yaml required to fulfill the description of the requirements, not just the
            yaml that has been changed.
            I'm going to be parsing your response with a computer program, so it's extremely important that you do not include any additional explanation
            or context or markdown formatting.  ONLY RETURN THE YAML SPEC FOR THE OBJECTS.
             You may include ONE additional yaml object
            in the following format, if you have additional comments to share.  This will be parsed by the computer program to add notes for the user.
            ---
            comments:
              - "I can't solve this problem because I need to know more about how foo works with baz.  Please update the description."
 """,
        },
    ]
    messages += [
        {
            "role": "user",
            "content": """Current spec:
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        repository: docker.io
        image: nginx:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 80
  type: LoadBalancer
Updated description:
            I need to deploy an nginx container open on port 8080 along with a service, and it should have 3 replicas.
Error:
kubernetes.client.exceptions.ApiException: (500)
Reason: Internal Server Error
HTTP response headers: HTTPHeaderDict({'Audit-Id': '25f2f9ad-2fa9-4162-8201-0690ab6d6a2b', 'Cache-Control': 'no-cache, private', 'Content-Type': 'application/json', 'X-Kubernetes-Pf-Flowschema-Uid': 'd5b4ded1-4ba5-48f3-844a-9815443d2a91', 'X-Kubernetes-Pf-Prioritylevel-Uid': 'fc650202-a7df-4f51-ac4f-e9d96103b97c', 'Date': 'Sun, 16 Apr 2023 18:25:35 GMT', 'Content-Length': '251'})
HTTP response body: b'{"kind":"Status","apiVersion":"v1","metadata":{},"status":"Failure","message":"failed to create typed patch object (default/nginx-deployment; "apps/v1", Kind=Deployment): .spec.template.spec.containers.repository: field not declared in schema","code":500}\n'
    """,
        },
        {
            "role": "assistant",
            "content": """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-service
spec:
  selector:
    app: nginx
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 80
  type: LoadBalancer
""",
        },
    ]
    messages += [
        {
            "role": "user",
            "content": f"""
Current spec:
{current_spec}
Updated description:
{description}
Error:
{error}
""",
        }
    ]
    response = openai_client.ChatCompletion.create(
        model=os.environ["GPT_MODEL"], messages=messages
    )
    return remove_codeblock_formatting(response["choices"][0]["message"]["content"])


@kopf.on.create(GROUP, VERSION, PLURAL)
def created(spec, status, patch, logger, **_):
    # check if there's an error in the status and an expected_objects field in the spec

    description = spec.get("description")
    openai.api_key = os.environ["OPENAI_API_KEY"]
    if "error" in status and "expectedObjects" in spec and status["error"] != "":
        expected_objects_yaml = ask_for_help(
            openai, spec["expectedObjects"], description, status["error"]
        )
    else:
        if "expectedObjects" in spec:
            expected_objects_yaml = update_spec(
                openai, spec["expectedObjects"], description
            )
        else:
            expected_objects_yaml = generate_spec(openai, description)
    logger.debug(expected_objects_yaml)
    try:
        expected_objects = list(yaml.safe_load_all(expected_objects_yaml))
    except yaml.YAMLError as exc:
        patch.status["error"] = f"Error parsing yaml: {exc}"
        raise kopf.TemporaryError("Error parsing yaml, asking for help.", delay=60)

    patch.spec["expectedObjects"] = "\n---\n".join(
        [yaml.dump(object) for object in expected_objects if "comments" not in object]
    )
    k8s_client = kubernetes.client.ApiClient()
    dynamic_client = kubernetes.dynamic.DynamicClient(k8s_client)

    try:
        for object in expected_objects:
            if "comments" in object:
                patch.status["comments"] = object["comments"]
                # go to next object
                continue

            if spec["dryRun"]:
                continue
            namespace = object.get("metadata", {}).get("namespace", None)
            api = dynamic_client.resources.get(
                api_version=object["apiVersion"], kind=object["kind"]
            )

            try:
                resp = api.create(
                    namespace=namespace,
                    body=object,
                )
                logger.debug(f"Create Response: response: {resp}")
            except kubernetes.client.exceptions.ApiException as e:
                resp = api.server_side_apply(
                    namespace=namespace,
                    body=object,
                    field_manager="kube-autogpt",
                )
                logger.debug(f"Patch Response: response: {resp}")

                logger.debug(resp)
            logger.debug(resp)
    except kubernetes.client.exceptions.ApiException as e:
        logger.debug(e)
        patch.status["error"] = str(e)
        raise kopf.TemporaryError("Error creating objects, asking for help.", delay=60)
    patch.status["error"] = None


@kopf.on.update(GROUP, VERSION, PLURAL)
def updated(spec, status, logger, patch, **kwargs):
    description = spec.get("description")
    openai.api_key = os.environ["OPENAI_API_KEY"]
    if "error" in status and "expectedObjects" in spec and status["error"] != "":
        expected_objects_yaml = ask_for_help(
            openai, spec["expectedObjects"], description, status["error"]
        )
    else:
        expected_objects_yaml = update_spec(
            openai, spec["expectedObjects"], description
        )

    logger.debug(expected_objects_yaml)
    try:
        expected_objects = yaml.safe_load_all(expected_objects_yaml)
    except Exception as e:
        logger.debug(e)
        patch.status["error"] = f"Error parsing yaml: {e}"
        raise kopf.TemporaryError("Error parsing yaml, asking for help.", delay=60)
    patch.spec["expectedObjects"] = "\n---\n".join(
        [yaml.dump(object) for object in expected_objects if "comments" not in object]
    )
    expected_objects = list(expected_objects)
    k8s_client = kubernetes.client.ApiClient()
    dynamic_client = kubernetes.dynamic.DynamicClient(k8s_client)

    try:
        for object in expected_objects:
            if "comments" in object:
                patch.status["comments"] = object["comments"]
                # go to next object
                continue
            if spec["dryRun"]:
                continue
            namespace = object.get("metadata", {}).get("namespace", None)
            api = dynamic_client.resources.get(
                api_version=object["apiVersion"], kind=object["kind"]
            )
            try:
                resp = api.create(
                    namespace=namespace,
                    body=object,
                )
                logger.debug(f"Create Response: response: {resp}")
            except kubernetes.client.exceptions.ApiException as e:
                logger.debug(e)
                resp = api.server_side_apply(
                    namespace=namespace,
                    body=object,
                    field_manager="kube-autogpt",
                )
                logger.debug(f"Patch Response: response: {resp}")
            logger.debug(resp)
    except Exception as e:
        logger.debug(e)
        patch.status["error"] = str(e)
        raise kopf.TemporaryError("Error creating objects, asking for help.", delay=60)
    patch.status["error"] = ""


@kopf.on.delete(GROUP, VERSION, PLURAL)
def delete_fn(spec, status, **kwargs):
    # Placeholder for logic to handle delete event
    # Here you can implement the deletion of created_objects based on the status
    created_objects = status.get("createdObjects", [])

    # Placeholder for logic to confirm deletion of created_objects

    # Return a message indicating successful deletion
    return "Resource and associated objects deleted successfully."


@kopf.on.login()
def login_fn(**kwargs):
    return kopf.login_with_service_account(**kwargs) or kopf.login_with_kubeconfig(**kwargs)


@kopf.on.startup()
def create_crds(**_):
    apply_crd()