{{/*
Expand the name of the chart.
*/}}
{{- define "graphql-proxy.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "graphql-proxy.fullname" -}}
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
{{- define "graphql-proxy.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "graphql-proxy.labels" -}}
helm.sh/chart: {{ include "graphql-proxy.chart" . }}
{{ include "graphql-proxy.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: proxy
{{- if .Values.global }}
{{- with .Values.global.labels }}
{{ toYaml . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "graphql-proxy.selectorLabels" -}}
app.kubernetes.io/name: {{ include "graphql-proxy.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "graphql-proxy.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "graphql-proxy.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the secret to use
*/}}
{{- define "graphql-proxy.secretName" -}}
{{- if .Values.existingSecret }}
{{- .Values.existingSecret }}
{{- else }}
{{- include "graphql-proxy.fullname" . }}
{{- end }}
{{- end }}

{{/*
PostgreSQL connection string
*/}}
{{- define "graphql-proxy.databaseUrl" -}}
{{- if .Values.config.databaseUrl }}
{{- .Values.config.databaseUrl }}
{{- else }}
{{- $host := .Values.postgresql.host | default (tpl .Values.global.services.postgresql.host .) }}
{{- $port := .Values.postgresql.port | default .Values.global.services.postgresql.port }}
{{- $db := .Values.postgresql.database | default .Values.global.services.postgresql.database }}
{{- printf "postgresql://$(DB_USER):$(DB_PASSWORD)@%s:%d/%s" $host (int $port) $db }}
{{- end }}
{{- end }}

{{/*
PostgreSQL secret name for credentials
*/}}
{{- define "graphql-proxy.postgresqlSecretName" -}}
{{- if .Values.postgresql.existingSecret }}
{{- .Values.postgresql.existingSecret }}
{{- else if .Values.global }}
{{- printf "%s-postgresql" .Release.Name }}
{{- else }}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}
{{- end }}
