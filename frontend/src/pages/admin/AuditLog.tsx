import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Shield } from "lucide-react";

interface Log {
  id: string; action: string; entity_type: string; entity_id: string;
  old_value: any; new_value: any; ip_address: string; created_at: string;
}

const ACTION_COLORS: Record<string, string> = {
  created: "bg-green-100 text-green-700", updated: "bg-blue-100 text-blue-700",
  deleted: "bg-red-100 text-red-700", status_changed: "bg-yellow-100 text-yellow-700",
};

const AuditLog = () => {
  const { tenantId } = useAuth();
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [entityType, setEntityType] = useState("");

  const fetchData = async () => {
    if (!tenantId) return;
    setLoading(true);
    try {
      const params = entityType ? `?entity_type=${entityType}` : "";
      const data = await api.get<Log[]>(`/api/audit-logs${params}`);
      setLogs(data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [tenantId, entityType]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Audit Log</h1>
          <p className="text-muted-foreground mt-1">Track all changes made in the system</p>
        </div>
        <Select value={entityType} onValueChange={setEntityType}>
          <SelectTrigger className="w-40"><SelectValue placeholder="All types" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="">All types</SelectItem>
            {["bookings", "rooms", "guests", "payments", "settings"].map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <Card><CardContent className="p-6"><div className="h-48 bg-muted rounded animate-pulse" /></CardContent></Card>
      ) : logs.length === 0 ? (
        <Card><CardContent className="p-12 text-center">
          <Shield className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">No audit logs yet</h3>
          <p className="text-muted-foreground mt-1">System actions will appear here</p>
        </CardContent></Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Changes</TableHead>
                  <TableHead>IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map(log => (
                  <TableRow key={log.id}>
                    <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString("en-IN")}
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ACTION_COLORS[log.action] || "bg-gray-100 text-gray-600"}`}>
                        {log.action}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">
                      <span className="font-medium">{log.entity_type}</span>
                      {log.entity_id && <p className="text-xs text-muted-foreground font-mono">{log.entity_id.slice(0, 8)}…</p>}
                    </TableCell>
                    <TableCell className="text-xs max-w-xs">
                      {log.new_value ? (
                        <code className="bg-muted px-1 py-0.5 rounded text-[10px] break-all">
                          {typeof log.new_value === "object"
                            ? Object.entries(log.new_value).map(([k, v]) => `${k}: ${v}`).join(", ")
                            : String(log.new_value)}
                        </code>
                      ) : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground font-mono">{log.ip_address || "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
};

export default AuditLog;
