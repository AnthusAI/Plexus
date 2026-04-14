import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3'
import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params
    if (!UUID_RE.test(id)) {
      return NextResponse.json({ error: 'Invalid ID' }, { status: 400 })
    }

    const s3key = req.nextUrl.searchParams.get('s3key')
    if (!s3key) {
      return NextResponse.json({ error: 'Missing s3key parameter' }, { status: 400 })
    }

    // Use explicit credentials when available (dev), otherwise fall back to
    // the Lambda IAM role automatically provided by Amplify Hosting (prod).
    const credentialOptions = process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY
      ? { credentials: {
          accessKeyId: process.env.AWS_ACCESS_KEY_ID,
          secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
        }}
      : {}

    const s3 = new S3Client({
      region: process.env.AWS_REGION_NAME || process.env.AWS_DEFAULT_REGION || 'us-east-1',
      followRegionRedirects: true,
      ...credentialOptions,
    })

    const obj = await s3.send(new GetObjectCommand({
      Bucket: process.env.AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME!,
      Key: s3key,
    }))
    const fullState = JSON.parse(await (obj.Body as any).transformToString())
    return NextResponse.json({ state: fullState })
  } catch (err) {
    console.error('[procedure-state] S3 fetch error:', err)
    return NextResponse.json({ error: String(err) }, { status: 500 })
  }
}
