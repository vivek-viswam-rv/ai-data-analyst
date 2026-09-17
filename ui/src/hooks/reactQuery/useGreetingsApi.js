import { useQuery } from "@tanstack/react-query";
import greetingsApi from "apis/greetings";

import { QUERY_KEYS } from "constants/query";
import { isPresent } from "utils";

export const useFetchGreeting = name =>
  useQuery({
    queryKey: [QUERY_KEYS.GREETINGS, name],
    queryFn: () => greetingsApi.fetch({ name }),
    select: response => response.data,
    enabled: isPresent(name),
  });
