import { useEffect, useRef, useState } from "react";
import {
  getUserDetails,
  getUserFiles,
  getSharedFiles,
  uploadFile,
  shareFile,
  deleteFile
} from "../services/api";
import * as pdfjsLib from "pdfjs-dist";
import BottomRightToast from "../components/BottomRightToast";
import "../styles/MainPage.css";

export default function MainPage() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [viewMode, setViewMode] = useState("my-files");
  const [email, setEmail] = useState("");
  const [previewFile, setPreviewFile] = useState(null);
  const [pdfThumbnails, setPdfThumbnails] = useState({});
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [shareTargetFile, setShareTargetFile] = useState(null);
  const [shareEmail, setShareEmail] = useState("");
  const [showSuccessOverlay, setShowSuccessOverlay] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  const currentFetchId = useRef(0);
  const MAX_PREVIEW_SIZE = 5 * 1024 * 1024; 

  useEffect(() => {
    fetchUser();
  }, []);

  useEffect(() => {
    if (email) fetchFiles(viewMode);
    setPreviewFile(null);
  }, [viewMode, email]);

  const fetchUser = async () => {
    try {
      const cachedEmail = localStorage.getItem("user_email");
      if (cachedEmail) {
        setEmail(cachedEmail);
        return;
      }
      const res = await getUserDetails();
      const userEmail = res?.email || "";
      setEmail(userEmail);
      localStorage.setItem("user_email", userEmail);
    } catch (err) {
      console.error("Failed to load user", err);
    }
  };

  const fetchFiles = async (mode) => {
    setLoading(true);
    setFiles([]);
    const fetchId = ++currentFetchId.current;
    try {
      const res = mode === "my-files" ? await getUserFiles() : await getSharedFiles();
      if (fetchId === currentFetchId.current) {
        const fileList = mode === "my-files" ? res.files : res.shared_files;
        setFiles(fileList);
      }
    } catch (err) {
      console.error("Failed to load files:", err);
    } finally {
      if (fetchId === currentFetchId.current) {
        setLoading(false);
      }
    }
  };

  const handleDelete = async (file_name) => {
    if (window.confirm(`Are you sure you want to delete "${file_name}"?`)) {
      try {
        await deleteFile(file_name);
        setFiles((prev) => prev.filter((f) => f.file_name !== file_name));
        setSuccessMessage("File deleted successfully!");
        setShowSuccessOverlay(true);
      } catch (err) {
        console.error("Failed to delete file:", err);
        alert("Could not delete the file.");
      }
    }
  };
  

  const generatePDFThumbnail = async (pdfData) => {
    try {
      pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;
      const loadingTask = pdfjsLib.getDocument({ data: atob(pdfData) });
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(1);
      const canvas = document.createElement("canvas");
      const viewport = page.getViewport({ scale: 1 });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
      return canvas.toDataURL();
    } catch (error) {
      console.error("Error generating PDF thumbnail:", error);
      return null;
    }
  };

  useEffect(() => {
    const generateThumbnails = async () => {
      const thumbnails = {};
      for (const file of files) {
        if (file.file_type === "application/pdf") {
          const thumbnail = await generatePDFThumbnail(file.decrypted_content);
          if (thumbnail) {
            thumbnails[file.file_name] = thumbnail;
          }
        }
      }
      setPdfThumbnails(thumbnails);
    };
    if (files.length > 0) {
      generateThumbnails();
    }
  }, [files]);

  const handleDownload = (file) => {
    const link = document.createElement("a");
    link.href = `data:${file.file_type};base64,${file.decrypted_content}`;
    link.download = file.file_name;
    link.click();
  };

  const handlePreview = (file) => {
    if (file.file_type === "application/pdf") {
      const byteCharacters = atob(file.decrypted_content);
      const byteNumbers = new Array(byteCharacters.length)
        .fill()
        .map((_, i) => byteCharacters.charCodeAt(i));
      const byteArray = new Uint8Array(byteNumbers);

      if (byteArray.length > MAX_PREVIEW_SIZE) {
        alert("The file is too large to preview. Please download it.");
        return;
      }

      const blob = new Blob([byteArray], { type: file.file_type });
      const blobUrl = URL.createObjectURL(blob);
      setPreviewFile({ ...file, blobUrl });
    } else {
      setPreviewFile(file);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_email");
    window.location.href = "/";
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (file) {
      try {
        setIsUploading(true);
        const res = await uploadFile(file);
        if (viewMode === "my-files" && res.file) {
          setFiles((prevFiles) => [...prevFiles, res.file]);
        }
        setSuccessMessage("File uploaded successfully!");
        setShowSuccessOverlay(true);
      } catch (err) {
        console.error("Upload failed:", err);
        alert("Upload failed. Please try again.");
      } finally {
        setIsUploading(false);
      }
    }
  };

  const openShareModal = (file) => {
    setShareTargetFile(file);
    setShareModalOpen(true);
    setShareEmail("");
  };

  const handleShareSubmit = async (e) => {
    e.preventDefault();
    try {
      await shareFile(shareTargetFile.file_name, shareEmail);
      alert("File shared successfully!");
      setShareModalOpen(false);
    } catch (err) {
      console.error("Share failed", err);
      alert("Failed to share the file.");
    }
  };

  const handleShareCancel = () => setShareModalOpen(false);

  return (
    <div className="main-wrapper">
      <aside className="sidebar">
        <h2>CipherDrive</h2>
        <label className="upload-btn">
          Upload
          <input type="file" hidden onChange={handleFileChange} />
        </label>
        <ul>
          <li className={viewMode === "my-files" ? "active" : ""} onClick={() => setViewMode("my-files")}>
            My Files
          </li>
          <li className={viewMode === "shared" ? "active" : ""} onClick={() => setViewMode("shared")}>
            Shared with Me
          </li>
        </ul>
        <div className="sidebar-spacer" style={{ flexGrow: 1 }}></div>
        <button className="logout-button" onClick={handleLogout}>
          Logout
        </button>
      </aside>

      <main className="main-container">
        <div className="topbar">
          <div className="user-email">{email}</div>
        </div>

        <h1 className="main-title">{viewMode === "my-files" ? "My Files" : "Shared with Me"}</h1>

        <div className="file-grid">
          {loading ? (
            [...Array(5)].map((_, i) => (
              <div className="file-tile skeleton" key={i}>
                <div className="file-thumbnail skeleton-box"></div>
                <div className="file-name skeleton-text"></div>
                <div className="file-tile-actions">
                  <div className="skeleton-button"></div>
                  <div className="skeleton-button"></div>
                </div>
              </div>
            ))
          ) : files.length > 0 ? (
            files.map((file) => (
              <div key={file.file_name} className="file-tile">
                <div className="file-thumbnail" onClick={() => handlePreview(file)}>
                  {file.file_type?.startsWith("image/") ? (
                    <img src={`data:${file.file_type};base64,${file.decrypted_content}`} alt={file.file_name} />
                  ) : file.file_type === "application/pdf" ? (
                    <img
                      src={pdfThumbnails[file.file_name] || "/pdf-icon.png"}
                      alt="PDF Preview"
                      className="file-icon"
                    />
                  ) : (
                    <img src="/file-icon.png" alt="File Icon" className="file-icon" />
                  )}
                </div>
                <div className="file-name">{file.file_name}</div>
                {viewMode === "shared" && (
                  <div className="owner-info">
                    <span className="label">Shared by</span>
                    <span className="email">{file.owner_email}</span>
                  </div>
                )}

            <div className="file-tile-actions">
              <button onClick={() => handleDownload(file)}>Download</button>
              {viewMode === "my-files" && (
                <>
                  <button onClick={() => openShareModal(file)}>Share</button>
                  <button onClick={() => handleDelete(file.file_name)}>
                  🗑️
                  </button>
                </>
              )}
            </div>

              </div>
            ))
          ) : (
            <p>No files {viewMode === "shared" ? "shared with you" : "uploaded"} yet.</p>
          )}
        </div>

        {previewFile && (
          <div className="preview-overlay" onClick={() => setPreviewFile(null)}>
            <div className="preview-content" onClick={(e) => e.stopPropagation()}>
              {previewFile.file_type === "application/pdf" ? (
                previewFile.blobUrl ? (
                  <iframe
                    src={previewFile.blobUrl}
                    className="pdf-fullscreen"
                    frameBorder="0"
                    title="PDF Preview"
                  ></iframe>
                ) : (
                  <p>The file is too large to preview. Please download it.</p>
                )
              ) : (
                <>
                  <button
                    className="close-preview-button"
                    onClick={() => setPreviewFile(null)}
                  >
                    ✕
                  </button>
                  <img
                    src={`data:${previewFile.file_type};base64,${previewFile.decrypted_content}`}
                    alt={previewFile.file_name}
                    style={{ maxWidth: "100%", maxHeight: "80vh" }}
                  />
                </>
              )}
            </div>
          </div>
        )}

        {shareModalOpen && (
          <div className="share-overlay" onClick={handleShareCancel}>
            <div className="share-content" onClick={(e) => e.stopPropagation()}>
              <h2>Share File</h2>
              <form onSubmit={handleShareSubmit}>
                <label>
                  Email:
                  <input
                    type="email"
                    value={shareEmail}
                    onChange={(e) => setShareEmail(e.target.value)}
                    required
                  />
                </label>
                <div className="share-actions">
                  <button type="submit">Share</button>
                  <button type="button" onClick={handleShareCancel}>
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {showSuccessOverlay && (
          <BottomRightToast
            message={successMessage}
            onClose={() => setShowSuccessOverlay(false)}
          />
        )}

        {isUploading && (
          <div className="uploading-overlay">
            <div className="uploading-box">
              <div className="spinner" />
              <p style={{ margin: 0 }}>Uploading file...</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}