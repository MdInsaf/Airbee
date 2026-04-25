import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { formatCurrency, formatDate } from "@/lib/format";
import { BarChart3, Download, TrendingUp, FileText, IndianRupee } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

interface Summary {
  month: string;
  kpis: {
    total_bookings: number; cancellations: number; total_room_nights: number;
    total_available_nights: number; occupancy_rate: number; adr: number;
    rev_par: number; total_revenue: number; base_revenue: number;
    total_gst: number; total_service_charge: number; amount_collected: number;
    outstanding: number; expense_total: number; net_revenue: number;
  };
  revenue_by_source: { source: string; bookings: number; revenue: number }[];
  daily_revenue: { date: string; revenue: number; bookings: number }[];
  status_breakdown: { status: string; count: number; amount: number }[];
}

interface GSTReport {
  month: string;
  bookings: any[];
  totals: { base_amount: number; tax_amount: number; service_charge: number; total_amount: number };
}

const Reports = () => {
  const { tenantId } = useAuth();
  const today = new Date();
  const [month, setMonth] = useState(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [gst, setGST] = useState<GSTReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");

  const fetchData = async () => {
    if (!tenantId) return;
    setLoading(true);
    try {
      const [s, g] = await Promise.all([
        api.get<Summary>(`/api/reports/summary?month=${month}`),
        api.get<GSTReport>(`/api/reports/gst?month=${month}`),
      ]);
      setSummary(s);
      setGST(g);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [tenantId, month]);

  const handleExport = () => {
    const firstDay = `${month}-01`;
    const lastDate = new Date(parseInt(month.split("-")[0]), parseInt(month.split("-")[1]), 0);
    const lastDay = `${month}-${String(lastDate.getDate()).padStart(2, "0")}`;
    window.open(`${(import.meta.env.VITE_API_URL || "https://fu6frsnvui.execute-api.ap-south-1.amazonaws.com")}/api/reports/export/bookings?from=${firstDay}&to=${lastDay}`, "_blank");
  };

  const kpis = summary?.kpis;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Reports</h1>
          <p className="text-muted-foreground mt-1">Revenue analytics and performance metrics</p>
        </div>
        <div className="flex gap-3 items-center">
          <input type="month" value={month} onChange={e => setMonth(e.target.value)} className="border rounded px-3 py-1.5 text-sm bg-background" />
          <Button variant="outline" onClick={handleExport}><Download className="w-4 h-4 mr-2" />Export CSV</Button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">{Array.from({ length: 8 }).map((_, i) => <Card key={i}><CardContent className="p-4"><div className="h-12 bg-muted rounded animate-pulse" /></CardContent></Card>)}</div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card><CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Occupancy Rate</p>
              <p className="text-2xl font-bold">{kpis?.occupancy_rate ?? 0}%</p>
            </CardContent></Card>
            <Card><CardContent className="p-4">
              <p className="text-sm text-muted-foreground">ADR</p>
              <p className="text-2xl font-bold">{formatCurrency(kpis?.adr ?? 0)}</p>
              <p className="text-xs text-muted-foreground">Avg Daily Rate</p>
            </CardContent></Card>
            <Card><CardContent className="p-4">
              <p className="text-sm text-muted-foreground">RevPAR</p>
              <p className="text-2xl font-bold">{formatCurrency(kpis?.rev_par ?? 0)}</p>
              <p className="text-xs text-muted-foreground">Revenue Per Available Room</p>
            </CardContent></Card>
            <Card><CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Total Revenue</p>
              <p className="text-2xl font-bold">{formatCurrency(kpis?.total_revenue ?? 0)}</p>
            </CardContent></Card>
            <Card><CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Collected</p>
              <p className="text-2xl font-bold text-green-600">{formatCurrency(kpis?.amount_collected ?? 0)}</p>
            </CardContent></Card>
            <Card><CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Outstanding</p>
              <p className="text-2xl font-bold text-red-600">{formatCurrency(kpis?.outstanding ?? 0)}</p>
            </CardContent></Card>
            <Card><CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Expenses</p>
              <p className="text-2xl font-bold text-orange-600">{formatCurrency(kpis?.expense_total ?? 0)}</p>
            </CardContent></Card>
            <Card><CardContent className="p-4">
              <p className="text-sm text-muted-foreground">Net Revenue</p>
              <p className={`text-2xl font-bold ${(kpis?.net_revenue ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>{formatCurrency(kpis?.net_revenue ?? 0)}</p>
            </CardContent></Card>
          </div>

          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="gst">GST Report</TabsTrigger>
              <TabsTrigger value="source">By Source</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="mt-4 space-y-4">
              <Card>
                <CardHeader><CardTitle className="text-base">Daily Revenue — {month}</CardTitle></CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={summary?.daily_revenue || []}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="date" tickFormatter={d => d.slice(8)} tick={{ fontSize: 11 }} />
                      <YAxis tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(v: any) => formatCurrency(v)} labelFormatter={l => `Date: ${l}`} />
                      <Bar dataKey="revenue" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-base">Booking Status Breakdown</CardTitle></CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {(summary?.status_breakdown || []).map(s => (
                      <div key={s.status} className="p-3 rounded-lg bg-muted/50">
                        <p className="text-xs text-muted-foreground capitalize">{s.status}</p>
                        <p className="text-xl font-bold">{s.count}</p>
                        <p className="text-sm text-muted-foreground">{formatCurrency(s.amount)}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="gst" className="mt-4">
              <Card>
                <CardHeader>
                  <div className="flex justify-between items-center">
                    <CardTitle className="text-base">GST Report — {month}</CardTitle>
                    <div className="grid grid-cols-4 gap-4 text-right text-sm">
                      <div><p className="text-muted-foreground">Base</p><p className="font-bold">{formatCurrency(gst?.totals.base_amount ?? 0)}</p></div>
                      <div><p className="text-muted-foreground">GST</p><p className="font-bold text-orange-600">{formatCurrency(gst?.totals.tax_amount ?? 0)}</p></div>
                      <div><p className="text-muted-foreground">Service</p><p className="font-bold">{formatCurrency(gst?.totals.service_charge ?? 0)}</p></div>
                      <div><p className="text-muted-foreground">Total</p><p className="font-bold">{formatCurrency(gst?.totals.total_amount ?? 0)}</p></div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Guest</TableHead>
                          <TableHead>Room</TableHead>
                          <TableHead>Check-in</TableHead>
                          <TableHead>Check-out</TableHead>
                          <TableHead>Base</TableHead>
                          <TableHead>GST</TableHead>
                          <TableHead>Service</TableHead>
                          <TableHead>Total</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(gst?.bookings || []).map(b => (
                          <TableRow key={b.id}>
                            <TableCell>
                              <p className="font-medium">{b.guest_name}</p>
                              <p className="text-xs text-muted-foreground">{b.guest_email}</p>
                            </TableCell>
                            <TableCell className="text-sm">{b.room_name || "—"}</TableCell>
                            <TableCell className="text-sm">{formatDate(b.check_in)}</TableCell>
                            <TableCell className="text-sm">{formatDate(b.check_out)}</TableCell>
                            <TableCell>{formatCurrency(b.base_amount)}</TableCell>
                            <TableCell className="text-orange-600">{formatCurrency(b.tax_amount)}</TableCell>
                            <TableCell>{formatCurrency(b.service_charge)}</TableCell>
                            <TableCell className="font-medium">{formatCurrency(b.total_amount)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="source" className="mt-4">
              <Card>
                <CardHeader><CardTitle className="text-base">Revenue by Booking Source</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {(summary?.revenue_by_source || []).length === 0 ? (
                      <p className="text-muted-foreground text-sm">No data for this period</p>
                    ) : (summary?.revenue_by_source || []).map(s => {
                      const pct = summary?.kpis.total_revenue ? Math.round((s.revenue / summary.kpis.total_revenue) * 100) : 0;
                      return (
                        <div key={s.source} className="flex items-center gap-4">
                          <div className="w-24 text-sm capitalize font-medium">{s.source}</div>
                          <div className="flex-1 bg-muted rounded-full h-2">
                            <div className="bg-primary h-2 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                          <div className="text-sm text-right w-32">
                            <span className="font-medium">{formatCurrency(s.revenue)}</span>
                            <span className="text-muted-foreground ml-2">({s.bookings} bookings)</span>
                          </div>
                          <div className="text-sm font-medium w-10 text-right">{pct}%</div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
};

export default Reports;
