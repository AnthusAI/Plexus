{{/*
Expand the name of the chart.
*/}}
{{- define "plexus-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "plexus-stack.fullname" -}}
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
{{- define "plexus-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "plexus-stack.labels" -}}
helm.sh/chart: {{ include "plexus-stack.chart" . }}
{{ include "plexus-stack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.global.labels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "plexus-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "plexus-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
GraphQL Proxy URL - constructs the full URL for the proxy service
Usage: {{ include "plexus-stack.graphqlProxyUrl" . }}
*/}}
{{- define "plexus-stack.graphqlProxyUrl" -}}
{{- if .Values.global.services.graphqlProxy.externalUrl -}}
{{- .Values.global.services.graphqlProxy.externalUrl -}}
{{- else -}}
{{- $host := tpl .Values.global.services.graphqlProxy.host . -}}
{{- $port := .Values.global.services.graphqlProxy.port -}}
{{- $path := .Values.global.services.graphqlProxy.path -}}
{{- printf "http://%s:%d%s" $host (int $port) $path -}}
{{- end -}}
{{- end -}}

{{/*
PostgreSQL connection string - constructs database URL
Usage: {{ include "plexus-stack.postgresqlUrl" . }}
*/}}
{{- define "plexus-stack.postgresqlUrl" -}}
{{- $host := tpl .Values.global.services.postgresql.host . -}}
{{- $port := .Values.global.services.postgresql.port -}}
{{- $db := .Values.global.services.postgresql.database -}}
{{- printf "postgresql://$(DB_USER):$(DB_PASSWORD)@%s:%d/%s" $host (int $port) $db -}}
{{- end -}}

{{/*
PostgreSQL host - just the hostname
Usage: {{ include "plexus-stack.postgresqlHost" . }}
*/}}
{{- define "plexus-stack.postgresqlHost" -}}
{{- tpl .Values.global.services.postgresql.host . -}}
{{- end -}}
