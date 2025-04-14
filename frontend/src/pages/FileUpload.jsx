// import React, { useEffect, useState } from "react";
// import { getUserFiles } from "../services/api";

// function FileList() {
//     const [files, setFiles] = useState([]);

//     useEffect(() => {
//         const fetchFiles = async () => {
//             try {
//                 const data = await getUserFiles();
//                 setFiles(data.files);
//             } catch (error) {
//                 console.error("Failed to fetch files:", error.response?.data?.detail || error.message);
//             }
//         };

//         fetchFiles();
//     }, []);

//     const renderFile = (file) => {
//         if (file.file_type.startsWith("text/")) {
//             // Render text content
//             return (
//                 <div key={file.file_name}>
//                     <h3>{file.file_name}</h3>
//                     <pre>{file.decrypted_content}</pre>
//                 </div>
//             );
//         } else if (file.file_type.startsWith("image/")) {
//             // Render image
//             return (
//                 <div key={file.file_name}>
//                     <h3>{file.file_name}</h3>
//                     <img
//                         src={`data:${file.file_type};base64,${file.decrypted_content}`}
//                         alt={file.file_name}
//                         style={{ maxWidth: "100%" }}
//                     />
//                 </div>
//             );
//         } else if (file.file_type === "application/pdf") {
//             // Render PDF
//             const pdfBlob = new Blob([Uint8Array.from(atob(file.decrypted_content), c => c.charCodeAt(0))], {
//                 type: file.file_type,
//             });
//             const pdfUrl = URL.createObjectURL(pdfBlob);

//             return (
//                 <div key={file.file_name}>
//                     <h3>{file.file_name}</h3>
//                     <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
//                         View PDF
//                     </a>
//                     <br />
//                     <a href={pdfUrl} download={file.file_name}>
//                         Download PDF
//                     </a>
//                 </div>
//             );
//         } else {
//             // Render download link for other binary files
//             const blob = new Blob([Uint8Array.from(atob(file.decrypted_content), c => c.charCodeAt(0))], {
//                 type: file.file_type,
//             });
//             const url = URL.createObjectURL(blob);

//             return (
//                 <div key={file.file_name}>
//                     <h3>{file.file_name}</h3>
//                     <a href={url} download={file.file_name}>
//                         Download {file.file_name}
//                     </a>
//                 </div>
//             );
//         }
//     };

//     return (
//         <div>
//             <h2>Your Files</h2>
//             <ul>
//                 {files.map(renderFile)}
//             </ul>
//         </div>
//     );
// }

// export default FileList;