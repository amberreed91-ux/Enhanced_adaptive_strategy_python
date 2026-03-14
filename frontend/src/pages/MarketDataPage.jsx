import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Database, Plus, Trash2, RefreshCw, Loader2, Activity } from "lucide-react";
import { toast } from "sonner";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIMEFRAMES = ["1D", "30m", "5m", "1m"];
const DATA_TYPES = ["OHLC", "Tick Trades", "Order Book", "Volume"];

export default function MarketDataPage() {
  const [feeds, setFeeds] = useState([]);
  const [assets, setAssets] = useState({ futures: [], crypto: [] });
  const [exchanges, setExchanges] = useState([]);
  const [orderBook, setOrderBook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const { getAuthHeader } = useAuth();

  const [formData, setFormData] = useState({
    asset: "",
    exchange: "",
    timeframe: "1D",
    data_type: "OHLC"
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [feedsRes, assetsRes, exchangesRes] = await Promise.all([
        axios.get(`${API}/market-data/feeds`, getAuthHeader()),
        axios.get(`${API}/market-data/assets`, getAuthHeader()),
        axios.get(`${API}/market-data/exchanges`, getAuthHeader())
      ]);
      setFeeds(feedsRes.data);
      setAssets(assetsRes.data);
      setExchanges(exchangesRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchOrderBook = async (asset) => {
    try {
      const response = await axios.get(`${API}/market-data/orderbook/${encodeURIComponent(asset)}`, getAuthHeader());
      setOrderBook(response.data);
    } catch (error) {
      console.error("Failed to fetch order book:", error);
    }
  };

  const handleIngest = async () => {
    if (!formData.asset || !formData.exchange) {
      toast.error("Please select asset and exchange");
      return;
    }

    setSubmitting(true);
    try {
      await axios.post(`${API}/market-data/ingest`, formData, getAuthHeader());
      toast.success("Data feed created successfully");
      setDialogOpen(false);
      fetchData();
      setFormData({ asset: "", exchange: "", timeframe: "1D", data_type: "OHLC" });
    } catch (error) {
      toast.error("Failed to create data feed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (feedId) => {
    try {
      await axios.delete(`${API}/market-data/feeds/${feedId}`, getAuthHeader());
      toast.success("Feed deleted");
      fetchData();
    } catch (error) {
      toast.error("Failed to delete feed");
    }
  };

  const allAssets = [...assets.futures, ...assets.crypto];

  const orderBookChartData = orderBook ? [
    ...orderBook.bids.map((b, i) => ({ level: -i - 1, size: -b.size, type: "bid" })).reverse(),
    ...orderBook.asks.map((a, i) => ({ level: i + 1, size: a.size, type: "ask" }))
  ] : [];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading market data...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="market-data-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Market Data Manager</h1>
          <p className="text-muted-foreground">Manage data ingestion pipelines</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchData} data-testid="refresh-feeds">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button data-testid="add-feed-btn">
                <Plus className="w-4 h-4 mr-2" />
                Add Feed
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-card border-border">
              <DialogHeader>
                <DialogTitle>Configure Data Feed</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>Asset</Label>
                  <Select value={formData.asset} onValueChange={(v) => setFormData({ ...formData, asset: v })}>
                    <SelectTrigger data-testid="asset-select">
                      <SelectValue placeholder="Select asset" />
                    </SelectTrigger>
                    <SelectContent>
                      <div className="px-2 py-1 text-xs text-muted-foreground">Futures</div>
                      {assets.futures.map(a => (
                        <SelectItem key={a} value={a}>{a}</SelectItem>
                      ))}
                      <div className="px-2 py-1 text-xs text-muted-foreground mt-2">Crypto</div>
                      {assets.crypto.map(a => (
                        <SelectItem key={a} value={a}>{a}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Exchange</Label>
                  <Select value={formData.exchange} onValueChange={(v) => setFormData({ ...formData, exchange: v })}>
                    <SelectTrigger data-testid="exchange-select">
                      <SelectValue placeholder="Select exchange" />
                    </SelectTrigger>
                    <SelectContent>
                      {exchanges.map(e => (
                        <SelectItem key={e} value={e}>{e}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Timeframe</Label>
                    <Select value={formData.timeframe} onValueChange={(v) => setFormData({ ...formData, timeframe: v })}>
                      <SelectTrigger data-testid="timeframe-select">
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
                    <Label>Data Type</Label>
                    <Select value={formData.data_type} onValueChange={(v) => setFormData({ ...formData, data_type: v })}>
                      <SelectTrigger data-testid="datatype-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DATA_TYPES.map(t => (
                          <SelectItem key={t} value={t}>{t}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <Button onClick={handleIngest} disabled={submitting} className="w-full" data-testid="submit-feed">
                  {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                  Ingest Data
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Feeds Table */}
        <Card className="lg:col-span-2 bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Database className="w-5 h-5 text-primary" />
              Active Data Feeds
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table className="data-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Asset</TableHead>
                  <TableHead>Exchange</TableHead>
                  <TableHead>Timeframe</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Records</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {feeds.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      No data feeds configured. Click "Add Feed" to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  feeds.map(feed => (
                    <TableRow key={feed.id}>
                      <TableCell className="font-medium">{feed.asset}</TableCell>
                      <TableCell>{feed.exchange}</TableCell>
                      <TableCell>{feed.timeframe}</TableCell>
                      <TableCell>{feed.data_type}</TableCell>
                      <TableCell>{feed.record_count.toLocaleString()}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="status-healthy">{feed.status}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => fetchOrderBook(feed.asset)}
                            data-testid={`view-orderbook-${feed.id}`}
                          >
                            <Activity className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDelete(feed.id)}
                            data-testid={`delete-feed-${feed.id}`}
                          >
                            <Trash2 className="w-4 h-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Order Book Viewer */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Order Book Viewer</CardTitle>
          </CardHeader>
          <CardContent>
            {orderBook ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="label-overline">Mid Price</p>
                    <p className="font-mono text-lg">${orderBook.mid_price}</p>
                  </div>
                  <div>
                    <p className="label-overline">Spread</p>
                    <p className="font-mono text-lg">{(orderBook.spread * 100).toFixed(2)}%</p>
                  </div>
                </div>

                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={orderBookChartData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis type="number" tick={{ fill: "#a3a3a3", fontSize: 10 }} />
                      <YAxis type="category" dataKey="level" hide />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            const data = payload[0].payload;
                            return (
                              <div className="glass px-2 py-1 rounded-sm text-xs">
                                <p>{data.type === "bid" ? "Bid" : "Ask"}: {Math.abs(data.size)}</p>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Bar
                        dataKey="size"
                        fill={(entry) => entry.size < 0 ? "#00C853" : "#FF3B30"}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="flex items-center justify-between">
                  <p className="label-overline">Imbalance</p>
                  <Badge variant="outline" className={orderBook.imbalance > 0 ? "status-healthy" : "status-error"}>
                    {orderBook.imbalance > 0 ? "Bid Pressure" : "Ask Pressure"}
                  </Badge>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                Select a feed to view order book
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
