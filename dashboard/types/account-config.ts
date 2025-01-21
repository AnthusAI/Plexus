export interface AccountSettings {
    hiddenMenuItems: string[]
}

export function isValidAccountSettings(
    settings: unknown
): settings is AccountSettings {
    if (!settings || typeof settings !== 'object') {
        return false
    }

    const candidate = settings as AccountSettings
    return Array.isArray(candidate.hiddenMenuItems) && 
        candidate.hiddenMenuItems.every(item => typeof item === 'string')
} 