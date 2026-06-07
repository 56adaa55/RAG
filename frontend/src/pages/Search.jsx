// src/pages/Search.jsx
import React, { useState, useEffect } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const Search = () => {
  const [query, setQuery] = useState('');
  const [collection, setCollection] = useState('');
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [topK, setTopK] = useState(3);
  const [threshold, setThreshold] = useState(0.7);
  const [collections, setCollections] = useState([]);
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('milvus');
  const [wordCountThreshold, setWordCountThreshold] = useState(100);
  const [saveResults, setSaveResults] = useState(false);
  const [status, setStatus] = useState('');

  // ---- 检索优化相关状态（新增） ----
  const [useOptimization, setUseOptimization] = useState(false);
  const [showOptimizePanel, setShowOptimizePanel] = useState(false);
  // 检索前
  const [preRewrite, setPreRewrite] = useState(false);
  const [preExpand, setPreExpand] = useState(false);
  const [preHyde, setPreHyde] = useState(false);
  const [preDecompose, setPreDecompose] = useState(false);
  // 检索后
  const [postRerank, setPostRerank] = useState(false);
  const [postMMR, setPostMMR] = useState(false);
  const [postDeduplicate, setPostDeduplicate] = useState(false);
  const [postFilter, setPostFilter] = useState(false);
  // 优化结果日志
  const [optimizationLog, setOptimizationLog] = useState(null);
  const [effectiveQuery, setEffectiveQuery] = useState('');

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

  const getSelectedPreStrategies = () => {
    const s = [];
    if (preRewrite) s.push('rewrite');
    if (preExpand) s.push('expand');
    if (preHyde) s.push('hyde');
    if (preDecompose) s.push('decompose');
    return s;
  };

  const getSelectedPostStrategies = () => {
    const s = [];
    if (postRerank) s.push('rerank');
    if (postMMR) s.push('mmr');
    if (postDeduplicate) s.push('deduplicate');
    if (postFilter) s.push('filter');
    return s;
  };

  const handleSearch = async () => {
    if (!query || !collection) {
      setStatus('请选择集合并输入搜索内容');
      return;
    }

    setIsSearching(true);
    setStatus('');
    setOptimizationLog(null);
    setEffectiveQuery('');

    const preStrategies = useOptimization ? getSelectedPreStrategies() : [];
    const postStrategies = useOptimization ? getSelectedPostStrategies() : [];

    try {
      // 如果启用了优化策略，使用优化搜索端点
      if (useOptimization && (preStrategies.length > 0 || postStrategies.length > 0)) {
        const response = await fetch(`${apiBaseUrl}/search-optimized`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query,
            collection_id: collection,
            top_k: topK,
            threshold,
            pre_strategies: preStrategies,
            post_strategies: postStrategies,
          }),
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        setResults(data.results || []);
        setOptimizationLog(data.optimization_log || null);
        setEffectiveQuery(data.effective_query || query);

        if (data.results && data.results.length > 0) {
          setStatus('优化搜索完成！');
        } else {
          setStatus('未找到匹配的结果');
        }
      } else {
        // 使用原有搜索端点
        const searchParams = {
          query,
          collection_id: collection,
          top_k: topK,
          threshold,
          word_count_threshold: wordCountThreshold,
          save_results: saveResults
        };

        const response = await fetch(`${apiBaseUrl}/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(searchParams),
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();

        if (data.results && data.results.results && data.results.results.length > 0) {
          setResults(data.results.results);
          if (saveResults && data.saved_filepath) {
            setStatus(`搜索完成！结果已保存至: ${data.saved_filepath}`);
          } else {
            setStatus('搜索完成！');
          }
        } else {
          setResults([]);
          setStatus('未找到匹配的结果');
        }
      }
    } catch (error) {
      console.error('搜索错误:', error);
      setStatus(`搜索出错: ${error.message}`);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSaveResults = async () => {
    if (!results.length) {
      setStatus('没有可保存的搜索结果');
      return;
    }
    try {
      const saveParams = { query, collection_id: collection, results };
      const response = await fetch(`${apiBaseUrl}/save-search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(saveParams),
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setStatus(`结果已保存至: ${data.saved_filepath}`);
    } catch (error) {
      console.error('保存错误:', error);
      setStatus(`保存失败: ${error.message}`);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6"> 检索增强生成工具 </h1>
      <hr />
      <h2 className="text-2xl font-bold mb-6">相似性检索</h2>

      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel - Search Controls */}
        <div className="col-span-3 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">用户查询</label>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter your search query..."
                  className="block w-full p-2 border rounded h-32 resize-none"
                />
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
                <label className="block text-sm font-medium mb-1">集合</label>
                <select
                  value={collection}
                  onChange={(e) => setCollection(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">Choose a collection...</option>
                  {collections.map(coll => (
                    <option key={coll.id} value={coll.id}>{coll.name} ({coll.count} documents)</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">前K个检索结果</label>
                <input
                  type="number"
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value))}
                  min="1" max="20"
                  className="block w-full p-2 border rounded"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">相似性阈值: {threshold}</label>
                <input
                  type="range" value={threshold}
                  onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  min="0" max="1" step="0.1"
                  className="block w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  包含最少单词个数: {wordCountThreshold}
                </label>
                <input
                  type="range" value={wordCountThreshold}
                  onChange={(e) => setWordCountThreshold(parseInt(e.target.value))}
                  min="0" max="500" step="10"
                  className="block w-full"
                />
              </div>

              <div className="mt-4">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox" checked={saveResults}
                    onChange={(e) => setSaveResults(e.target.checked)}
                    className="form-checkbox h-4 w-4 text-blue-600"
                  />
                  <span className="text-sm font-medium">保存检索结果</span>
                </label>
              </div>

              <button
                onClick={handleSearch}
                disabled={isSearching}
                className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-blue-300"
              >
                {isSearching ? '检索过程中...' : '检索'}
              </button>
            </div>
          </div>

          {/* ---- 检索优化面板（新增） ---- */}
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <button
              onClick={() => setShowOptimizePanel(!showOptimizePanel)}
              className="w-full flex items-center justify-between text-sm font-medium"
            >
              <span>🔧 检索优化选项</span>
              <span className={`transform transition-transform ${showOptimizePanel ? 'rotate-90' : ''}`}>▶</span>
            </button>

            {showOptimizePanel && (
              <div className="mt-4 space-y-4">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox" checked={useOptimization}
                    onChange={(e) => setUseOptimization(e.target.checked)}
                    className="form-checkbox h-4 w-4"
                  />
                  <span className="text-sm font-medium text-green-600">启用检索优化</span>
                </label>

                {useOptimization && (
                  <>
                    {/* 检索前优化 */}
                    <div>
                      <div className="text-xs font-semibold text-gray-500 mb-2">检索前优化 (Pre-retrieval)</div>
                      <label className="flex items-center space-x-2 cursor-pointer mb-1">
                        <input type="checkbox" checked={preRewrite} onChange={(e) => setPreRewrite(e.target.checked)} className="form-checkbox h-3 w-3" />
                        <span className="text-xs">Query Rewriting (查询改写)</span>
                      </label>
                      <label className="flex items-center space-x-2 cursor-pointer mb-1">
                        <input type="checkbox" checked={preExpand} onChange={(e) => setPreExpand(e.target.checked)} className="form-checkbox h-3 w-3" />
                        <span className="text-xs">Query Expansion (查询扩展)</span>
                      </label>
                      <label className="flex items-center space-x-2 cursor-pointer mb-1">
                        <input type="checkbox" checked={preHyde} onChange={(e) => setPreHyde(e.target.checked)} className="form-checkbox h-3 w-3" />
                        <span className="text-xs">HyDE (假设性文档嵌入)</span>
                      </label>
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <input type="checkbox" checked={preDecompose} onChange={(e) => setPreDecompose(e.target.checked)} className="form-checkbox h-3 w-3" />
                        <span className="text-xs">Multi-Query (多查询分解)</span>
                      </label>
                    </div>

                    {/* 检索后优化 */}
                    <div>
                      <div className="text-xs font-semibold text-gray-500 mb-2">检索后优化 (Post-retrieval)</div>
                      <label className="flex items-center space-x-2 cursor-pointer mb-1">
                        <input type="checkbox" checked={postRerank} onChange={(e) => setPostRerank(e.target.checked)} className="form-checkbox h-3 w-3" />
                        <span className="text-xs">Cross-Encoder Rerank (精确重排序)</span>
                      </label>
                      <label className="flex items-center space-x-2 cursor-pointer mb-1">
                        <input type="checkbox" checked={postMMR} onChange={(e) => setPostMMR(e.target.checked)} className="form-checkbox h-3 w-3" />
                        <span className="text-xs">MMR Diversity (多样性过滤)</span>
                      </label>
                      <label className="flex items-center space-x-2 cursor-pointer mb-1">
                        <input type="checkbox" checked={postDeduplicate} onChange={(e) => setPostDeduplicate(e.target.checked)} className="form-checkbox h-3 w-3" />
                        <span className="text-xs">Deduplication (去重)</span>
                      </label>
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <input type="checkbox" checked={postFilter} onChange={(e) => setPostFilter(e.target.checked)} className="form-checkbox h-3 w-3" />
                        <span className="text-xs">Relevance Filter (相关性过滤)</span>
                      </label>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {status && (
            <div className={`p-4 rounded-lg ${
              status.includes('错误') || status.includes('失败') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
            }`}>
              {status}
            </div>
          )}
        </div>

        {/* Right Panel - Results */}
        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          {results.length > 0 ? (
            <div className="p-4">
              {/* 优化日志（新增） */}
              {optimizationLog && (
                <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded text-sm">
                  <div className="font-medium text-blue-700 mb-1">🔍 优化信息</div>
                  {effectiveQuery && effectiveQuery !== query && (
                    <div className="text-blue-600 mb-1">
                      <span className="font-medium">改写后查询:</span> {effectiveQuery}
                    </div>
                  )}
                  {optimizationLog.pre && Object.keys(optimizationLog.pre).length > 0 && (
                    <div className="text-gray-600">
                      <span className="font-medium">检索前:</span>{' '}
                      {Object.entries(optimizationLog.pre).map(([k, v]) => (
                        <span key={k} className="mr-2 px-1 bg-blue-100 rounded">{k}</span>
                      ))}
                    </div>
                  )}
                  {optimizationLog.post && (
                    <div className="text-gray-600">
                      <span className="font-medium">检索后:</span>{' '}
                      {optimizationLog.post.steps_applied?.join(', ') || '—'}
                      {' | '}结果: {optimizationLog.post.original_count} → {optimizationLog.post.optimized_count}
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-semibold">Search Results ({results.length})</h3>
                <button
                  onClick={handleSaveResults}
                  className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
                >
                  保存搜索结果
                </button>
              </div>
              <div className="space-y-4 max-h-[calc(100vh-200px)] overflow-y-auto">
                {results.map((result, idx) => (
                  <div key={idx} className="p-4 border rounded bg-gray-50">
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-medium text-sm text-gray-500">
                        {result.rerank_score != null
                          ? `Rerank: ${(result.rerank_score * 100).toFixed(1)}% (原始: ${(result.original_score * 100).toFixed(1)}%)`
                          : `Match Score: ${((result.score || 0) * 100).toFixed(1)}%`
                        }
                      </span>
                      <div className="text-sm text-gray-500">
                        <div>Source: {result.metadata?.source || result.metadata?.document_name || '-'}</div>
                        <div>Page: {result.metadata?.page || result.metadata?.page_number || '-'}</div>
                        <div>Chunk: {result.metadata?.chunk || '-'}</div>
                      </div>
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{result.text}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <RandomImage message="Search results will appear here" />
          )}
        </div>
      </div>
    </div>
  );
};

export default Search;
