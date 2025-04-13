import React, { useEffect, useState } from "react";
import { getUserFiles } from "../services/api";

function FileList() {
    const [files, setFiles] = useState([]);

    useEffect(() => {
        const fetchFiles = async () => {
            try {
                const data = await getUserFiles();
                setFiles(data.files);
            } catch (error) {
                console.error("Failed to fetch files:", error.response?.data?.detail || error.message);
            }
        };

        fetchFiles();
    }, []);

    const renderFileCard = (file) => {
        if (file.file_type.startsWith("image/")) {
            // Render image thumbnail
            return (
                <div key={file.file_name} className="file-card">
                    <img
                        src={`data:${file.file_type};base64,${file.decrypted_content}`}
                        alt={file.file_name}
                        className="file-thumbnail"
                    />
                    <h4>{file.file_name}</h4>
                    <a
                        href={`data:${file.file_type};base64,${file.decrypted_content}`}
                        download={file.file_name}
                        className="file-action"
                    >
                        Download
                    </a>
                </div>
            );
        } else if (file.file_type === "application/pdf") {
            // Render PDF preview
            const pdfBlob = new Blob([Uint8Array.from(atob(file.decrypted_content), c => c.charCodeAt(0))], {
                type: file.file_type,
            });
            const pdfUrl = URL.createObjectURL(pdfBlob);

            return (
                <div key={file.file_name} className="file-card">
                    <img
                        src="https://upload.wikimedia.org/wikipedia/commons/8/87/PDF_file_icon.svg"
                        alt="PDF Icon"
                        className="file-thumbnail"
                    />
                    <h4>{file.file_name}</h4>
                    <a href={pdfUrl} target="_blank" rel="noopener noreferrer" className="file-action">
                        View
                    </a>
                    <a href={pdfUrl} download={file.file_name} className="file-action">
                        Download
                    </a>
                </div>
            );
        } else {
            // Render other file types
            const blob = new Blob([Uint8Array.from(atob(file.decrypted_content), c => c.charCodeAt(0))], {
                type: file.file_type,
            });
            const url = URL.createObjectURL(blob);

            return (
                <div key={file.file_name} className="file-card">
                    <img
                        src="https://upload.wikimedia.org/wikipedia/commons/e/e0/Document_icon_%28the_Noun_Project_25296%29.svg"
                        alt="File Icon"
                        className="file-thumbnail"
                    />
                    <h4>{file.file_name}</h4>
                    <a href={url} download={file.file_name} className="file-action">
                        Download
                    </a>
                </div>
            );
        }
    };

    return (
        <div className="file-grid">
            {files.map(renderFileCard)}
        </div>
    );
}

export default FileList;