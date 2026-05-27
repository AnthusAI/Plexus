# Security Best Practices - Plexus Kubernetes Workers

This document outlines the security measures implemented and additional hardening recommendations for Plexus workers deployed to Kubernetes.

## ✅ Security Measures Implemented

### 1. Container Security

#### Non-Root User
✅ **Implemented**: Container runs as non-root user `plexus` (UID 1000)
```dockerfile
RUN groupadd -r plexus --gid=1000 && \
    useradd -r -g plexus --uid=1000 --home-dir=/app --shell=/bin/bash plexus
USER plexus
```

**Why**: Prevents privilege escalation if container is compromised

#### Minimal File Permissions
✅ **Implemented**: Files and directories use restrictive permissions (750 instead of 777)
```dockerfile
RUN chmod 750 /app/data /app/logs /app/tmp
```

**Why**: Limits access to sensitive data and prevents unauthorized modifications

#### Slim Base Image
✅ **Implemented**: Uses `python:3.11-slim` instead of full Python image
```dockerfile
FROM python:3.11-slim
```

**Why**: Reduces attack surface by minimizing installed packages (~100MB vs ~1GB)

#### Minimal System Dependencies
✅ **Implemented**: Only installs required system packages with `--no-install-recommends`
```dockerfile
RUN apt-get install -y --no-install-recommends git libpq5 libcurl4 graphviz
```

**Why**: Fewer packages = fewer vulnerabilities

### 2. Kubernetes Pod Security

#### Security Contexts
✅ **Implemented**: Comprehensive pod and container security contexts

**Pod Security Context**:
```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
```

**Container Security Context**:
```yaml
securityContext:
  allowPrivilegeEscalation: false
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: false
  capabilities:
    drop:
    - ALL
```

**Why**:
- `runAsNonRoot`: Prevents running as root even if image is compromised
- `allowPrivilegeEscalation: false`: Blocks privilege escalation exploits
- `capabilities.drop: ALL`: Removes all Linux capabilities (principle of least privilege)
- `seccompProfile: RuntimeDefault`: Restricts syscalls available to container

### 3. Secrets Management

#### Secrets Stored in Kubernetes Secrets
✅ **Implemented**: All sensitive data in Kubernetes Secrets, not ConfigMaps or environment variables
```yaml
- name: PLEXUS_API_KEY
  valueFrom:
    secretKeyRef:
      name: plexus-worker-secrets
      key: api-key
```

**Why**: Secrets are encrypted at rest and have stricter RBAC controls

#### IRSA Support (AWS IAM Roles for Service Accounts)
✅ **Implemented**: Production configuration uses IRSA instead of embedded AWS credentials
```yaml
serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/PlexusWorkerRole
```

**Why**: No AWS credentials stored in cluster; uses short-lived tokens

#### External Secrets Integration Ready
✅ **Implemented**: Helm chart supports `existingSecret` parameter for External Secrets Operator
```yaml
plexus:
  existingSecret: "external-secrets-plexus"
```

**Why**: Secrets can be synced from AWS Secrets Manager, Vault, etc.

### 4. Network Security

#### Network Policies
✅ **Implemented**: NetworkPolicy template restricts pod-to-pod communication
```yaml
networkPolicy:
  enabled: true  # Enable in production
```

