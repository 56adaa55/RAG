// src/pages/Comparison.jsx
import React, { useState, useEffect } from 'react';
import { apiBaseUrl } from '../config/config';

// 数据库和索引模式的配置（与 Indexing.jsx 保持一致）
const dbConfigs = {
  pinecone: { modes: ['standard', 'hybrid'] },
  milvus: { modes: ['flat', 'ivf_flat', 'ivf_sq8', 'hnsw'] },
  qdrant: { modes: ['hnsw', 'custom'] },
  weaviate: { modes: ['hnsw', 'flat'] },
  chroma: { modes: ['hnsw', 'standard'] },
  faiss: { modes: ['flat', 'ivf', 'hnsw'] }
};

const Comparison = () => {
  // 表单状态
  const [embeddingFile, setEmbeddingFile] = useState('');
  const [embeddedFiles, setEmbeddedFiles] = useState([]);
  const [providers, setProviders] = useState([]);
  const [selectedConfigs, setSelectedConfigs] = useState({});
  const [queryMode, setQueryMode] = useState('text'); // 'text' or 'csv'
  const [queryText, setQueryText] = useState('');
  const [csvFile, setCsvFile] = useState(null);
  const [topK, setTopK] = useState(10);
  const [threshold, setThreshold] = useState(0.7);

  // 运行状态
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState('');
  const [comparisonResult, setComparisonResult] = useState(null);
  const [expandedQuery, setExpandedQuery] = useState(null);

  // 加载嵌入文件列表和 providers
  useEffect(() => {
    fetchEmbeddedFiles();
    fetchProviders();
  }, []);

  const fetchEmbeddedFiles = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/list-embedded`);
      const data = await response.json();
      if (data.documents) {
        setEmbeddedFiles(data.documents.map(doc => ({
          id: doc.name,
          name: doc.name
        })));
      }
    } catch (error) {
      console.error('Error fetching embedded files:', error);
    }
  };

  const fetchProviders = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/providers`);
      const data = await response.json();
      if (data.providers) {
        setProviders(data.providers);
        // 初始化所有配置为未选中
        const initialConfigs = {};
        data.providers.forEach(p => {
          const modes = dbConfigs[p.id]?.modes || [];
          modes.forEach(mode => {
            initialConfigs[`${p.id}_${mode}`] = false;
          });
        });
        setSelectedConfigs(initialConfigs);
      }
    } catch (error) {
      console.error('Error fetching providers:', error);
    }
  };

  // 切换索引配置选中状态
  const toggleConfig = (provider, mode) => {
    const key = `${provider}_${mode}`;
    setSelectedConfigs(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // 获取选中的配置列表
  const getSelectedConfigsList = () => {
    const configs = [];
    Object.entries(selectedConfigs).forEach(([key, checked]) => {
      if (checked) {
        const [provider, ...modeParts] = key.split('_');
        const index_mode = modeParts.join('_');
        configs.push({ provider, index_mode });
      }
    });
    return configs;
  };

  // 解析文本查询（一行一条）
  const parseTextQueries = () => {
    return queryText
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
      .map(line => ({ query_text: line, expected_pages: [] }));
  };

  // 运行对比
  const handleRunComparison = async () => {
    const indexConfigs = getSelectedConfigsList();

    if (!embeddingFile) {
      setStatus('请选择嵌入文件');
      return;
    }
    if (indexConfigs.length === 0) {
      setStatus('请至少选择一种索引配置');
      return;
    }
    if (indexConfigs.length < 2) {
      setStatus('请至少选择两种索引配置进行对比');
      return;
    }

    // 准备查询
    let queries = [];
    if (queryMode === 'text') {
      queries = parseTextQueries();
      if (queries.length === 0) {
        setStatus('请输入至少一条查询');
        return;
      }
    } else if (queryMode === 'csv' && csvFile) {
      // CSV 模式使用 /compare/from-csv 端点
      await runCsvComparison(indexConfigs);
      return;
    }

    setIsRunning(true);
    setStatus('正在运行对比分析...');
    setComparisonResult(null);

    try {
      const response = await fetch(`${apiBaseUrl}/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          embedding_file: embeddingFile,
          index_configs: indexConfigs,
          queries: queries,
          top_k: topK,
          threshold: threshold
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setComparisonResult(data);
      setStatus('对比分析完成！');
    } catch (error) {
      console.error('对比分析失败:', error);
      setStatus(`对比分析失败: ${error.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  // CSV 模式对比
  const runCsvComparison = async (indexConfigs) => {
    setIsRunning(true);
    setStatus('正在通过 CSV 运行对比分析...');
    setComparisonResult(null);

    try {
      const formData = new FormData();
      formData.append('file', csvFile);
      formData.append('embedding_file', embeddingFile);
      formData.append('index_configs_json', JSON.stringify(indexConfigs));
      formData.append('top_k', topK);
      formData.append('threshold', threshold);

      const response = await fetch(`${apiBaseUrl}/compare/from-csv`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setComparisonResult(data);
      setStatus('CSV 对比分析完成！');
    } catch (error) {
      console.error('CSV 对比分析失败:', error);
      setStatus(`CSV 对比分析失败: ${error.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  // 获取对比结果的统计摘要
  const getSummaryRows = () => {
    if (!comparisonResult?.results) return [];
    return comparisonResult.results;
  };

  // 找出延迟最优、命中率最优的配置
  const getBestConfig = (results, field) => {
    if (!results || results.length === 0) return null;
    const valid = results.filter(r => r[field] != null && !r.index_error);
    if (valid.length === 0) return null;
    if (field === 'avg_search_latency_ms') {
      return valid.reduce((best, r) => r[field] < best[field] ? r : best, valid[0]);
    }
    return valid.reduce((best, r) => r[field] > best[field] ? r : best, valid[0]);
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6">检索增强生成工具</h1>
      <hr />
      <h2 className="text-2xl font-bold mb-6">索引对比分析</h2>

      <div className="grid grid-cols-12 gap-6">
        {/* ============================================================ */}
        {/* 左侧面板 - 配置 */}
        {/* ============================================================ */}
        <div className="col-span-3 space-y-4">
          {/* 嵌入文件选择 */}
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <label className="block text-sm font-medium mb-1">嵌入文件</label>
            <select
              value={embeddingFile}
              onChange={(e) => setEmbeddingFile(e.target.value)}
              className="block w-full p-2 border rounded"
            >
              <option value="">选择嵌入文件...</option>
              {embeddedFiles.map(file => (
                <option key={file.name} value={file.name}>
                  {file.name}
                </option>
              ))}
            </select>
          </div>

          {/* 索引配置多选 */}
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <label className="block text-sm font-medium mb-2">
              索引配置（至少选择两项）
            </label>
            <div className="max-h-64 overflow-y-auto space-y-1">
              {providers.map(provider => {
                const modes = dbConfigs[provider.id]?.modes || [];
                return (
                  <div key={provider.id} className="mb-2">
                    <div className="text-xs font-semibold text-gray-500 uppercase mb-1">
                      {provider.name}
                    </div>
                    {modes.map(mode => {
                      const key = `${provider.id}_${mode}`;
                      return (
                        <label key={key} className="flex items-center space-x-2 py-1 px-2 hover:bg-gray-50 rounded cursor-pointer">
                          <input
                            type="checkbox"
                            checked={selectedConfigs[key] || false}
                            onChange={() => toggleConfig(provider.id, mode)}
                            className="form-checkbox h-4 w-4 text-blue-600"
                          />
                          <span className="text-sm">{mode.toUpperCase()}</span>
                        </label>
                      );
                    })}
                  </div>
                );
              })}
            </div>
            <div className="mt-2 text-xs text-gray-500">
              已选: {getSelectedConfigsList().length} 项
            </div>
          </div>

          {/* 查询输入 */}
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <label className="block text-sm font-medium mb-2">查询方式</label>
            <div className="flex space-x-4 mb-3">
              <label className="flex items-center space-x-1 cursor-pointer">
                <input
                  type="radio"
                  value="text"
                  checked={queryMode === 'text'}
                  onChange={() => setQueryMode('text')}
                  className="form-radio"
                />
                <span className="text-sm">文本输入</span>
              </label>
              <label className="flex items-center space-x-1 cursor-pointer">
                <input
                  type="radio"
                  value="csv"
                  checked={queryMode === 'csv'}
                  onChange={() => setQueryMode('csv')}
                  className="form-radio"
                />
                <span className="text-sm">CSV上传</span>
              </label>
            </div>

            {queryMode === 'text' ? (
              <div>
                <textarea
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder={"每行一条查询，例如：\n什么是机器学习？\n深度学习有哪些应用？"}
                  className="block w-full p-2 border rounded h-32 resize-none text-sm"
                />
              </div>
            ) : (
              <div>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setCsvFile(e.target.files[0])}
                  className="block w-full text-sm"
                />
                {csvFile && (
                  <p className="text-xs text-green-600 mt-1">已选择: {csvFile.name}</p>
                )}
              </div>
            )}
          </div>

          {/* 参数设置 */}
          <div className="p-4 border rounded-lg bg-white shadow-sm space-y-3">
            <div>
              <label className="block text-sm font-medium mb-1">
                前K个检索结果: {topK}
              </label>
              <input
                type="range"
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value))}
                min="1"
                max="20"
                className="block w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                相似性阈值: {threshold}
              </label>
              <input
                type="range"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                min="0"
                max="1"
                step="0.05"
                className="block w-full"
              />
            </div>
          </div>

          {/* 运行按钮 */}
          <button
            onClick={handleRunComparison}
            disabled={isRunning}
            className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 font-medium"
          >
            {isRunning ? '对比分析运行中...' : '运行对比分析'}
          </button>

          {/* 状态提示 */}
          {status && (
            <div className={`p-3 rounded-lg text-sm ${
              status.includes('失败') || status.includes('错误')
                ? 'bg-red-100 text-red-700'
                : 'bg-green-100 text-green-700'
            }`}>
              {status}
            </div>
          )}
        </div>

        {/* ============================================================ */}
        {/* 右侧面板 - 结果展示 */}
        {/* ============================================================ */}
        <div className="col-span-9 space-y-6">
          {comparisonResult ? (
            <>
              {/* 汇总对比表 */}
              <div className="border rounded-lg bg-white shadow-sm overflow-hidden">
                <div className="p-4 bg-gray-50 border-b">
                  <h3 className="text-lg font-semibold">对比汇总</h3>
                  <p className="text-xs text-gray-500">
                    嵌入文件: {comparisonResult.embedding_file} |
                    配置数: {comparisonResult.total_configs} |
                    查询数: {comparisonResult.total_queries}
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-100 text-left">
                        <th className="p-3 font-medium">向量库</th>
                        <th className="p-3 font-medium">索引模式</th>
                        <th className="p-3 font-medium text-right">索引时间(s)</th>
                        <th className="p-3 font-medium text-right">索引大小</th>
                        <th className="p-3 font-medium text-right">平均搜索延迟(ms)</th>
                        <th className="p-3 font-medium text-right">Avg Score Hit</th>
                        <th className="p-3 font-medium text-right">Avg Score Find</th>
                        <th className="p-3 font-medium text-center">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {getSummaryRows().map((row, idx) => {
                        const bestLatency = getBestConfig(getSummaryRows(), 'avg_search_latency_ms');
                        const bestHit = getBestConfig(getSummaryRows(), 'avg_score_hit');
                        const isBestLatency = bestLatency && row.combination === bestLatency.combination;
                        const isBestHit = bestHit && row.combination === bestHit.combination;

                        return (
                          <tr key={idx} className={`border-t hover:bg-gray-50 ${row.index_error ? 'bg-red-50' : ''}`}>
                            <td className="p-3 font-medium">{row.provider}</td>
                            <td className="p-3">{row.index_mode}</td>
                            <td className="p-3 text-right">{row.indexing_time_s.toFixed(2)}</td>
                            <td className="p-3 text-right">{row.index_size}</td>
                            <td className={`p-3 text-right font-mono ${isBestLatency ? 'text-green-600 font-bold' : ''}`}>
                              {row.avg_search_latency_ms.toFixed(1)}
                              {isBestLatency && <span className="ml-1 text-green-500">✓</span>}
                            </td>
                            <td className={`p-3 text-right font-mono ${isBestHit ? 'text-green-600 font-bold' : ''}`}>
                              {row.avg_score_hit != null ? (row.avg_score_hit * 100).toFixed(2) + '%' : 'N/A'}
                              {isBestHit && <span className="ml-1 text-green-500">✓</span>}
                            </td>
                            <td className={`p-3 text-right font-mono`}>
                              {row.avg_score_find != null ? (row.avg_score_find * 100).toFixed(2) + '%' : 'N/A'}
                            </td>
                            <td className="p-3 text-center">
                              {row.index_error ? (
                                <span className="text-red-500 text-xs" title={row.index_error}>错误</span>
                              ) : (
                                <span className="text-green-500">✓</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* 横向条形图 - 搜索延迟对比 */}
              <div className="border rounded-lg bg-white shadow-sm p-4">
                <h3 className="text-lg font-semibold mb-4">搜索延迟对比 (ms)</h3>
                <div className="space-y-2">
                  {getSummaryRows()
                    .filter(r => !r.index_error)
                    .sort((a, b) => a.avg_search_latency_ms - b.avg_search_latency_ms)
                    .map((row, idx) => {
                      const maxLatency = Math.max(...getSummaryRows().filter(r => !r.index_error).map(r => r.avg_search_latency_ms), 1);
                      const barWidth = (row.avg_search_latency_ms / maxLatency) * 100;
                      return (
                        <div key={idx} className="flex items-center space-x-3">
                          <div className="w-40 text-xs font-medium text-right truncate" title={row.combination}>
                            {row.combination}
                          </div>
                          <div className="flex-1 bg-gray-100 rounded h-6 relative">
                            <div
                              className="bg-blue-500 h-6 rounded flex items-center justify-end pr-2 text-xs text-white font-mono"
                              style={{ width: `${barWidth}%` }}
                            >
                              {row.avg_search_latency_ms.toFixed(1)}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>

              {/* 准确率对比条形图 */}
              {getSummaryRows().some(r => r.avg_score_hit != null) && (
                <div className="border rounded-lg bg-white shadow-sm p-4">
                  <h3 className="text-lg font-semibold mb-4">命中率对比 (Score Hit %)</h3>
                  <div className="space-y-2">
                    {getSummaryRows()
                      .filter(r => !r.index_error && r.avg_score_hit != null)
                      .sort((a, b) => b.avg_score_hit - a.avg_score_hit)
                      .map((row, idx) => {
                        const barWidth = (row.avg_score_hit || 0) * 100;
                        return (
                          <div key={idx} className="flex items-center space-x-3">
                            <div className="w-40 text-xs font-medium text-right truncate" title={row.combination}>
                              {row.combination}
                            </div>
                            <div className="flex-1 bg-gray-100 rounded h-6 relative">
                              <div
                                className="bg-green-500 h-6 rounded flex items-center justify-end pr-2 text-xs text-white font-mono"
                                style={{ width: `${barWidth}%` }}
                              >
                                {(row.avg_score_hit * 100).toFixed(1)}%
                              </div>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}

              {/* 逐查询详情 */}
              <div className="border rounded-lg bg-white shadow-sm p-4">
                <h3 className="text-lg font-semibold mb-4">逐查询详情</h3>
                {getSummaryRows().map((configRow, cIdx) => (
                  <div key={cIdx} className="mb-4 border rounded overflow-hidden">
                    <button
                      onClick={() => setExpandedQuery(expandedQuery === cIdx ? null : cIdx)}
                      className="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 flex justify-between items-center"
                    >
                      <span className="font-medium text-sm">
                        {configRow.combination}
                        {configRow.index_error && (
                          <span className="text-red-500 ml-2">(索引失败: {configRow.index_error})</span>
                        )}
                      </span>
                      <span className="text-xs text-gray-500">
                        {expandedQuery === cIdx ? '收起 ▲' : '展开 ▼'}
                      </span>
                    </button>
                    {expandedQuery === cIdx && configRow.per_query_results?.length > 0 && (
                      <div className="p-3 max-h-96 overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="bg-gray-100 text-left">
                              <th className="p-2">查询</th>
                              <th className="p-2">延迟(ms)</th>
                              <th className="p-2">找到页码</th>
                              <th className="p-2">预期页码</th>
                              <th className="p-2">Hit</th>
                              <th className="p-2">Find</th>
                            </tr>
                          </thead>
                          <tbody>
                            {configRow.per_query_results.map((qr, qIdx) => (
                              <tr key={qIdx} className={`border-t ${qr.search_error ? 'bg-red-50' : ''}`}>
                                <td className="p-2 max-w-xs truncate" title={qr.query}>
                                  {qr.query}
                                </td>
                                <td className="p-2 font-mono">
                                  {qr.search_latency_ms.toFixed(1)}
                                </td>
                                <td className="p-2 font-mono text-sm">
                                  [{qr.found_pages.join(', ')}]
                                </td>
                                <td className="p-2 font-mono text-sm text-gray-500">
                                  [{qr.expected_pages.join(', ')}]
                                </td>
                                <td className="p-2 font-mono">
                                  {qr.score_hit != null ? (qr.score_hit * 100).toFixed(1) + '%' : '-'}
                                </td>
                                <td className="p-2 font-mono">
                                  {qr.score_find != null ? (qr.score_find * 100).toFixed(1) + '%' : '-'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* 保存路径 */}
              {comparisonResult.saved_path && (
                <div className="text-xs text-gray-500 text-right">
                  结果已保存至: {comparisonResult.saved_path}
                </div>
              )}
            </>
          ) : (
            <div className="border rounded-lg bg-white shadow-sm h-96 flex items-center justify-center">
              <div className="text-center text-gray-400">
                <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <p>对比结果将在此处显示</p>
                <p className="text-sm mt-1">选择嵌入文件和至少两种索引配置后运行对比</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Comparison;
