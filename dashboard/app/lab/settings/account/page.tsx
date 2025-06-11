"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useAuthenticator } from "@aws-amplify/ui-react"
import { generateClient } from "@aws-amplify/api"
import type { Schema } from "@/amplify/data/resource"
import type { AccountSettings } from "@/types/account-config"
import { isValidAccountSettings } from "@/types/account-config"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { useAccount } from "@/app/contexts/AccountContext"

type Account = Schema["Account"]["type"]

const client = generateClient<Schema>()

const accountApi = {
    async update(id: string, settings: string) {
        type UpdateAccountFn = (args: { id: string; settings: string }) => Promise<Account>
        const update = client.models.Account.update as unknown as UpdateAccountFn
        return update({ id, settings })
    }
}

const MENU_ITEMS = [
    "Activity",
    "Scorecards",
    "Sources",
    "Evaluations",
    "Items",
    "Batches",
    "Feedback",
    "Reports",
    "Alerts"
]

export default function LabAccountSettings() {
    const { authStatus } = useAuthenticator((context) => [context.authStatus])
    const router = useRouter()
    const { toast } = useToast()
    const { selectedAccount, refreshAccount } = useAccount()
    const [hiddenItems, setHiddenItems] = useState<string[]>([])
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
            const newSettings: AccountSettings = {
                hiddenMenuItems: hiddenItems
            }
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
                    Customize your account menu visibility settings.
                </p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Menu Visibility for {selectedAccount.name}</CardTitle>
                    <CardDescription>
                        Choose which menu items to show or hide in the sidebar.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
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
                </CardContent>
            </Card>
        </div>
    )
} 