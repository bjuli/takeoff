---
layout: page
title: Deploy to Kubernetes
date: 2019-09-13
summary: Deploy a provided Kubernetes deployment/service/secret 
permalink: deployment-step/deploy-to-kubernetes
category: Kubernetes
---

# Deploy to Kubernetes

Deploy a Kubernetes resource, as well as optionally a Kubernetes secret containing your Docker registry credentials. This
 secret containing the Docker registry credentials is always called "acr-auth". Also can create a Kubernetes secret
of any secrets available in your cloud vault that match the application name. This Kubernetes secret will be given the name: 
{application_name}-secret. All cloud vault secrets will be stored in a key-value form in this single Kubernetes Secret.
If any of the Kubernetes resources already exists, this step will update them where appropriate (similar to what the 
`kubectl apply -f` command will do. In some cases, you may wish to restart a Kubernetes resource, even if the Kubernetes 
yaml configuration has not changed. An example of this is if you build a new Docker image, with the same tag. The default Kubernetes 
behaviour is to not restart the resource. Takeoff allows you to override this behaviour if so desired. 

This task is usually used in combination with [Build Docker Image](build-docker-image) (assuming your Kubernetes config references the image that is built)

## Deployment
Add the following task to `deployment.yaml`:

```yaml
- task: deploy_to_kubernetes
  kubernetes_config_path: my_kubernetes_config.yml.j2
```

This should be after the [build_docker_image](build-docker-image) task if used together.

{:.table}
| field | description | value
| ----- | ----------- 
| `kubernetes_config_path` | The path to a `yml` [jinja_templated](http://jinja.pocoo.org/) Kubernetes deployment config | Mandatory value, must be a valid path in the repository |
| `image_pull_secret` | Whether or not to create Kubernetes image pull secret to allow pulling images from your container registry. | Defaults to True, with `secret_name=registry-auth` and `namespace=default` |
| `image_pull_secret.create` | Whether or not to create Kubernetes image pull secret to allow pulling images from your container registry. | Defaults to True
| `image_pull_secret.secret_name` | The name of secret | Defaults to `secret_name`
| `image_pull_secret.namespace` | The namespace where the secret should be created in | Default to `default` 
| `restart_unchanged_resources` | Whether or not to restart unchanged Kubernetes resources. Takeoff will attempt to restart all unchanged resources, which may result in error messages in the 
 logs, as not all resources are 'restartable' | Boolean, defaults to False. | 
| `custom_values` | Any custom values you'd like to pass in to be rendered into your Jinja-templates Kubernetes configuration. Should be specified per environment | No custom values are passed by default. Should be a set of key-value pairs per environment |


An example of `kubernetes_config_path.yml.j2` 

```
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: my-app
        image: my-docker-image:{{docker_tag}}
        imagePullPolicy: {{secret_pull_policy}}
        ports:
        - containerPort: 8443
        env:
        - name: SOME_SECRET
          valueFrom:
            secretKeyRef:
              name: my-app-secret
              key: some-secret
      imagePullSecrets:
      - name: acr-auth
---
apiVersion: v1
kind: Service
metadata:
  name: my_service
spec:
  ports:
  - port: 443
    protocol: TCP
    targetPort: 8443
  selector:
    app: my_app
  type: LoadBalancer
---
apiVersion: networking.k8s.io/v1beta1
kind: Ingress
metadata:
  name: my-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: {{ url }}
    http:
      paths:
      - path: /foo
        backend:
          serviceName: service1
          servicePort: 4200
```

An explanation for the Jinja templated values. These values get resolved automatically during deployment.

{:.table}
| field | description 
| ----- | ----------- 
| `docker_tag` | The docker tag to apply. In a D/T/A/P setup, this will allow you to point to the image that was built in a previous step in your Takeoff config without explicitly specifying this

Other templated variables can be filled in two ways:
- Via your cloud keyvault, such as `{{secret_pull_policy}}` is a reference to a cloud vault key. The task will pull all secrets from the cloud vault prefixed with you application name and resolve them in the template.
For the example above, if your application name is `myapp`, then a secret in your cloud vault must be `myapp-secret-pull-policy` or `myapp-secret_pull_policy`. The prefix gets removed by Takeoff and key `secret_pull_policy` with it's value will be passed into the template. Hyphens `-` get normalized to underscores `_`.
- Via the `custom_values` configuration option specified in `deployment.yml`. Here, you are expected to set any custom key-value pairs, per environment. An example is shown below. In the above Kubernetes
configuration, the `{{url}}` key is filled by a custom value passed in via `deployment.yml`.

## Takeoff config
Make sure `.takeoff/config.yml` contains the following keys:

```yaml
azure:
  kubernetes_naming: "my_kubernetes{env}"
  keyvault_keys:
    container_registry:
      username: "registry-username"
      password: "registry-password"
      registry: "registry-server"
```

## Examples
Minimum Takeoff deployment configuration example to deploy Kubernetes resources. This will not create image pull secrets:
```yaml
steps:
- task: deploy_to_kubernetes
  kubernetes_config_path: my_kubernetes_config.yml.j2
  image_pull_secret: 
    create: False
```

Extended configuration example, where we have explicitly disabled the creation of kubernetes secrets by Takeoff. In this case,
we also want to restart the resources, even if their Kubernetes yaml config is unchanged. It will also create image pull secrets in namespace `default` with name `registry-auth`.
We also pass in a custom url value per environment in this example. In this case, we're using the default environment naming that Takeoff itself uses too. Please take a look at
the [environment](../environment.md) docs for more information on how to define your own environment names.

```yaml
steps:
- task: deploy_to_kubernetes
  kubernetes_config_path: my_kubernetes_config.yml.j2
  image_pull_secret: 
    create: True
  restart_unchanged_resources: true
  custom_values:
    dev:
      url: 'dev-url-here-being-buggy'
    acp:
      url: 'acp-url-here-being-awesome'
    prd:
      url: 'prd-url-here-being-glorious'
```

### Takeoff Context
Eventhub producer policy secrets and consumer group secrets from [`configure_eventhub`](deployment-step/configure-eventhub) are available during this task. This makes it possible for the configuration below to inject the secrets into `my_kubernetes_config.yml.j2`:
```yaml
steps:
  - task: configure_eventhub
    create_producer_policies:
      - eventhub_entity_naming: entity1
      - eventhub_entity_naming: entity2
    create_consumer_groups:
      - eventhub_entity_naming: entity3
  - task: deploy_to_kubernetes
    kubernetes_config_path: my_kubernetes_config.yml.j2
```
with `my_kubernetes_config.yml.j2`
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: armada-connections
data:
  entity1-producer-secret: {{ entity1_connection_string }}
  entity2-producer-secret: {{ entity2_connection_string }}
  entity3-consumer-secret: {{ entity3_connection_string }}
```

The jinja variables `entity1_connection_string` and `entity2_connection_string` are named by your `eventhub_entity_naming` in `create_producer_policies`, posfixed with `connection_string`.

## Base64 encoding of secrets
Kubernetes requires the values of secrets to be base64 encoded. Values that are inserted 
into your Kubernetes template that originate from the *Keyvault* or via the *custom values* support (i.e. that are 
supplied in Takeoff's deployment.yml) be inserted into the template in plain text. The user should be responsible for the base64 encoding:
- Provide or store secret base64 encoded
- In `my_kubernetes_config.yml.j2` use `stringData` parameter. Kubernetes then automatically base64 encodes the secret.
  Example:
  ```yaml
  apiVersion: v1
  kind: Secret
  metadata:
    name: armada-connections
  data:
    provided-base64-secret: {{ provided_base64_secret }}
  stringData:
    provided-nonbase64-secret: {{ provided_nonbase64_secret }}
  ```

If, for some reason, you want/need to deviate from this, you can by using the following two filters in your Jinja template:
- `b64_encode`: apply base64 encoding. Example usage: `{{ non_encoded_value |  b64_encode }}`
- `b64_decode`: apply base64 decoding. Example usage: `{{ encoded_value |  b64_decode }}`
