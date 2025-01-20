import { isValidAccountSettings, type AccountSettings } from '../account-config'

describe('AccountSettings validation', () => {
    it('accepts valid settings with empty array', () => {
        const settings: AccountSettings = {
            hiddenMenuItems: []
        }
        expect(isValidAccountSettings(settings)).toBe(true)
    })

    it('accepts valid settings with string array', () => {
        const settings: AccountSettings = {
            hiddenMenuItems: ['dashboard', 'settings', 'evaluations']
        }
        expect(isValidAccountSettings(settings)).toBe(true)
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
            hiddenMenuItems: 'dashboard'
        }
        expect(isValidAccountSettings(settings)).toBe(false)
    })

    it('rejects array with non-string elements', () => {
        const settings = {
            hiddenMenuItems: ['dashboard', 42, 'settings']
        }
        expect(isValidAccountSettings(settings)).toBe(false)
    })
}) 