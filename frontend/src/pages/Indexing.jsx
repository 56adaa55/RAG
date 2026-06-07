// src/pages/Indexing.jsx
import React, { useState, useEffect } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const Indexing = () => {
  const [embeddingFile, setEmbeddingFile] = useState('');
  const [vectorDb, setVectorDb] = useState('chroma');
  const [indexMode, setIndexMode] = useState('standard');
  const [status, setStatus] = useState('');
  const [embeddedFiles, setEmbeddedFiles] = useState([]);
  const [indexingResult, setIndexingResult] = useState(null);
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState('');
  const [collectionDetails, setCollectionDetails] = useState(null);
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('chroma');

  // ---- 索引对比相关状态 ----
  const [activeTab, setActiveTab] = useState('index'); // 'index' | 'benchmark'
  const [benchmarkFile, setBenchmarkFile] = useState('');
  const [benchmarkQueries, setBenchmarkQueries] = useState('');
  const [benchmarkTopK, setBenchmarkTopK] = useState(5);
  const [selectedPresets, setSelectedPresets] = useState([]);
  const [availablePresets, setAvailablePresets] = useState({});
  const [benchmarkRunning, setBenchmarkRunning] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState(null);
  const [benchmarkHistory, setBenchmarkHistory] = useState([]);

  // 数据库和索引模式的配置
  const dbConfigs = {
    pinecone: { modes: ['standard', 'hybrid'] },
    milvus: { modes: ['flat', 'ivf_flat', 'ivf_sq8', 'hnsw'] },
    qdrant: { modes: ['hnsw', 'custom'] },
    weaviate: { modes: ['hnsw', 'flat'] },
    chroma: { modes: ['hnsw', 'standard'] },
    faiss: { modes: ['flat', 'ivf', 'hnsw'] }
  };

  useEffect(() => {
    fetchEmbeddedFiles();
    fetchCollections();
    fetchPresets();
  }, []);

  useEffect(() => {
    setIndexMode(dbConfigs[vectorDb].modes[0]);
  }, [vectorDb]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const providersResponse = await fetch(`${apiBaseUrl}/providers`);
        const providersData = await providersResponse.json();
        setProviders(providersData.providers);

        const collectionsResponse = await fetch(`${apiBaseUrl}/collections?provider=${selectedProvider}`);
        const collectionsData = await collectionsResponse.json();
        setCollections(collectionsData.collections);
      } catch (error) {
        console.error('Error fetching data:', error);
      }
    };
    fetchData();
  }, [selectedProvider]);

  const fetchEmbeddedFiles = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/list-embedded`);
      const data = await response.json();
      if (data.documents) {
        setEmbeddedFiles(data.documents.map(doc => ({
          ...doc,
          id: doc.name,
          displayName: doc.name
        })));
      }
    } catch (error) {
      console.error('Error fetching embedded files:', error);
      setStatus('Error loading embedding files');
    }
  };

  const fetchCollections = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/collections?provider=${selectedProvider}`);
      const data = await response.json();
      setCollections(data.collections || []);
    } catch (error) {
      console.error('Error fetching collections:', error);
    }
  };

  const fetchPresets = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/index-presets`);
      const data = await response.json();
      setAvailablePresets(data.presets || {});
    } catch (error) {
      console.error('Error fetching presets:', error);
    }
  };

  const handleIndex = async () => {
    if (!embeddingFile) {
      setStatus('Please select an embedding file');
      return;
    }
    setStatus('Indexing...');
    try {
      const response = await fetch(`${apiBaseUrl}/index`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fileId: embeddingFile,
          vectorDb: selectedProvider,
          indexMode
        }),
      });
      const data = await response.json();
      setIndexingResult(data);
      setStatus('Indexing completed successfully');
      fetchCollections();
    } catch (error) {
      console.error('Error indexing:', error);
      setStatus('Error during indexing: ' + error.message);
    }
  };

  const handleDisplay = async (collectionName) => {
    if (!collectionName) return;
    try {
      const response = await fetch(`${apiBaseUrl}/collections/${selectedProvider}/${collectionName}`);
      const data = await response.json();
      const result = {
        database: selectedProvider,
        collection_name: data.name,
        total_vectors: data.num_entities,
        index_size: data.num_entities
      };
      if (data.processing_time) {
        result.processing_time = data.processing_time;
      }
      setIndexingResult(result);
    } catch (error) {
      console.error('Error displaying collection:', error);
    }
  };

  const handleDelete = async (collectionName) => {
    if (!collectionName) return;
    if (window.confirm(`Are you sure you want to delete collection "${collectionName}"?`)) {
      try {
        await fetch(`${apiBaseUrl}/collections/${selectedProvider}/${collectionName}`, { method: 'DELETE' });
        setSelectedCollection('');
        const response = await fetch(`${apiBaseUrl}/collections?provider=${selectedProvider}`);
        const data = await response.json();
        setCollections(data.collections);
      } catch (error) {
        console.error('Error deleting collection:', error);
      }
    }
  };

  // ---- 索引对比功能 ----
  const handlePresetToggle = (presetId) => {
    setSelectedPresets(prev =>
      prev.includes(presetId)
        ? prev.filter(p => p !== presetId)
        : [...prev, presetId]
    );
  };

  const handleSelectAllPresets = () => {
    const allIds = Object.keys(availablePresets);
    if (selectedPresets.length === allIds.length) {
      setSelectedPresets([]);
    } else {
      setSelectedPresets(allIds);
    }
  };

  const handleRunBenchmark = async () => {
    if (!benchmarkFile || !benchmarkQueries.trim()) {
      setStatus('请选择嵌入文件并输入测试查询');
      return;
    }
    const queries = benchmarkQueries.split('\n').filter(q => q.trim());
    if (queries.length === 0) {
      setStatus('请至少输入一个测试查询');
      return;
    }
    if (selectedPresets.length === 0) {
      setStatus('请至少选择一个索引类型');
      return;
    }

    setBenchmarkRunning(true);
    setStatus('正在运行索引对比...');
    try {
      const response = await fetch(`${apiBaseUrl}/index-benchmark`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          embedding_file: benchmarkFile,
          test_queries: queries,
          presets: selectedPresets,
          top_k: benchmarkTopK,
        }),
      });
      const data = await response.json();
      setBenchmarkResult(data);
      setStatus('索引对比完成！');
      fetchBenchmarkHistory();
    } catch (error) {
      console.error('Error running benchmark:', error);
      setStatus('索引对比失败: ' + error.message);
    } finally {
      setBenchmarkRunning(false);
    }
  };

  const fetchBenchmarkHistory = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/benchmark-results`);
      const data = await response.json();
      setBenchmarkHistory(data.results || []);
    } catch (error) {
      console.error('Error fetching benchmark history:', error);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6"> 检索增强生成工具 </h1>
      <hr />

      {/* Tab切换 */}
      <div className="flex space-x-4 mb-6 mt-4">
        <button
          onClick={() => setActiveTab('index')}
          className={`px-6 py-2 rounded-lg font-medium ${
            activeTab === 'index' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          向量库索引
        </button>
        <button
          onClick={() => { setActiveTab('benchmark'); fetchBenchmarkHistory(); }}
          className={`px-6 py-2 rounded-lg font-medium ${
            activeTab === 'benchmark' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          索引对比分析
        </button>
      </div>

      {/* ================================================================ */}
      {/* Tab 1: 原有索引功能 */}
      {/* ================================================================ */}
      {activeTab === 'index' && (
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-3">
            <div className="p-4 border rounded-lg bg-white shadow-sm space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">需要索引的文件</label>
                <select
                  value={embeddingFile}
                  onChange={(e) => setEmbeddingFile(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">Choose a file...</option>
                  {embeddedFiles.map(file => (
                    <option key={file.name} value={file.name}>{file.displayName}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">向量库</label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  {providers.map(provider => (
                    <option key={provider.id} value={provider.id}>{provider.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">索引模式</label>
                <select
                  value={indexMode}
                  onChange={(e) => setIndexMode(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  {dbConfigs[vectorDb].modes.map(mode => (
                    <option key={mode} value={mode}>{mode.toUpperCase()}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <button
                  onClick={handleIndex}
                  className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-blue-300"
                  disabled={!embeddingFile}
                >
                  索引数据
                </button>
                <div>
                  <label className="block text-sm font-medium mb-1">索引集合</label>
                  <select
                    value={selectedCollection}
                    onChange={(e) => setSelectedCollection(e.target.value)}
                    className="block w-full p-2 border rounded"
                  >
                    <option value="">Choose a collection...</option>
                    {collections.map(coll => (
                      <option key={coll.id} value={coll.id}>{coll.name} ({coll.count} documents)</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={() => handleDisplay(selectedCollection)}
                  disabled={!selectedCollection}
                  className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-blue-300"
                >
                  显示集合
                </button>
                <button
                  onClick={() => handleDelete(selectedCollection)}
                  disabled={!selectedCollection}
                  className="w-full px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:bg-red-300"
                >
                  删除集合
                </button>
              </div>
              {status && (
                <div className="mt-4 p-3 rounded border bg-gray-50">
                  <p className="text-sm">{status}</p>
                </div>
              )}
            </div>
          </div>
          <div className="col-span-9 border rounded-lg bg-white shadow-sm">
            {indexingResult ? (
              <div className="p-4">
                <h3 className="text-xl font-semibold mb-4">索引结果</h3>
                <div className="space-y-3">
                  <div className="p-3 border rounded bg-gray-50">
                    <div className="text-sm text-gray-600">
                      <p>Database: {indexingResult.database}</p>
                      {indexingResult.index_mode && (<p>Index Mode: {indexingResult.index_mode}</p>)}
                      <p>Total Vectors: {indexingResult.total_vectors}</p>
                      <p>Index Size: {indexingResult.index_size}</p>
                      {indexingResult.processing_time && (<p>Processing Time: {indexingResult.processing_time}s</p>)}
                      <p>Collection Name: {indexingResult.collection_name}</p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <RandomImage message="Indexing results will appear here" />
            )}
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/* Tab 2: 索引对比分析（新增） */}
      {/* ================================================================ */}
      {activeTab === 'benchmark' && (
        <div className="grid grid-cols-12 gap-6">
          {/* 左侧控制面板 */}
          <div className="col-span-4 space-y-4">
            <div className="p-4 border rounded-lg bg-white shadow-sm space-y-4">
              <h3 className="text-lg font-semibold">索引对比配置</h3>

              <div>
                <label className="block text-sm font-medium mb-1">嵌入文件</label>
                <select
                  value={benchmarkFile}
                  onChange={(e) => setBenchmarkFile(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">选择嵌入文件...</option>
                  {embeddedFiles.map(file => (
                    <option key={file.name} value={file.name}>{file.displayName}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  测试查询（每行一个）
                </label>
                <textarea
                  value={benchmarkQueries}
                  onChange={(e) => setBenchmarkQueries(e.target.value)}
                  placeholder="输入测试查询，每行一个..."
                  className="block w-full p-2 border rounded h-32 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Top K: {benchmarkTopK}</label>
                <input
                  type="range"
                  value={benchmarkTopK}
                  onChange={(e) => setBenchmarkTopK(parseInt(e.target.value))}
                  min="1" max="20"
                  className="block w-full"
                />
              </div>

              {/* 索引类型多选 */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  选择索引类型对比
                  <button
                    onClick={handleSelectAllPresets}
                    className="ml-2 text-xs text-blue-500 underline"
                  >
                    {selectedPresets.length === Object.keys(availablePresets).length ? '取消全选' : '全选'}
                  </button>
                </label>
                <div className="max-h-64 overflow-y-auto border rounded p-2 space-y-1">
                  {Object.entries(availablePresets).map(([id, preset]) => (
                    <label key={id} className="flex items-start space-x-2 p-1 hover:bg-gray-50 rounded cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedPresets.includes(id)}
                        onChange={() => handlePresetToggle(id)}
                        className="mt-0.5"
                      />
                      <div className="text-sm">
                        <div className="font-medium">{preset.name}</div>
                        <div className="text-gray-500 text-xs">{preset.description}</div>
                      </div>
                    </label>
                  ))}
                </div>
                <div className="text-xs text-gray-500 mt-1">已选 {selectedPresets.length} 个</div>
              </div>

              <button
                onClick={handleRunBenchmark}
                disabled={benchmarkRunning || selectedPresets.length === 0}
                className="w-full px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-green-300"
              >
                {benchmarkRunning ? '正在运行对比...' : '运行索引对比'}
              </button>

              {status && (
                <div className="p-3 rounded border bg-gray-50">
                  <p className="text-sm">{status}</p>
                </div>
              )}
            </div>
          </div>

          {/* 右侧结果展示 */}
          <div className="col-span-8">
            {benchmarkResult ? (
              <div className="space-y-6">
                {/* 概览信息 */}
                <div className="p-4 border rounded-lg bg-white shadow-sm">
                  <h3 className="text-lg font-semibold mb-3">对比概览</h3>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div className="p-2 bg-blue-50 rounded">
                      <div className="text-gray-500">向量总数</div>
                      <div className="font-bold text-lg">{benchmarkResult.num_vectors}</div>
                    </div>
                    <div className="p-2 bg-green-50 rounded">
                      <div className="text-gray-500">测试查询数</div>
                      <div className="font-bold text-lg">{benchmarkResult.num_queries}</div>
                    </div>
                    <div className="p-2 bg-purple-50 rounded">
                      <div className="text-gray-500">对比类型数</div>
                      <div className="font-bold text-lg">{benchmarkResult.results.length}</div>
                    </div>
                  </div>
                </div>

                {/* 对比表格 */}
                <div className="p-4 border rounded-lg bg-white shadow-sm overflow-x-auto">
                  <h3 className="text-lg font-semibold mb-3">性能指标对比</h3>
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-gray-100">
                        <th className="border p-2 text-left">索引类型</th>
                        <th className="border p-2 text-right">构建时间(s)</th>
                        <th className="border p-2 text-right">磁盘大小(MB)</th>
                        <th className="border p-2 text-right">平均延迟(ms)</th>
                        <th className="border p-2 text-right">P50(ms)</th>
                        <th className="border p-2 text-right">P99(ms)</th>
                        <th className="border p-2 text-right">QPS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {benchmarkResult.results.map((r, idx) => (
                        <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          <td className="border p-2 font-medium">{r.name}</td>
                          <td className="border p-2 text-right">
                            <span className={r.build_time_s < 2 ? 'text-green-600' : r.build_time_s > 5 ? 'text-red-600' : 'text-yellow-600'}>
                              {r.build_time_s ?? '-'}
                            </span>
                          </td>
                          <td className="border p-2 text-right">{r.disk_size_mb ?? '-'}</td>
                          <td className="border p-2 text-right">
                            <span className={r.avg_query_latency_ms < 20 ? 'text-green-600' : r.avg_query_latency_ms > 100 ? 'text-red-600' : 'text-yellow-600'}>
                              {r.avg_query_latency_ms ?? '-'}
                            </span>
                          </td>
                          <td className="border p-2 text-right">{r.p50_latency_ms ?? '-'}</td>
                          <td className="border p-2 text-right">{r.p99_latency_ms ?? '-'}</td>
                          <td className="border p-2 text-right font-medium">{r.qps ?? '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 简易柱状图：构建时间对比 */}
                <div className="p-4 border rounded-lg bg-white shadow-sm">
                  <h3 className="text-lg font-semibold mb-3">构建时间对比 (s)</h3>
                  <div className="space-y-2">
                    {benchmarkResult.results.map((r, idx) => {
                      const maxTime = Math.max(...benchmarkResult.results.map(x => x.build_time_s || 0), 1);
                      const width = ((r.build_time_s || 0) / maxTime * 100).toFixed(0);
                      return (
                        <div key={idx} className="flex items-center text-xs">
                          <div className="w-32 truncate" title={r.name}>{r.name}</div>
                          <div className="flex-1 bg-gray-200 rounded h-5 mr-2">
                            <div
                              className="bg-blue-500 rounded h-5 flex items-center justify-end pr-1 text-white text-xs"
                              style={{ width: `${Math.max(width, 3)}%` }}
                            >
                              {r.build_time_s}s
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 简易柱状图：检索延迟对比 */}
                <div className="p-4 border rounded-lg bg-white shadow-sm">
                  <h3 className="text-lg font-semibold mb-3">平均检索延迟对比 (ms)</h3>
                  <div className="space-y-2">
                    {benchmarkResult.results.map((r, idx) => {
                      const maxLatency = Math.max(...benchmarkResult.results.map(x => x.avg_query_latency_ms || 0), 1);
                      const width = ((r.avg_query_latency_ms || 0) / maxLatency * 100).toFixed(0);
                      return (
                        <div key={idx} className="flex items-center text-xs">
                          <div className="w-32 truncate" title={r.name}>{r.name}</div>
                          <div className="flex-1 bg-gray-200 rounded h-5 mr-2">
                            <div
                              className="bg-green-500 rounded h-5 flex items-center justify-end pr-1 text-white text-xs"
                              style={{ width: `${Math.max(width, 3)}%` }}
                            >
                              {r.avg_query_latency_ms}ms
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <RandomImage message="索引对比结果将显示在这里" />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Indexing;
