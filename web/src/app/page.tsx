"use client";

export const dynamic = "force-dynamic";

import { useAuth } from "@/hooks/useAuth";
import LoginScreen from "@/components/LoginScreen";
import AppShell from "@/components/AppShell";

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-[#6a6a8a] text-sm">Loading…</div>
      </div>
    );
  }

  if (!user) {
    return <LoginScreen />;
  }

  return <AppShell user={user} />;
}
