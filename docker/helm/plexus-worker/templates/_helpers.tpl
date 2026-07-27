{{/*
Expand the name of the chart.
*/}}
{{- define "plexus-worker.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create the name of the object-store credential Secret.
*/}}
{{- define "plexus-worker.objectStoreSecretName" -}}
{{- required "objectStore.existingSecret is required when objectStore.enabled=true" .Values.objectStore.existingSecret -}}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "plexus-worker.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "plexus-worker.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "plexus-worker.labels" -}}
helm.sh/chart: {{ include "plexus-worker.chart" . }}
{{ include "plexus-worker.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "plexus-worker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "plexus-worker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Pod labels
*/}}
{{- define "plexus-worker.podLabels" -}}
{{ include "plexus-worker.selectorLabels" . }}
worker-type: {{ .Values.workerType }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "plexus-worker.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "plexus-worker.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the secret to use for Plexus API
*/}}
{{- define "plexus-worker.secretName" -}}
{{- if .Values.plexus.existingSecret }}
{{- .Values.plexus.existingSecret }}
{{- else }}
{{- include "plexus-worker.fullname" . }}-secrets
{{- end }}
{{- end }}

{{/*
Create the Plexus API URL for the worker secret.
*/}}
{{- define "plexus-worker.apiUrl" -}}
{{- if .Values.plexus.api.url -}}
{{- .Values.plexus.api.url -}}
{{- else -}}
{{- $global := default dict .Values.global -}}
{{- $services := default dict $global.services -}}
{{- $graphqlProxy := default dict $services.graphqlProxy -}}
{{- if $graphqlProxy.externalUrl -}}
{{- $graphqlProxy.externalUrl -}}
{{- else if and $graphqlProxy.host $graphqlProxy.port -}}
{{- $host := tpl $graphqlProxy.host . -}}
{{- $port := $graphqlProxy.port -}}
{{- $path := default "/graphql" $graphqlProxy.path -}}
{{- printf "http://%s:%d%s" $host (int $port) $path -}}
{{- else -}}
{{- "" -}}
{{- end -}}
{{- end -}}
{{- end }}

{{/*
Create the name of the secret to use for AWS credentials
*/}}
{{- define "plexus-worker.awsSecretName" -}}
{{- if .Values.scoreProcessor.aws.existingSecret }}
{{- .Values.scoreProcessor.aws.existingSecret }}
{{- else }}
{{- include "plexus-worker.fullname" . }}-aws-secrets
{{- end }}
{{- end }}

{{/*
Create the name of the secret to use for Celery broker
*/}}
{{- define "plexus-worker.celerySecretName" -}}
{{- if .Values.celery.broker.existingSecret }}
{{- .Values.celery.broker.existingSecret }}
{{- else }}
{{- include "plexus-worker.fullname" . }}-celery-secrets
{{- end }}
{{- end }}

{{/*
Create the Gateway name for scoring API HTTP routing.
*/}}
{{- define "plexus-worker.gatewayName" -}}
{{- if .Values.scoringApi.gateway.gatewayName }}
{{- .Values.scoringApi.gateway.gatewayName | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-gateway" (include "plexus-worker.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create the HTTPRoute name for scoring API HTTP routing.
*/}}
{{- define "plexus-worker.routeName" -}}
{{- if .Values.scoringApi.gateway.routeName }}
{{- .Values.scoringApi.gateway.routeName | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-route" (include "plexus-worker.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
