"use client";

import { useState, useEffect, useCallback } from "react";
import { getUserCollection, saveUserCollection } from "@/lib/firestore";
import { UserCollection } from "@/lib/types";

export function useCollection(userId: string | null) {
  const [collection, setCollection] = useState<UserCollection>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }
    getUserCollection(userId).then((c) => {
      setCollection(c);
      setLoading(false);
    });
  }, [userId]);

  const toggle = useCallback(
    async (pokemonId: number, field: "shundo" | "lucky") => {
      if (!userId) return;

      const key = pokemonId.toString();
      const current = collection[key] || { shundo: false, lucky: false };
      const updated = { ...current, [field]: !current[field] };

      const newCollection = { ...collection };
      if (!updated.shundo && !updated.lucky) {
        delete newCollection[key];
      } else {
        newCollection[key] = updated;
      }
      setCollection(newCollection);

      try {
        await saveUserCollection(userId, newCollection);
      } catch (err) {
        console.error("Failed to save:", err);
        setCollection(collection);
      }
    },
    [userId, collection]
  );

  return { collection, loading, toggle };
}
