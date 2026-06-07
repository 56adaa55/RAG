import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const MarkdownViewer = ({ markdownText }) => {
  return (
    <div className="markdown-container">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdownText}</ReactMarkdown>
    </div>
  );
};


const Generation = () => {
  const location = useLocation();
  const [provider, setProvider] = useState('');
  const [modelName, setModelName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [models, setModels] = useState({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [response, setResponse] = useState('');
  const [status, setStatus] = useState('');
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedFile, setSelectedFile] = useState('');
  const [searchFiles, setSearchFiles] = useState([]);
  const [showReasoning, setShowReasoning] = useState(true);
  const [loadModel, setLoadModel] = useState(false);

  // ---- 上下文优化相关状态（新增） ----
  const [enableCompression, setEnableCompression] = useState(false);
  const [maxContextChunks, setMaxContextChunks] = useState(5);
  const [showContextPanel, setShowContextPanel] = useState(false);
  const [compressedContext, setCompressedContext] = useState(null);
  const [contextStats, setContextStats] = useState(null);

  // 加载可用模型列表和搜索结果文件列表
  useEffect(() => {
    const fetchData = async () => {
      try {
        const modelsResponse = await fetch(`${apiBaseUrl}/generation/models`);
        const modelsData = await modelsResponse.json();
        setModels(modelsData.models);

        const filesResponse = await fetch(`${apiBaseUrl}/search-results`);
        const filesData = await filesResponse.json();
        setSearchFiles(filesData.files);
      } catch (error) {
        console.error('Error fetching data:', error);
        setStatus('获取数据失败');
      }
    };

    fetchData();
  }, []);

  // 加载选中的搜索结果文件内容
  useEffect(() => {
    const loadSearchResults = async () => {
      if (!selectedFile) {
        setQuery('');
        setSearchResults([]);
        setCompressedContext(null);
        setContextStats(null);
        return;
      }

      try {
        const response = await fetch(`${apiBaseUrl}/search-results/${selectedFile}`);
        const data = await response.json();
        setQuery(data.query);
        setSearchResults(data.results);

        // 计算上下文统计信息
        if (data.results) {
          const rawLen = data.results.reduce((sum, r) => sum + (r.text?.length || 0), 0);
          setContextStats({
            originalChunks: data.results.length,
            originalChars: rawLen,
          });
        }
      } catch (error) {
        console.error('Error loading search results:', error);
        setStatus('加载搜索结果失败');
      }
    };

    loadSearchResults();
  }, [selectedFile]);

  // 如果从搜索页面跳转过来
  useEffect(() => {
    if (location.state) {
      const { query: searchQuery, results } = location.state;
      if (searchQuery) setQuery(searchQuery);
      if (results) setSearchResults(results);
    }
  }, [location]);

  const handleGenerate = async () => {
    if (!provider || !modelName) {
      setStatus('请选择生成模型');
      return;
    }

    if (!query) {
      setStatus('请输入问题并确保有搜索结果');
      return;
    }

    setIsGenerating(true);
    setStatus('');

    // 准备上下文
    let context = searchResults;

    // 上下文压缩
    if (enableCompression && context.length > 0) {
      try {
        const compressResponse = await fetch(`${apiBaseUrl}/optimization-options`);
        // 用 post-optimizer 的 compress 功能
        const searchResp = await fetch(`${apiBaseUrl}/search-optimized`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: query,
            collection_id: selectedFile || 'default',
            top_k: maxContextChunks,
            threshold: 0.0,
            pre_strategies: [],
            post_strategies: ['compress'],
          }),
        });

        if (searchResp.ok) {
          const optimizedData = await searchResp.json();
          if (optimizedData.results && optimizedData.results.length > 0) {
            setCompressedContext(optimizedData.results[0].text);
            setContextStats(prev => ({
              ...prev,
              compressedChars: optimizedData.results[0].text?.length || 0,
            }));
          }
        }
      } catch (e) {
        console.warn('Context compression not available:', e);
      }
    }

    // 限制上下文块数
    if (maxContextChunks && context.length > maxContextChunks) {
      context = context.slice(0, maxContextChunks);
    }

    try {
      const response = await fetch(`${apiBaseUrl}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          provider,
          model_name: modelName,
          search_results: context,
          load_model: loadModel,
          api_key: apiKey || null,
          show_reasoning: showReasoning,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setResponse(data.response);
      setLoadModel(false);
      setStatus(`生成完成！结果已保存至: ${data.saved_filepath}`);
    } catch (error) {
      console.error('Generation error:', error);
      setStatus(`生成失败: ${error.message}`);
    } finally {
      setIsGenerating(false);
      setLoadModel(false);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6"> 检索增强生成工具 </h1>
      <hr />
      <h2 className="text-2xl font-bold mb-6">响应生成</h2>

      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel - Generation Controls */}
        <div className="col-span-4 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">提问</label>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter your question..."
                  className="block w-full p-2 border rounded h-32 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">检索文档（可选）</label>
                <select
                  value={selectedFile}
                  onChange={(e) => setSelectedFile(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">Select search results file...</option>
                  {searchFiles.map(file => (
                    <option key={file.id} value={file.id}>{file.name}</option>
                  ))}
                </select>
              </div>

              {/* ---- 上下文优化选项（新增） ---- */}
              <div className="border-t pt-3">
                <button
                  onClick={() => setShowContextPanel(!showContextPanel)}
                  className="w-full flex items-center justify-between text-sm font-medium"
                >
                  <span>📐 上下文优化选项</span>
                  <span className={`transform transition-transform ${showContextPanel ? 'rotate-90' : ''}`}>▶</span>
                </button>

                {showContextPanel && (
                  <div className="mt-3 space-y-3">
                    <label className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={enableCompression}
                        onChange={(e) => setEnableCompression(e.target.checked)}
                        className="form-checkbox h-4 w-4"
                      />
                      <span className="text-sm">上下文压缩 (Context Compression)</span>
                    </label>

                    <div>
                      <label className="block text-xs text-gray-500 mb-1">
                        最大上下文块数: {maxContextChunks}
                      </label>
                      <input
                        type="range"
                        value={maxContextChunks}
                        onChange={(e) => setMaxContextChunks(parseInt(e.target.value))}
                        min="1" max="20"
                        className="block w-full"
                      />
                    </div>

                    {/* 上下文统计信息 */}
                    {contextStats && (
                      <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                        <div>上下文块: {contextStats.originalChunks} 个</div>
                        <div>原始长度: {contextStats.originalChars} chars</div>
                        {contextStats.compressedChars && (
                          <div className="text-green-600">
                            压缩后: {contextStats.compressedChars} chars
                            ({Math.round(contextStats.compressedChars / contextStats.originalChars * 100)}%)
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* ---- 原有选项 ---- */}
              <div>
                <label className="block text-sm font-medium mb-1">生成模型提供方</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">Select provider...</option>
                  {Object.keys(models).map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>

              {provider && (
                <div>
                  <label className="block text-sm font-medium mb-1">生成模型</label>
                  <select
                    value={modelName}
                    onChange={(e) => {setModelName(e.target.value); setLoadModel(true)}}
                    className="block w-full p-2 border rounded"
                  >
                    <option value="">Select model...</option>
                    {Object.entries(models[provider] || {}).map(([id, name]) => (
                      <option key={id} value={id}>
                        {id === 'deepseek-v3' ? 'DeepSeek V3' :
                         id === 'deepseek-r1' ? 'DeepSeek R1' :
                         name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {(provider === 'openai' || provider === 'deepseek') && (
                <div>
                  <label className="block text-sm font-medium mb-1">API Key</label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter your API key..."
                    className="block w-full p-2 border rounded"
                  />
                </div>
              )}

              {provider === 'deepseek' && modelName === 'deepseek-r1' && (
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="showReasoning"
                    checked={showReasoning}
                    onChange={(e) => setShowReasoning(e.target.checked)}
                    className="rounded border-gray-300 text-green-500 focus:ring-green-500"
                  />
                  <label htmlFor="showReasoning" className="text-sm font-medium">
                    显示思维链过程
                  </label>
                </div>
              )}

              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-green-300"
              >
                {isGenerating ? '生成回答中...' : '生成回答'}
              </button>

              {status && (
                <div className={`p-4 rounded-lg ${
                  status.includes('失败') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                }`}>
                  {status}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Panel - Context and Response */}
        <div className="col-span-8">
          {/* 压缩后的上下文展示（新增） */}
          {compressedContext && (
            <div className="mb-6 p-4 border rounded-lg bg-green-50 shadow-sm">
              <h3 className="text-lg font-semibold mb-2 text-green-700">📦 压缩后的上下文</h3>
              <div className="text-sm whitespace-pre-wrap max-h-[200px] overflow-y-auto">
                {compressedContext}
              </div>
            </div>
          )}

          {selectedFile ? (
            <>
              {/* Search Results Context */}
              <div className="mb-6 p-4 border rounded-lg bg-white shadow-sm">
                <h3 className="text-xl font-semibold mb-4">
                  检索的上下文
                  {maxContextChunks < searchResults.length && (
                    <span className="text-sm font-normal text-gray-500 ml-2">
                      (显示前 {maxContextChunks}/{searchResults.length} 个)
                    </span>
                  )}
                </h3>
                <div className="space-y-4 max-h-[300px] overflow-y-auto">
                  {searchResults.slice(0, maxContextChunks).map((result, idx) => (
                    <div key={idx} className="p-4 border rounded bg-gray-50">
                      <div className="flex justify-between items-start mb-2">
                        <span className="font-medium text-sm text-gray-500">
                          Match Score: {(result.score * 100).toFixed(1)}%
                        </span>
                        <div className="text-sm text-gray-500">
                          <div>Source: {result.metadata?.source || result.metadata?.document_name}</div>
                          <div>Page: {result.metadata?.page || result.metadata?.page_number}</div>
                        </div>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{result.text}</p>
                    </div>
                  ))}
                </div>
              </div>
           </>
          ) : (
            <div className="mb-6 p-4 border rounded-lg bg-white shadow-sm">
                <h3 className="text-xl font-semibold mb-4">无检索上下文</h3>
            </div>
          )}
              {/* Generated Response */}
              {response && (
                <div className="p-4 border rounded-lg bg-white shadow-sm">
                  <h3 className="text-xl font-semibold mb-4">生成的回答</h3>
                  <div className="p-4 border rounded bg-gray-50">
                    <p className="whitespace-pre-wrap"><MarkdownViewer markdownText={response} /></p>
                  </div>
                </div>
              )}
        </div>
      </div>
    </div>
  );
};

export default Generation;
