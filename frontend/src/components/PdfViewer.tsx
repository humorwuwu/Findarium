import { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { ChevronLeft, ChevronRight } from "lucide-react";

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

interface Props {
  fileUrl: string;
  page: number;
}

export function PdfViewer({ fileUrl, page }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [pdf, setPdf] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [currentPage, setCurrentPage] = useState(Math.max(1, page || 1));
  const [pageCount, setPageCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const task = pdfjsLib.getDocument({ url: fileUrl });
    task.promise
      .then((document) => {
        if (cancelled) {
          document.destroy();
          return;
        }
        setPdf(document);
        setPageCount(document.numPages);
        setCurrentPage(Math.min(Math.max(1, page || 1), document.numPages));
      })
      .catch((exc) => setError(String(exc?.message ?? exc)));
    return () => {
      cancelled = true;
      task.destroy();
    };
  }, [fileUrl]);

  useEffect(() => {
    if (!pdf) return;
    setCurrentPage(Math.min(Math.max(1, page || 1), pdf.numPages));
  }, [page, pdf]);

  useEffect(() => {
    if (!pdf || !canvasRef.current) return;
    let cancelled = false;
    pdf.getPage(currentPage).then(async (pageProxy) => {
      if (cancelled || !canvasRef.current) return;
      const viewport = pageProxy.getViewport({ scale: 1.35 });
      const canvas = canvasRef.current;
      const context = canvas.getContext("2d");
      if (!context) return;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await pageProxy.render({ canvasContext: context, viewport }).promise;
    });
    return () => {
      cancelled = true;
    };
  }, [pdf, currentPage]);

  if (error) {
    return (
      <div className="rounded-xl border border-[var(--border)] p-4 text-[12px] text-[var(--danger)]">
        PDF 预览失败：{error}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-center gap-2">
        <button
          className="btn ghost !p-1"
          disabled={currentPage <= 1}
          onClick={() => setCurrentPage((value) => Math.max(1, value - 1))}
        >
          <ChevronLeft size={15} />
        </button>
        <span className="text-[12px] text-[var(--muted)]">
          {currentPage} / {pageCount || "…"}
        </span>
        <button
          className="btn ghost !p-1"
          disabled={pageCount > 0 && currentPage >= pageCount}
          onClick={() => setCurrentPage((value) => Math.min(pageCount || value + 1, value + 1))}
        >
          <ChevronRight size={15} />
        </button>
      </div>
      <div className="max-h-[460px] overflow-auto rounded-xl border border-[var(--border)] bg-white p-2">
        <canvas ref={canvasRef} className="mx-auto block" />
      </div>
    </div>
  );
}
