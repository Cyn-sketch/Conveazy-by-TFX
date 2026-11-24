"use client";
import { createContext, useContext } from "react";
import type { User } from "@/lib/api";

export type AIStatus = { provider: string; live: boolean; label: string };
export const SessionCtx = createContext<{ user: User; ai: AIStatus | null; refresh: () => void } | null>(null);
export const useSession = () => {
  const s = useContext(SessionCtx);
  if (!s) throw new Error("useSession outside app shell");
  return s;
};
