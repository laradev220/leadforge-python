"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/**
 * URL-backed filter state. Filters serialize to query string so they're
 * shareable, refresh-safe, and SSR-friendly.
 */
export function useUrlFilters<T extends Record<string, string | undefined>>(
  defaults: T,
) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const values = useMemo(() => {
    const out: Record<string, string | undefined> = { ...defaults };
    for (const key of Object.keys(defaults)) {
      const v = searchParams.get(key);
      out[key] = v ?? defaults[key];
    }
    return out as T;
  }, [searchParams, defaults]);

  const setValues = useCallback(
    (patch: Partial<T>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value === undefined || value === null || value === "") {
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      }
      // Reset to page 1 whenever any filter changes
      if (!("page" in patch)) {
        next.delete("page");
      }
      router.push(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  const setPage = useCallback(
    (page: number) => {
      const next = new URLSearchParams(searchParams.toString());
      if (page <= 1) next.delete("page");
      else next.set("page", String(page));
      router.push(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  const reset = useCallback(() => {
    router.push(pathname, { scroll: false });
  }, [router, pathname]);

  return { values, setValues, setPage, reset };
}