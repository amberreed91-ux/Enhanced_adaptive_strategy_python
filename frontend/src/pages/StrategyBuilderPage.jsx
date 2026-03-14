import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { FlaskConical, Plus, Loader2, Trash2, Edit, Play } from "lucide-react";
import { toast } from "sonner";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const POSITION_SIZING = ["fixed", "volatility_adjusted", "risk_parity"];
const STRATEGY_STATUS = ["draft", "testing", "live", "retired"];

export default function StrategyBuilderPage() {
  const [strategies, setStrategies] = useState([]);
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const { getAuthHeader } = useAuth();

  const [formData, setFormData] = useState({
    name: "",
    signal_ids: [],
    entry_rules: { condition: "signal_threshold", value: 0.5 },
    exit_rules: { target: 2.0, stop: 1.0, trailing_stop: 0.5 },
    position_sizing: "fixed",
    risk_params: { max_loss_per_trade: 1.0, max_daily_loss: 3.0, max_drawdown: 10.0 }
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [strategiesRes, signalsRes] = await Promise.all([
        axios.get(`${API}/strategies/`, getAuthHeader()),
        axios.get(`${API}/signals/`, getAuthHeader())
      ]);
      setStrategies(strategiesRes.data);
      setSignals(signalsRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name) {
      toast.error("Please enter a strategy name");
      return;
    }

    setSubmitting(true);
    try {
      await axios.post(`${API}/strategies/`, formData, getAuthHeader());
      toast.success("Strategy created successfully");
      setDialogOpen(false);
      fetchData();
      resetForm();
    } catch (error) {
      toast.error("Failed to create strategy");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (strategyId) => {
    try {
      await axios.delete(`${API}/strategies/${strategyId}`, getAuthHeader());
      toast.success("Strategy deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete strategy");
    }
  };

  const handleStatusChange = async (strategyId, status) => {
    try {
      await axios.patch(`${API}/strategies/${strategyId}/status?status=${status}`, {}, getAuthHeader());
      toast.success("Status updated");
      fetchData();
    } catch (error) {
      toast.error("Failed to update status");
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      signal_ids: [],
      entry_rules: { condition: "signal_threshold", value: 0.5 },
      exit_rules: { target: 2.0, stop: 1.0, trailing_stop: 0.5 },
      position_sizing: "fixed",
      risk_params: { max_loss_per_trade: 1.0, max_daily_loss: 3.0, max_drawdown: 10.0 }
    });
  };

  const getStatusBadge = (status) => {
    const styles = {
      draft: "bg-gray-500/20 text-gray-400 border-gray-500/30",
      testing: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
      live: "bg-green-500/20 text-green-400 border-green-500/30",
      retired: "bg-red-500/20 text-red-400 border-red-500/30"
    };
    return styles[status] || styles.draft;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading strategies...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="strategy-builder-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Strategy Builder</h1>
          <p className="text-muted-foreground">Build and manage trading strategies</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="create-strategy-btn">
              <Plus className="w-4 h-4 mr-2" />
              New Strategy
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-card border-border max-w-2xl max-h-[85vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>Create New Strategy</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4 overflow-y-auto pr-2 flex-1">
              {/* Strategy Name */}
              <div className="space-y-2">
                <Label>Strategy Name</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Momentum Breakout v1"
                  data-testid="strategy-name-input"
                />
              </div>

              {/* Signal Selection */}
              <div className="space-y-2">
                <Label>Alpha Signals</Label>
                <Select
                  value={formData.signal_ids[0] || ""}
                  onValueChange={(v) => setFormData({ ...formData, signal_ids: [v] })}
                >
                  <SelectTrigger data-testid="signal-select">
                    <SelectValue placeholder="Select signals" />
                  </SelectTrigger>
                  <SelectContent>
                    {signals.length === 0 ? (
                      <div className="px-2 py-4 text-sm text-muted-foreground text-center">
                        No signals available. Generate features first.
                      </div>
                    ) : (
                      signals.map(s => (
                        <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              {/* Entry Rules */}
              <div className="space-y-2">
                <Label>Entry Rules</Label>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Condition</Label>
                    <Select
                      value={formData.entry_rules.condition}
                      onValueChange={(v) => setFormData({ 
                        ...formData, 
                        entry_rules: { ...formData.entry_rules, condition: v } 
                      })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="signal_threshold">Signal Threshold</SelectItem>
                        <SelectItem value="momentum_crossover">Momentum Crossover</SelectItem>
                        <SelectItem value="volatility_breakout">Volatility Breakout</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Threshold Value</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.entry_rules.value}
                      onChange={(e) => setFormData({
                        ...formData,
                        entry_rules: { ...formData.entry_rules, value: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                </div>
              </div>

              {/* Exit Rules */}
              <div className="space-y-2">
                <Label>Exit Rules</Label>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Target (%)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.exit_rules.target}
                      onChange={(e) => setFormData({
                        ...formData,
                        exit_rules: { ...formData.exit_rules, target: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Stop Loss (%)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.exit_rules.stop}
                      onChange={(e) => setFormData({
                        ...formData,
                        exit_rules: { ...formData.exit_rules, stop: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Trailing Stop (%)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.exit_rules.trailing_stop}
                      onChange={(e) => setFormData({
                        ...formData,
                        exit_rules: { ...formData.exit_rules, trailing_stop: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                </div>
              </div>

              {/* Position Sizing */}
              <div className="space-y-2">
                <Label>Position Sizing</Label>
                <Select
                  value={formData.position_sizing}
                  onValueChange={(v) => setFormData({ ...formData, position_sizing: v })}
                >
                  <SelectTrigger data-testid="position-sizing-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {POSITION_SIZING.map(ps => (
                      <SelectItem key={ps} value={ps}>{ps.replace("_", " ")}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Risk Parameters */}
              <div className="space-y-2">
                <Label>Risk Parameters</Label>
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Max Loss/Trade (%)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.risk_params.max_loss_per_trade}
                      onChange={(e) => setFormData({
                        ...formData,
                        risk_params: { ...formData.risk_params, max_loss_per_trade: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Max Daily Loss (%)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.risk_params.max_daily_loss}
                      onChange={(e) => setFormData({
                        ...formData,
                        risk_params: { ...formData.risk_params, max_daily_loss: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Max Drawdown (%)</Label>
                    <Input
                      type="number"
                      step="0.1"
                      value={formData.risk_params.max_drawdown}
                      onChange={(e) => setFormData({
                        ...formData,
                        risk_params: { ...formData.risk_params, max_drawdown: parseFloat(e.target.value) }
                      })}
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="pt-4 border-t border-border mt-4">
              <Button onClick={handleSubmit} disabled={submitting} className="w-full" data-testid="submit-strategy">
                {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
                Create Strategy
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Strategies List */}
        <Card className="lg:col-span-2 bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-primary" />
              Strategies
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table className="data-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Position Sizing</TableHead>
                  <TableHead>Risk (Max DD)</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {strategies.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      No strategies created yet. Click "New Strategy" to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  strategies.map(strategy => (
                    <TableRow key={strategy.id}>
                      <TableCell className="font-medium">{strategy.name}</TableCell>
                      <TableCell className="capitalize">{strategy.position_sizing.replace("_", " ")}</TableCell>
                      <TableCell>{strategy.risk_params.max_drawdown}%</TableCell>
                      <TableCell>
                        <Select
                          value={strategy.status}
                          onValueChange={(v) => handleStatusChange(strategy.id, v)}
                        >
                          <SelectTrigger className="w-24 h-7">
                            <Badge variant="outline" className={getStatusBadge(strategy.status)}>
                              {strategy.status}
                            </Badge>
                          </SelectTrigger>
                          <SelectContent>
                            {STRATEGY_STATUS.map(s => (
                              <SelectItem key={s} value={s}>{s}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {strategy.created_at.slice(0, 10)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(strategy.id)}
                          data-testid={`delete-strategy-${strategy.id}`}
                        >
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <div className="space-y-4">
          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Strategy Stats</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Total Strategies</span>
                  <span className="font-mono text-lg">{strategies.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Live</span>
                  <Badge variant="outline" className="status-healthy">
                    {strategies.filter(s => s.status === "live").length}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Testing</span>
                  <Badge variant="outline" className="status-warning">
                    {strategies.filter(s => s.status === "testing").length}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Draft</span>
                  <Badge variant="outline" className="status-idle">
                    {strategies.filter(s => s.status === "draft").length}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Available Signals</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {signals.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No signals available
                  </p>
                ) : (
                  signals.slice(0, 5).map(signal => (
                    <div key={signal.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                      <span className="text-sm truncate mr-2">{signal.name}</span>
                      <Badge variant="outline">{signal.market}</Badge>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
