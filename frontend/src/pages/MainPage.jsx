import { useEffect, useState } from "react";
import { getUserDetails, getUserFiles, uploadFile } from "../services/api";
import axios from "axios";
import "../styles/MainPage.css";

export default function MainPage() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState("my-files");
  const [email, setEmail] = useState("");
  const [showLogout, setShowLogout] = useState(false);
  const [previewFile, setPreviewFile] = useState(null);

  useEffect(() => {
    fetchUser();
    fetchFiles();
  }, []);

  const fetchUser = async () => {
    try {
      const res = await getUserDetails();
      console.log("User:", res);
      setEmail(res?.email || "");
    } catch (err) {
      console.error("Failed to load user", err);
    }
  };

  const fetchFiles = async () => {
    try {
      const res = await getUserFiles();
      setFiles(res.files);
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
          <div className="user-email" onClick={() => setShowLogout(!showLogout)}>
            {email}
            {showLogout && (
              <button onClick={handleLogout} className="logout-btn-inline">
                Logout
              </button>
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
                <div key={file.id || file.file_name} className="file-tile">
                  <div className="file-thumbnail" onClick={() => handlePreview(file)}>
                    {file.file_type.startsWith("image/") ? (
                      <img
                        src={`data:${file.file_type};base64,${file.decrypted_content}`}
                        alt={file.file_name}
                      />
                    ) : (
                      <img
                        src="/file-icon.png"
                        alt="file"
                        className="file-icon"
                      />
                    )}
                  </div>
                  <div className="file-name">{file.file_name}</div>
                  <div className="file-tile-actions">
                    <button onClick={() => handlePreview(file)}>View</button>
                    <button onClick={() => handleDownload(file)}>Download</button>
                  </div>
                </div>
              ))
            ) : (
              <p>No files uploaded yet.</p>
            )}
          </div>
        )}

        {previewFile && (
          <div className="preview-overlay" onClick={() => setPreviewFile(null)}>
            <div className="preview-content" onClick={(e) => e.stopPropagation()}>
              {previewFile.file_type === "application/pdf" ? (
                <iframe
                  src={`data:${previewFile.file_type};base64,${previewFile.decrypted_content}`}
                  width="100%"
                  height="600px"
                  style={{ border: "none" }}
                ></iframe>
              ) : (
                <img
                  src={`data:${previewFile.file_type};base64,${previewFile.decrypted_content}`}
                  alt={previewFile.file_name}
                  style={{ maxWidth: "100%", maxHeight: "80vh" }}
                />
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}