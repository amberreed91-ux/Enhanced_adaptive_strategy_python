import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from "recharts";
import { 
  Activity, TrendingUp, AlertTriangle, Zap, Target, Shield,
  Database, Cpu, LineChart as LineChartIcon, Server
} from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const COLORS = ["#007AFF", "#00C853", "#FF3B30", "#FFD600", "#AA00FF"];

const StatCard = ({ title, value, subtitle, icon: Icon, trend }) => (
  <Card className="bg-card border-border">
    <CardContent className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="label-overline mb-1">{title}</p>
          <p className="text-2xl font-bold font-mono">{value}</p>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        <div className={`p-2 rounded-sm ${trend === "up" ? "bg-green-500/10" : trend === "down" ? "bg-red-500/10" : "bg-primary/10"}`}>
          <Icon className={`w-5 h-5 ${trend === "up" ? "text-profit" : trend === "down" ? "text-loss" : "text-primary"}`} />
        </div>
      </div>
    </CardContent>
  </Card>
);

const SystemHealthItem = ({ name, status }) => {
  const statusColors = {
    healthy: "status-healthy",
    warning: "status-warning",
    error: "status-error",
    idle: "status-idle"
  };

  return (
    <div className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
      <span className="text-sm text-muted-foreground">{name}</span>
      <Badge variant="outline" className={statusColors[status]}>
        {status}
      </Badge>
    </div>
  );
};

const RegimeBadge = ({ regime }) => {
  const regimeStyles = {
    "Trend": "bg-green-500/20 text-green-400 border-green-500/30",
    "Range": "bg-blue-500/20 text-blue-400 border-blue-500/30",
    "Volatility Expansion": "bg-orange-500/20 text-orange-400 border-orange-500/30",
    "Mean Reversion": "bg-purple-500/20 text-purple-400 border-purple-500/30"
  };

  return (
    <Badge variant="outline" className={`text-sm px-3 py-1 ${regimeStyles[regime] || "bg-secondary"}`}>
      {regime}
    </Badge>
  );
};

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const { getAuthHeader } = useAuth();

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/stats`, getAuthHeader());
      setStats(response.data);
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading dashboard...</div>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass px-3 py-2 rounded-sm">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-sm font-mono text-foreground">${payload[0].value.toLocaleString()}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6" data-testid="dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Research command center</p>
        </div>
        <Button variant="outline" onClick={fetchStats} data-testid="refresh-dashboard">
          <Activity className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Strategies"
          value={stats?.active_strategies || 0}
          subtitle={`${stats?.total_strategies || 0} total`}
          icon={Target}
          trend="up"
        />
        <StatCard
          title="Alpha Signals"
          value={stats?.total_signals || 0}
          subtitle="Discovered"
          icon={Zap}
        />
        <StatCard
          title="Backtests"
          value={stats?.total_backtests || 0}
          subtitle="Completed"
          icon={LineChartIcon}
        />
        <StatCard
          title="Current Drawdown"
          value={`${stats?.current_drawdown || 0}%`}
          subtitle={`Threshold: ${stats?.drawdown_threshold || 20}%`}
          icon={AlertTriangle}
          trend={stats?.current_drawdown > 10 ? "down" : "up"}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Curve */}
        <Card className="lg:col-span-2 bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              Portfolio Equity Curve
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={stats?.equity_curve || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis 
                    dataKey="date" 
                    tick={{ fill: "#a3a3a3", fontSize: 11 }}
                    tickFormatter={(val) => val.slice(5)}
                  />
                  <YAxis 
                    tick={{ fill: "#a3a3a3", fontSize: 11 }}
                    tickFormatter={(val) => `$${(val/1000).toFixed(0)}k`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Line 
                    type="monotone" 
                    dataKey="equity" 
                    stroke="#007AFF" 
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Market Regime & Research Cycle */}
        <div className="space-y-4">
          {/* Current Regime */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Market Regime</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-center py-4">
                <RegimeBadge regime={stats?.current_regime || "Unknown"} />
              </div>
            </CardContent>
          </Card>

          {/* Research Cycle Progress */}
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Research Cycle</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Progress</span>
                  <span className="text-sm font-mono">{stats?.research_cycle_progress || 0}%</span>
                </div>
                <Progress value={stats?.research_cycle_progress || 0} className="h-2" />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Bottom Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Signals */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" />
              Top Signals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(stats?.top_signals || []).map((signal, idx) => (
                <div key={idx} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                  <span className="text-sm truncate mr-2">{signal.name}</span>
                  <span className="text-sm font-mono text-profit">{(signal.ic * 100).toFixed(1)}%</span>
                </div>
              ))}
              {(!stats?.top_signals || stats.top_signals.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">No signals discovered yet</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Capital Allocation */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Target className="w-5 h-5 text-primary" />
              Capital Allocation
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.capital_allocation && stats.capital_allocation.length > 0 ? (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={stats.capital_allocation}
                      dataKey="allocation"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={2}
                    >
                      {stats.capital_allocation.map((_, idx) => (
                        <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip 
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          return (
                            <div className="glass px-3 py-2 rounded-sm">
                              <p className="text-xs">{payload[0].name}</p>
                              <p className="text-sm font-mono">{payload[0].value}%</p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No allocations yet</p>
            )}
          </CardContent>
        </Card>

        {/* System Health */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" />
              System Health
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              <SystemHealthItem name="Market Data" status={stats?.system_health?.market_data || "idle"} />
              <SystemHealthItem name="Feature Engine" status={stats?.system_health?.feature_engine || "idle"} />
              <SystemHealthItem name="Backtest Engine" status={stats?.system_health?.backtest_engine || "idle"} />
              <SystemHealthItem name="Execution" status={stats?.system_health?.execution_engine || "idle"} />
              <SystemHealthItem name="Risk Monitor" status={stats?.system_health?.risk_monitor || "idle"} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Risk Monitor */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-primary" />
              Risk Monitor
            </CardTitle>
            <Button variant="destructive" size="sm" data-testid="kill-switch">
              KILL SWITCH
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <p className="label-overline">Drawdown</p>
              <div className="flex items-center gap-4">
                <Progress 
                  value={(stats?.current_drawdown / stats?.drawdown_threshold) * 100 || 0} 
                  className="flex-1 h-3"
                />
                <span className={`font-mono text-sm ${stats?.current_drawdown > 15 ? "text-loss" : "text-profit"}`}>
                  {stats?.current_drawdown || 0}%
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <p className="label-overline">Active Positions</p>
              <p className="text-2xl font-mono">{stats?.active_strategies || 0}</p>
            </div>
            <div className="space-y-2">
              <p className="label-overline">Max Exposure</p>
              <p className="text-2xl font-mono">25%</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
