import {
    isValidAccountSettings,
    mergeAccountSettings,
    validateDashboardBaseUrl,
    type AccountSettings,
} from '../account-config'

describe('AccountSettings validation', () => {
    it('accepts valid settings with empty array', () => {
        const settings: AccountSettings = {
            hiddenMenuItems: []
        }
        expect(isValidAccountSettings(settings)).toBe(true)
    })

    it('accepts valid settings with string array', () => {
        const settings: AccountSettings = {
            hiddenMenuItems: ['Feedback', 'Activity', 'Evaluations']
        }
        expect(isValidAccountSettings(settings)).toBe(true)
    })

    it('accepts a valid reporting dashboard base URL', () => {
        const settings: AccountSettings = {
            hiddenMenuItems: [],
            reporting: {
                dashboardBaseUrl: 'https://dashboard.example.com',
            },
        }
        expect(isValidAccountSettings(settings)).toBe(true)
    })

    it('accepts legacy settings without reporting configuration', () => {
        expect(isValidAccountSettings({ hiddenMenuItems: ['Feedback'] })).toBe(true)
    })

    it.each([
        'http://dashboard.example.com',
        'ftp://dashboard.example.com',
        'https://user:secret@dashboard.example.com',
        'https://dashboard.example.com/path',
        'not a URL',
    ])('rejects unsafe or malformed dashboard base URL %s', (dashboardBaseUrl) => {
        expect(isValidAccountSettings({
            hiddenMenuItems: [],
            reporting: { dashboardBaseUrl },
        })).toBe(false)
    })

    it('reports an actionable dashboard URL validation error', () => {
        expect(validateDashboardBaseUrl('http://dashboard.example.com')).toEqual({
            valid: false,
            message: 'Enter an HTTPS dashboard origin without a path, query, fragment, or credentials.',
        })
    })

    it('preserves unrelated settings when account settings are merged', () => {
        expect(mergeAccountSettings(
            {
                hiddenMenuItems: ['Feedback'],
                featureFlags: { beta: true },
                reporting: { existingSetting: 'preserve-me' },
            },
            {
                hiddenMenuItems: ['Activity'],
                dashboardBaseUrl: 'https://dashboard.example.com/',
            },
        )).toEqual({
            hiddenMenuItems: ['Activity'],
            featureFlags: { beta: true },
            reporting: {
                existingSetting: 'preserve-me',
                dashboardBaseUrl: 'https://dashboard.example.com',
            },
        })
    })

    it('removes only the dashboard URL when it is left unset', () => {
        expect(mergeAccountSettings(
            {
                hiddenMenuItems: [],
                reporting: {
                    dashboardBaseUrl: 'https://old.example.com',
                    existingSetting: 'preserve-me',
                },
            },
            { hiddenMenuItems: [], dashboardBaseUrl: '' },
        )).toEqual({
            hiddenMenuItems: [],
            reporting: { existingSetting: 'preserve-me' },
        })
    })

    it('rejects null input', () => {
        expect(isValidAccountSettings(null)).toBe(false)
    })

    it('rejects undefined input', () => {
        expect(isValidAccountSettings(undefined)).toBe(false)
    })

    it('rejects missing hiddenMenuItems', () => {
        const settings = {}
        expect(isValidAccountSettings(settings)).toBe(false)
    })

    it('rejects non-array hiddenMenuItems', () => {
        const settings = {
            hiddenMenuItems: 'not an array'
        }
        expect(isValidAccountSettings(settings)).toBe(false)
    })

    it('rejects array with non-string elements', () => {
        const settings = {
            hiddenMenuItems: ['Feedback', 123, 'Activity']
        }
        expect(isValidAccountSettings(settings)).toBe(false)
    })
})
