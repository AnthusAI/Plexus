'use client'

import React from 'react'
import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AlertTriangle, ArrowLeft, Download, FileText, Loader2 } from 'lucide-react'

import { useAccount } from '@/app/contexts/AccountContext'
import { Button } from '@/components/ui/button'
import { issueTaskArtifactReadTicket } from '@/lib/artifact-ticket-client'
import {
  buildReportArtifactHref,
  parseOptimizationRunRevisions,
  parseReportArtifactManifest,
  readTaskArtifact,
  selectArtifactDescriptor,
  selectReportRevision,
  type ArtifactDescriptor,
} from '@/lib/report-artifacts'
import { formatAmplifyError, getClient } from '@/utils/amplify-client'

type ViewerState = {
  reportName: string
  latestRevision: number
  descriptor: ArtifactDescriptor
  bytes: Uint8Array
}

function decodeUtf8(bytes: Uint8Array): string {
  return new TextDecoder('utf-8', { fatal: true }).decode(bytes)
}

function downloadName(descriptor: ArtifactDescriptor): string {
  const fromKey = descriptor.object_key.split('/').pop()
  return fromKey || descriptor.display_name
}

export default function ReportArtifactViewer({
  reportId,
  revision,
  logicalId,
}: {
  reportId: string
  revision: number
  logicalId: string
}) {
  const { selectedAccount } = useAccount()
  const [state, setState] = useState<ViewerState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)
      setState(null)
      try {
        if (!Number.isSafeInteger(revision) || revision < 1 || !logicalId) {
          throw new Error('A positive revision and logical artifact identifier are required.')
        }
        const response = await (getClient().models.Report as any).get({ id: reportId })
        if (response?.errors?.length) {
          throw new Error(formatAmplifyError(response))
        }
        const report = response?.data
        if (!report) throw new Error('Report was not found.')
        if (selectedAccount?.id && report.accountId !== selectedAccount.id) {
          throw new Error('This Report belongs to a different account.')
        }

        const revisions = parseOptimizationRunRevisions(report.parameters)
        const selectedRevision = selectReportRevision(revisions, revision)
        const manifestBytes = await readTaskArtifact(selectedRevision.manifest, {
          issueTicket: issueTaskArtifactReadTicket,
        })
        const manifest = parseReportArtifactManifest(decodeUtf8(manifestBytes), revision)
        const descriptor = selectArtifactDescriptor(manifest, logicalId)
        const bytes = await readTaskArtifact(descriptor, {
          issueTicket: issueTaskArtifactReadTicket,
        })

        if (!cancelled) {
          setState({
            reportName: report.name || 'Optimization report',
            latestRevision: revisions.latestRevisionNumber,
            descriptor,
            bytes,
          })
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : String(loadError))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [logicalId, reportId, revision, selectedAccount?.id])

  const text = useMemo(() => {
    if (!state) return null
    if (
      state.descriptor.content_type === 'text/markdown' ||
      state.descriptor.content_type === 'text/csv' ||
      state.descriptor.content_type === 'application/json'
    ) {
      try {
        return decodeUtf8(state.bytes)
      } catch {
        return null
      }
    }
    return null
  }, [state])

  const download = () => {
    if (!state) return
    const bytes = state.bytes.slice().buffer
    const url = URL.createObjectURL(new Blob([bytes], {
      type: state.descriptor.content_type,
    }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = downloadName(state.descriptor)
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <Link
        href={`/lab/reports/${encodeURIComponent(reportId)}`}
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to living report
      </Link>

      {loading && (
        <div className="flex min-h-64 items-center justify-center rounded-lg bg-card">
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Authorizing and verifying artifact revision {revision}…
          </div>
        </div>
      )}

      {!loading && error && (
        <div className="rounded-lg bg-destructive/10 p-6 text-destructive">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <h1 className="font-semibold">Artifact unavailable</h1>
              <p className="mt-1 text-sm">{error}</p>
            </div>
          </div>
        </div>
      )}

      {!loading && state && (
        <>
          <section className="rounded-lg bg-card p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  {state.reportName} · revision {revision}
                </div>
                <h1 className="mt-2 text-2xl font-semibold">{state.descriptor.display_name}</h1>
                {state.descriptor.scorecard_name && (
                  <p className="mt-1 text-muted-foreground">{state.descriptor.scorecard_name}</p>
                )}
              </div>
              <Button onClick={download} className="gap-2">
                <Download className="h-4 w-4" />
                Download
              </Button>
            </div>
          </section>

          {state.latestRevision > revision && (
            <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-amber-500/10 p-4 text-sm">
              <span>
                You are viewing the evidence from revision {revision}. Revision {state.latestRevision} is newer.
              </span>
              <Link
                href={buildReportArtifactHref({
                  reportId,
                  revision: state.latestRevision,
                  logicalId,
                })}
                className="font-medium text-primary hover:underline"
              >
                Open newer revision
              </Link>
            </section>
          )}

          <section className="rounded-lg bg-card p-6">
            {state.descriptor.content_type === 'text/markdown' && text !== null ? (
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
              </div>
            ) : text !== null ? (
              <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap rounded-md bg-muted p-4 text-sm">
                {text}
              </pre>
            ) : (
              <p className="text-sm text-muted-foreground">
                This artifact is available for verified download but does not have an inline preview.
              </p>
            )}
          </section>
        </>
      )}
    </main>
  )
}
