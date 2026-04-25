import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Bell, Check } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface Notification {
  id: string; type: string; title: string; message: string;
  is_read: boolean; created_at: string;
}

const TYPE_COLORS: Record<string, string> = {
  new_booking: "bg-green-100 text-green-700",
  maintenance: "bg-orange-100 text-orange-700",
  payment: "bg-blue-100 text-blue-700",
  default: "bg-gray-100 text-gray-600",
};

export function NotificationsBell() {
  const { tenantId } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);

  const fetchNotifications = async () => {
    if (!tenantId) return;
    try {
      const data = await api.get<any>("/api/notifications");
      setNotifications(data?.notifications || []);
      setUnread(data?.unread_count || 0);
    } catch { /* silent fail */ }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30_000);
    return () => clearInterval(interval);
  }, [tenantId]);

  const markAllRead = async () => {
    try {
      await api.put("/api/notifications/all/read", {});
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnread(0);
    } catch { /* silent */ }
  };

  const markRead = async (id: string) => {
    try {
      await api.put(`/api/notifications/${id}/read`, {});
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      setUnread(prev => Math.max(0, prev - 1));
    } catch { /* silent */ }
  };

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-destructive text-[10px] font-bold text-white flex items-center justify-center">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <h4 className="font-semibold text-sm">Notifications</h4>
          {unread > 0 && (
            <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={markAllRead}>
              <Check className="w-3 h-3 mr-1" />Mark all read
            </Button>
          )}
        </div>
        <ScrollArea className="h-80">
          {notifications.length === 0 ? (
            <div className="text-center text-muted-foreground text-sm py-8">No notifications</div>
          ) : notifications.map(n => (
            <div
              key={n.id}
              className={`px-4 py-3 border-b cursor-pointer hover:bg-muted/50 transition-colors ${!n.is_read ? "bg-primary/5" : ""}`}
              onClick={() => !n.is_read && markRead(n.id)}
            >
              <div className="flex items-start gap-2">
                <span className={`shrink-0 px-1.5 py-0.5 rounded text-[9px] font-medium mt-0.5 ${TYPE_COLORS[n.type] || TYPE_COLORS.default}`}>
                  {n.type.replace("_", " ")}
                </span>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm ${!n.is_read ? "font-semibold" : "font-medium"}`}>{n.title}</p>
                  {n.message && <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.message}</p>}
                  <p className="text-[10px] text-muted-foreground mt-1">{timeAgo(n.created_at)}</p>
                </div>
                {!n.is_read && <div className="shrink-0 w-2 h-2 rounded-full bg-primary mt-1.5" />}
              </div>
            </div>
          ))}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
