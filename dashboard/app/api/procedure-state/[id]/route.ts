import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3'
import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    if (!UUID_RE.test(id)) {
      return NextResponse.json({ error: 'Invalid ID' }, { status: 400 })
    }

    const apiUrl = process.env.PLEXUS_API_URL
    const apiKey = process.env.PLEXUS_API_KEY
    if (!apiUrl || !apiKey) {
      console.error('[procedure-state] Missing PLEXUS_API_URL or PLEXUS_API_KEY')
      return NextResponse.json({ error: 'API not configured' }, { status: 500 })
    }

    const gqlResponse = await fetch(apiUrl, {
      method: 'POST',
      headers: { 'x-api-key': apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: `query { getProcedure(id: "${id}") { metadata } }` }),
    })

    if (!gqlResponse.ok) {
      console.error('[procedure-state] GraphQL fetch failed:', gqlResponse.status)
      return NextResponse.json({ error: 'Failed to fetch procedure' }, { status: 502 })
    }

    const gqlData = await gqlResponse.json()
    const raw = gqlData.data?.getProcedure?.metadata
    if (!raw) {
      return NextResponse.json({ state: {} })
    }

    const metadata = typeof raw === 'string' ? JSON.parse(raw) : raw
    const state = metadata?.state || {}

    if (state._s3_key) {
      const s3 = new S3Client({
        region: process.env.AWS_REGION_NAME || process.env.AWS_DEFAULT_REGION || 'us-east-1',
        followRegionRedirects: true,
        credentials: {
          accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
          secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
        },
      })
      const obj = await s3.send(new GetObjectCommand({
        Bucket: process.env.AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME || 'reportblockdetails-production',
        Key: state._s3_key,
      }))
      const fullState = JSON.parse(await (obj.Body as any).transformToString())
      return NextResponse.json({ state: fullState })
    }

    return NextResponse.json({ state })
  } catch (err) {
    console.error('[procedure-state] Unhandled error:', err)
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
