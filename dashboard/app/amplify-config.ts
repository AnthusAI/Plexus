type AmplifyOutputs = Record<string, any>

function loadLocalAmplifyOutputs(): AmplifyOutputs | null {
  try {
    return require('../amplify_outputs.json')
  } catch {
    return null
  }
}

export function resolveAmplifyOutputs(
  env: NodeJS.ProcessEnv = process.env,
  outputsLoader: () => AmplifyOutputs | null = loadLocalAmplifyOutputs,
): AmplifyOutputs | null {
  if (env.NEXT_PUBLIC_PLEXUS_BACKEND === 'local') {
    return {
      data: {
        url: env.NEXT_PUBLIC_PLEXUS_API_URL || 'http://localhost:18080/graphql',
        api_key: env.NEXT_PUBLIC_PLEXUS_API_KEY || 'local-smoke-key',
        aws_region: env.NEXT_PUBLIC_PLEXUS_API_REGION || 'local',
        default_authorization_type: 'API_KEY',
        authorization_types: ['API_KEY'],
      },
      auth: {
        user_pool_id: 'local-demo-user-pool',
        user_pool_client_id: 'local-demo-client',
        aws_region: env.NEXT_PUBLIC_PLEXUS_API_REGION || 'local',
      },
      storage: {
        aws_region: env.NEXT_PUBLIC_PLEXUS_API_REGION || 'local',
        bucket_name: 'local-demo',
      },
    }
  }

  const outputs = outputsLoader()
  if (!outputs) {
    return null
  }

  const legacyApiUrl = env.NEXT_PUBLIC_PLEXUS_API_URL?.trim()
  const legacyApiKey = env.NEXT_PUBLIC_PLEXUS_API_KEY?.trim()
  if (legacyApiUrl || legacyApiKey) {
    console.warn(
      'Ignoring legacy NEXT_PUBLIC_PLEXUS_API_URL/NEXT_PUBLIC_PLEXUS_API_KEY in non-local mode. Using amplify_outputs.json auth configuration.',
    )
  }

  return outputs
}
