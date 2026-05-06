# Upgrading RabbitMQ

## Choosing a Version Tag

RabbitMQ follows semantic versioning: `MAJOR.MINOR.PATCH` (e.g. `4.1.3`).

### Production / Operator (Kubernetes)

**Pin to an exact patch version** (e.g. `rabbitmq:4.2.3-management`) in `helm/values/operators.yaml`.

In production you want deterministic, reproducible deployments. A floating minor tag like `4.2-management` can silently resolve to a different patch the next time a pod is rescheduled or recreated, making it hard to reproduce issues or roll back. Pinning to the patch level ensures every deploy is intentional and auditable. You upgrade only when you explicitly bump the tag.

### Local Development (Docker Compose)

**Use the minor-version tag** (e.g. `rabbitmq:4.2-management`) in `docker-compose.yaml`. This is what we currently do.

For local development, convenience matters more than strict reproducibility. The minor tag automatically picks up patch-level fixes (bug fixes, security patches) whenever you pull or recreate the container, without risking breaking changes from a minor or major bump.

### Tags to avoid everywhere

- `rabbitmq:4-management` or `rabbitmq:latest` — these float across minor and major versions and can introduce breaking changes silently. Never use them.
### Summary

| Tag format | Example | Auto-receives | Risk | Where to use |
|---|---|---|---|---|
| `MAJOR.MINOR.PATCH` | `4.2.3-management` | Nothing | None | **Operator / Production** |
| `MAJOR.MINOR` | `4.2-management` | Patch fixes | Low | **Local dev (docker-compose)** |
| `MAJOR` | `4-management` | Minor + patch | Medium | Never |
| `latest` | `latest` | Everything | High | Never |

---

## Upgrade Path

RabbitMQ has strict upgrade path requirements. You cannot skip minor versions arbitrarily.

### Within the 4.x series

Upgrades within the 4.x line (e.g. `4.0` → `4.1` → `4.2`) are supported sequentially. You can upgrade one minor version at a time. Always enable all stable feature flags after each upgrade step.

### General rules

- Always read the [release notes](https://github.com/rabbitmq/rabbitmq-server/releases) between your current and target version.
- Enable all stable feature flags before *and* after each upgrade: `rabbitmqctl enable_feature_flag all`.
- Back up definitions before upgrading: `rabbitmqctl export_definitions definitions.json`.
- Downgrades are not supported. If an upgrade fails, restore from backup or use a blue-green migration.
- Check the [Erlang version requirements](https://www.rabbitmq.com/docs/which-erlang) — a RabbitMQ upgrade may require a newer Erlang. The official Docker images bundle the correct Erlang, so this mainly matters for non-Docker deployments.
For full details, see the [official RabbitMQ upgrade documentation](https://www.rabbitmq.com/docs/upgrade).

---

## Upgrading the Operator (Kubernetes)

The RabbitMQ cluster is managed via the RabbitMQ Cluster Operator and defined in `helm/values/operators.yaml`.

To upgrade the RabbitMQ version used by the operator-managed cluster, update the `spec` section of the `rabbitmq-cluster` manifest:

[helm/values/operators.yaml](helm/values/operators.yaml)
```yaml
app:
  extraManifests:
    rabbitmq-cluster:
      apiVersion: rabbitmq.com/v1beta1
      kind: RabbitmqCluster
      metadata:
        name: monty-rabbitmq  # NOTE: This is used as the secret name
      spec:
        replicas: 1  # Scaling down is not supported
        image: rabbitmq:4.2.3-management  # <-- pin to exact patch in production
```

### Steps

1. Check the current RabbitMQ version running in the cluster:
   ```bash
   kubectl get rabbitmqcluster monty-rabbitmq -o jsonpath='{.status.defaultUser.serviceReference}'
   ```

2. Choose the target version from the [official RabbitMQ Docker tags](https://hub.docker.com/_/rabbitmq/tags). Stick to `-management` variants so the management UI remains available.
3. Update `helm/values/operators.yaml` by adding or changing the `image` field under `spec`:
   ```yaml
   spec:
     replicas: 1
     image: rabbitmq:<new-version>-management  # e.g. rabbitmq:4.2.4-management
   ```

4. Create a helm release, and apply it to the [go-deploy](https://github.com/IFRCGo/go-deploy/) staging instance

5. Monitor the rollout. The operator performs a rolling restart of the RabbitMQ pod(s):
   ```bash
   kubectl get pods -l app.kubernetes.io/component=rabbitmq -w
   ```

6. Verify the new version once the pod is ready:
   ```bash
   kubectl exec monty-rabbitmq-server-0 -- rabbitmqctl version
   ```

7. Repeat the steps for the production in [go-deploy](https://github.com/IFRCGo/go-deploy/)

### Important notes

- Always consult the [RabbitMQ upgrade documentation](https://www.rabbitmq.com/docs/upgrade) for breaking changes between versions.
- Scaling down replicas is not supported by the operator — do not reduce the `replicas` count.
- Back up definitions (exchanges, queues, bindings, policies) before upgrading: `rabbitmqctl export_definitions /tmp/definitions.json`.
---

## Upgrading Local Development (Docker Compose)

The local RabbitMQ instance is defined in `docker-compose.yaml`.

### Steps

1. Update the image tag in `docker-compose.yaml`:
   ```yaml
   services:
     rabbitmq:
       image: rabbitmq:<new-version>-management  # e.g. rabbitmq:4.3-management
       hostname: "rabbit"
       environment:
         RABBITMQ_DEFAULT_VHOST: celery
   ```

2. Pull the new image and recreate the container:
   ```bash
   docker compose pull rabbitmq
   docker compose up -d rabbitmq
   ```

3. Confirm the upgrade:
   ```bash
   docker compose exec rabbitmq rabbitmqctl version
   ```

4. Access the management UI at [http://localhost:15672](http://localhost:15672) (default credentials: `guest` / `guest`) to verify queues and connections are healthy.
### Important notes

- Local RabbitMQ data is ephemeral unless you have a named volume mounted. If you do, major version jumps may require wiping the data directory — stop the container, remove the volume (`docker volume rm <volume>`), and start fresh.
- Keep the local image tag aligned with what the operator deploys in staging/production to avoid version-mismatch surprises.
