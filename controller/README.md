# ROCK specs for Nginx ingress `controller`.

Aims to be compatible with the `registry.k8s.io/ingress-nginx/controller:vX.Y.Z` images.

:warning: the current version of the `controller` ROCKs must be run as `root`,
both because the ROCKs must `ldconfig` some dynamic libs on startup (which is
automatically handled by an entrypoint script), as well as `rockcraft` not
currently being able to preserve file capabilities via extended attributes
(see https://github.com/canonical/rockcraft/issues/683).

In order to use it with the upstream Helm chart or similar setups, please ensure
you set the proper securityContext settings as follows:

```bash
helm install ingress-nginx \
    # Relevant individual settings:
    --set controller.image.runAsUser=0 \
    --set controller.image.runAsGroup=0 \
    --set controller.image.runAsNonRoot=false \
    --set controller.image.readOnlyRootFilesystem=false \
    # Required by the `kube-webhook-certgen` rock, as Pebble writes to '/var/lib/pebble':
    --set controller.admissionWebhooks.createSecretJob.securityContext.readOnlyRootFilesystem=false \
    --set controller.admissionWebhooks.patchWebhookJob.securityContext.readOnlyRootFilesystem=false \
    # Required security context for controller. Of special note is `capabilities: null`:
    --set-json controller.containerSecurityContext='{"runAsNonRoot":false,"runAsUser":0,"runAsGroup":0,"allowPrivilegeEscalation":false,"capabilities":null,"readOnlyRootFilesystem":false}'
```
