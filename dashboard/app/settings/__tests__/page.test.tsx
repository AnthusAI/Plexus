import SettingsPage from '../page'
import AccountSettingsPage from '../account/page'
import { redirect } from 'next/navigation'

jest.mock('next/navigation', () => ({
  redirect: jest.fn(),
}))

const mockRedirect = redirect as jest.MockedFunction<typeof redirect>

describe('settings redirects', () => {
  beforeEach(() => {
    mockRedirect.mockReset()
  })

  it('redirects /settings to the lab settings route', () => {
    SettingsPage()
    expect(mockRedirect).toHaveBeenCalledWith('/lab/settings')
  })

  it('redirects /settings/account to the lab account settings route', () => {
    AccountSettingsPage()
    expect(mockRedirect).toHaveBeenCalledWith('/lab/settings/account')
  })
})
