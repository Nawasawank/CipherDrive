import { useEffect, useRef, useState } from "react";
import { getAllUsers, getUserFilesById } from "../services/api";
import * as pdfjsLib from "pdfjs-dist";
import "../styles/AdminPage.css";

export default function AdminPanel() {
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userFiles, setUserFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [pdfThumbnails, setPdfThumbnails] = useState({});
  const [view, setView] = useState("user-list");
  const [previewFile, setPreviewFile] = useState(null);

  const currentFetchId = useRef(0);
  const MAX_PREVIEW_SIZE = 5 * 1024 * 1024; // 5 MB limit for preview

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const res = await getAllUsers();
      setUsers(res.users || []);
    } catch (error) {
      console.error("Failed to load users", error);
    }
  };

  const handleUserClick = async (user) => {
    setSelectedUser(user);
    setView("user-files");
    setLoadingFiles(true);
    setUserFiles([]);
    const fetchId = ++currentFetchId.current;
    try {
      const res = await getUserFilesById(user.id);
      if (fetchId === currentFetchId.current) {
        setUserFiles(res.files || []);
      }
    } catch (error) {
      console.error("Failed to fetch user files", error);
    } finally {
      if (fetchId === currentFetchId.current) setLoadingFiles(false);
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
      for (const file of userFiles) {
        if (file.file_type === "application/pdf") {
          const thumbnail = await generatePDFThumbnail(file.decrypted_content);
          if (thumbnail) thumbnails[file.file_name] = thumbnail;
        }
      }
      setPdfThumbnails(thumbnails);
    };
    if (userFiles.length > 0) {
      generateThumbnails();
    }
  }, [userFiles]);

  const handleLogout = () => {
    localStorage.clear();
    window.location.href = "/";
  };

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

  return (
    <div className="admin-panel-dashboard">
      <aside className="admin-panel-sidebar">
        <h1 className="admin-panel-logo">SecureDrive</h1>
        <nav className="admin-panel-nav">
          <button
            className={`admin-panel-nav-button ${view === "user-list" ? "active" : ""}`}
            onClick={() => setView("user-list")}
          >
            👥 User List
          </button>
        </nav>
        <button className="admin-panel-logout-button" onClick={handleLogout}>Logout</button>
      </aside>

      <main className="admin-panel-content">
        {view === "user-list" && (
          <>
            <h2>User Emails</h2>
            <div className="admin-panel-user-list">
              {users.map((user) => (
                <div
                  key={user.id}
                  className="admin-panel-user-card"
                  onClick={() => handleUserClick(user)}
                >
                  {user.email}
                </div>
              ))}
            </div>
          </>
        )}

        {view === "user-files" && selectedUser && (
          <>
            <h2>Files of {selectedUser.email}</h2>
            <button className="admin-panel-back-button" onClick={() => setView("user-list")}>← Back to User List</button>
            <div className="admin-panel-file-grid">
              {loadingFiles ? (
                [...Array(5)].map((_, i) => (
                  <div className="admin-panel-file-tile skeleton" key={i}>
                    <div className="admin-panel-file-thumbnail skeleton-box"></div>
                    <div className="admin-panel-file-name skeleton-text"></div>
                    <div className="file-tile-actions">
                      <div className="skeleton-button"></div>
                    </div>
                  </div>
                ))
              ) : userFiles.length > 0 ? (
                userFiles.map((file) => (
                  <div key={file.file_name} className="admin-panel-file-tile">
                    <div
                      className="admin-panel-file-thumbnail"
                      onClick={() => handlePreview(file)}
                      style={{ cursor: "pointer" }}
                    >
                      {file.file_type?.startsWith("image/") ? (
                        <img src={`data:${file.file_type};base64,${file.decrypted_content}`} alt={file.file_name} />
                      ) : file.file_type === "application/pdf" ? (
                        <img src={pdfThumbnails[file.file_name] || "/pdf-icon.png"} alt="PDF" />
                      ) : (
                        <img src="/file-icon.png" alt="File" />
                      )}
                    </div>
                    <div className="admin-panel-file-name">{file.file_name}</div>
                    <button onClick={() => handleDownload(file)}>Download</button>
                  </div>
                ))
              ) : (
                <p>No files available.</p>
              )}
            </div>
          </>
        )}

        {/* Preview overlay */}
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
      </main>
    </div>
  );
}