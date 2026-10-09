'use client';

import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, PointerEvent, ReactElement } from 'react';
import { Upload, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { Store, StoreProfile } from '@/lib/types';
import { useShop } from './providers';
import { useDialogFocus } from './ui';

type ImageKind = 'avatar' | 'banner';
type CropSelection = {
  kind: ImageKind;
  sourceUrl: string;
  image: HTMLImageElement;
};
type CropPosition = { x: number; y: number; zoom: number };
type CropBounds = { x: number; y: number; width: number; height: number };
type DragStart = { clientX: number; clientY: number; x: number; y: number };

const dimensions: Record<ImageKind, { width: number; height: number; label: string }> = {
  avatar: { width: 512, height: 512, label: 'profile image' },
  banner: { width: 1600, height: 600, label: 'banner' },
};

function clamp(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function cropBounds(selection: CropSelection, position: CropPosition): CropBounds {
  const { width, height } = dimensions[selection.kind];
  const image = selection.image;
  const cropWidth = Math.min(image.naturalWidth, image.naturalHeight * width / height) / position.zoom;
  const cropHeight = cropWidth * height / width;
  return {
    x: (image.naturalWidth - cropWidth) * position.x / 100,
    y: (image.naturalHeight - cropHeight) * position.y / 100,
    width: cropWidth,
    height: cropHeight,
  };
}

function croppedFile(canvas: HTMLCanvasElement, kind: ImageKind): Promise<File> {
  return new Promise<File>((resolve, reject) => {
    canvas.toBlob((blob: Blob | null): void => {
      if (!blob) {
        reject(new Error('Could not prepare this image. Please choose it again.'));
        return;
      }
      resolve(new File([blob], `${kind}.png`, { type: 'image/png' }));
    }, 'image/png');
  });
}

export function StoreBranding({
  store,
  profile,
  onSaved,
}: {
  store: Store;
  profile: StoreProfile | undefined;
  onSaved: (profile: StoreProfile) => Promise<void>;
}): ReactElement {
  const { notify } = useShop();
  const [selection, setSelection] = useState<CropSelection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pendingUrl = useRef<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return (): void => {
      mounted.current = false;
      if (pendingUrl.current) URL.revokeObjectURL(pendingUrl.current);
    };
  }, []);

  function close(): void {
    if (busy) return;
    if (pendingUrl.current) URL.revokeObjectURL(pendingUrl.current);
    pendingUrl.current = null;
    setSelection(null);
    setError('');
  }

  async function choose(event: ChangeEvent<HTMLInputElement>, kind: ImageKind): Promise<void> {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    const size = dimensions[kind];
    setError('');
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      setError('Choose a JPEG, PNG or WebP image up to 5 MB.');
      return;
    }
    setBusy(true);
    const sourceUrl = URL.createObjectURL(file);
    pendingUrl.current = sourceUrl;
    try {
      const image = new Image();
      image.src = sourceUrl;
      await image.decode();
      if (!mounted.current) return;
      if (image.naturalWidth < size.width || image.naturalHeight < size.height) {
        throw new Error(`Choose an image at least ${size.width} × ${size.height} pixels.`);
      }
      setSelection({ kind, image, sourceUrl });
    } catch (cause: unknown) {
      URL.revokeObjectURL(sourceUrl);
      pendingUrl.current = null;
      if (mounted.current) {
        setError(cause instanceof Error ? cause.message : 'Could not open this image.');
      }
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  async function save(file: File): Promise<void> {
    if (!selection) return;
    const kind = selection.kind;
    const form = new FormData();
    form.append('image', file);
    const result = await api<StoreProfile>(`stores/${store.id}/profile-images/${kind}`, 'POST', form);
    await onSaved(result);
    if (!mounted.current) return;
    URL.revokeObjectURL(selection.sourceUrl);
    pendingUrl.current = null;
    setSelection(null);
    notify(`Store ${dimensions[kind].label} saved`);
  }

  async function remove(kind: ImageKind): Promise<void> {
    setBusy(true);
    setError('');
    try {
      const result = await api<StoreProfile>(`stores/${store.id}/profile-images/${kind}`, 'DELETE');
      await onSaved(result);
      notify(`Store ${dimensions[kind].label} removed`);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Could not remove this image.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="store-branding" aria-label="Store branding">
      <div className="store-branding-preview">
        <div className="store-branding-banner">
          {profile?.banner_url && <img src={profile.banner_url} alt={`${store.name} banner`} />}
        </div>
        <div className="store-branding-identity">
          <div className="store-branding-avatar">
            {profile?.avatar_url ? (
              <img src={profile.avatar_url} alt={`${store.name} profile image`} />
            ) : (
              <span>{store.name[0]}</span>
            )}
          </div>
          <div>
            <strong>{store.name}</strong>
            <small className="muted">@{store.username}</small>
          </div>
        </div>
      </div>
      <div className="store-branding-pickers">
        {(['avatar', 'banner'] as const).map((kind: ImageKind): ReactElement => {
          const size = dimensions[kind];
          const existing = kind === 'avatar' ? profile?.avatar_url : profile?.banner_url;
          return (
            <div className="store-branding-picker" key={kind}>
              <strong>{kind === 'avatar' ? 'Profile image' : 'Store banner'}</strong>
              <p className="muted">
                {kind === 'avatar' ? 'A circular crop for your store identity.' : 'A wide crop for your storefront header.'}
                {' '}Choose a photo at least {size.width} × {size.height} pixels.
              </p>
              <label className="button secondary store-branding-upload">
                <Upload size={17} />
                {existing ? 'Replace' : 'Upload'} {size.label}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  aria-label={`Upload ${size.label}`}
                  disabled={busy || selection !== null}
                  onChange={(event: ChangeEvent<HTMLInputElement>): void => { void choose(event, kind); }}
                />
              </label>
              {existing && (
                <button
                  type="button"
                  className="text-link"
                  disabled={busy || selection !== null}
                  onClick={(): void => { void remove(kind); }}
                >
                  Remove {size.label}
                </button>
              )}
            </div>
          );
        })}
      </div>
      <p className="muted">JPEG, PNG or WebP · Up to 5 MB. Images save immediately after cropping.</p>
      {error && <p role="alert" className="store-branding-error">{error}</p>}
      {selection && <CropDialog selection={selection} onClose={close} onSave={save} />}
    </section>
  );
}

function CropDialog({
  selection,
  onClose,
  onSave,
}: {
  selection: CropSelection;
  onClose: () => void;
  onSave: (file: File) => Promise<void>;
}): ReactElement {
  const [position, setPosition] = useState<CropPosition>({ x: 50, y: 50, zoom: 1 });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drag = useRef<DragStart | null>(null);
  const dialogRef = useDialogFocus(true, (): void => { if (!saving) onClose(); });
  const size = dimensions[selection.kind];

  useEffect((): void => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    const bounds = cropBounds(selection, position);
    context.clearRect(0, 0, size.width, size.height);
    context.imageSmoothingQuality = 'high';
    context.drawImage(
      selection.image,
      bounds.x, bounds.y, bounds.width, bounds.height,
      0, 0, size.width, size.height,
    );
  }, [position, selection, size.width, size.height]);

  function move(event: PointerEvent<HTMLCanvasElement>): void {
    if (!drag.current || saving) return;
    const bounds = cropBounds(selection, position);
    const frame = event.currentTarget.getBoundingClientRect();
    const availableX = selection.image.naturalWidth - bounds.width;
    const availableY = selection.image.naturalHeight - bounds.height;
    setPosition({
      ...position,
      x: availableX > 0
        ? clamp(drag.current.x - (event.clientX - drag.current.clientX) * bounds.width / frame.width / availableX * 100)
        : 50,
      y: availableY > 0
        ? clamp(drag.current.y - (event.clientY - drag.current.clientY) * bounds.height / frame.height / availableY * 100)
        : 50,
    });
  }

  async function confirm(): Promise<void> {
    if (!canvasRef.current || saving) return;
    setSaving(true);
    setError('');
    try {
      const file = await croppedFile(canvasRef.current, selection.kind);
      await onSave(file);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Could not save this image. Please retry.');
      setSaving(false);
    }
  }

  return (
    <div className="store-crop-backdrop" onMouseDown={(event): void => {
      if (event.target === event.currentTarget && !saving) onClose();
    }}>
      <section
        ref={dialogRef}
        className="store-crop-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="store-crop-title"
        aria-describedby="store-crop-description"
      >
        <div className="store-crop-heading">
          <h2 id="store-crop-title">Crop your {size.label}</h2>
          <button type="button" className="icon-button" aria-label="Close image editor" disabled={saving} onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        <p id="store-crop-description" className="muted">
          Drag the image to choose what appears {selection.kind === 'avatar' ? 'inside the circle' : 'in your banner'}.
          {' '}Use the sliders to zoom and adjust the crop. Saves at {size.width} × {size.height} pixels.
        </p>
        <div className="store-crop-stage">
          <canvas
            ref={canvasRef}
            width={size.width}
            height={size.height}
            className={`store-crop-canvas ${selection.kind}`}
            role="img"
            aria-label={selection.kind === 'avatar' ? 'Circular profile image preview' : 'Banner image preview'}
            onPointerDown={(event: PointerEvent<HTMLCanvasElement>): void => {
              if (saving) return;
              event.currentTarget.setPointerCapture(event.pointerId);
              drag.current = { clientX: event.clientX, clientY: event.clientY, x: position.x, y: position.y };
            }}
            onPointerMove={move}
            onPointerUp={(): void => { drag.current = null; }}
            onPointerCancel={(): void => { drag.current = null; }}
          />
        </div>
        <fieldset className="store-crop-controls" disabled={saving}>
          <label>
            Zoom
            <input type="range" min="1" max="3" step="0.01" value={position.zoom} onChange={(event): void => {
              setPosition({ ...position, zoom: Number(event.target.value) });
            }} />
          </label>
          <label>
            Horizontal position
            <input type="range" min="0" max="100" value={position.x} onChange={(event): void => {
              setPosition({ ...position, x: Number(event.target.value) });
            }} />
          </label>
          <label>
            Vertical position
            <input type="range" min="0" max="100" value={position.y} onChange={(event): void => {
              setPosition({ ...position, y: Number(event.target.value) });
            }} />
          </label>
        </fieldset>
        {error && <p role="alert" className="store-branding-error">{error}</p>}
        <div className="store-crop-actions">
          <button type="button" className="button secondary" disabled={saving} onClick={onClose}>Cancel</button>
          <button type="button" className="button" disabled={saving} onClick={(): void => { void confirm(); }}>
            {saving ? 'Saving…' : `Save ${size.label}`}
          </button>
        </div>
      </section>
    </div>
  );
}
