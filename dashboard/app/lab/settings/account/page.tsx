"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useAuthenticator } from "@aws-amplify/ui-react"
import { generateClient } from "@aws-amplify/api"
import type { Schema } from "@/amplify/data/resource"
import type { AccountSettings } from "@/types/account-config"
import {
    isValidAccountSettings,
    mergeAccountSettings,
    validateDashboardBaseUrl,
} from "@/types/account-config"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { useAccount } from "@/app/contexts/AccountContext"
import { menuItems } from "@/components/dashboard-layout"

type Account = Schema["Account"]["type"]

let amplifyClient: ReturnType<typeof generateClient<Schema>> | null = null
const getAmplifyClient = () => (amplifyClient ??= generateClient<Schema>())

const accountApi = {
    async update(id: string, settings: string) {
        type UpdateAccountFn = (args: { id: string; settings: string }) => Promise<Account>
        const update = getAmplifyClient().models.Account.update as unknown as UpdateAccountFn
        return update({ id, settings })
    }
}

const MENU_ITEMS = menuItems.map((item) => item.name)

export default function LabAccountSettings() {
    const { authStatus } = useAuthenticator((context) => [context.authStatus])
    const router = useRouter()
    const { toast } = useToast()
    const { selectedAccount, refreshAccount } = useAccount()
    const [hiddenItems, setHiddenItems] = useState<string[]>([])
    const [dashboardBaseUrl, setDashboardBaseUrl] = useState("")
    const [dashboardBaseUrlError, setDashboardBaseUrlError] = useState<string | null>(null)
    const [isSaving, setIsSaving] = useState(false)

    useEffect(() => {
        if (authStatus !== "authenticated") {
            router.push("/")
        }
    }, [authStatus, router])

    useEffect(() => {
        if (selectedAccount?.settings) {
            const parsedSettings = typeof selectedAccount.settings === 'string' ?
                JSON.parse(selectedAccount.settings) : selectedAccount.settings
            if (isValidAccountSettings(parsedSettings)) {
                setHiddenItems(parsedSettings.hiddenMenuItems)
                setDashboardBaseUrl(parsedSettings.reporting?.dashboardBaseUrl ?? "")
            }
        }
    }, [selectedAccount])

    const handleToggleMenuItem = (item: string) => {
        setHiddenItems(current => {
            if (current.includes(item)) {
                return current.filter(i => i !== item)
            }
            return [...current, item]
        })
    }

    const handleSave = async () => {
        if (!selectedAccount) return

        setIsSaving(true)
        try {
            const parsedSettings = selectedAccount.settings
                ? (typeof selectedAccount.settings === 'string'
                    ? JSON.parse(selectedAccount.settings)
                    : selectedAccount.settings)
                : { hiddenMenuItems: [] }
            const currentSettings: AccountSettings = isValidAccountSettings(parsedSettings)
                ? parsedSettings
                : { hiddenMenuItems: [] }
            const validation = validateDashboardBaseUrl(dashboardBaseUrl)
            if (!validation.valid) {
                setDashboardBaseUrlError(validation.message)
                return
            }

            const newSettings = mergeAccountSettings(currentSettings, {
                hiddenMenuItems: hiddenItems,
                dashboardBaseUrl,
            })
            await accountApi.update(selectedAccount.id, JSON.stringify(newSettings))
            
            // Refresh the account data to update the menu
            await refreshAccount()

            toast({
                title: "Success",
                description: "Account settings saved successfully"
            })
            router.push("/lab/settings")
        } catch (error) {
            console.error("Error saving settings:", error)
            toast({
                title: "Error",
                description: "Failed to save account settings",
                variant: "destructive"
            })
        } finally {
            setIsSaving(false)
        }
    }

    if (authStatus !== "authenticated") {
        return null
    }

    if (!selectedAccount) {
        return (
            <div className="px-6 pt-0 pb-6">
                <p>No account selected</p>
            </div>
        )
    }

    return (
        <div className="px-6 pt-0 pb-6 space-y-6">
            <div>
                <h1 className="text-3xl font-bold">Account Settings</h1>
                <p className="text-muted-foreground">
                    Configure account-wide dashboard behavior and menu visibility.
                </p>
            </div>

            <div className="bg-card p-6 space-y-4 rounded-lg">
                <div>
                    <h2 className="text-xl font-semibold">Report Links for {selectedAccount.name}</h2>
                    <p className="text-muted-foreground">
                        Set the deployed dashboard origin used for durable links in reports and exported artifacts.
                    </p>
                </div>
                <div className="space-y-2">
                    <Label htmlFor="dashboard-base-url">Dashboard base URL</Label>
                    <Input
                        id="dashboard-base-url"
                        type="url"
                        value={dashboardBaseUrl}
                        placeholder="https://dashboard.example.com"
                        aria-invalid={Boolean(dashboardBaseUrlError)}
                        aria-describedby={dashboardBaseUrlError ? "dashboard-base-url-error" : undefined}
                        onChange={(event) => {
                            setDashboardBaseUrl(event.target.value)
                            setDashboardBaseUrlError(null)
                        }}
                        onBlur={() => {
                            const validation = validateDashboardBaseUrl(dashboardBaseUrl)
                            if (!validation.valid) {
                                setDashboardBaseUrlError(validation.message)
                            }
                        }}
                    />
                    {dashboardBaseUrlError && (
                        <p id="dashboard-base-url-error" className="text-sm text-destructive">
                            {dashboardBaseUrlError}
                        </p>
                    )}
                    <p className="text-sm text-muted-foreground">
                        Use the HTTPS origin only, without a path. Leave blank until the deployed URL is known.
                    </p>
                </div>
            </div>

            <div className="bg-card p-6 space-y-6 rounded-lg">
                <div>
                    <h2 className="text-xl font-semibold">Menu Visibility for {selectedAccount.name}</h2>
                    <p className="text-muted-foreground">
                        Choose which menu items to show or hide in the sidebar.
                    </p>
                </div>
                <div className="space-y-4">
                    {MENU_ITEMS.map((item) => (
                        <div key={item} className="flex items-center space-x-4">
                            <Switch 
                                id={`menu-${item}`}
                                checked={!hiddenItems.includes(item)}
                                onCheckedChange={() => handleToggleMenuItem(item)}
                            />
                            <Label htmlFor={`menu-${item}`}>{item}</Label>
                        </div>
                    ))}
                </div>
                <Button 
                    onClick={handleSave} 
                    disabled={isSaving}
                >
                    {isSaving ? "Saving..." : "Save Changes"}
                </Button>
            </div>
        </div>
    )
} 
