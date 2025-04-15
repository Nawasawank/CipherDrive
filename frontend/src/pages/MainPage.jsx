import { useEffect, useRef, useState } from "react";
import {
  getUserDetails,
  getUserFiles,
  getSharedFiles,
  uploadFile,
  shareFile,
} from "../services/api";
import "../styles/MainPage.css";

export default function MainPage() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState("my-files");
  const [email, setEmail] = useState("");
  const [showLogout, setShowLogout] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [shareTargetFile, setShareTargetFile] = useState(null);
  const [shareEmail, setShareEmail] = useState("");
  const [sharePermission, setSharePermission] = useState("view");
  const userMenuRef = useRef(null);

  useEffect(() => {
    fetchUser();
    fetchFiles();
  }, [viewMode]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setShowLogout(false);
      }
    }
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === "Escape") {
        setPreviewFile(null);
      }
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, []);

  const fetchUser = async () => {
    try {
      const res = await getUserDetails();
      setEmail(res?.email || "");
    } catch (err) {
      console.error("Failed to load user", err);
    }
  };

  const fetchFiles = async () => {
    setLoading(true);
    try {
      const res =
        viewMode === "my-files" ? await getUserFiles() : await getSharedFiles();
      setFiles(viewMode === "my-files" ? res.files : res.shared_files);
    } catch (err) {
      console.error("Failed to load files:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (file) => {
    const link = document.createElement("a");
    link.href = `data:${file.file_type};base64,${file.decrypted_content}`;
    link.download = file.file_name;
    link.click();
  };

  const handlePreview = (file) => {
    if (
      file.file_type.startsWith("image/") ||
      file.file_type === "application/pdf"
    ) {
      setPreviewFile(file);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    window.location.href = "/";
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (file) {
      await uploadFile(file);
      fetchFiles();
    }
  };

  const openShareModal = (file) => {
    setShareTargetFile(file);
    setShareModalOpen(true);
    setShareEmail("");
    setSharePermission("view");
  };

  const handleShareSubmit = async (e) => {
    e.preventDefault();
    try {
      await shareFile(
        shareTargetFile.file_name,
        shareEmail,
        sharePermission
      );
      alert("File shared successfully!");
      setShareModalOpen(false);
    } catch (err) {
      console.error("Share failed", err);
      alert("Failed to share the file.");
    }
  };

  const handleShareCancel = () => {
    setShareModalOpen(false);
  };

  return (
    <div className="main-wrapper">
      <aside className="sidebar">
        <h2>SecureDrive</h2>
        <label className="upload-btn">
          + Upload
          <input type="file" hidden onChange={handleFileChange} />
        </label>
        <ul>
          <li
            className={viewMode === "my-files" ? "active" : ""}
            onClick={() => setViewMode("my-files")}
          >
            My Files
          </li>
          <li
            className={viewMode === "shared" ? "active" : ""}
            onClick={() => setViewMode("shared")}
          >
            Shared with Me
          </li>
        </ul>
      </aside>

      <main className="main-container">
        <div className="topbar">
          <div ref={userMenuRef} className="user-dropdown">
            <div onClick={() => setShowLogout((prev) => !prev)}>
              {email} <span className="caret">▼</span>
            </div>
            {showLogout && (
              <div className="dropdown-menu">
                <button onClick={handleLogout}>Logout</button>
              </div>
            )}
          </div>
        </div>

        <h1 className="main-title">
          {viewMode === "my-files" ? "My Files" : "Shared with Me"}
        </h1>

        {loading ? (
          <div className="loading-text">Loading files...</div>
        ) : (
          <div className="file-grid">
            {files.length > 0 ? (
              files.map((file) => (
                <div key={file.file_name} className="file-tile">
                  <div
                    className="file-thumbnail"
                    onClick={() => handlePreview(file)}
                  >
                    {file.file_type.startsWith("image/") ? (
                      <img
                        src={`data:${file.file_type};base64,${file.decrypted_content}`}
                        alt={file.file_name}
                      />
                    ) : file.file_type === "application/pdf" ? (
                      <img src="/pdf-icon.png" alt="PDF" className="file-icon" />
                    ) : (
                      <img src="/file-icon.png" alt="file" className="file-icon" />
                    )}
                  </div>
                  <div className="file-name">{file.file_name}</div>
                  <div className="file-tile-actions">
                    <button onClick={() => handleDownload(file)}>Download</button>
                    {viewMode === "my-files" && (
                      <button onClick={() => openShareModal(file)}>Share</button>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <p>No files {viewMode === "shared" ? "shared with you" : "uploaded"} yet.</p>
            )}
          </div>
        )}

        {/* 🧾 Fullscreen Clean PDF Viewer */}
        {previewFile && (
          <div className="preview-overlay" onClick={() => setPreviewFile(null)}>
            <div className="preview-content" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => setPreviewFile(null)}
                style={{
                  position: "absolute",
                  top: 20,
                  right: 30,
                  fontSize: "28px",
                  color: "white",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  zIndex: 1001,
                }}
              >
                ✕
              </button>
              {previewFile.file_type === "application/pdf" ? (
                <object
                  data={`data:${previewFile.file_type};base64,${previewFile.decrypted_content}`}
                  type="application/pdf"
                  className="pdf-fullscreen"
                >
                  <p>
                    PDF preview not supported in this browser.{" "}
                    <a
                      href={`data:${previewFile.file_type};base64,${previewFile.decrypted_content}`}
                      download={previewFile.file_name}
                    >
                      Download PDF
                    </a>
                  </p>
                </object>
              ) : (
                <img
                  src={`data:${previewFile.file_type};base64,${previewFile.decrypted_content}`}
                  alt={previewFile.file_name}
                  style={{ maxWidth: "100%", maxHeight: "90vh" }}
                />
              )}
            </div>
          </div>
        )}

        {/* Share Modal */}
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
                <label>
                  Permission:
                  <select
                    value={sharePermission}
                    onChange={(e) => setSharePermission(e.target.value)}
                  >
                    <option value="view">View only</option>
                    <option value="download">Download only</option>
                    <option value="view_download">View & Download</option>
                  </select>
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
      </main>
    </div>
  );
}
