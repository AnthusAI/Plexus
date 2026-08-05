export interface AccountReportingSettings {
    dashboardBaseUrl?: string
    [key: string]: unknown
}

export interface AccountSettings {
    hiddenMenuItems: string[]
    reporting?: AccountReportingSettings
    [key: string]: unknown
}

export type DashboardBaseUrlValidation =
    | { valid: true; normalizedUrl?: string }
    | { valid: false; message: string }

const DASHBOARD_BASE_URL_ERROR =
    'Enter an HTTPS dashboard origin without a path, query, fragment, or credentials.'

export function validateDashboardBaseUrl(value: string): DashboardBaseUrlValidation {
    const trimmed = value.trim()
    if (!trimmed) {
        return { valid: true }
    }

    try {
        const url = new URL(trimmed)
        const isOriginOnly =
            (url.pathname === '/' || url.pathname === '') &&
            !url.search &&
            !url.hash
        if (
            url.protocol !== 'https:' ||
            url.username ||
            url.password ||
            !url.hostname ||
            !isOriginOnly
        ) {
            return { valid: false, message: DASHBOARD_BASE_URL_ERROR }
        }

        return { valid: true, normalizedUrl: url.origin }
    } catch {
        return { valid: false, message: DASHBOARD_BASE_URL_ERROR }
    }
}

export function isValidAccountSettings(
    settings: unknown
): settings is AccountSettings {
    if (!settings || typeof settings !== 'object') {
        return false
    }

    const candidate = settings as AccountSettings
    if (
        !Array.isArray(candidate.hiddenMenuItems) ||
        !candidate.hiddenMenuItems.every(item => typeof item === 'string')
    ) {
        return false
    }

    if (candidate.reporting === undefined) {
        return true
    }
    if (!candidate.reporting || typeof candidate.reporting !== 'object') {
        return false
    }

    const dashboardBaseUrl = candidate.reporting.dashboardBaseUrl
    return dashboardBaseUrl === undefined || (
        typeof dashboardBaseUrl === 'string' &&
        validateDashboardBaseUrl(dashboardBaseUrl).valid
    )
}

export function mergeAccountSettings(
    current: AccountSettings,
    updates: { hiddenMenuItems: string[]; dashboardBaseUrl: string },
): AccountSettings {
    const validation = validateDashboardBaseUrl(updates.dashboardBaseUrl)
    if (!validation.valid) {
        throw new Error(validation.message)
    }

    const reporting = {
        ...(current.reporting ?? {}),
    }
    if (validation.normalizedUrl) {
        reporting.dashboardBaseUrl = validation.normalizedUrl
    } else {
        delete reporting.dashboardBaseUrl
    }

    return {
        ...current,
        hiddenMenuItems: updates.hiddenMenuItems,
        reporting,
    }
}
