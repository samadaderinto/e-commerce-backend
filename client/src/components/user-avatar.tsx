'use client';

import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, PointerEvent, ReactElement } from 'react';
import { Camera, Trash2, Upload, UserRound, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { User } from '@/lib/types';
import { useShop } from './providers';
import { useDialogFocus } from './ui';
import { useQueryClient } from '@tanstack/react-query';

type CropPosition = { x: number; y: number; zoom: number };
type CropBounds = { x: number; y: number; width: number; height: number };
type DragStart = { clientX: number; clientY: number; x: number; y: number };

const AVATAR_SIZE = { width: 512, height: 512 };

function clamp(value: number): number {
  return Math.max(0, Math.min(100, value));
}

function cropBounds(image: HTMLImageElement, position: CropPosition): CropBounds {
  const { width, height } = AVATAR_SIZE;
  const cropWidth = Math.min(image.naturalWidth, (image.naturalHeight * width) / height) / position.zoom;
  const cropHeight = (cropWidth * height) / width;
  return {
    x: ((image.naturalWidth - cropWidth) * position.x) / 100,
    y: ((image.naturalHeight - cropHeight) * position.y) / 100,
    width: cropWidth,
    height: cropHeight,
  };
}

function croppedFile(canvas: HTMLCanvasElement): Promise<File> {
  return new Promise<File>((resolve, reject) => {
    canvas.toBlob((blob: Blob | null): void => {
      if (!blob) {
        reject(new Error('Could not prepare this image. Please choose it again.'));
        return;
      }
      resolve(new File([blob], 'avatar.png', { type: 'image/png' }));
    }, 'image/png');
  });
}

export function UserAvatarUpload({ user }: { user?: User | null }): ReactElement | null {
  const { notify } = useShop();
  const queryClient = useQueryClient();
  const [selection, setSelection] = useState<{ sourceUrl: string; image: HTMLImageElement } | null>(null);
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

  if (!user) return null;

  function close(): void {
    if (busy) return;
    if (pendingUrl.current) URL.revokeObjectURL(pendingUrl.current);
    pendingUrl.current = null;
    setSelection(null);
    setError('');
  }

  async function choose(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
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
      if (image.naturalWidth < AVATAR_SIZE.width || image.naturalHeight < AVATAR_SIZE.height) {
        throw new Error(`Choose an image at least ${AVATAR_SIZE.width} × ${AVATAR_SIZE.height} pixels.`);
      }
      setSelection({ image, sourceUrl });
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
    const form = new FormData();
    form.append('image', file);
    const updated = await api<User>('me/avatar', 'POST', form);
    queryClient.setQueryData(['me'], updated);
    void queryClient.invalidateQueries({ queryKey: ['me'] });
    void queryClient.invalidateQueries({ queryKey: ['admin'] });
    if (!mounted.current) return;
    URL.revokeObjectURL(selection.sourceUrl);
    pendingUrl.current = null;
    setSelection(null);
    notify('Profile picture saved');
  }

  async function remove(): Promise<void> {
    setBusy(true);
    setError('');
    try {
      const updated = await api<User>('me/avatar', 'DELETE');
      queryClient.setQueryData(['me'], updated);
      void queryClient.invalidateQueries({ queryKey: ['me'] });
      void queryClient.invalidateQueries({ queryKey: ['admin'] });
      notify('Profile picture removed');
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Could not remove profile picture.');
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  return (
    <section className="user-avatar-branding" aria-label="Profile picture settings">
      <div className="user-avatar-card">
        <div className="user-avatar-display">
          {user.avatar_url ? (
            <img src={user.avatar_url} alt={`${user.first_name} profile`} />
          ) : (
            <span>{user.first_name?.[0]?.toUpperCase() || <UserRound size={32} />}</span>
          )}
        </div>
        <div className="user-avatar-meta">
          <strong>{user.first_name} {user.last_name}</strong>
          <span className="muted">{user.email}</span>
          <div className="user-avatar-actions">
            <label className="button secondary user-avatar-upload-btn">
              <Camera size={16} />
              {user.avatar_url ? 'Change photo' : 'Upload photo'}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                aria-label="Upload profile photo"
                disabled={busy || selection !== null}
                onChange={(event: ChangeEvent<HTMLInputElement>): void => {
                  void choose(event);
                }}
              />
            </label>
            {user.avatar_url && (
              <button
                type="button"
                className="button secondary user-avatar-remove-btn"
                disabled={busy || selection !== null}
                onClick={(): void => {
                  void remove();
                }}
              >
                <Trash2 size={15} />
                Remove
              </button>
            )}
          </div>
        </div>
      </div>
      <p className="muted" style={{ fontSize: '13px', marginTop: '8px' }}>
        PNG, JPEG or WebP up to 5 MB. Crop to a clean 512 × 512 circle. Your profile picture reflects across your account, comments, and navigation.
      </p>
      {error && <p role="alert" className="store-branding-error">{error}</p>}
      {selection && (
        <UserAvatarCropDialog
          image={selection.image}
          onClose={close}
          onSave={save}
        />
      )}
    </section>
  );
}

function UserAvatarCropDialog({
  image,
  onClose,
  onSave,
}: {
  image: HTMLImageElement;
  onClose: () => void;
  onSave: (file: File) => Promise<void>;
}): ReactElement {
  const [position, setPosition] = useState<CropPosition>({ x: 50, y: 50, zoom: 1 });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drag = useRef<DragStart | null>(null);
  const dialogRef = useDialogFocus(true, (): void => {
    if (!saving) onClose();
  });
  const size = AVATAR_SIZE;

  useEffect((): void => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;
    const bounds = cropBounds(image, position);
    context.clearRect(0, 0, size.width, size.height);
    context.imageSmoothingQuality = 'high';
    context.drawImage(
      image,
      bounds.x,
      bounds.y,
      bounds.width,
      bounds.height,
      0,
      0,
      size.width,
      size.height,
    );
  }, [position, image, size.width, size.height]);

  function move(event: PointerEvent<HTMLCanvasElement>): void {
    if (!drag.current || saving) return;
    const bounds = cropBounds(image, position);
    const frame = event.currentTarget.getBoundingClientRect();
    const availableX = image.naturalWidth - bounds.width;
    const availableY = image.naturalHeight - bounds.height;
    setPosition({
      ...position,
      x:
        availableX > 0
          ? clamp(
              drag.current.x -
                ((event.clientX - drag.current.clientX) * bounds.width) / frame.width / availableX * 100,
            )
          : 50,
      y:
        availableY > 0
          ? clamp(
              drag.current.y -
                ((event.clientY - drag.current.clientY) * bounds.height) / frame.height / availableY * 100,
            )
          : 50,
    });
  }

  async function confirm(): Promise<void> {
    if (!canvasRef.current || saving) return;
    setSaving(true);
    setError('');
    try {
      const file = await croppedFile(canvasRef.current);
      await onSave(file);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Could not save this photo. Please retry.');
      setSaving(false);
    }
  }

  return (
    <div
      className="store-crop-backdrop"
      onMouseDown={(event): void => {
        if (event.target === event.currentTarget && !saving) onClose();
      }}
    >
      <section
        ref={dialogRef}
        className="store-crop-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-crop-title"
        aria-describedby="user-crop-description"
      >
        <div className="store-crop-heading">
          <h2 id="user-crop-title">Crop your profile picture</h2>
          <button
            type="button"
            className="icon-button"
            aria-label="Close image editor"
            disabled={saving}
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        <p id="user-crop-description" className="muted">
          Drag to position what appears inside the circle. Use the sliders to zoom and adjust. Saves at 512 × 512 pixels.
        </p>
        <div className="store-crop-stage">
          <canvas
            ref={canvasRef}
            width={size.width}
            height={size.height}
            className="store-crop-canvas avatar"
            role="img"
            aria-label="Circular profile image preview"
            onPointerDown={(event: PointerEvent<HTMLCanvasElement>): void => {
              if (saving) return;
              event.currentTarget.setPointerCapture(event.pointerId);
              drag.current = { clientX: event.clientX, clientY: event.clientY, x: position.x, y: position.y };
            }}
            onPointerMove={move}
            onPointerUp={(): void => {
              drag.current = null;
            }}
            onPointerCancel={(): void => {
              drag.current = null;
            }}
          />
        </div>
        <fieldset className="store-crop-controls" disabled={saving}>
          <label>
            Zoom
            <input
              type="range"
              min="1"
              max="3"
              step="0.01"
              value={position.zoom}
              onChange={(event): void => {
                setPosition({ ...position, zoom: Number(event.target.value) });
              }}
            />
          </label>
          <label>
            Horizontal position
            <input
              type="range"
              min="0"
              max="100"
              value={position.x}
              onChange={(event): void => {
                setPosition({ ...position, x: Number(event.target.value) });
              }}
            />
          </label>
          <label>
            Vertical position
            <input
              type="range"
              min="0"
              max="100"
              value={position.y}
              onChange={(event): void => {
                setPosition({ ...position, y: Number(event.target.value) });
              }}
            />
          </label>
        </fieldset>
        {error && <p role="alert" className="store-branding-error">{error}</p>}
        <div className="store-crop-actions">
          <button type="button" className="button secondary" disabled={saving} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="button"
            disabled={saving}
            onClick={(): void => {
              void confirm();
            }}
          >
            {saving ? 'Saving…' : 'Save profile picture'}
          </button>
        </div>
      </section>
    </div>
  );
}
