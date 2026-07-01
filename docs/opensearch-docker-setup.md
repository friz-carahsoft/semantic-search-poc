# Step 1: Docker Setup for OpenSearch

This guide sets up a single-node OpenSearch instance in Docker for local semantic-search development with persistent storage.

## Goal

By the end of this step, you should be able to:

- Run OpenSearch locally with Docker
- Connect to the cluster on `https://localhost:9200`
- Verify the cluster is healthy
- Confirm the k-NN plugin is available for vector search
- Keep indexed data after stopping or removing the container

## Prerequisites

- Docker Desktop installed and running
- At least 4 GB of RAM available to Docker
- A terminal with `curl`

## Recommended Version

Use a pinned OpenSearch image tag instead of `latest` so the POC stays reproducible.

As of June 29, 2026, the OpenSearch downloads page lists `3.7.0` as the current release, so the examples below use:

```bash
opensearchproject/opensearch:3.7.0
```

If the team standardizes on a different version later, update the tag in the commands below.

## 1. Pull the Docker image

```bash
docker pull opensearchproject/opensearch:3.7.0
```

## 2. Start OpenSearch in single-node mode

OpenSearch 2.12+ requires an initial admin password when using the bundled demo security configuration. Set a strong password first:

```bash
export OPENSEARCH_INITIAL_ADMIN_PASSWORD='Cedar!Orbit9Maple'
```

Start the container:

```bash
docker run -d \
  --name opensearch-poc \
  -p 9200:9200 \
  -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m" \
  -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=${OPENSEARCH_INITIAL_ADMIN_PASSWORD}" \
  -v opensearch-poc-data:/usr/share/opensearch/data \
  opensearchproject/opensearch:3.7.0
```

What this does:

- `9200` exposes the REST API
- `9600` exposes the Performance Analyzer endpoint
- `discovery.type=single-node` avoids multi-node bootstrap requirements
- `OPENSEARCH_JAVA_OPTS` keeps memory usage reasonable for a local POC
- `-v opensearch-poc-data:/usr/share/opensearch/data` stores OpenSearch data in a named Docker volume

## Data persistence behavior

With the named volume above:

- `docker stop opensearch-poc` preserves your data
- `docker start opensearch-poc` brings the same data back
- `docker rm opensearch-poc` removes the container but keeps the named volume
- Deleting the Docker volume removes the indexed data permanently

To see the volume:

```bash
docker volume ls
```

## 3. Confirm the container is running

```bash
docker ps
```

You should see a container named `opensearch-poc`.

If it exits immediately, inspect the logs:

```bash
docker logs opensearch-poc
```

## 4. Verify the cluster is responding

Because the default demo security is enabled, use HTTPS and pass the admin credentials:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200'
```

You should get a JSON response with cluster and version details.

To check cluster health:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/_cluster/health?pretty'
```

For a fresh single-node setup, `yellow` is normal if replicas are configured but unassigned. `green` is also fine.

## 5. Confirm the k-NN plugin is enabled

List installed plugins:

```bash
curl -k -u "admin:$OPENSEARCH_INITIAL_ADMIN_PASSWORD" 'https://localhost:9200/_cat/plugins?v'
```

Look for a row containing `opensearch-knn`.

You can also confirm vector indexing support by creating a small test index later with:

- `"index.knn": true`
- a `knn_vector` field in the mapping

## 6. Stop and remove the container when needed

Stop:

```bash
docker stop opensearch-poc
```

Remove:

```bash
docker rm opensearch-poc
```

If you also want to delete the persisted OpenSearch data:

```bash
docker volume rm opensearch-poc-data
```

## Troubleshooting

### Port 9200 or 9600 already in use

Either stop the conflicting service or remap the port:

```bash
-p 9201:9200
```

If you change the host port, update the `curl` commands too.

### Container starts and then exits

Check:

```bash
docker logs opensearch-poc
```

Common causes:

- Docker does not have enough memory
- The password does not meet current OpenSearch requirements
- The password is too similar to the username `admin`
- Another container is already using the same name or ports
- A leftover Docker volume contains incompatible data from a different OpenSearch version

### TLS/certificate warnings in curl

The `-k` flag is expected here for local demo certificates.

### zsh reports "no matches found"

If you are using `zsh`, unquoted URLs containing `?` can be treated as wildcard patterns. The examples in this guide quote the URL to avoid that issue.

### Password validation error during startup

If the container exits and the logs mention password validation, remove the stopped container, set a stronger password, and start it again:

```bash
docker rm opensearch-poc
export OPENSEARCH_INITIAL_ADMIN_PASSWORD='Cedar!Orbit9Maple'
```

Use a password that:

- Is at least 8 characters long
- Includes uppercase, lowercase, numeric, and special characters
- Is not too similar to `admin`

## Result

After this step, OpenSearch should be running locally and ready for the next phase: setting up the Python environment and generating embeddings for the semantic-search POC.
