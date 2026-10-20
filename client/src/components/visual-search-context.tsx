'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type {
  VisualSearchResponse,
  VisualSearchDetectedItem,
} from '@/lib/types';

export type VisualSearchSession = {
  previewUrl: string | null;
  analysis: VisualSearchResponse | null;
  selectedItemId: string | null;
  lookTitle?: string;
};

export type VisualSearchContextType = {
  isAnalyzing: boolean;
  error: string | null;
  session: VisualSearchSession | null;
  uploadAndReroute: (file: File) => Promise<void>;
  switchItem: (item: VisualSearchDetectedItem) => Promise<void>;
  clearVisualSearch: () => void;
};

const VisualSearchContext = createContext<VisualSearchContextType | null>(null);

const STORAGE_KEY = 'proace_visual_search_session';

export function VisualSearchProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<VisualSearchSession | null>(null);
  const sourceImage = useRef<File | null>(null);
  const preview = useRef<string | null>(null);
  const generation = useRef<number>(0);

  // Results depend on a source File that cannot survive a page reload. Never
  // restore stale product snapshots without that file.
  useEffect(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignore sessionStorage parsing errors
    }
    return () => {
      generation.current += 1;
      if (preview.current) URL.revokeObjectURL(preview.current);
    };
  }, []);

  const uploadAndReroute = useCallback(
    async (file: File) => {
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        setError('Please select a valid image file (JPEG, PNG, or WebP).');
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        setError('Image size must be 5MB or less.');
        return;
      }

      setError(null);
      setIsAnalyzing(true);
      const requestId: number = ++generation.current;
      const objectUrl = URL.createObjectURL(file);
      let accepted: boolean = false;

      const formData = new FormData();
      formData.append('image', file);

      try {
        const res = await api<VisualSearchResponse>('products/visual-search/', 'POST', formData);
        if (requestId !== generation.current) return;
        if (preview.current) URL.revokeObjectURL(preview.current);
        preview.current = objectUrl;
        sourceImage.current = file;
        accepted = true;
        const newSession: VisualSearchSession = {
          previewUrl: objectUrl,
          analysis: res,
          selectedItemId: res.selected_item_id,
          lookTitle: res.selected_item?.label || (res.selection_required ? 'Choose an item in your photo' : 'No reliable subject recognized'),
        };
        setSession(newSession);
        router.push('/shop?visual=1');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to analyze image.';
        if (requestId === generation.current) setError(msg);
      } finally {
        if (!accepted) URL.revokeObjectURL(objectUrl);
        if (requestId === generation.current) setIsAnalyzing(false);
      }
    },
    [router]
  );

  const switchItem = useCallback(
    async (item: VisualSearchDetectedItem) => {
      if (!session || !sourceImage.current) return;
      const requestId: number = ++generation.current;
      setIsAnalyzing(true);
      setError(null);

      const formData = new FormData();
      formData.append('image', sourceImage.current);
      formData.append('item_id', item.id);

      try {
        const res = await api<VisualSearchResponse>('products/visual-search/', 'POST', formData);
        if (requestId !== generation.current) return;
        const updated: VisualSearchSession = {
          ...session,
          analysis: res,
          selectedItemId: res.selected_item_id,
          lookTitle: res.selected_item?.label || (res.selection_required ? 'Choose an item in your photo' : 'No reliable subject recognized'),
        };
        setSession(updated);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to switch detected item.';
        if (requestId === generation.current) setError(msg);
      } finally {
        if (requestId === generation.current) setIsAnalyzing(false);
      }
    },
    [session]
  );

  const clearVisualSearch = useCallback(() => {
    generation.current += 1;
    sourceImage.current = null;
    if (preview.current) URL.revokeObjectURL(preview.current);
    preview.current = null;
    setError(null);
    setIsAnalyzing(false);
    setSession(null);
    router.push('/shop');
  }, [router]);

  return (
    <VisualSearchContext.Provider
      value={{
        isAnalyzing,
        error,
        session,
        uploadAndReroute,
        switchItem,
        clearVisualSearch,
      }}
    >
      {children}
    </VisualSearchContext.Provider>
  );
}

export function useVisualSearch(): VisualSearchContextType {
  const context = useContext(VisualSearchContext);
  if (!context) {
    throw new Error('useVisualSearch must be used within a VisualSearchProvider');
  }
  return context;
}