**Default policy**:
- **Ingress**: Deny all (workers don't need incoming connections)
- **Egress**: Allow only DNS, HTTPS, and required broker connections

**Why**: Limits blast radius if pod is compromised

#### Service Account with Minimal Permissions
✅ **Implemented**: Dedicated service account per deployment
```yaml
serviceAccount:
  create: true
```

**Why**: Follows principle of least privilege

### 5. Resource Management

#### Resource Limits and Requests
✅ **Implemented**: All pods have CPU and memory limits
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1500m"
```

**Why**: Prevents resource exhaustion attacks and ensures QoS

#### Pod Disruption Budget
✅ **Implemented**: Ensures minimum availability during cluster operations
```yaml
podDisruptionBudget:
  enabled: true
  minAvailable: 2
```

**Why**: Protects against accidental denial of service

### 6. High Availability

#### Pod Anti-Affinity
✅ **Implemented**: Spreads pods across nodes to prevent single point of failure
```yaml
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - topologyKey: kubernetes.io/hostname
```

**Why**: Improves resilience against node failures

#### Rolling Updates
✅ **Implemented**: Zero-downtime deployments with `maxUnavailable: 0`
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

**Why**: Maintains service availability during updates

### 7. Observability

#### Config/Secret Checksums
✅ **Implemented**: Pods restart when configs/secrets change
```yaml
annotations:
  checksum/config: {{ include "configmap.yaml" . | sha256sum }}
  checksum/secret: {{ include "secret.yaml" . | sha256sum }}
```

**Why**: Ensures pods pick up configuration changes automatically

#### Health Checks
✅ **Implemented**: Liveness and readiness probes
```yaml
livenessProbe:
  exec:
    command: [python, -c, "import sys; sys.exit(0)"]
```

**Why**: Detects and restarts unhealthy pods

### 8. Image Security

#### Image Labels
✅ **Implemented**: Metadata labels for tracking
```dockerfile
LABEL maintainer="Anthus AI <engineering@anthus.ai>" \
      version="1.52.0"
```

**Why**: Helps with image management and compliance

#### No Secrets in Image
✅ **Implemented**: No secrets baked into image; all provided at runtime

**Why**: Prevents credential leaks if image is compromised

## 🔒 Additional Hardening (Recommended)

### 1. Image Scanning

Add to CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Scan image for vulnerabilities
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: 'your-registry/plexus-worker:${{ github.sha }}'
    format: 'sarif'
    output: 'trivy-results.sarif'
    severity: 'CRITICAL,HIGH'
```

**Tools**: Trivy, Snyk, Clair, Anchore

### 2. Image Signing

Sign images with cosign or Notary v2:

```bash
cosign sign your-registry/plexus-worker:1.52.0
```

Use admission controller to verify signatures.

### 3. Pod Security Standards

Enforce Pod Security Standards at namespace level:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: plexus-prod
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

**Standard**: Use `restricted` in production

### 4. Runtime Security

Deploy a runtime security tool:

**Options**:
- **Falco**: Detects anomalous behavior
- **Tracee**: eBPF-based security observability
- **Tetragon**: Cilium's runtime enforcement

### 5. Secret Encryption at Rest

Ensure etcd encryption is enabled:

```bash
kubectl get encryptionconfig -o yaml
```

For EKS, it's enabled by default with KMS.

### 6. Private Container Registry

Use private registry with authentication:

```yaml
imagePullSecrets:
- name: registry-credentials
```

**Registries**:
- AWS ECR (with IRSA for pull)
- Google GCR
- Azure ACR
- Harbor (self-hosted)

### 7. Audit Logging

Enable Kubernetes audit logging:

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: RequestResponse
  resources:
  - group: ""
    resources: ["secrets"]
```

### 8. Network Segmentation

Use separate namespaces per environment:

```bash
kubectl create namespace plexus-prod
kubectl create namespace plexus-staging
kubectl create namespace plexus-dev
```

Apply namespace-scoped network policies.

### 9. Principle of Least Privilege RBAC

Create minimal RBAC roles:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: plexus-worker-role
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get"]
```

### 10. Read-Only Root Filesystem

If application allows, enable:

```yaml
securityContext:
  readOnlyRootFilesystem: true
```

Mount writable volumes only where needed:

```yaml
volumeMounts:
- name: tmp
  mountPath: /tmp
- name: cache
  mountPath: /app/data
```

### 11. AppArmor/SELinux Profiles

Apply mandatory access control:

```yaml
annotations:
  container.apparmor.security.beta.kubernetes.io/worker: runtime/default
```

### 12. mTLS for Service-to-Service Communication

If workers communicate with other services, use service mesh:

**Options**:
- Istio
- Linkerd
- Cilium Service Mesh

### 13. Vulnerability Scanning in CI

Add Snyk or similar to CI:

```yaml
- name: Snyk Python scan
  uses: snyk/actions/python@master
  env:
    SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
```

### 14. Secrets Rotation

Implement automated secret rotation:

**AWS**: Use AWS Secrets Manager with automatic rotation  
**Vault**: Use Vault dynamic secrets  
**External Secrets Operator**: Configure refresh interval

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: plexus-secrets
spec:
  refreshInterval: 1h
```

## 🚨 Security Checklist

Before deploying to production, verify:

### Container Security
- [ ] Container runs as non-root user (UID 1000)
- [ ] `allowPrivilegeEscalation: false` set
- [ ] All capabilities dropped
- [ ] Minimal base image used
- [ ] Image scanned for vulnerabilities
- [ ] No secrets in image layers
- [ ] Image signed (optional but recommended)

### Pod Security
- [ ] `runAsNonRoot: true` in pod security context
- [ ] seccomp profile applied
- [ ] Read-only root filesystem (if possible)
- [ ] Resource limits defined
- [ ] Liveness and readiness probes configured

### Network Security
- [ ] Network policies enabled
- [ ] Ingress restricted (deny-all for workers)
- [ ] Egress restricted to required destinations only
- [ ] mTLS enabled (if applicable)

### Secrets Management
- [ ] All secrets in Kubernetes Secrets (not ConfigMaps)
- [ ] IRSA enabled (for AWS resources)
- [ ] External Secrets Operator configured (recommended)
- [ ] Secrets encryption at rest enabled in etcd
- [ ] No hardcoded credentials anywhere

### Access Control
- [ ] Dedicated service account created
- [ ] RBAC roles follow least privilege
- [ ] Pod Security Standards enforced at namespace level
- [ ] Image pull secrets configured for private registry

### Monitoring & Audit
- [ ] Audit logging enabled
- [ ] Runtime security monitoring deployed (Falco, etc.)
- [ ] Anomaly detection configured
- [ ] Security alerts configured

### Compliance
- [ ] Image provenance tracked
- [ ] SBOM (Software Bill of Materials) generated
- [ ] Vulnerability scan results reviewed
- [ ] Security scan results below acceptable threshold
- [ ] Pen testing completed (for sensitive workloads)

## 🎯 Security by Environment

### Development
- Basic security contexts
- Secrets management
- Resource limits

### Staging
- All Dev security measures
- Network policies enabled
- IRSA enabled (to test production config)
- Image scanning in CI

### Production
- All Staging security measures
- Pod Security Standards: `restricted`
- Pod Disruption Budget enabled
- Runtime security monitoring (Falco)
- Audit logging
- Secret rotation automated
- mTLS (if applicable)
- Regular security reviews

## 📚 References

- [OWASP Kubernetes Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Kubernetes_Security_Cheat_Sheet.html)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
- [NSA/CISA Kubernetes Hardening Guide](https://www.nsa.gov/Press-Room/News-Highlights/Article/Article/2716980/nsa-cisa-release-kubernetes-hardening-guidance/)
- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [AWS EKS Best Practices - Security](https://aws.github.io/aws-eks-best-practices/security/docs/)

## 🔐 Incident Response

If a security incident occurs:

1. **Isolate**: Apply network policy to block traffic
2. **Investigate**: Examine logs, audit trail, runtime events
3. **Remediate**: Update image, rotate secrets, patch vulnerabilities
4. **Review**: Conduct post-mortem, update security controls

## 📞 Security Contact

For security issues or questions:
- Internal: Contact your security team
- Report vulnerabilities: security@anthus.ai (if applicable)

---

**Last Updated**: 2026-05-26  
**Next Review**: Quarterly or after major changes
