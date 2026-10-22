import React, { useState, useEffect, useRef } from 'react';
import {
  FileText,
  Upload,
  Search,
  Replace,
  Download,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Crosshair,
  CheckCircle2,
  AlertCircle,
  Eye,
  Type,
  Palette,
  Layers,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Trash2,
  Edit3,
  HelpCircle,
  Check,
  Scroll,
  LayoutList,
  Terminal
} from 'lucide-react';

export default function App() {
  const [docId, setDocId] = useState('sample_linux_terminal');
  const [pageCount, setPageCount] = useState(26);
  const [currentPage, setCurrentPage] = useState(0);
  const [docInfo, setDocInfo] = useState({ filename: 'sample_linux_terminal.pdf' });
  const [viewMode, setViewMode] = useState('scroll'); // 'scroll' (continuous) | 'single'
  const [pagesData, setPagesData] = useState({});
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [zoom, setZoom] = useState(1.0);
  const [showDetectedBoxes, setShowDetectedBoxes] = useState(true);

  // Find & Replace inputs
  const [findText, setFindText] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [wholeWord, setWholeWord] = useState(false);
  const [searchAllPages, setSearchAllPages] = useState(true);
  const [searchStatus, setSearchStatus] = useState('');

  // Marked replacements queue
  const [replacements, setReplacements] = useState([]);
  const [selectedReplacementId, setSelectedReplacementId] = useState(null);

  // Manual draw tool state for missed text
  const [isDrawMode, setIsDrawMode] = useState(false);
  const [activeDrawPage, setActiveDrawPage] = useState(null);
  const [drawStart, setDrawStart] = useState(null);
  const [currentDrawRect, setCurrentDrawRect] = useState(null);

  // Active right tab: 'replacements' | 'words' | 'help'
  const [activeTab, setActiveTab] = useState('replacements');

  // Preview cache buster
  const [imageTimestamp, setImageTimestamp] = useState(Date.now());
  const [toast, setToast] = useState(null);

  const fileInputRef = useRef(null);
  const scrollContainerRef = useRef(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Load single page data (vector & OCR) with GitHub Pages demo fallback
  const loadPageData = async (targetDocId, targetPage, includeOcr = false) => {
    try {
      const res = await fetch(`/api/doc/${targetDocId}/page/${targetPage}?include_ocr=${includeOcr}`);
      if (res.ok) {
        const data = await res.json();
        setPagesData(prev => ({ ...prev, [targetPage]: data }));
        return data;
      }
    } catch (err) {
      // Backend not running on static GitHub Pages
    }

    // Static Demo Fallback for GitHub Pages
    try {
      let demoJsonUrl = '';
      if (targetDocId.includes('linux')) {
        demoJsonUrl = `./demo_data/sample_linux_page_${targetPage % 10}.json`;
      } else if (targetDocId.includes('digital')) {
        demoJsonUrl = `./demo_data/sample_digital_page_0.json`;
      } else if (targetDocId.includes('scanned')) {
        demoJsonUrl = `./demo_data/sample_scanned_page_0.json`;
      }

      if (demoJsonUrl) {
        const demoRes = await fetch(demoJsonUrl);
        if (demoRes.ok) {
          const raw = await demoRes.json();
          const fallbackData = {
            doc_id: targetDocId,
            page_num: targetPage,
            page_width: raw.page_width || 595,
            page_height: raw.page_height || 842,
            has_vector_text: !!(raw.blocks && raw.blocks.length > 0),
            vector_blocks: raw.blocks || [],
            vector_words: raw.words || [],
            ocr_data: raw.boxes ? raw : null
          };
          setPagesData(prev => ({ ...prev, [targetPage]: fallbackData }));
          return fallbackData;
        }
      }
    } catch (e) {
      console.warn('Demo fallback also unavailable', e);
    }
    return null;
  };

  // When docId or currentPage changes, ensure current page's data is loaded
  useEffect(() => {
    if (!pagesData[currentPage]) {
      loadPageData(docId, currentPage);
    }
  }, [docId, currentPage]);

  // IntersectionObserver to auto-update currentPage when scrolling through continuous pages
  useEffect(() => {
    if (viewMode !== 'scroll' || !scrollContainerRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const pIdx = Number(entry.target.getAttribute('data-page-index'));
            if (!isNaN(pIdx)) {
              setCurrentPage(pIdx);
            }
          }
        });
      },
      {
        root: scrollContainerRef.current,
        threshold: 0.35,
      }
    );

    const pageElements = scrollContainerRef.current.querySelectorAll('.scroll-page-item');
    pageElements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [viewMode, pageCount, docId, imageTimestamp]);

  // Press Escape to exit drag mode
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isDrawMode) {
        setIsDrawMode(false);
        setDrawStart(null);
        setCurrentDrawRect(null);
        setActiveDrawPage(null);
        showToast('Exited Drag Box mode');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDrawMode]);

  const jumpToPage = (targetPage) => {
    const p = Math.max(0, Math.min(pageCount - 1, targetPage));
    setCurrentPage(p);
    if (!pagesData[p]) {
      loadPageData(docId, p);
    }
    if (viewMode === 'scroll') {
      const el = document.getElementById(`doc-page-${p}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  };

  const loadSample = async (sampleType) => {
    setReplacements([]);
    setSelectedReplacementId(null);
    setFindText('');
    setReplaceText('');
    setSearchStatus('');
    setPagesData({});

    let targetDocId = 'sample_linux_terminal';
    let targetFilename = 'sample_linux_terminal.pdf';
    let count = 26;

    if (sampleType === 'linux') {
      targetDocId = 'sample_linux_terminal';
      targetFilename = 'sample_linux_terminal.pdf';
      count = 26;
      showToast('Loaded Sample Linux Terminal PDF (26 Pages)');
    } else if (sampleType === 'digital') {
      targetDocId = 'sample_digital';
      targetFilename = 'sample_digital_contract.pdf';
      count = 1;
      showToast('Loaded Sample Digital Contract (Vector PDF)');
    } else if (sampleType === 'scanned') {
      targetDocId = 'sample_scanned';
      targetFilename = 'sample_scanned_receipt.pdf';
      count = 1;
      showToast('Loaded Sample Scanned Receipt (OCR & Inpainting)');
    }

    setDocId(targetDocId);
    setDocInfo({ filename: targetFilename });
    setPageCount(count);
    setCurrentPage(0);
    setImageTimestamp(Date.now());

    try {
      const res = await fetch(`/api/doc/${targetDocId}/info`);
      if (res.ok) {
        const info = await res.json();
        setPageCount(info.page_count);
      }
    } catch (e) {
      // fallback
    }

    await loadPageData(targetDocId, 0);
  };

  // Initial load
  useEffect(() => {
    loadSample('linux');
  }, []);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    setPagesData({});
    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('Failed to upload document');
      const data = await res.json();
      setDocId(data.doc_id);
      setPageCount(data.page_count);
      setCurrentPage(0);
      setDocInfo({ filename: data.filename });
      setReplacements([]);
      setSelectedReplacementId(null);
      setImageTimestamp(Date.now());
      showToast(`Uploaded: ${data.filename} (${data.page_count} pages)`);
      await loadPageData(data.doc_id, 0);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeepOcr = async (targetPage = currentPage) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/doc/${docId}/run-ocr/${targetPage}`, { method: 'POST' });
      if (!res.ok) throw new Error('OCR failed');
      const ocrRes = await res.json();
      setPagesData(prev => ({
        ...prev,
        [targetPage]: { ...(prev[targetPage] || {}), ocr_data: ocrRes }
      }));
      showToast(`Page ${targetPage + 1}: Detected ${ocrRes.words?.length || ocrRes.boxes?.length || 0} words via OCR!`);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Search & Mark exact word/phrase occurrences
  const handleSearchAndMark = async () => {
    if (!findText.trim()) {
      showToast('Please enter a word or phrase to find', 'error');
      return;
    }

    setProcessing(true);
    setSearchStatus(searchAllPages ? `Analyzing whole PDF (${pageCount} pages)...` : `Searching Page ${currentPage + 1}...`);
    try {
      const res = await fetch('/api/search-and-match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_id: docId,
          page_num: currentPage,
          query: findText,
          replace_with: replaceText,
          whole_word: wholeWord,
          all_pages: searchAllPages
        })
      });
      if (!res.ok) throw new Error('Search failed');
      const result = await res.json();

      if (result.matches && result.matches.length > 0) {
        const existingIds = new Set(replacements.map(r => r.id));
        const newItems = result.matches.filter(m => !existingIds.has(m.id));
        setReplacements(prev => [...prev, ...newItems]);
        setSelectedReplacementId(result.matches[0].id);
        setActiveTab('replacements');

        const firstMatch = result.matches[0];
        jumpToPage(firstMatch.page);

        // Preload page data for matching pages so overlay shows immediately
        const pagesWithMatches = [...new Set(result.matches.map(m => m.page))];
        pagesWithMatches.forEach(p => {
          if (!pagesData[p]) loadPageData(docId, p);
        });

        const statusMsg = searchAllPages
          ? `Analyzed whole document (${pageCount} pages): Selected all ${result.matches.length} occurrence(s) across ${pagesWithMatches.length} page(s)!`
          : `Page ${currentPage + 1}: Selected ${result.matches.length} occurrence(s)!`;
        setSearchStatus(statusMsg);
        showToast(`Selected all ${result.matches.length} target word(s) across whole PDF!`);
      } else {
        const statusMsg = searchAllPages
          ? `Analyzed whole document (${pageCount} pages): No matches found for "${findText}".`
          : `Page ${currentPage + 1}: No matches found for "${findText}".`;
        setSearchStatus(statusMsg);
        showToast(`No matches found for "${findText}". Try clicking or drawing a box on the word!`, 'error');
      }
    } catch (err) {
      // Fallback: search client-side across loaded page words (GitHub Pages static mode)
      const clientMatches = [];
      const scale = 150.0 / 72.0;
      const q = findText.trim().toLowerCase();

      Object.entries(pagesData).forEach(([pStr, pData]) => {
        const pNum = Number(pStr);
        const words = [...(pData.vector_words || []), ...(pData.ocr_data?.words || [])];
        words.forEach(w => {
          const wText = (w.text || '').toLowerCase();
          const isMatch = wholeWord ? wText === q : wText.includes(q);
          if (isMatch) {
            const bbox = w.bbox || w.pdf_bbox;
            const px_bbox = w.pixel_bbox || (bbox ? [bbox[0] * scale, bbox[1] * scale, bbox[2] * scale, bbox[3] * scale] : [50, 50, 150, 70]);
            clientMatches.push({
              id: `demo_match_${pNum}_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
              type: w.type || 'vector',
              page: pNum,
              original_text: w.text,
              new_text: replaceText || '',
              pdf_bbox: bbox || [px_bbox[0] / scale, px_bbox[1] / scale, px_bbox[2] / scale, px_bbox[3] / scale],
              pixel_bbox: px_bbox,
              span_text: w.text,
              font_name: w.font || 'helv',
              font_type: 'sans',
              font_size: w.size || 12,
              font_color: w.color || '#111827',
              bg_color: w.bg_color || '#ffffff',
              inpaint: true
            });
          }
        });
      });

      if (clientMatches.length > 0) {
        setReplacements(prev => [...prev, ...clientMatches]);
        setSelectedReplacementId(clientMatches[0].id);
        setActiveTab('replacements');
        setSearchStatus(`Found ${clientMatches.length} match(es) in loaded document pages.`);
        showToast(`Marked ${clientMatches.length} match(es) for replacement!`);
      } else {
        showToast('No exact matches found. Try clicking any word box on the preview!', 'error');
      }
    } finally {
      setProcessing(false);
    }
  };

  // Manual Click on an individual word
  const handleSelectWord = (wordItem, pageIndex) => {
    const isVector = wordItem.type === 'vector';
    const scale = 150.0 / 72.0;
    const px_bbox = isVector
      ? [wordItem.bbox[0] * scale, wordItem.bbox[1] * scale, wordItem.bbox[2] * scale, wordItem.bbox[3] * scale]
      : (wordItem.pixel_bbox || [wordItem.pdf_bbox[0] * scale, wordItem.pdf_bbox[1] * scale, wordItem.pdf_bbox[2] * scale, wordItem.pdf_bbox[3] * scale]);

    const bgHex = wordItem.bg_color || '#ffffff';
    let isDarkBg = false;
    if (bgHex.startsWith('#') && bgHex.length === 7) {
      const r = parseInt(bgHex.slice(1, 3), 16);
      const g = parseInt(bgHex.slice(3, 5), 16);
      const b = parseInt(bgHex.slice(5, 7), 16);
      isDarkBg = (0.299 * r + 0.587 * g + 0.114 * b) < 120;
    }
    const isTerminal = isDarkBg || /[@~$/[\]]/.test(wordItem.full_line_text || '');

    const newItem = {
      id: wordItem.id || `word_${Date.now()}`,
      type: isVector ? 'vector' : 'image_ocr',
      page: pageIndex,
      original_text: wordItem.text,
      new_text: replaceText || wordItem.text,
      pdf_bbox: wordItem.bbox || wordItem.pdf_bbox,
      pixel_bbox: px_bbox,
      span_text: wordItem.full_line_text || wordItem.text,
      font_name: isTerminal ? 'Consolas' : (wordItem.font || (isVector ? 'helv' : 'Arial')),
      font_type: isTerminal ? 'mono' : (wordItem.font_type || ((wordItem.font && wordItem.font.toLowerCase().includes('bold')) ? 'bold' : 'sans')),
      font_size: wordItem.size || wordItem.est_font_size || 11,
      font_color: wordItem.color || '#000000',
      bg_color: wordItem.bg_color || '#ffffff',
      inpaint: !isVector
    };

    const exists = replacements.find(r => r.id === newItem.id);
    if (!exists) {
      setReplacements(prev => [...prev, newItem]);
    }
    setSelectedReplacementId(newItem.id);
    setActiveTab('replacements');
    showToast(`Selected word on Page ${pageIndex + 1}: "${wordItem.text}"`);
  };

  // Manual Canvas Mouse Down / Up for Drag Box (Missed Text)
  const handleMouseDown = (e, pageIndex) => {
    if (!isDrawMode) return;
    const container = document.getElementById(`canvas-container-${pageIndex}`);
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoom;
    const y = (e.clientY - rect.top) / zoom;
    setActiveDrawPage(pageIndex);
    setDrawStart({ x, y });
    setCurrentDrawRect({ x0: x, y0: y, x1: x, y1: y });
  };

  const handleMouseMove = (e, pageIndex) => {
    if (!isDrawMode || !drawStart || activeDrawPage !== pageIndex) return;
    const container = document.getElementById(`canvas-container-${pageIndex}`);
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const x = (e.clientX - rect.left) / zoom;
    const y = (e.clientY - rect.top) / zoom;
    setCurrentDrawRect({
      x0: Math.min(drawStart.x, x),
      y0: Math.min(drawStart.y, y),
      x1: Math.max(drawStart.x, x),
      y1: Math.max(drawStart.y, y),
    });
  };

  const handleMouseUp = async (pageIndex) => {
    if (!isDrawMode || !drawStart || !currentDrawRect || activeDrawPage !== pageIndex) {
      setDrawStart(null);
      setCurrentDrawRect(null);
      setActiveDrawPage(null);
      return;
    }

    const boxW = currentDrawRect.x1 - currentDrawRect.x0;
    const boxH = currentDrawRect.y1 - currentDrawRect.y0;

    if (boxW > 6 && boxH > 5) {
      const pixel_bbox = [
        Math.round(currentDrawRect.x0),
        Math.round(currentDrawRect.y0),
        Math.round(currentDrawRect.x1),
        Math.round(currentDrawRect.y1)
      ];

      try {
        const res = await fetch('/api/sample-area', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            doc_id: docId,
            page_num: pageIndex,
            pixel_bbox: pixel_bbox,
            dpi: 150
          })
        });
        const sampleData = await res.json();
        const style = sampleData.style || {};

        const newItem = {
          id: `manual_${Date.now()}`,
          type: 'manual',
          page: pageIndex,
          original_text: '[Custom Word]',
          new_text: replaceText || '',
          pdf_bbox: sampleData.pdf_bbox,
          pixel_bbox: pixel_bbox,
          font_name: 'helv',
          font_type: 'sans',
          font_size: style.font_size || 12,
          font_color: style.font_color || '#111827',
          bg_color: style.bg_color || '#ffffff',
          inpaint: true
        };

        setReplacements(prev => [...prev, newItem]);
        setSelectedReplacementId(newItem.id);
        setActiveTab('replacements');
        showToast(`Created custom word box on Page ${pageIndex + 1}! Drag again for more boxes.`);
      } catch (err) {
        showToast(err.message, 'error');
      }
    }

    setDrawStart(null);
    setCurrentDrawRect(null);
    setActiveDrawPage(null);
    // Keep isDrawMode active so user can continuously drag and select boxes without restarting
  };

  const updateReplacement = (id, fields) => {
    setReplacements(prev =>
      prev.map(item => (item.id === id ? { ...item, ...fields } : item))
    );
  };

  const removeReplacement = (id) => {
    setReplacements(prev => prev.filter(item => item.id !== id));
    if (selectedReplacementId === id) setSelectedReplacementId(null);
  };

  // Apply either ONLY the selected occurrence OR all marked occurrences
  const handleApply = async (applyOnlySelected = false) => {
    let itemsToApply = replacements;
    if (applyOnlySelected) {
      if (!selectedReplacementId) {
        showToast('Please select a replacement item first', 'error');
        return;
      }
      itemsToApply = replacements.filter(r => r.id === selectedReplacementId);
    }

    if (itemsToApply.length === 0) {
      showToast('No text replacements marked to apply', 'error');
      return;
    }

    setProcessing(true);
    try {
      const res = await fetch('/api/apply-replacements', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_id: docId,
          page_num: currentPage,
          replacements: itemsToApply,
          render_dpi: 200
        })
      });

      if (!res.ok) throw new Error('Failed to apply replacements');
      const data = await res.json();

      showToast(data.message, 'success');

      // Remove applied items from queue
      const appliedIds = new Set(itemsToApply.map(i => i.id));
      setReplacements(prev => prev.filter(i => !appliedIds.has(i.id)));
      setSelectedReplacementId(null);
      setImageTimestamp(Date.now());

      // Invalidate page data cache so refreshed pages reload
      setPagesData({});
      await loadPageData(docId, currentPage);
    } catch (err) {
      // Fallback: search client-side across loaded page words (GitHub Pages static mode)
      const clientMatches = [];
      const scale = 150.0 / 72.0;
      const q = findText.trim().toLowerCase();

      Object.entries(pagesData).forEach(([pStr, pData]) => {
        const pNum = Number(pStr);
        const words = [...(pData.vector_words || []), ...(pData.ocr_data?.words || [])];
        words.forEach(w => {
          const wText = (w.text || '').toLowerCase();
          const isMatch = wholeWord ? wText === q : wText.includes(q);
          if (isMatch) {
            const bbox = w.bbox || w.pdf_bbox;
            const px_bbox = w.pixel_bbox || (bbox ? [bbox[0] * scale, bbox[1] * scale, bbox[2] * scale, bbox[3] * scale] : [50, 50, 150, 70]);
            clientMatches.push({
              id: `demo_match_${pNum}_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
              type: w.type || 'vector',
              page: pNum,
              original_text: w.text,
              new_text: replaceText || '',
              pdf_bbox: bbox || [px_bbox[0] / scale, px_bbox[1] / scale, px_bbox[2] / scale, px_bbox[3] / scale],
              pixel_bbox: px_bbox,
              span_text: w.text,
              font_name: w.font || 'helv',
              font_type: 'sans',
              font_size: w.size || 12,
              font_color: w.color || '#111827',
              bg_color: w.bg_color || '#ffffff',
              inpaint: true
            });
          }
        });
      });

      if (clientMatches.length > 0) {
        setReplacements(prev => [...prev, ...clientMatches]);
        setSelectedReplacementId(clientMatches[0].id);
        setActiveTab('replacements');
        setSearchStatus(`Found ${clientMatches.length} match(es) in loaded document pages.`);
        showToast(`Marked ${clientMatches.length} match(es) for replacement!`);
      } else {
        showToast('No exact matches found. Try clicking any word box on the preview!', 'error');
      }
    } finally {
      setProcessing(false);
    }
  };

  const handleResetDoc = async () => {
    setProcessing(true);
    try {
      const res = await fetch(`/api/reset-doc/${docId}`, { method: 'POST' });
      if (!res.ok) throw new Error('Reset failed');
      setReplacements([]);
      setSelectedReplacementId(null);
      setImageTimestamp(Date.now());
      setPagesData({});
      await loadPageData(docId, currentPage);
      showToast('Document reset to original version');
    } catch (err) {
      // Fallback: search client-side across loaded page words (GitHub Pages static mode)
      const clientMatches = [];
      const scale = 150.0 / 72.0;
      const q = findText.trim().toLowerCase();

      Object.entries(pagesData).forEach(([pStr, pData]) => {
        const pNum = Number(pStr);
        const words = [...(pData.vector_words || []), ...(pData.ocr_data?.words || [])];
        words.forEach(w => {
          const wText = (w.text || '').toLowerCase();
          const isMatch = wholeWord ? wText === q : wText.includes(q);
          if (isMatch) {
            const bbox = w.bbox || w.pdf_bbox;
            const px_bbox = w.pixel_bbox || (bbox ? [bbox[0] * scale, bbox[1] * scale, bbox[2] * scale, bbox[3] * scale] : [50, 50, 150, 70]);
            clientMatches.push({
              id: `demo_match_${pNum}_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`,
              type: w.type || 'vector',
              page: pNum,
              original_text: w.text,
              new_text: replaceText || '',
              pdf_bbox: bbox || [px_bbox[0] / scale, px_bbox[1] / scale, px_bbox[2] / scale, px_bbox[3] / scale],
              pixel_bbox: px_bbox,
              span_text: w.text,
              font_name: w.font || 'helv',
              font_type: 'sans',
              font_size: w.size || 12,
              font_color: w.color || '#111827',
              bg_color: w.bg_color || '#ffffff',
              inpaint: true
            });
          }
        });
      });

      if (clientMatches.length > 0) {
        setReplacements(prev => [...prev, ...clientMatches]);
        setSelectedReplacementId(clientMatches[0].id);
        setActiveTab('replacements');
        setSearchStatus(`Found ${clientMatches.length} match(es) in loaded document pages.`);
        showToast(`Marked ${clientMatches.length} match(es) for replacement!`);
      } else {
        showToast('No exact matches found. Try clicking any word box on the preview!', 'error');
      }
    } finally {
      setProcessing(false);
    }
  };

  const handleDownload = () => {
    window.open(`/api/download/${docId}`, '_blank');
  };

  const pageData = pagesData[currentPage] || null;
  const isScannedMode = pageData && !pageData.has_vector_text;
  const selectedItem = replacements.find(r => r.id === selectedReplacementId);

  // Helper renderer for a single page item (used in both Continuous Scroll and Single Page modes)
  const renderPageCanvas = (pIdx) => {
    const pData = pagesData[pIdx];
    const pageReps = replacements.filter(r => r.page === pIdx);
    const isCurrent = currentPage === pIdx;

    return (
      <div
        key={pIdx}
        id={`doc-page-${pIdx}`}
        data-page-index={pIdx}
        className={`scroll-page-item flex flex-col items-center mb-8 transition-all ${
          isCurrent ? 'ring-2 ring-indigo-500/40 rounded-sm' : ''
        }`}
        onClick={() => {
          if (currentPage !== pIdx) setCurrentPage(pIdx);
          if (!pData) loadPageData(docId, pIdx);
        }}
      >
        {/* Page Top Badge */}
        <div className="w-full flex items-center justify-between px-2 py-1.5 bg-slate-900/90 border border-slate-800 text-xs text-slate-400 rounded-t-sm">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded font-mono font-semibold transition ${
              isCurrent ? 'bg-indigo-600 text-white shadow' : 'bg-slate-800 text-slate-300'
            }`}>
              Page {pIdx + 1}
            </span>
            <span className="text-[11px] text-slate-400">
              {pIdx === 7 ? '★ Linux Terminal Experiment' : ''}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {pageReps.length > 0 && (
              <span className="bg-emerald-950 text-emerald-300 border border-emerald-800 text-[10px] px-2 py-0.5 rounded font-mono">
                {pageReps.length} edit(s) marked
              </span>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDeepOcr(pIdx);
              }}
              className="text-[11px] px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-amber-300 rounded border border-slate-700 transition flex items-center gap-1"
              title="Run OCR on this specific page"
            >
              <Sparkles className="w-3 h-3" />
              OCR Page {pIdx + 1}
            </button>
          </div>
        </div>

        {/* Page Canvas Container */}
        <div
          id={`canvas-container-${pIdx}`}
          onMouseDown={(e) => handleMouseDown(e, pIdx)}
          onMouseMove={(e) => handleMouseMove(e, pIdx)}
          onMouseUp={() => handleMouseUp(pIdx)}
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top center',
            transition: 'transform 0.1s ease-out',
            cursor: isDrawMode ? 'crosshair' : 'default',
          }}
          className="relative shadow-2xl rounded-b-sm border border-slate-800 bg-white select-none inline-block overflow-hidden"
        >
          {/* Document Page Image */}
          <img
            src={`/api/doc/${docId}/page-image/${pIdx}?dpi=150&t=${imageTimestamp}`}
            onError={(e) => {
              let fallback = '';
              if (docId.includes('linux')) {
                fallback = `./demo_data/sample_linux_page_${pIdx % 10}.png`;
              } else if (docId.includes('digital')) {
                fallback = './demo_data/sample_digital_page_0.png';
              } else if (docId.includes('scanned')) {
                fallback = './demo_data/sample_scanned_page_0.png';
              }
              if (fallback && !e.target.src.endsWith(fallback.replace('./', ''))) {
                e.target.src = fallback;
              }
            }}
            alt={`Document Page ${pIdx + 1}`}
            loading="lazy"
            className="block max-w-none pointer-events-none"
            style={{ minWidth: '400px' }}
            onDragStart={(e) => e.preventDefault()}
          />

          {/* OVERLAY 1: Clickable Word Boxes */}
          {showDetectedBoxes && pData && (
            <>
              {/* Digital Vector Words */}
              {pData.vector_words?.map((wordItem) => {
                const scale = 150.0 / 72.0;
                const left = wordItem.bbox[0] * scale;
                const top = wordItem.bbox[1] * scale;
                const width = (wordItem.bbox[2] - wordItem.bbox[0]) * scale;
                const height = (wordItem.bbox[3] - wordItem.bbox[1]) * scale;
                const isMarked = pageReps.some(r => r.id === wordItem.id);

                if (isMarked) return null;

                return (
                  <div
                    key={wordItem.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectWord(wordItem, pIdx);
                    }}
                    title={`Select word: "${wordItem.text}" (Page ${pIdx + 1})`}
                    style={{
                      left: `${left}px`,
                      top: `${top}px`,
                      width: `${Math.max(10, width)}px`,
                      height: `${Math.max(10, height)}px`,
                    }}
                    className="absolute cursor-pointer border border-sky-400/20 hover:border-sky-500 hover:bg-sky-400/30 transition group"
                  >
                    <span className="opacity-0 group-hover:opacity-100 absolute -top-5 left-0 bg-slate-900 text-sky-300 text-[10px] px-1.5 py-0.5 rounded shadow pointer-events-none whitespace-nowrap z-30 border border-slate-700">
                      {wordItem.text}
                    </span>
                  </div>
                );
              })}

              {/* OCR Scanned Words */}
              {pData.ocr_data?.words?.map((wItem) => {
                const left = wItem.pixel_bbox[0];
                const top = wItem.pixel_bbox[1];
                const width = wItem.pixel_bbox[2] - wItem.pixel_bbox[0];
                const height = wItem.pixel_bbox[3] - wItem.pixel_bbox[1];
                const isMarked = pageReps.some(r => r.id === wItem.id);

                if (isMarked) return null;

                return (
                  <div
                    key={wItem.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectWord({ ...wItem, type: 'image_ocr' }, pIdx);
                    }}
                    title={`OCR Word: "${wItem.text}" (Page ${pIdx + 1})`}
                    style={{
                      left: `${left}px`,
                      top: `${top}px`,
                      width: `${Math.max(10, width)}px`,
                      height: `${Math.max(10, height)}px`,
                    }}
                    className="absolute cursor-pointer border border-amber-400/20 hover:border-amber-500 hover:bg-amber-400/30 transition group"
                  >
                    <span className="opacity-0 group-hover:opacity-100 absolute -top-5 left-0 bg-slate-900 text-amber-300 text-[10px] px-1.5 py-0.5 rounded shadow pointer-events-none whitespace-nowrap z-30 border border-slate-700">
                      {wItem.text}
                    </span>
                  </div>
                );
              })}
            </>
          )}

          {/* OVERLAY 2: Marked Word Replacements for this Page */}
          {pageReps.map((rep) => {
            const isSelected = selectedReplacementId === rep.id;
            let left, top, width, height;

            if (rep.type === 'vector' && rep.pdf_bbox) {
              const scale = 150.0 / 72.0;
              left = rep.pdf_bbox[0] * scale;
              top = rep.pdf_bbox[1] * scale;
              width = (rep.pdf_bbox[2] - rep.pdf_bbox[0]) * scale;
              height = (rep.pdf_bbox[3] - rep.pdf_bbox[1]) * scale;
            } else if (rep.pixel_bbox) {
              left = rep.pixel_bbox[0];
              top = rep.pixel_bbox[1];
              width = rep.pixel_bbox[2] - rep.pixel_bbox[0];
              height = rep.pixel_bbox[3] - rep.pixel_bbox[1];
            }

            if (left === undefined) return null;

            return (
              <div
                key={rep.id}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedReplacementId(rep.id);
                  setActiveTab('replacements');
                }}
                style={{
                  left: `${left}px`,
                  top: `${top}px`,
                  width: `${Math.max(16, width)}px`,
                  height: `${Math.max(12, height)}px`,
                }}
                className={`absolute cursor-pointer transition z-20 ${
                  isSelected
                    ? 'border-2 border-emerald-400 bg-emerald-400/35 ring-2 ring-emerald-400/60 shadow-lg'
                    : 'border-2 border-amber-500 bg-amber-500/30 hover:bg-amber-500/40'
                }`}
              >
                <div className="absolute -top-6 left-0 bg-slate-900/95 text-white text-[10px] px-1.5 py-0.5 rounded shadow border border-slate-700 flex items-center gap-1 whitespace-nowrap pointer-events-none z-30">
                  <span className="text-rose-400 line-through truncate max-w-[90px]">
                    {rep.original_text}
                  </span>
                  <span className="text-slate-400">→</span>
                  <span className="text-emerald-400 font-semibold truncate max-w-[100px]">
                    {rep.new_text || '[erase]'}
                  </span>
                </div>
              </div>
            );
          })}

          {/* OVERLAY 3: Current Draw Box on this Page */}
          {isDrawMode && activeDrawPage === pIdx && currentDrawRect && (
            <div
              style={{
                left: `${currentDrawRect.x0}px`,
                top: `${currentDrawRect.y0}px`,
                width: `${currentDrawRect.x1 - currentDrawRect.x0}px`,
                height: `${currentDrawRect.y1 - currentDrawRect.y0}px`,
              }}
              className="absolute border-2 border-dashed border-amber-400 bg-amber-400/25 pointer-events-none z-30"
            />
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-4 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-2xl text-xs font-semibold border transition-all ${
            toast.type === 'error'
              ? 'bg-rose-950/95 text-rose-200 border-rose-800'
              : 'bg-emerald-950/95 text-emerald-200 border-emerald-800'
          }`}
        >
          {toast.type === 'error' ? <AlertCircle className="w-4 h-4 text-rose-400" /> : <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Top Navbar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/90 backdrop-blur px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-600/30">
            <FileText className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-wide text-white flex items-center gap-2">
              AcroText Precision
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800 font-mono">
                Exact Word Editor
              </span>
            </h1>
            <p className="text-[11px] text-slate-400 truncate max-w-xs">{docInfo.filename} ({pageCount} pages)</p>
          </div>
        </div>

        {/* Center: Mode Indicator & Demo Switcher */}
        <div className="flex items-center gap-2">
          {/* Demo Document Buttons */}
          <div className="flex items-center bg-slate-800/80 p-0.5 rounded-lg border border-slate-700">
            <button
              onClick={() => loadSample('linux')}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md transition ${
                docId === 'sample_linux_terminal' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              Demo Linux Terminal (26p)
            </button>
            <button
              onClick={() => loadSample('digital')}
              className={`text-xs px-2.5 py-1 rounded-md transition ${
                docId === 'sample_digital' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Demo Contract (Vector)
            </button>
            <button
              onClick={() => loadSample('scanned')}
              className={`text-xs px-2.5 py-1 rounded-md transition ${
                docId === 'sample_scanned' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Demo Receipt (Scan)
            </button>
          </div>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,image/*"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition"
          >
            <Upload className="w-3.5 h-3.5" />
            Upload PDF/Image
          </button>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleResetDoc}
            disabled={processing}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition"
            title="Undo and reset document"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>

          {selectedReplacementId && (
            <button
              onClick={() => handleApply(true)}
              disabled={processing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg shadow transition"
              title="Apply only the currently selected word replacement"
            >
              <Check className="w-3.5 h-3.5" />
              Apply Selected
            </button>
          )}

          <button
            onClick={() => handleApply(false)}
            disabled={processing || replacements.length === 0}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg shadow transition ${
              replacements.length > 0 && !processing
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            {processing ? 'Applying...' : `Apply All (${replacements.length})`}
          </button>

          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg shadow-lg shadow-indigo-600/30 transition"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </button>
        </div>
      </header>

      {/* Exact Word Find & Replace Command Bar */}
      <section className="bg-slate-900 border-b border-slate-800 px-4 py-2 flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3 flex-1 flex-wrap">
          {/* Search Input */}
          <div className="flex items-center gap-2 bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 flex-1 max-w-xs focus-within:border-indigo-500 transition">
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <input
              type="text"
              placeholder="Exact search word (e.g. ashwant)..."
              value={findText}
              onChange={(e) => setFindText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearchAndMark()}
              className="bg-transparent text-xs w-full text-white placeholder-slate-500 focus:outline-none font-mono"
            />
          </div>

          {/* Replacement Input */}
          <div className="flex items-center gap-2 bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-1.5 flex-1 max-w-xs focus-within:border-indigo-500 transition">
            <Replace className="w-4 h-4 text-emerald-400 shrink-0" />
            <input
              type="text"
              placeholder="Replacement word (e.g. boopathi)..."
              value={replaceText}
              onChange={(e) => setReplaceText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearchAndMark()}
              className="bg-transparent text-xs w-full text-white placeholder-slate-500 focus:outline-none font-mono"
            />
          </div>

          {/* Whole Word Checkbox */}
          <label className="flex items-center gap-1.5 cursor-pointer text-xs text-slate-300 select-none">
            <input
              type="checkbox"
              checked={wholeWord}
              onChange={(e) => setWholeWord(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-0"
            />
            <span>Exact Whole Word</span>
          </label>

          {/* Search All Pages Checkbox */}
          <label className="flex items-center gap-1.5 cursor-pointer text-xs text-slate-300 select-none">
            <input
              type="checkbox"
              checked={searchAllPages}
              onChange={(e) => setSearchAllPages(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-0"
            />
            <span>Search All {pageCount} Pages</span>
          </label>

          <button
            onClick={handleSearchAndMark}
            disabled={processing || !findText.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition disabled:opacity-50 shadow"
          >
            <Search className="w-3.5 h-3.5" />
            Scan & Mark Matches
          </button>

          {searchStatus && (
            <span className="text-xs text-amber-400 italic flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5" />
              {searchStatus}
            </span>
          )}
        </div>

        <div className="text-[11px] text-slate-400 flex items-center gap-1 shrink-0">
          <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
          <span>Click any word to isolate & replace without altering design</span>
        </div>
      </section>

      {/* Main Workspace */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Document Viewport */}
        <main className="flex-1 flex flex-col bg-slate-950 border-r border-slate-800 overflow-hidden relative">
          {/* Canvas Toolbar */}
          <div className="h-10 border-b border-slate-800/80 bg-slate-900/60 px-4 flex items-center justify-between text-xs text-slate-300 shrink-0">
            {/* View Mode Toggle: Continuous Scroll vs Single Page */}
            <div className="flex items-center gap-2">
              <div className="flex items-center bg-slate-800/80 p-0.5 rounded-lg border border-slate-700">
                <button
                  onClick={() => setViewMode('scroll')}
                  className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-md transition ${
                    viewMode === 'scroll' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Continuous vertical scroll through all pages"
                >
                  <Scroll className="w-3.5 h-3.5" />
                  Scroll Type Pages
                </button>
                <button
                  onClick={() => setViewMode('single')}
                  className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-md transition ${
                    viewMode === 'single' ? 'bg-indigo-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Single page view with navigation"
                >
                  <LayoutList className="w-3.5 h-3.5" />
                  Single Page
                </button>
              </div>

              {/* Page navigation & quick select */}
              <div className="flex items-center gap-1.5 ml-2">
                <button
                  onClick={() => jumpToPage(currentPage - 1)}
                  disabled={currentPage === 0}
                  className="p-1 rounded hover:bg-slate-800 disabled:opacity-40 transition"
                  title="Previous Page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <div className="flex items-center gap-1 font-mono text-slate-300 text-xs">
                  <span>Page</span>
                  <select
                    value={currentPage}
                    onChange={(e) => jumpToPage(Number(e.target.value))}
                    className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none focus:border-indigo-500 font-mono"
                  >
                    {Array.from({ length: pageCount }).map((_, i) => (
                      <option key={i} value={i}>
                        {i + 1}
                      </option>
                    ))}
                  </select>
                  <span>of {pageCount}</span>
                </div>
                <button
                  onClick={() => jumpToPage(currentPage + 1)}
                  disabled={currentPage >= pageCount - 1}
                  className="p-1 rounded hover:bg-slate-800 disabled:opacity-40 transition"
                  title="Next Page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>

              {/* Terminal Quick Jump Pill if Linux sample */}
              {docId === 'sample_linux_terminal' && (
                <button
                  onClick={() => jumpToPage(7)}
                  className="ml-2 flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-slate-800 hover:bg-indigo-900/60 text-indigo-300 border border-indigo-700/50 transition font-mono"
                  title="Jump directly to terminal screenshot on Page 8"
                >
                  <Terminal className="w-3 h-3 text-emerald-400" />
                  Jump to Terminal (Page 8)
                </button>
              )}
            </div>

            {/* Tools */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsDrawMode(!isDrawMode)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition border ${
                  isDrawMode
                    ? 'bg-amber-500 text-slate-950 border-amber-400 shadow-lg shadow-amber-500/30 ring-2 ring-amber-400/50'
                    : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700'
                }`}
                title="Click once to start. Stays active always so you can draw multiple boxes continuously. Press Esc or click again to stop."
              >
                <Crosshair className={`w-3.5 h-3.5 ${isDrawMode ? 'animate-spin' : ''}`} />
                {isDrawMode ? '🎯 Drag Mode ON (Always Active • Esc to stop)' : 'Drag Box Tool'}
              </button>

              <button
                onClick={() => setShowDetectedBoxes(!showDetectedBoxes)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs transition border ${
                  showDetectedBoxes
                    ? 'bg-indigo-950/80 text-indigo-300 border-indigo-800'
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}
              >
                <Eye className="w-3.5 h-3.5" />
                {showDetectedBoxes ? 'Hide Word Boxes' : 'Show Word Boxes'}
              </button>

              {/* Zoom */}
              <div className="flex items-center gap-1.5 ml-2">
                <button
                  onClick={() => setZoom(z => Math.max(0.4, Math.round((z - 0.1) * 10) / 10))}
                  className="p-1 rounded hover:bg-slate-800 transition"
                  title="Zoom Out"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
                <span className="font-mono text-slate-400 w-11 text-center text-xs">
                  {Math.round(zoom * 100)}%
                </span>
                <button
                  onClick={() => setZoom(z => Math.min(2.0, Math.round((z + 0.1) * 10) / 10))}
                  className="p-1 rounded hover:bg-slate-800 transition"
                  title="Zoom In"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setZoom(1.0)}
                  className="p-1 rounded hover:bg-slate-800 transition"
                  title="Reset Zoom"
                >
                  <Maximize2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Document Canvas Container */}
          <div
            ref={scrollContainerRef}
            className="flex-1 overflow-auto p-6 flex flex-col items-center bg-slate-950/90 relative"
          >
            {loading && (
              <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-50 pointer-events-none">
                <div className="flex flex-col items-center gap-2 text-indigo-400 text-xs bg-slate-900 border border-slate-800 p-4 rounded-xl shadow-2xl">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                  <span>Processing document page...</span>
                </div>
              </div>
            )}

            {/* Continuous Scroll View: Render all pages vertically */}
            {viewMode === 'scroll' ? (
              <div className="flex flex-col items-center w-full">
                {Array.from({ length: pageCount }).map((_, pIdx) => renderPageCanvas(pIdx))}
              </div>
            ) : (
              /* Single Page View: Render only current page */
              <div className="flex flex-col items-center">
                {renderPageCanvas(currentPage)}
              </div>
            )}
          </div>
        </main>

        {/* Right: Word Replacement & Typography Inspector */}
        <aside className="w-96 bg-slate-900 flex flex-col shrink-0 border-l border-slate-800">
          {/* Tabs */}
          <div className="flex border-b border-slate-800 bg-slate-900/90 text-xs shrink-0">
            <button
              onClick={() => setActiveTab('replacements')}
              className={`flex-1 py-3 font-medium flex items-center justify-center gap-1.5 border-b-2 transition ${
                activeTab === 'replacements'
                  ? 'border-indigo-500 text-indigo-400 bg-slate-800/50'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Replace className="w-3.5 h-3.5" />
              Marked Words
              <span className="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-indigo-300 border border-slate-700">
                {replacements.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('words')}
              className={`flex-1 py-3 font-medium flex items-center justify-center gap-1.5 border-b-2 transition ${
                activeTab === 'words'
                  ? 'border-indigo-500 text-indigo-400 bg-slate-800/50'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Type className="w-3.5 h-3.5" />
              Page Words ({pageData?.vector_words?.length || pageData?.ocr_data?.words?.length || 0})
            </button>

            <button
              onClick={() => setActiveTab('help')}
              className={`px-3 py-3 font-medium flex items-center justify-center border-b-2 transition ${
                activeTab === 'help'
                  ? 'border-indigo-500 text-indigo-400 bg-slate-800/50'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>

          {/* Tab 1: Marked Words Queue */}
          {activeTab === 'replacements' && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {replacements.length === 0 ? (
                <div className="text-center py-12 px-4">
                  <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500 mb-3 border border-slate-700">
                    <Replace className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-300">No Words Marked</h3>
                  <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
                    Type a word in the top search bar (e.g. <code className="text-indigo-400 font-mono">ashwant</code>) and click <b>Scan & Mark</b>, or click any word on the preview!
                  </p>
                </div>
              ) : (
                replacements.map((item, idx) => {
                  const isSelected = selectedReplacementId === item.id;
                  return (
                    <div
                      key={item.id}
                      onClick={() => {
                        setSelectedReplacementId(item.id);
                        jumpToPage(item.page);
                      }}
                      className={`rounded-xl border p-3 transition space-y-3 cursor-pointer ${
                        isSelected
                          ? 'border-indigo-500 bg-slate-800/80 shadow-md ring-1 ring-indigo-500/30'
                          : 'border-slate-800 bg-slate-900/60 hover:border-slate-700'
                      }`}
                    >
                      {/* Header */}
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1.5">
                          <span className="w-5 h-5 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center text-[10px] font-mono border border-slate-700">
                            #{idx + 1}
                          </span>
                          <span
                            onClick={(e) => {
                              e.stopPropagation();
                              jumpToPage(item.page);
                            }}
                            className="text-[10px] px-1.5 py-0.5 rounded font-mono bg-indigo-950 text-indigo-300 border border-indigo-800 font-semibold"
                            title="Jump to this page in preview"
                          >
                            Page {item.page + 1}
                          </span>
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded font-mono border ${
                              item.type === 'vector'
                                ? 'bg-cyan-950 text-cyan-300 border-cyan-800'
                                : 'bg-amber-950 text-amber-300 border-amber-800'
                            }`}
                          >
                            {item.type === 'vector' ? 'Vector Word' : 'Image / OCR Word'}
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedReplacementId(item.id);
                              handleApply(true);
                            }}
                            className="text-xs px-2 py-0.5 bg-emerald-700 hover:bg-emerald-600 text-white rounded font-medium transition"
                            title="Apply only this replacement"
                          >
                            Apply This
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              removeReplacement(item.id);
                            }}
                            className="text-slate-500 hover:text-rose-400 p-1 transition"
                            title="Remove"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Surrounding Context Sentence Preview */}
                      {item.span_text && (
                        <div>
                          <label className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 block mb-1">
                            Context in Sentence
                          </label>
                          <div className="text-[11px] text-slate-300 bg-slate-950 border border-slate-800 rounded p-2 font-mono leading-relaxed">
                            {item.span_text.split(new RegExp(`(${item.original_text})`, 'gi')).map((part, pIdx) => {
                              if (part.toLowerCase() === item.original_text.toLowerCase()) {
                                return (
                                  <span key={pIdx} className="bg-amber-950 text-amber-300 font-bold px-1 rounded border border-amber-800">
                                    {item.new_text ? `${part} → ${item.new_text}` : part}
                                  </span>
                                );
                              }
                              return part;
                            })}
                          </div>
                        </div>
                      )}

                      {/* Word Inputs */}
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 block mb-1">
                            Original Word
                          </label>
                          <div className="text-xs text-rose-300 bg-slate-950/80 border border-slate-800 rounded px-2.5 py-1.5 font-mono truncate">
                            {item.original_text}
                          </div>
                        </div>

                        <div>
                          <label className="text-[10px] uppercase tracking-wider font-semibold text-emerald-400 block mb-1">
                            Replacement
                          </label>
                          <input
                            type="text"
                            value={item.new_text}
                            onChange={(e) => updateReplacement(item.id, { new_text: e.target.value })}
                            placeholder="New word..."
                            className="bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-emerald-300 focus:outline-none focus:border-emerald-500 font-mono w-full"
                          />
                        </div>
                      </div>

                      {/* Style Inspector Badges (Locked for Visual Blend) */}
                      <div className="bg-slate-950/60 rounded-lg p-2.5 border border-slate-800 space-y-2">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-400 flex items-center gap-1">
                            <Palette className="w-3 h-3 text-indigo-400" />
                            Sampled Background
                          </span>
                          <div className="flex items-center gap-1.5">
                            <span
                              className="w-3.5 h-3.5 rounded border border-slate-700"
                              style={{ backgroundColor: item.bg_color || '#ffffff' }}
                            />
                            <span className="font-mono text-slate-300 text-[10px]">
                              {item.bg_color || '#ffffff'}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-400 flex items-center gap-1">
                            <Type className="w-3 h-3 text-indigo-400" />
                            Original Font Color
                          </span>
                          <div className="flex items-center gap-1.5">
                            <span
                              className="w-3.5 h-3.5 rounded border border-slate-700"
                              style={{ backgroundColor: item.font_color || '#000000' }}
                            />
                            <span className="font-mono text-slate-300 text-[10px]">
                              {item.font_color || '#000000'}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-400">Locked Font Size</span>
                          <span className="font-mono text-slate-300 text-[10px] bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                            {item.font_size ? `${item.font_size} pt` : 'Auto-Fit'}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Tab 2: All Detected Words on Current Page */}
          {activeTab === 'words' && (
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              <div className="text-xs text-slate-400 mb-2 flex items-center justify-between">
                <span>Words on Page {currentPage + 1}:</span>
                <span className="font-mono text-indigo-400">
                  {(pageData?.vector_words?.length || 0) + (pageData?.ocr_data?.words?.length || 0)} detected
                </span>
              </div>

              {/* Vector words */}
              {pageData?.vector_words && pageData.vector_words.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">Vector Words</div>
                  <div className="flex flex-wrap gap-1">
                    {pageData.vector_words.map((w, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSelectWord(w, currentPage)}
                        className="text-xs px-2 py-0.5 rounded bg-slate-800 hover:bg-cyan-900/40 text-slate-200 border border-slate-700 hover:border-cyan-500 font-mono transition"
                      >
                        {w.text}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* OCR words */}
              {pageData?.ocr_data?.words && pageData.ocr_data.words.length > 0 && (
                <div className="space-y-1 pt-3">
                  <div className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">OCR Scanned Words</div>
                  <div className="flex flex-wrap gap-1 max-h-96 overflow-y-auto">
                    {pageData.ocr_data.words.map((w, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSelectWord({ ...w, type: 'image_ocr' }, currentPage)}
                        className="text-xs px-2 py-0.5 rounded bg-slate-800 hover:bg-amber-900/40 text-slate-200 border border-slate-700 hover:border-amber-500 font-mono transition"
                      >
                        {w.text}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {!pageData?.vector_words?.length && !pageData?.ocr_data?.words?.length && (
                <div className="text-center py-8 text-xs text-slate-500">
                  No words indexed for Page {currentPage + 1} yet. Click <b>OCR Page {currentPage + 1}</b> to detect words!
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Help & Guide */}
          {activeTab === 'help' && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs text-slate-300 leading-relaxed">
              <div className="p-3 bg-indigo-950/40 rounded-xl border border-indigo-900/60">
                <h4 className="font-semibold text-indigo-300 flex items-center gap-1.5 mb-1">
                  <Terminal className="w-4 h-4 text-emerald-400" />
                  Linux Terminal & Code Editing
                </h4>
                <p className="text-slate-400 text-[11px]">
                  Terminal prompts like <code className="text-indigo-300 font-mono">-(ashwant@ashwant)-[~/exp4]</code> have each word and symbol (<code className="text-amber-300">@</code>, <code className="text-amber-300">[ ]</code>) isolated. You can replace just <code className="text-emerald-400 font-mono">ashwant</code> without touching <code className="text-amber-400 font-mono">@</code>!
                </p>
              </div>

              <div className="space-y-2">
                <h4 className="font-semibold text-white">How to Use Scroll View</h4>
                <ul className="list-disc list-inside space-y-1.5 text-slate-400">
                  <li><b>Scroll Type Pages:</b> Scroll down continuously through all 26 pages of the document.</li>
                  <li><b>Jump to Terminal:</b> Click the "Jump to Terminal (Page 8)" button in the toolbar to go straight to the prompt screenshot.</li>
                  <li><b>Search All Pages:</b> Check "Search All Pages" to find matches across the whole PDF.</li>
                  <li><b>Exact Word Erasing:</b> Erasing samples surrounding background pixels to make new text blend seamlessly.</li>
                </ul>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
