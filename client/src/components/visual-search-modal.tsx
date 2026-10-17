"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  Camera,
  Sparkles,
  X,
  UploadCloud,
  Check,
  Search,
  ArrowRight,
  ArrowUpRight,
  Layers,
  Palette,
  Crosshair,
  RotateCcw,
} from "lucide-react";
import { api, money } from "@/lib/api";
import {
  Product,
  VisualSearchResponse,
  VisualSearchDetectedItem,
  VisualSearchPaletteColor,
  VisualSearchResultItem,
  VisualSearchPresetLook,
} from "@/lib/types";
import { VerifiedBadge, AddToBagButton } from "./ui";

interface VisualSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialPresetId?: string;
}

export function VisualSearchModal({
  isOpen,
  onClose,
  initialPresetId,
}: VisualSearchModalProps) {
  const [dragOver, setDragOver] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);
  const [currentPresetId, setCurrentPresetId] = useState<string | null>(null);

  const [presets, setPresets] = useState<VisualSearchPresetLook[]>([]);
  const [analysis, setAnalysis] = useState<VisualSearchResponse | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [hoveredItemId, setHoveredItemId] = useState<string | null>(null);
  const [refinementQuery, setRefinementQuery] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Fetch curated preset looks once
  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    api<VisualSearchPresetLook[]>("products/visual-search/presets/")
      .then((data) => {
        if (active && Array.isArray(data)) {
          setPresets(data);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [isOpen]);

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Clipboard paste listener
  const handlePaste = useCallback(
    (e: ClipboardEvent) => {
      if (!isOpen || isAnalyzing) return;
      const items = e.clipboardData?.items;
      if (!items) return;

      for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith("image/")) {
          const file = items[i].getAsFile();
          if (file) {
            handleFileUpload(file);
            break;
          }
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isOpen, isAnalyzing]
  );

  useEffect(() => {
    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
  }, [handlePaste]);

  // Trigger search with uploaded file
  const handleFileUpload = async (file: File) => {
    if (!file.type.startsWith("image/")) {
      setError("Please select a valid image file (JPEG, PNG, or WebP).");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Image size must be 5MB or less.");
      return;
    }

    setError(null);
    setCurrentFile(file);
    setCurrentPresetId(null);
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    setIsAnalyzing(true);
    setAnalysis(null);

    const formData = new FormData();
    formData.append("image", file);
    if (refinementQuery) {
      formData.append("query", refinementQuery);
    }

    try {
      const res = await api<VisualSearchResponse>("products/visual-search/", "POST", formData);
      setAnalysis(res);
      setSelectedItemId(res.selected_item_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to analyze image. Please try another photo.";
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Trigger search with preset look
  const handlePresetSelect = async (presetId: string, itemId?: string) => {
    setError(null);
    setCurrentFile(null);
    setCurrentPresetId(presetId);
    setIsAnalyzing(true);
    setAnalysis(null);

    // Set preview image for preset
    const preset = presets.find((p) => p.id === presetId);
    if (preset) {
      setPreviewUrl(preset.image_url);
    }

    const formData = new FormData();
    formData.append("preset_id", presetId);
    if (itemId) {
      formData.append("item_id", itemId);
    }
    if (refinementQuery) {
      formData.append("query", refinementQuery);
    }

    try {
      const res = await api<VisualSearchResponse>("products/visual-search/", "POST", formData);
      setAnalysis(res);
      setSelectedItemId(res.selected_item_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to match preset. Please try again.";
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Trigger refinement or item focus change
  const handleItemSelect = async (item: VisualSearchDetectedItem) => {
    setSelectedItemId(item.id);
    setIsAnalyzing(true);
    setError(null);

    const formData = new FormData();
    if (currentFile) {
      formData.append("image", currentFile);
    } else if (currentPresetId) {
      formData.append("preset_id", currentPresetId);
    }
    formData.append("item_id", item.id);
    if (refinementQuery) {
      formData.append("query", refinementQuery);
    }

    try {
      const res = await api<VisualSearchResponse>("products/visual-search/", "POST", formData);
      setAnalysis(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update match results.";
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRefineSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentFile && !currentPresetId) return;

    setIsAnalyzing(true);
    setError(null);

    const formData = new FormData();
    if (currentFile) {
      formData.append("image", currentFile);
    } else if (currentPresetId) {
      formData.append("preset_id", currentPresetId);
    }
    if (selectedItemId) {
      formData.append("item_id", selectedItemId);
    }
    if (refinementQuery) {
      formData.append("query", refinementQuery);
    }

    try {
      const res = await api<VisualSearchResponse>("products/visual-search/", "POST", formData);
      setAnalysis(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to refine search results.";
      setError(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const resetAll = () => {
    setPreviewUrl(null);
    setCurrentFile(null);
    setCurrentPresetId(null);
    setAnalysis(null);
    setSelectedItemId(null);
    setHoveredItemId(null);
    setRefinementQuery("");
    setError(null);
  };

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="visual-search-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-content visual-search-modal" ref={modalRef}>
        {/* Header */}
        <div className="visual-search-header">
          <div className="visual-search-title-group">
            <span className="visual-search-icon-badge">
              <Camera size={18} />
            </span>
            <div>
              <h2 id="visual-search-title" className="visual-search-title">
                AI Visual Lens <span>• Shop The Look</span>
              </h2>
              <p className="visual-search-subtitle">
                Upload any outfit, room setup, or screenshot to identify pieces and shop exact matches.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close visual search modal"
          >
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="form-error-banner" role="alert">
            {error}
          </div>
        )}

        {/* Content Body */}
        {!analysis && !isAnalyzing ? (
          <div className="visual-search-intro-grid">
            {/* Drag & Drop Upload Zone */}
            <div
              className={`visual-search-dropzone ${dragOver ? "drag-over" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const file = e.dataTransfer.files[0];
                if (file) handleFileUpload(file);
              }}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                style={{ display: "none" }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileUpload(file);
                }}
              />
              <div className="visual-drop-icon">
                <UploadCloud size={38} strokeWidth={1.5} />
              </div>
              <h3 className="visual-drop-heading">Drag & drop your photo here</h3>
              <p className="visual-drop-caption">
                Or <span className="visual-browse-link">browse files</span> • Paste screenshot (Ctrl+V)
              </p>
              <div className="visual-drop-formats">
                <span>JPEG</span>
                <span>PNG</span>
                <span>WebP</span>
                <span>Max 5MB</span>
              </div>
            </div>

            {/* Curated Sample Looks */}
            <div className="visual-presets-section">
              <div className="visual-presets-header">
                <Sparkles size={16} className="text-accent" />
                <h4>Or test-drive curated sample looks</h4>
              </div>

              <div className="visual-presets-grid">
                {presets.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    className="visual-preset-card"
                    onClick={() => handlePresetSelect(preset.id)}
                  >
                    <div className="visual-preset-thumb">
                      <div className="visual-preset-badge">{preset.style}</div>
                      <div className="visual-preset-items-count">
                        <Layers size={13} /> {preset.items.length} pieces
                      </div>
                    </div>
                    <div className="visual-preset-info">
                      <div className="visual-preset-title">{preset.title}</div>
                      <div className="visual-preset-sub">{preset.subtitle}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : isAnalyzing ? (
          <div className="visual-analyzing-state">
            <div className="visual-spinner-container">
              <span className="spinner" />
            </div>
            <h3 className="visual-analyzing-title">Analyzing visual attributes…</h3>
            <p className="visual-analyzing-desc">
              Extracting color palettes, segmenting focal items, and scanning marketplace listings.
            </p>
          </div>
        ) : (
          /* Workspace with results & interactive bounding hotspots */
          <div className="visual-workspace-layout">
            {/* Left Column: Image preview with interactive hotspots & items */}
            <div className="visual-left-pane">
              <div className="visual-preview-container">
                {previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={previewUrl}
                    alt="Analyzed look"
                    className="visual-preview-img"
                  />
                ) : (
                  <div className="visual-preview-placeholder">
                    <Palette size={40} />
                  </div>
                )}

                {/* Hotspot bounding box overlays */}
                {analysis?.detected_items.map((item, idx) => {
                  const [ymin, xmin, ymax, xmax] = item.box;
                  const isSelected = item.id === selectedItemId;
                  const isHovered = item.id === hoveredItemId;

                  return (
                    <div
                      key={item.id}
                      className={`visual-hotspot-box ${isSelected ? "selected" : ""} ${
                        isHovered ? "hovered" : ""
                      }`}
                      style={{
                        top: `${ymin * 100}%`,
                        left: `${xmin * 100}%`,
                        width: `${(xmax - xmin) * 100}%`,
                        height: `${(ymax - ymin) * 100}%`,
                      }}
                      onClick={() => handleItemSelect(item)}
                      onMouseEnter={() => setHoveredItemId(item.id)}
                      onMouseLeave={() => setHoveredItemId(null)}
                      title={`Focus on ${item.label}`}
                    >
                      <span className="visual-hotspot-pin">
                        <Crosshair size={12} />
                        <span>{idx + 1}</span>
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Detected Items Selector Chips */}
              <div className="visual-items-selector">
                <div className="visual-section-label">
                  <Layers size={14} />
                  <span>Detected Pieces in Look ({analysis?.detected_items.length}):</span>
                </div>
                <div className="visual-item-chips">
                  {analysis?.detected_items.map((item, idx) => {
                    const isSelected = item.id === selectedItemId;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={`visual-item-chip ${isSelected ? "active" : ""}`}
                        onClick={() => handleItemSelect(item)}
                        onMouseEnter={() => setHoveredItemId(item.id)}
                        onMouseLeave={() => setHoveredItemId(null)}
                      >
                        <span className="visual-chip-number">{idx + 1}</span>
                        <span className="visual-chip-label">{item.label}</span>
                        {isSelected && <Check size={13} className="visual-chip-check" />}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Dominant Palette Swatches */}
              {analysis?.palette && analysis.palette.length > 0 && (
                <div className="visual-palette-container">
                  <div className="visual-section-label">
                    <Palette size={14} />
                    <span>Extracted Palette:</span>
                  </div>
                  <div className="visual-palette-swatches">
                    {analysis.palette.map((color, idx) => (
                      <div
                        key={idx}
                        className="visual-palette-swatch-item"
                        title={`${color.name} (${color.percentage}%) - ${color.hex}`}
                      >
                        <span
                          className="visual-swatch-circle"
                          style={{ backgroundColor: color.hex }}
                        />
                        <span className="visual-swatch-name">{color.name}</span>
                        <span className="visual-swatch-pct">{color.percentage}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button
                type="button"
                className="button outline compact visual-reset-btn"
                onClick={resetAll}
              >
                <RotateCcw size={14} />
                <span>Upload or choose another look</span>
              </button>
            </div>

            {/* Right Column: Matched products and refinement controls */}
            <div className="visual-right-pane">
              {/* Refinement search bar */}
              <form className="visual-refine-form" onSubmit={handleRefineSubmit}>
                <div className="visual-refine-input-wrap">
                  <Search size={16} className="visual-refine-icon" />
                  <input
                    type="text"
                    value={refinementQuery}
                    onChange={(e) => setRefinementQuery(e.target.value)}
                    placeholder="Refine look (e.g. under $100, black only, leather)…"
                    className="visual-refine-input"
                  />
                </div>
                <button type="submit" className="button compact visual-refine-btn">
                  <span>Refine</span>
                </button>
              </form>

              {/* Results summary header */}
              <div className="visual-results-meta">
                <div>
                  <h4 className="visual-results-heading">
                    {analysis?.selected_item
                      ? `Matching: ${analysis.selected_item.label}`
                      : "Matching Pieces"}
                  </h4>
                  <p className="visual-results-sub">
                    {analysis?.results.length === 1
                      ? "1 marketplace match found"
                      : `${analysis?.results.length || 0} marketplace matches ranked by visual affinity`}
                  </p>
                </div>
              </div>

              {/* Products list grid */}
              {analysis && analysis.results.length > 0 ? (
                <div className="visual-results-grid">
                  {analysis.results.map((matchItem: VisualSearchResultItem) => {
                    const prod = matchItem.product;
                    return (
                      <article key={prod.id} className="visual-result-card">
                        <div className="visual-result-thumb-wrap">
                          <Link href={`/products/${prod.id}`} onClick={onClose}>
                            {prod.image ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={prod.image}
                                alt={prod.title}
                                className="visual-result-img"
                              />
                            ) : (
                              <div className="visual-result-no-img">No Image</div>
                            )}
                          </Link>
                          <div className="visual-match-badge">
                            <Sparkles size={11} />
                            <span>{matchItem.similarity_score}% Match</span>
                          </div>
                        </div>

                        <div className="visual-result-body">
                          <div className="visual-result-store">
                            <span>{prod.store_name}</span>
                            {prod.seller_tier && (
                              <VerifiedBadge tier={prod.seller_tier.tier} size={13} />
                            )}
                          </div>

                          <Link
                            href={`/products/${prod.id}`}
                            className="visual-result-title"
                            onClick={onClose}
                          >
                            {prod.title}
                          </Link>

                          <div className="visual-result-price-row">
                            <span className="visual-result-price">
                              {money(prod.sale_price || prod.price)}
                            </span>
                            {prod.discount > 0 && (
                              <span className="visual-result-original">
                                {money(prod.price)}
                              </span>
                            )}
                          </div>

                          {/* Match reasons */}
                          <div className="visual-reasons-list">
                            {matchItem.match_reasons.slice(0, 2).map((reason, rIdx) => (
                              <span key={rIdx} className="visual-reason-pill">
                                {reason}
                              </span>
                            ))}
                          </div>

                          <div className="visual-result-actions">
                            <Link
                              href={`/products/${prod.id}`}
                              className="button compact outline"
                              onClick={onClose}
                            >
                              <span>View Product</span>
                              <ArrowUpRight size={13} />
                            </Link>
                            <AddToBagButton
                              product={prod}
                              className="button compact visual-add-bag-btn"
                            />
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="visual-no-results">
                  <Palette size={32} />
                  <h5>No direct visual matches found</h5>
                  <p>Try clearing your refinement query or picking another detected piece.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
