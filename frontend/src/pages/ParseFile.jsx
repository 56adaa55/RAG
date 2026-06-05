import React, { useState } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const ParseFile = () => {
  const [file, setFile] = useState(null);
  const [loadingMethod, setLoadingMethod] = useState('pymupdf');
  const [parsingOption, setParsingOption] = useState('all_text');
  const [parsedContent, setParsedContent] = useState(null);
  const [status, setStatus] = useState('');
  const [docName, setDocName] = useState('');
  const [isProcessed, setIsProcessed] = useState(false);
  const [activeTab, setActiveTab] = useState('preview'); // 'preview' or 'documents'
  const [documents, setDocuments] = useState([]);

  React.useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/documents?type=parsed`);
      const data = await response.json();
      setDocuments(data.documents);
    } catch (error) {
      console.error('Error fetching parsed documents:', error);
    }
  };

  const handleProcess = async () => {
    if (!file || !loadingMethod || !parsingOption) {
      setStatus('Please select all required options');
      return;
    }

    setStatus('Processing...');
    setParsedContent(null);
    setIsProcessed(false);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('loading_method', loadingMethod);
      formData.append('parsing_option', parsingOption);
      
      if (loadingMethod === 'unstructured') {
        formData.append('strategy', window.unstructuredStrategy || 'fast');
      }

      const response = await fetch(`${apiBaseUrl}/parse`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setParsedContent(data.parsed_content);
      setStatus('Processing completed successfully!');
      setIsProcessed(true);
      fetchDocuments(); // Refresh the list after successful parse
      setActiveTab('preview');
    } catch (error) {
      console.error('Error:', error);
      setStatus(`Error: ${error.message}`);
    }
  };

  const handleDeleteDocument = async (docName) => {
    try {
      const response = await fetch(`${apiBaseUrl}/documents/${docName}?type=loaded`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      setStatus('Document deleted successfully');
      fetchDocuments();
    } catch (error) {
      console.error('Error deleting document:', error);
      setStatus(`Error deleting document: ${error.message}`);
    }
  };

  const handleViewDocument = async (doc) => {
    try {
      setStatus('Loading document...');
      const response = await fetch(`${apiBaseUrl}/documents/${doc.name}?type=loaded`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      
      // Convert standard loaded format back to parsedContent format for preview
      const formattedContent = {
        metadata: data.metadata,
        content: data.chunks.map(chunk => ({
          type: chunk.metadata.type || 'Text',
          title: chunk.metadata.title,
          content: chunk.content,
          page: chunk.metadata.page_number
        }))
      };
      
      setParsedContent(formattedContent);
      setActiveTab('preview');
      setStatus('');
    } catch (error) {
      console.error('Error loading document:', error);
      setStatus(`Error loading document: ${error.message}`);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setFile(file);
      const baseName = file.name.replace('.pdf', '');
      setDocName(baseName);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6"> 检索增强生成工具 </h1>
      <hr />
      <h2 className="text-2xl font-bold mb-6">文件解析</h2>
      
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel (3/12) */}
        <div className="col-span-3 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div>
              <label className="block text-sm font-medium mb-1">选择PDF文件</label>
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                className="block w-full border rounded px-3 py-2"
                required
              />
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">装载工具</label>
              <select
                value={loadingMethod}
                onChange={(e) => setLoadingMethod(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="pymupdf">PyMuPDF</option>
                <option value="pypdf">PyPDF</option>
                <option value="unstructured">Unstructured</option>
                <option value="pdfplumber">PDF Plumber</option>
              </select>
            </div>

            {loadingMethod === 'unstructured' && (
              <div className="mt-4">
                <label className="block text-sm font-medium mb-1">Unstructured 策略</label>
                <select
                  value={window.unstructuredStrategy || 'fast'}
                  onChange={(e) => { window.unstructuredStrategy = e.target.value; }}
                  className="block w-full p-2 border rounded"
                >
                  <option value="fast">Fast (仅文本提取)</option>
                  <option value="hi_res">High Res (需下载AI视觉模型)</option>
                  <option value="ocr_only">OCR Only</option>
                </select>
              </div>
            )}

            <div className="mt-4">
              <label className="block text-sm font-medium mb-1">解析选项</label>
              <select
                value={parsingOption}
                onChange={(e) => setParsingOption(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="all_text">All Text</option>
                <option value="by_pages">By Pages</option>
                <option value="by_titles">By Titles</option>
                <option value="text_and_tables">Text and Tables</option>
                <option value="titles_and_tables">Titles and Tables (结合版)</option>
              </select>
            </div>

            <button 
              onClick={handleProcess}
              className="mt-4 w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              disabled={!file}
            >
              解析文件
            </button>
          </div>
        </div>

        {/* Right Panel (9/12) */}
        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          <div className="p-4">
            {/* Tabs */}
            <div className="flex mb-4 border-b">
              <button
                className={`px-4 py-2 ${
                  activeTab === 'preview'
                    ? 'border-b-2 border-blue-500 text-blue-600'
                    : 'text-gray-600'
                }`}
                onClick={() => setActiveTab('preview')}
              >
                解析预览
              </button>
              <button
                className={`px-4 py-2 ml-4 ${
                  activeTab === 'documents'
                    ? 'border-b-2 border-blue-500 text-blue-600'
                    : 'text-gray-600'
                }`}
                onClick={() => setActiveTab('documents')}
              >
                解析文件管理
              </button>
            </div>

            {/* Tab Content */}
            {activeTab === 'preview' ? (
              parsedContent ? (
                <div>
                  <h3 className="text-xl font-semibold mb-4">Parsing Results</h3>
                  <div className="mb-4 p-3 border rounded bg-gray-100">
                    <h4 className="font-medium mb-2">Document Information</h4>
                    <div className="text-sm text-gray-600">
                      <p>Total Pages: {parsedContent.metadata?.total_pages}</p>
                      <p>Parsing Method: {parsedContent.metadata?.parsing_method || parsedContent.metadata?.loading_method}</p>
                      <p>Timestamp: {parsedContent.metadata?.timestamp && new Date(parsedContent.metadata.timestamp).toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto">
                    {parsedContent.content.map((item, idx) => (
                      <div key={idx} className="p-3 border rounded bg-gray-50">
                        <div className="font-medium text-sm text-gray-500 mb-1">
                          {item.type} - Page {item.page}
                        </div>
                        {item.title && (
                          <div className="font-bold text-gray-700 mb-2">
                            {item.title}
                          </div>
                        )}
                        <div className="text-sm text-gray-600">
                          {item.content}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <RandomImage message="Upload and parse a file to see the results here" />
              )
            ) : (
              // Documents Management Tab
              <div>
                <h3 className="text-xl font-semibold mb-4">已解析文档：</h3>
                <div className="space-y-4">
                  {documents.map((doc) => (
                    <div key={doc.name} className="p-4 border rounded-lg bg-gray-50">
                      <div className="flex justify-between items-start">
                        <div>
                          <h4 className="font-medium text-lg">{doc.name}</h4>
                          <div className="text-sm text-gray-600 mt-1">
                            <p>Pages: {doc.metadata?.total_pages || 'N/A'}</p>
                            <p>Parsing Method: {doc.metadata?.loading_method?.replace('parsed_', '') || 'N/A'}</p>
                            <p>Created: {doc.metadata?.timestamp ? 
                              new Date(doc.metadata.timestamp).toLocaleString() : 'N/A'}</p>
                          </div>
                        </div>
                        <div className="flex space-x-2">
                          <button
                            onClick={() => handleViewDocument(doc)}
                            className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600"
                          >
                            浏览
                          </button>
                          <button
                            onClick={() => handleDeleteDocument(doc.name)}
                            className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                  {documents.length === 0 && (
                    <div className="text-center text-gray-500 py-8">
                      没有找到已解析的文档
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ParseFile; 