import { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { uploadCatalog, type UploadCatalogResponse } from '../api';

interface CatalogUploadScreenProps {
  onCatalogReady: (catalog: UploadCatalogResponse) => void;
}

export function CatalogUploadScreen({ onCatalogReady }: CatalogUploadScreenProps) {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (file: File) => {
    setErrorMsg(null);

    if (file.type !== 'application/pdf') {
      setUploadStatus('error');
      setErrorMsg('Please upload a PDF file.');
      return;
    }

    setUploadedFile(file);
    setUploadStatus('uploading');

    try {
      const resp = await uploadCatalog(file);
      setUploadStatus('success');
      onCatalogReady(resp);
    } catch (e: any) {
      setUploadStatus('error');
      setErrorMsg(e?.message ?? 'Upload failed.');
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(file);
  };

  return (
    <div className="min-h-screen py-12 px-6">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(218, 165, 32, 0.15)' }}>
              <FileText className="w-8 h-8" style={{ color: 'var(--academic-gold)' }} />
            </div>
          </div>
          <h2 className="mb-3">Upload AUBG Academic Catalog (PDF)</h2>
          <p style={{ color: 'var(--neutral-dark)' }}>
            The app will extract the available majors/minors and course catalog directly from your PDF.
          </p>
        </div>

        <div
          className={`upload-zone ${isDragging ? 'dragging' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileInputChange}
            style={{ display: 'none' }}
          />

          {uploadStatus === 'idle' && (
            <div className="text-center">
              <Upload className="w-10 h-10 mx-auto mb-4" style={{ color: 'var(--academic-gold)' }} />
              <p className="font-medium mb-2">Drop your catalog PDF here or click to browse</p>
              <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                The upload happens locally to your backend API.
              </p>
            </div>
          )}

          {uploadStatus === 'uploading' && (
            <div className="text-center">
              <div className="spinner mx-auto mb-4" />
              <p className="font-medium mb-2">Reading and parsing catalog…</p>
              <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                This can take a moment for large PDFs.
              </p>
            </div>
          )}

          {uploadStatus === 'success' && uploadedFile && (
            <div className="text-center">
              <CheckCircle2 className="w-10 h-10 mx-auto mb-4" style={{ color: 'var(--completed)' }} />
              <p className="font-medium mb-2">Catalog loaded: {uploadedFile.name}</p>
              <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                Redirecting to academic setup…
              </p>
            </div>
          )}

          {uploadStatus === 'error' && (
            <div className="text-center">
              <AlertCircle className="w-10 h-10 mx-auto mb-4" style={{ color: '#ef4444' }} />
              <p className="font-medium mb-2">Upload failed</p>
              <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                {errorMsg ?? 'Please try again.'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
