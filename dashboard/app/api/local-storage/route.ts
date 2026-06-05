import { GetObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

const DEFAULT_BUCKET = "plexus-local-report-block-details"

function localBackendEnabled() {
  return (
    process.env.NEXT_PUBLIC_PLEXUS_BACKEND === "local" ||
    process.env.PLEXUS_BACKEND_MODE === "local"
  )
}

function bucketName() {
  return process.env.AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME || DEFAULT_BUCKET
}

function objectKey(request: Request) {
  const url = new URL(request.url)
  const path = (url.searchParams.get("path") || "").trim()
  if (!path || path.startsWith("/") || path.includes("..")) {
    throw new Error("Invalid local storage path")
  }
  return path
}

function s3Client() {
  const endpoint = process.env.PLEXUS_OBJECT_STORE_ENDPOINT
  if (!endpoint) {
    throw new Error("PLEXUS_OBJECT_STORE_ENDPOINT is required in local storage mode")
  }

  const accessKeyId = process.env.PLEXUS_OBJECT_STORE_ACCESS_KEY_ID
  const secretAccessKey = process.env.PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY
  if (!accessKeyId || !secretAccessKey) {
    throw new Error("PLEXUS_OBJECT_STORE_ACCESS_KEY_ID and PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY are required")
  }

  return new S3Client({
    endpoint,
    region: process.env.PLEXUS_OBJECT_STORE_REGION || "us-east-1",
    forcePathStyle: String(process.env.PLEXUS_OBJECT_STORE_FORCE_PATH_STYLE || "true").toLowerCase() === "true",
    credentials: {
      accessKeyId,
      secretAccessKey,
    },
  })
}

async function streamToBytes(body: any): Promise<Uint8Array> {
  if (!body) {
    return new Uint8Array()
  }
  if (typeof body.transformToByteArray === "function") {
    return body.transformToByteArray()
  }

  const chunks: Buffer[] = []
  for await (const chunk of body) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
  }
  return Buffer.concat(chunks)
}

function localOnlyResponse() {
  return Response.json({ error: "Local storage is only available in local backend mode." }, { status: 404 })
}

export async function GET(request: Request) {
  if (!localBackendEnabled()) {
    return localOnlyResponse()
  }

  try {
    const key = objectKey(request)
    const result = await s3Client().send(
      new GetObjectCommand({
        Bucket: bucketName(),
        Key: key,
      }),
    )
    const bytes = await streamToBytes(result.Body)
    return new Response(bytes, {
      headers: {
        "content-type": result.ContentType || "application/octet-stream",
        "cache-control": "no-store",
      },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to download local object"
    return Response.json({ error: message }, { status: 404 })
  }
}

export async function PUT(request: Request) {
  if (!localBackendEnabled()) {
    return localOnlyResponse()
  }

  try {
    const key = objectKey(request)
    const body = Buffer.from(await request.arrayBuffer())
    await s3Client().send(
      new PutObjectCommand({
        Bucket: bucketName(),
        Key: key,
        Body: body,
        ContentType: request.headers.get("content-type") || "application/octet-stream",
      }),
    )
    return Response.json({ path: key, key })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to upload local object"
    return Response.json({ error: message }, { status: 500 })
  }
}

export const POST = PUT
