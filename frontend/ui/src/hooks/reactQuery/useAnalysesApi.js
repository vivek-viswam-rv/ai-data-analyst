import { useMutation, useQuery } from "@tanstack/react-query";

import { fetchLimits, preview } from "apis/analyses";
import { QUERY_KEYS } from "constants/query";

export const useFetchLimits = () =>
  useQuery({
    queryKey: [QUERY_KEYS.ANALYSIS_LIMITS],
    queryFn: fetchLimits,
    staleTime: Infinity,
  });

export const usePreview = () =>
  useMutation({
    mutationFn: preview,
  });
