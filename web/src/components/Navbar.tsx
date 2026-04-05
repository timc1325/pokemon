"use client";

import { signOut, User } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { LogOut } from "lucide-react";

interface NavbarProps {
  user: User;
}

export default function Navbar({ user }: NavbarProps) {
  return (
    <nav className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-white/[0.04]">
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold tracking-tight text-[#e0e0f0]">
          Pokémon GO
        </span>
        <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[#2e2e42]">
          Tracker
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-[#4a4a6a] hidden sm:inline">
          {user.displayName || user.email}
        </span>
        {user.photoURL && (
          <img
            src={user.photoURL}
            alt=""
            className="w-7 h-7 rounded-full border border-white/[0.06]"
            referrerPolicy="no-referrer"
          />
        )}
        <button
          onClick={() => signOut(getFirebaseAuth())}
          className="p-1.5 rounded-md text-[#4a4a6a] hover:text-[#8a8aaa] hover:bg-white/[0.04] transition-colors"
          title="Sign out"
        >
          <LogOut size={15} />
        </button>
      </div>
    </nav>
  );
}
