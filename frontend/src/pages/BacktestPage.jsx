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
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area
} from "recharts";
import { LineChart as LineChartIcon, Play, Loader2, CalendarIcon, Eye } from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIMEFRAMES = ["1D", "30m", "5m", "1m"];

export default function BacktestPage() {
  const [strategies, setStrategies] = useState([]);
  const [backtests, setBacktests] = useState([]);
  const [selectedBacktest, setSelectedBacktest] = useState(null);
  const [assets, setAssets] = useState({ futures: [], crypto: [] });
  const [exchanges, setExchanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const { getAuthHeader } = useAuth();

  const [formData, setFormData] = useState({
    strategy_id: "",
    asset: "",
    exchange: "",
    start_date: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000),
    end_date: new Date(),
    timeframe: "1D",
    slippage: 0.001,
    commission: 0.001
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [strategiesRes, backtestsRes, assetsRes, exchangesRes] = await Promise.all([
        axios.get(`${API}/strategies/`, getAuthHeader()),
        axios.get(`${API}/backtests/`, getAuthHeader()),
        axios.get(`${API}/market-data/assets`, getAuthHeader()),
        axios.get(`${API}/market-data/exchanges`, getAuthHeader())
      ]);
      setStrategies(strategiesRes.data);
      setBacktests(backtestsRes.data);
      setAssets(assetsRes.data);
      setExchanges(exchangesRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!formData.strategy_id || !formData.asset || !formData.exchange) {
      toast.error("Please fill all required fields");
      return;
    }

    setRunning(true);
    try {
      const response = await axios.post(`${API}/backtests/run`, {
        ...formData,
        start_date: formData.start_date.toISOString(),
        end_date: formData.end_date.toISOString()
      }, getAuthHeader());
      
      toast.success("Backtest completed");
      setDialogOpen(false);
      fetchData();
      setSelectedBacktest(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to run backtest");
    } finally {
      setRunning(false);
    }
  };

  const viewBacktest = async (backtestId) => {
    try {
      const response = await axios.get(`${API}/backtests/${backtestId}`, getAuthHeader());
      setSelectedBacktest(response.data);
    } catch (error) {
      toast.error("Failed to load backtest");
    }
  };

  const getReturnColor = (value) => {
    if (value > 0) return "text-profit";
    if (value < 0) return "text-loss";
    return "text-muted-foreground";
  };

  const allAssets = [...assets.futures, ...assets.crypto];

  // Calculate drawdown from equity curve
  const drawdownData = selectedBacktest?.equity_curve?.map((point, idx, arr) => {
    const peak = Math.max(...arr.slice(0, idx + 1).map(p => p.equity));
    const drawdown = ((peak - point.equity) / peak) * 100;
    return { ...point, drawdown };
  }) || [];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading backtests...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="backtest-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Backtesting Engine</h1>
          <p className="text-muted-foreground">Test strategies on historical data</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="run-backtest-btn">
              <Play className="w-4 h-4 mr-2" />
              Run Backtest
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-card border-border max-w-lg">
            <DialogHeader>
              <DialogTitle>Configure Backtest</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label>Strategy</Label>
                <Select 
                  value={formData.strategy_id} 
                  onValueChange={(v) => setFormData({ ...formData, strategy_id: v })}
                >
                  <SelectTrigger data-testid="strategy-select">
                    <SelectValue placeholder="Select strategy" />
                  </SelectTrigger>
                  <SelectContent>
                    {strategies.length === 0 ? (
                      <div className="px-2 py-4 text-sm text-muted-foreground text-center">
                        No strategies available. Create one first.
                      </div>
                    ) : (
                      strategies.map(s => (
                        <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Asset</Label>
                  <Select 
                    value={formData.asset} 
                    onValueChange={(v) => setFormData({ ...formData, asset: v })}
                  >
                    <SelectTrigger data-testid="backtest-asset-select">
                      <SelectValue placeholder="Select asset" />
                    </SelectTrigger>
                    <SelectContent>
                      {allAssets.map(a => (
                        <SelectItem key={a} value={a}>{a}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Exchange</Label>
                  <Select 
                    value={formData.exchange} 
                    onValueChange={(v) => setFormData({ ...formData, exchange: v })}
                  >
                    <SelectTrigger data-testid="backtest-exchange-select">
                      <SelectValue placeholder="Select exchange" />
                    </SelectTrigger>
                    <SelectContent>
                      {exchanges.map(e => (
                        <SelectItem key={e} value={e}>{e}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Start Date</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {format(formData.start_date, "PP")}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0 bg-card border-border">
                      <Calendar
                        mode="single"
                        selected={formData.start_date}
                        onSelect={(date) => date && setFormData({ ...formData, start_date: date })}
                      />
                    </PopoverContent>
                  </Popover>
                </div>

                <div className="space-y-2">
                  <Label>End Date</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {format(formData.end_date, "PP")}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0 bg-card border-border">
                      <Calendar
                        mode="single"
                        selected={formData.end_date}
                        onSelect={(date) => date && setFormData({ ...formData, end_date: date })}
                      />
                    </PopoverContent>
                  </Popover>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Timeframe</Label>
                  <Select 
                    value={formData.timeframe} 
                    onValueChange={(v) => setFormData({ ...formData, timeframe: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEFRAMES.map(t => (
                        <SelectItem key={t} value={t}>{t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Slippage</Label>
                  <Input
                    type="number"
                    step="0.001"
                    value={formData.slippage}
                    onChange={(e) => setFormData({ ...formData, slippage: parseFloat(e.target.value) })}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Commission</Label>
                  <Input
                    type="number"
                    step="0.001"
                    value={formData.commission}
                    onChange={(e) => setFormData({ ...formData, commission: parseFloat(e.target.value) })}
                  />
                </div>
              </div>

              <Button 
                onClick={handleRunBacktest} 
                disabled={running} 
                className="w-full"
                data-testid="submit-backtest"
              >
                {running ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                Run Backtest
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Backtests List */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <LineChartIcon className="w-5 h-5 text-primary" />
              Backtest Results
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {backtests.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No backtests run yet
                </p>
              ) : (
                backtests.map(bt => (
                  <div
                    key={bt.id}
                    className={`p-3 rounded-sm border cursor-pointer transition-colors ${
                      selectedBacktest?.id === bt.id 
                        ? "border-primary bg-primary/5" 
                        : "border-border hover:border-primary/50"
                    }`}
                    onClick={() => viewBacktest(bt.id)}
                    data-testid={`backtest-${bt.id}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-sm">{bt.asset}</span>
                      <Badge variant="outline" className={bt.total_return >= 0 ? "status-healthy" : "status-error"}>
                        {bt.total_return >= 0 ? "+" : ""}{bt.total_return}%
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                      <div>Sharpe: <span className="font-mono">{bt.sharpe_ratio}</span></div>
                      <div>Trades: <span className="font-mono">{bt.trade_count}</span></div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Results Panel */}
        <Card className="lg:col-span-2 bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">
              {selectedBacktest ? "Backtest Results" : "Select a Backtest"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {selectedBacktest ? (
              <div className="space-y-6">
                {/* Metrics Grid */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div>
                    <p className="label-overline">Total Return</p>
                    <p className={`text-2xl font-mono ${getReturnColor(selectedBacktest.total_return)}`}>
                      {selectedBacktest.total_return >= 0 ? "+" : ""}{selectedBacktest.total_return}%
                    </p>
                  </div>
                  <div>
                    <p className="label-overline">Sharpe Ratio</p>
                    <p className="text-2xl font-mono">{selectedBacktest.sharpe_ratio}</p>
                  </div>
                  <div>
                    <p className="label-overline">Max Drawdown</p>
                    <p className="text-2xl font-mono text-loss">-{selectedBacktest.max_drawdown}%</p>
                  </div>
                  <div>
                    <p className="label-overline">Win Rate</p>
                    <p className="text-2xl font-mono">{selectedBacktest.win_rate}%</p>
                  </div>
                  <div>
                    <p className="label-overline">Profit Factor</p>
                    <p className="text-2xl font-mono">{selectedBacktest.profit_factor}</p>
                  </div>
                </div>

                {/* Equity Curve */}
                <div>
                  <p className="label-overline mb-2">Equity Curve</p>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={selectedBacktest.equity_curve}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                        <XAxis 
                          dataKey="timestamp" 
                          tick={{ fill: "#a3a3a3", fontSize: 10 }}
                          tickFormatter={(val) => val.slice(5, 10)}
                        />
                        <YAxis 
                          tick={{ fill: "#a3a3a3", fontSize: 10 }}
                          tickFormatter={(val) => `$${(val/1000).toFixed(0)}k`}
                        />
                        <Tooltip
                          content={({ active, payload, label }) => {
                            if (active && payload && payload.length) {
                              return (
                                <div className="glass px-3 py-2 rounded-sm">
                                  <p className="text-xs text-muted-foreground">{label?.slice(0, 10)}</p>
                                  <p className="text-sm font-mono">${payload[0].value.toLocaleString()}</p>
                                </div>
                              );
                            }
                            return null;
                          }}
                        />
                        <Line type="monotone" dataKey="equity" stroke="#007AFF" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Drawdown Chart */}
                <div>
                  <p className="label-overline mb-2">Drawdown</p>
                  <div className="h-32">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={drawdownData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                        <XAxis 
                          dataKey="timestamp" 
                          tick={{ fill: "#a3a3a3", fontSize: 10 }}
                          tickFormatter={(val) => val.slice(5, 10)}
                        />
                        <YAxis 
                          tick={{ fill: "#a3a3a3", fontSize: 10 }}
                          tickFormatter={(val) => `-${val.toFixed(0)}%`}
                        />
                        <Area 
                          type="monotone" 
                          dataKey="drawdown" 
                          stroke="#FF3B30" 
                          fill="#FF3B30" 
                          fillOpacity={0.2} 
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Trade Log */}
                <div>
                  <p className="label-overline mb-2">Recent Trades ({selectedBacktest.trade_count} total)</p>
                  <div className="max-h-48 overflow-auto">
                    <Table className="data-table">
                      <TableHeader>
                        <TableRow>
                          <TableHead>Time</TableHead>
                          <TableHead>Side</TableHead>
                          <TableHead>Entry</TableHead>
                          <TableHead>Exit</TableHead>
                          <TableHead>P&L</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {selectedBacktest.trade_log.slice(0, 10).map(trade => (
                          <TableRow key={trade.id}>
                            <TableCell className="text-xs">{trade.timestamp.slice(0, 10)}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className={trade.side === "long" ? "status-healthy" : "status-error"}>
                                {trade.side}
                              </Badge>
                            </TableCell>
                            <TableCell>${trade.entry_price}</TableCell>
                            <TableCell>${trade.exit_price}</TableCell>
                            <TableCell className={trade.pnl >= 0 ? "text-profit" : "text-loss"}>
                              {trade.pnl >= 0 ? "+" : ""}${trade.pnl.toFixed(2)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-64 text-muted-foreground">
                Select a backtest from the list or run a new one
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
