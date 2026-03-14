import { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Cpu, ChevronDown, Play, Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const FEATURE_CATEGORIES = {
  price: {
    label: "Price Features",
    features: [
      { name: "Momentum_5", definition: { type: "momentum", lookback: 5 } },
      { name: "Momentum_20", definition: { type: "momentum", lookback: 20 } },
      { name: "Volatility_Expansion", definition: { type: "volatility", window: 20, threshold: 1.5 } },
      { name: "Range_Compression", definition: { type: "range", window: 10 } }
    ]
  },
  volume: {
    label: "Volume Features",
    features: [
      { name: "Volume_Spike", definition: { type: "volume_spike", threshold: 2.0 } },
      { name: "VWAP_Deviation", definition: { type: "vwap_deviation" } },
      { name: "Volume_Imbalance", definition: { type: "volume_imbalance", window: 5 } }
    ]
  },
  cross_timeframe: {
    label: "Cross-Timeframe Features",
    features: [
      { name: "Daily_Trend_vs_Intraday", definition: { type: "cross_tf", daily: true, intraday: "30m" } },
      { name: "Breakout_Confirmation", definition: { type: "breakout", tf1: "30m", tf2: "5m" } }
    ]
  },
  microstructure: {
    label: "Order Book Microstructure",
    features: [
      { name: "Liquidity_Imbalance", definition: { type: "liquidity_imbalance", levels: 10 } },
      { name: "Bid_Ask_Pressure", definition: { type: "pressure" } },
      { name: "Order_Flow_Acceleration", definition: { type: "flow_accel", window: 5 } },
      { name: "Absorption_Signal", definition: { type: "absorption", threshold: 0.8 } }
    ]
  }
};

const FeatureCategory = ({ category, categoryKey, selected, onToggle }) => {
  const [open, setOpen] = useState(true);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center justify-between w-full p-3 bg-secondary/30 rounded-sm hover:bg-secondary/50 transition-colors">
        <span className="font-medium text-sm">{category.label}</span>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{selected.length}/{category.features.length}</Badge>
          <ChevronDown className={`w-4 h-4 transition-transform ${open ? "" : "-rotate-90"}`} />
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-2 pl-2">
        {category.features.map(feature => (
          <div key={feature.name} className="flex items-center justify-between p-2 rounded-sm hover:bg-white/5">
            <div>
              <p className="text-sm">{feature.name}</p>
              <p className="text-xs text-muted-foreground font-mono">
                {JSON.stringify(feature.definition).slice(0, 40)}...
              </p>
            </div>
            <Switch
              checked={selected.includes(feature.name)}
              onCheckedChange={(checked) => onToggle(categoryKey, feature, checked)}
              data-testid={`toggle-${feature.name}`}
            />
          </div>
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
};

export default function FeatureGenerationPage() {
  const [features, setFeatures] = useState([]);
  const [selectedFeatures, setSelectedFeatures] = useState({
    price: [],
    volume: [],
    cross_timeframe: [],
    microstructure: []
  });
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const { getAuthHeader } = useAuth();

  useEffect(() => {
    fetchFeatures();
  }, []);

  const fetchFeatures = async () => {
    try {
      const response = await axios.get(`${API}/features/`, getAuthHeader());
      setFeatures(response.data);
    } catch (error) {
      console.error("Failed to fetch features:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (category, feature, checked) => {
    setSelectedFeatures(prev => ({
      ...prev,
      [category]: checked
        ? [...prev[category], feature.name]
        : prev[category].filter(f => f !== feature.name)
    }));
  };

  const handleGenerate = async () => {
    const featuresToGenerate = [];
    
    Object.entries(selectedFeatures).forEach(([categoryKey, names]) => {
      const category = FEATURE_CATEGORIES[categoryKey];
      names.forEach(name => {
        const feature = category.features.find(f => f.name === name);
        if (feature) {
          featuresToGenerate.push({
            name: feature.name,
            category: categoryKey,
            definition: feature.definition
          });
        }
      });
    });

    if (featuresToGenerate.length === 0) {
      toast.error("Please select at least one feature");
      return;
    }

    setGenerating(true);
    try {
      await axios.post(`${API}/features/generate`, featuresToGenerate, getAuthHeader());
      toast.success(`Generated ${featuresToGenerate.length} features`);
      fetchFeatures();
      setSelectedFeatures({
        price: [],
        volume: [],
        cross_timeframe: [],
        microstructure: []
      });
    } catch (error) {
      toast.error("Failed to generate features");
    } finally {
      setGenerating(false);
    }
  };

  const handleDelete = async (featureId) => {
    try {
      await axios.delete(`${API}/features/${featureId}`, getAuthHeader());
      toast.success("Feature deleted");
      fetchFeatures();
    } catch (error) {
      toast.error("Failed to delete feature");
    }
  };

  const getCorrelationColor = (corr) => {
    if (corr > 0.1) return "text-profit";
    if (corr < -0.1) return "text-loss";
    return "text-muted-foreground";
  };

  const totalSelected = Object.values(selectedFeatures).flat().length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading features...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="feature-generation-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Feature Generation Engine</h1>
          <p className="text-muted-foreground">Configure and generate alpha features</p>
        </div>
        <Button onClick={handleGenerate} disabled={generating || totalSelected === 0} data-testid="generate-features-btn">
          {generating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
          Generate {totalSelected > 0 ? `(${totalSelected})` : ""}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Feature Configuration */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Cpu className="w-5 h-5 text-primary" />
              Feature Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(FEATURE_CATEGORIES).map(([key, category]) => (
                <FeatureCategory
                  key={key}
                  categoryKey={key}
                  category={category}
                  selected={selectedFeatures[key]}
                  onToggle={handleToggle}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Generated Features Table */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Generated Features</CardTitle>
          </CardHeader>
          <CardContent>
            <Table className="data-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Correlation</TableHead>
                  <TableHead>IC</TableHead>
                  <TableHead>Significance</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {features.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      No features generated yet. Select features and click Generate.
                    </TableCell>
                  </TableRow>
                ) : (
                  features.map(feature => (
                    <TableRow key={feature.id}>
                      <TableCell className="font-medium">{feature.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{feature.category}</Badge>
                      </TableCell>
                      <TableCell className={`font-mono ${getCorrelationColor(feature.correlation_to_returns)}`}>
                        {feature.correlation_to_returns?.toFixed(4) || "N/A"}
                      </TableCell>
                      <TableCell className="font-mono">
                        {feature.information_coefficient?.toFixed(4) || "N/A"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={feature.significance_score > 0.7 ? "status-healthy" : feature.significance_score > 0.3 ? "status-warning" : "status-error"}
                        >
                          {(feature.significance_score * 100).toFixed(0)}%
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(feature.id)}
                          data-testid={`delete-feature-${feature.id}`}
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
      </div>
    </div>
  );
}
