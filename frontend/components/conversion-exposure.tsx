"use client";

import { useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { useApp } from './app-provider';

export function ConversionExposure({ surface, previewId }: {
  surface: 'preview' | 'pricing' | 'credits'; previewId?: string;
}) {
  const { data } = useApp();
  const marker = useRef<HTMLSpanElement>(null);
  const experiment = data?.conversion_experiment;
  const key = experiment?.key;
  const assigned = !!data?.authenticated && !!experiment?.variant;
  useEffect(() => {
    if (!assigned || !marker.current || !key || key === 'off') return;
    if (key === 'preview' ? surface !== 'preview' || !previewId :
        key === 'examples' ? surface !== 'pricing' : surface === 'preview') return;
    const controller = new AbortController();
    let visible = false;
    let sent = false;
    function record() {
      if (!visible || document.hidden || sent) return;
      sent = true;
      void api('/conversion-exposures', {
        method: 'POST', body: { experiment: key, surface, ...(previewId && { preview_id: previewId }) },
        signal: controller.signal,
      }).catch(() => { sent = false; });
    }
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; record(); });
    observer.observe(marker.current);
    document.addEventListener('visibilitychange', record);
    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', record);
      controller.abort();
    };
  }, [assigned, data?.session_identity, key, surface, previewId]);
  return <span aria-hidden="true" className="conversion-exposure-marker" ref={marker} />;
}
