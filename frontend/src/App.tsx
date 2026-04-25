import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Suspense, lazy } from "react";
import { AuthProvider } from "@/contexts/AuthContext";
import { AdminLayout } from "@/components/admin/AdminLayout";
import { isCoralBeachBookingHost } from "@/lib/custom-booking-sites";
import { shouldRenderPublicBookingAtRoot, supportsPlatformRoutes } from "@/lib/site-hosts";

const Index = lazy(() => import("./pages/Index"));
const Auth = lazy(() => import("./pages/Auth"));
const NotFound = lazy(() => import("./pages/NotFound"));
const CoralBeachBooking = lazy(() => import("./pages/CoralBeachBooking"));
const PublicBooking = lazy(() => import("./pages/PublicBooking"));
const GuestPortal = lazy(() => import("./pages/GuestPortal"));

// Admin pages
const Dashboard = lazy(() => import("@/pages/admin/Dashboard"));
const Rooms = lazy(() => import("@/pages/admin/Rooms"));
const Bookings = lazy(() => import("@/pages/admin/Bookings"));
const BookingCalendar = lazy(() => import("@/pages/admin/BookingCalendar"));
const Guests = lazy(() => import("@/pages/admin/Guests"));
const Payments = lazy(() => import("@/pages/admin/Payments"));
const PricingRules = lazy(() => import("@/pages/admin/PricingRules"));
const StaffManagement = lazy(() => import("@/pages/admin/StaffManagement"));
const Maintenance = lazy(() => import("@/pages/admin/Maintenance"));
const Expenses = lazy(() => import("@/pages/admin/Expenses"));
const Marketing = lazy(() => import("@/pages/admin/Marketing"));
const Messaging = lazy(() => import("@/pages/admin/Messaging"));
const Reports = lazy(() => import("@/pages/admin/Reports"));
const AuditLog = lazy(() => import("@/pages/admin/AuditLog"));
const Settings = lazy(() => import("@/pages/admin/Settings"));
const AICopilot = lazy(() => import("@/pages/admin/AICopilot"));
const Forecasting = lazy(() => import("@/pages/admin/Forecasting"));
const DynamicPricing = lazy(() => import("@/pages/admin/DynamicPricing"));
const GuestIntelligence = lazy(() => import("@/pages/admin/GuestIntelligence"));
const SentimentAnalysis = lazy(() => import("@/pages/admin/SentimentAnalysis"));
const BookingRisk = lazy(() => import("@/pages/admin/BookingRisk"));
const Channels = lazy(() => import("@/pages/admin/Channels"));
const Housekeeping = lazy(() => import("@/pages/admin/Housekeeping"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const RouteFallback = () => (
  <div className="min-h-screen flex items-center justify-center text-sm text-muted-foreground">
    Loading...
  </div>
);

const RootRoute = () => {
  if (typeof window !== "undefined" && isCoralBeachBookingHost(window.location.host)) {
    return <CoralBeachBooking />;
  }
  if (typeof window !== "undefined" && shouldRenderPublicBookingAtRoot(window.location.host)) {
    return <PublicBooking />;
  }
  return <Index />;
};

const PublicExperienceRoute = () => {
  if (typeof window !== "undefined" && isCoralBeachBookingHost(window.location.host)) {
    return <CoralBeachBooking />;
  }
  return <PublicBooking />;
};

const AppRoutes = () => {
  const platformRoutesEnabled = supportsPlatformRoutes();

  return (
    <Routes>
      <Route path="/" element={<RootRoute />} />
      <Route path="/preview/coral-beach" element={<CoralBeachBooking />} />
      <Route path="/book" element={<PublicExperienceRoute />} />
      <Route path="/book/:slug" element={<PublicExperienceRoute />} />
      <Route path="/my-booking" element={<GuestPortal />} />
      {platformRoutesEnabled ? <Route path="/auth" element={<Auth />} /> : null}
      {platformRoutesEnabled ? (
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="rooms" element={<Rooms />} />
          <Route path="bookings" element={<Bookings />} />
          <Route path="calendar" element={<BookingCalendar />} />
          <Route path="guests" element={<Guests />} />
          <Route path="payments" element={<Payments />} />
          <Route path="pricing-rules" element={<PricingRules />} />
          <Route path="staff" element={<StaffManagement />} />
          <Route path="maintenance" element={<Maintenance />} />
          <Route path="expenses" element={<Expenses />} />
          <Route path="housekeeping" element={<Housekeeping />} />
          <Route path="marketing" element={<Marketing />} />
          <Route path="messaging" element={<Messaging />} />
          <Route path="reports" element={<Reports />} />
          <Route path="audit-log" element={<AuditLog />} />
          <Route path="settings" element={<Settings />} />
          <Route path="ai-copilot" element={<AICopilot />} />
          <Route path="forecasting" element={<Forecasting />} />
          <Route path="dynamic-pricing" element={<DynamicPricing />} />
          <Route path="guest-intelligence" element={<GuestIntelligence />} />
          <Route path="sentiment" element={<SentimentAnalysis />} />
          <Route path="booking-risk" element={<BookingRisk />} />
          <Route path="channels" element={<Channels />} />
        </Route>
      ) : null}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Suspense fallback={<RouteFallback />}>
          {supportsPlatformRoutes() ? (
            <AuthProvider>
              <AppRoutes />
            </AuthProvider>
          ) : (
            <AppRoutes />
          )}
        </Suspense>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
