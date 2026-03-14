import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Settings, Key, Bell, Database, Server, Check, X } from "lucide-react";
import { toast } from "sonner";

const EXCHANGES = [
  { id: "binance", name: "Binance", type: "crypto", status: "mocked" },
  { id: "coinbase", name: "Coinbase Advanced Trade", type: "crypto", status: "mocked" },
  { id: "kraken", name: "Kraken", type: "crypto", status: "mocked" },
  { id: "cme", name: "CME Group", type: "futures", status: "mocked" }
];

export default function SettingsPage() {
  const { user } = useAuth();
  const [apiKeys, setApiKeys] = useState({
    binance: { key: "", secret: "" },
    coinbase: { key: "", secret: "" },
    kraken: { key: "", secret: "" },
    cme: { key: "", secret: "" }
  });

  const [preferences, setPreferences] = useState({
    autoRefresh: true,
    emailNotifications: false,
    riskAlerts: true,
    darkMode: true
  });

  const handleSaveApiKey = (exchange) => {
    toast.success(`${exchange} API key saved (MOCKED - keys will be validated when live)`);
  };

  return (
    <div className="space-y-6" data-testid="settings-page">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Manage your account and connections</p>
      </div>

      <Tabs defaultValue="connections" className="space-y-6">
        <TabsList>
          <TabsTrigger value="connections" data-testid="connections-tab">
            <Server className="w-4 h-4 mr-2" />
            Exchange Connections
          </TabsTrigger>
          <TabsTrigger value="preferences" data-testid="preferences-tab">
            <Settings className="w-4 h-4 mr-2" />
            Preferences
          </TabsTrigger>
          <TabsTrigger value="account" data-testid="account-tab">
            <Key className="w-4 h-4 mr-2" />
            Account
          </TabsTrigger>
        </TabsList>

        {/* Exchange Connections */}
        <TabsContent value="connections">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {EXCHANGES.map(exchange => (
              <Card key={exchange.id} className="bg-card border-border">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{exchange.name}</CardTitle>
                    <Badge variant="outline" className="status-warning">
                      {exchange.status}
                    </Badge>
                  </div>
                  <CardDescription className="capitalize">{exchange.type}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>API Key</Label>
                      <Input
                        type="password"
                        placeholder="Enter API key"
                        value={apiKeys[exchange.id].key}
                        onChange={(e) => setApiKeys({
                          ...apiKeys,
                          [exchange.id]: { ...apiKeys[exchange.id], key: e.target.value }
                        })}
                        data-testid={`${exchange.id}-api-key`}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>API Secret</Label>
                      <Input
                        type="password"
                        placeholder="Enter API secret"
                        value={apiKeys[exchange.id].secret}
                        onChange={(e) => setApiKeys({
                          ...apiKeys,
                          [exchange.id]: { ...apiKeys[exchange.id], secret: e.target.value }
                        })}
                        data-testid={`${exchange.id}-api-secret`}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
                        <span className="text-xs text-muted-foreground">Using mock data</span>
                      </div>
                      <Button 
                        size="sm" 
                        onClick={() => handleSaveApiKey(exchange.name)}
                        data-testid={`save-${exchange.id}-key`}
                      >
                        Save
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="mt-6 bg-card border-border">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Database className="w-5 h-5 text-primary" />
                Connection Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {EXCHANGES.map(exchange => (
                  <div key={exchange.id} className="flex items-center gap-3 p-3 rounded-sm bg-secondary/30">
                    <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                    <div>
                      <p className="text-sm font-medium">{exchange.name}</p>
                      <p className="text-xs text-muted-foreground">Mocked</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Preferences */}
        <TabsContent value="preferences">
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-lg">User Preferences</CardTitle>
              <CardDescription>Customize your experience</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Auto Refresh</p>
                    <p className="text-sm text-muted-foreground">Automatically refresh data every 30 seconds</p>
                  </div>
                  <Switch
                    checked={preferences.autoRefresh}
                    onCheckedChange={(checked) => setPreferences({ ...preferences, autoRefresh: checked })}
                    data-testid="auto-refresh-toggle"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Email Notifications</p>
                    <p className="text-sm text-muted-foreground">Receive email alerts for important events</p>
                  </div>
                  <Switch
                    checked={preferences.emailNotifications}
                    onCheckedChange={(checked) => setPreferences({ ...preferences, emailNotifications: checked })}
                    data-testid="email-notifications-toggle"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Risk Alerts</p>
                    <p className="text-sm text-muted-foreground">Get notified when risk thresholds are breached</p>
                  </div>
                  <Switch
                    checked={preferences.riskAlerts}
                    onCheckedChange={(checked) => setPreferences({ ...preferences, riskAlerts: checked })}
                    data-testid="risk-alerts-toggle"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Dark Mode</p>
                    <p className="text-sm text-muted-foreground">Use dark theme (locked for trading terminal aesthetic)</p>
                  </div>
                  <Switch
                    checked={preferences.darkMode}
                    disabled
                    data-testid="dark-mode-toggle"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Account */}
        <TabsContent value="account">
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-lg">Account Information</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input value={user?.name || ""} disabled />
                  </div>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input value={user?.email || ""} disabled />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Account Created</Label>
                  <Input value={user?.created_at?.slice(0, 10) || ""} disabled />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="mt-6 bg-card border-border">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Bell className="w-5 h-5 text-primary" />
                System Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between py-2 border-b border-border/50">
                  <span className="text-sm">API Backend</span>
                  <div className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-profit" />
                    <span className="text-sm text-profit">Connected</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-border/50">
                  <span className="text-sm">Database</span>
                  <div className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-profit" />
                    <span className="text-sm text-profit">MongoDB Connected</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-border/50">
                  <span className="text-sm">AI Assistant</span>
                  <div className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-profit" />
                    <span className="text-sm text-profit">GPT-5.2 Active</span>
                  </div>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm">Exchange APIs</span>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
                    <span className="text-sm text-yellow-400">Mocked</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
