"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { mapDieOut } from "@/lib/waferMappers";
import { fetchWaferDies } from "@/services/api";
import { useWaferStore } from "@/stores/waferStore";
import type { Die } from "@/types/wafer";

export function useWaferDies(waferId: string | null | undefined) {
  const hydrateDies = useWaferStore((s) => s.hydrateDies);
  const diesById = useWaferStore((s) => s.diesById);
  const setLifecycle = useWaferStore((s) => s.setLifecycle);

  const query = useQuery({
    queryKey: ["wafers", waferId, "dies"],
    queryFn: () => fetchWaferDies(waferId!),
    enabled: Boolean(waferId),
    staleTime: 10_000,
  });

  useEffect(() => {
    if (query.data) {
      hydrateDies(query.data.map(mapDieOut));
    }
  }, [query.data, hydrateDies]);

  useEffect(() => {
    if (query.isError) setLifecycle("error");
    else if (query.isSuccess && query.data.length === 0) setLifecycle("empty");
  }, [query.isError, query.isSuccess, query.data, setLifecycle]);

  const dies: Die[] = useMemo(() => Object.values(diesById), [diesById]);

  return {
    dies,
    diesById,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
